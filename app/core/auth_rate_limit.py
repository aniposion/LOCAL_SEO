"""Persistent auth-specific rate limiting for anonymous endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import hash_opaque_token
from app.core.time import utc_now_aware
from app.models.auth_rate_limit import AuthRateLimitBucket


@dataclass(frozen=True)
class AuthRateLimit:
    """Windowed auth rate limit configuration."""

    limit: int
    window_seconds: int
    message: str


AUTH_LIMITS: dict[str, AuthRateLimit] = {
    "signup_ip": AuthRateLimit(5, 3600, "Too many signup attempts. Please try again later."),
    "signup_identity": AuthRateLimit(3, 3600, "Too many signup attempts for this email. Please try again later."),
    "login_ip": AuthRateLimit(10, 900, "Too many login attempts. Please wait a bit and try again."),
    "login_identity": AuthRateLimit(8, 900, "Too many login attempts for this account. Please wait and try again."),
    "forgot_password_ip": AuthRateLimit(5, 3600, "Too many password reset requests. Please try again later."),
    "forgot_password_identity": AuthRateLimit(3, 3600, "Too many password reset requests for this account. Please try again later."),
    "resend_verification_ip": AuthRateLimit(5, 3600, "Too many verification resend requests. Please try again later."),
    "resend_verification_identity": AuthRateLimit(3, 3600, "Too many verification resend requests for this account. Please try again later."),
    "refresh_ip": AuthRateLimit(30, 900, "Too many token refresh attempts. Please try again later."),
}


class AuthRateLimiter:
    """DB-backed limiter for auth endpoints so throttling survives restarts."""

    def _ensure_aware(self, value):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=utc_now_aware().tzinfo)
        return value

    def _normalize_subject(self, scope: str, subject: str) -> str:
        normalized = subject.strip()
        if scope == "identity":
            return normalized.lower()
        return normalized

    def _bucket_hash(self, action: str, scope: str, subject: str) -> str:
        normalized = self._normalize_subject(scope, subject)
        return hash_opaque_token(f"auth-rate-limit:{action}:{scope}:{normalized}")

    def hit(
        self,
        db: Session,
        *,
        action: str,
        scope: str,
        subject: str,
        config: AuthRateLimit,
    ) -> int:
        """Record a hit and return seconds until reset if blocked."""
        now = utc_now_aware()
        bucket_key_hash = self._bucket_hash(action, scope, subject)
        bucket = (
            db.query(AuthRateLimitBucket)
            .filter(AuthRateLimitBucket.bucket_key_hash == bucket_key_hash)
            .first()
        )

        if bucket is None:
            bucket = AuthRateLimitBucket(
                action=action,
                scope=scope,
                bucket_key_hash=bucket_key_hash,
                hit_count=0,
                window_start=now,
                window_seconds=config.window_seconds,
                last_hit_at=None,
            )
            db.add(bucket)
            db.flush()

        window_start = self._ensure_aware(bucket.window_start) or now
        window_expires_at = window_start + timedelta(seconds=config.window_seconds)
        if bucket.window_seconds != config.window_seconds or window_expires_at <= now:
            bucket.window_start = now
            bucket.window_seconds = config.window_seconds
            bucket.hit_count = 0
            window_expires_at = now + timedelta(seconds=config.window_seconds)

        if bucket.hit_count >= config.limit:
            bucket.last_hit_at = now
            db.commit()
            return int(max(1, (window_expires_at - now).total_seconds()))

        bucket.hit_count += 1
        bucket.last_hit_at = now
        db.commit()
        return 0


auth_rate_limiter = AuthRateLimiter()


def _request_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def enforce_auth_rate_limit(
    request: Request,
    db: Session,
    action: str,
    identity: str | None = None,
) -> None:
    """Apply auth-specific rate limiting by IP and optional identity."""
    ip_key = f"{action}_ip"
    ip_limit = AUTH_LIMITS.get(ip_key)
    if ip_limit:
        retry_after = auth_rate_limiter.hit(
            db,
            action=action,
            scope="ip",
            subject=_request_ip(request),
            config=ip_limit,
        )
        if retry_after:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=ip_limit.message,
                headers={"Retry-After": str(retry_after)},
            )

    if identity:
        identity_key = f"{action}_identity"
        identity_limit = AUTH_LIMITS.get(identity_key)
        if identity_limit:
            retry_after = auth_rate_limiter.hit(
                db,
                action=action,
                scope="identity",
                subject=identity,
                config=identity_limit,
            )
            if retry_after:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=identity_limit.message,
                    headers={"Retry-After": str(retry_after)},
                )
