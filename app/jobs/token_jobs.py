"""P4: OAuth token management jobs."""

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.db.session import SessionLocal
from app.jobs.ops_alerts import notify_active_admins
from app.models.account import Account
from app.models.oauth import OAuthToken, OAuthStatus, OAuthEvent, OAuthEventType
from app.services.oauth_service import refresh_provider_access_token

logger = logging.getLogger(__name__)


def _session() -> Session:
    return SessionLocal()


async def check_expiring_tokens():
    """Check for tokens expiring within 1 hour and refresh them."""
    logger.info("Checking for expiring OAuth tokens")

    try:
        with _session() as db:
            # Find tokens expiring within 1 hour
            threshold = utc_now_aware() + timedelta(hours=1)

            result = db.execute(
                select(OAuthToken).where(
                    and_(
                        OAuthToken.status.in_([OAuthStatus.HEALTHY, OAuthStatus.DEGRADED]),
                        OAuthToken.expires_at <= threshold,
                    )
                )
            )
            expiring_tokens = result.scalars().all()

            logger.info("Found %s tokens to refresh", len(expiring_tokens))

            for token in expiring_tokens:
                try:
                    await refresh_token(db, token)
                except Exception as exc:
                    logger.error("Failed to refresh token %s: %s", token.id, exc)
                    await handle_refresh_failure(db, token, str(exc))
    except Exception as exc:
        logger.error("OAuth token refresh worker failed: %s", exc)
        try:
            with _session() as alert_db:
                notify_active_admins(
                    alert_db,
                    title="OAuth token refresh worker failed",
                    message=(
                        "The scheduled OAuth token refresh worker could not complete its run."
                        f"\n\nReason: {exc}"
                    ),
                    notification_type="oauth_token_refresh_job_failed",
                )
        except Exception as notify_exc:
            logger.warning("Failed to notify admins about OAuth token refresh worker failure: %s", notify_exc)


async def refresh_token(db: Session, token: OAuthToken):
    """Refresh a single OAuth token.
    """
    logger.info("Refreshing token %s for provider %s", token.id, token.provider)

    try:
        if token.provider.value == "google":
            new_tokens = await refresh_google_token(token)
        elif token.provider.value == "instagram":
            new_tokens = await refresh_instagram_token(token)
        elif token.provider.value == "facebook":
            new_tokens = await refresh_facebook_token(token)
        else:
            raise ValueError(f"Unknown provider: {token.provider}")
        
        # Update token
        token.access_token_ref = new_tokens["access_token_ref"]
        if new_tokens.get("refresh_token_ref"):
            token.refresh_token_ref = new_tokens["refresh_token_ref"]
        token.expires_at = new_tokens["expires_at"]
        token.status = OAuthStatus.HEALTHY
        token.refresh_failure_count = 0
        token.last_refresh_at = utc_now_aware()
        token.last_error = None
        token.last_error_code = None
        
        # Log event
        event = OAuthEvent(
            token_id=token.id,
            event_type=OAuthEventType.REFRESHED,
            event_data={"expires_at": token.expires_at.isoformat()},
        )
        db.add(event)

        db.commit()
        logger.info("Successfully refreshed token %s", token.id)

    except Exception:
        db.rollback()
        raise


def _requires_reauth(error: str) -> bool:
    """Return True when refresh failure should immediately require reauth."""
    lowered = error.lower()
    return any(
        marker in lowered
        for marker in (
            "invalid_grant",
            "invalid token",
            "refresh token missing",
            "no refresh token",
            "reconnect required",
            "reauth",
            "unsupported provider",
            "not supported",
            "unauthorized",
            "forbidden",
            "revoked",
            "consent required",
        )
    )


async def handle_refresh_failure(db: Session, token: OAuthToken, error: str):
    """Handle token refresh failure."""
    token.refresh_failure_count += 1
    token.last_error = error
    token.last_error_code = "REAUTH_REQUIRED" if _requires_reauth(error) else "REFRESH_FAILED"
    token.last_refresh_at = utc_now_aware()

    should_notify_reauth = False

    # Determine new status based on failure count
    if _requires_reauth(error) or token.refresh_failure_count >= 3:
        token.status = OAuthStatus.NEEDS_REAUTH
        should_notify_reauth = True
        logger.warning("Token %s needs reauthorization", token.id)
        token.next_refresh_at = None
    else:
        token.status = OAuthStatus.DEGRADED
        token.next_refresh_at = utc_now_aware() + timedelta(hours=1)
        logger.warning(
            "Token %s degraded after %s failures",
            token.id,
            token.refresh_failure_count,
        )
    
    # Log event
    event = OAuthEvent(
        token_id=token.id,
        event_type=OAuthEventType.REFRESH_FAILED,
        error_message=error,
        event_data={"failure_count": token.refresh_failure_count},
    )
    db.add(event)

    db.commit()

    if should_notify_reauth:
        await _notify_reauth_required(db, token)


async def _notify_reauth_required(db: Session, token: OAuthToken) -> None:
    """Create an operator-visible notification when a token needs reconnect."""
    from app.services.notification import NotificationService

    provider_label = token.provider.value.replace("_", " ").title()
    title = f"Reconnect {provider_label} integration"
    message = (
        f"The {provider_label} connection needs to be reauthorized before automations fail.\n\n"
        f"Reason: {token.last_error or 'Token refresh failed'}"
    )

    try:
        await NotificationService(db).send_notification(
            account_id=token.account_id,
            title=title,
            message=message,
            notification_type="oauth_reauth_required",
            data={
                "token_id": str(token.id),
                "provider": token.provider.value,
                "location_id": str(token.location_id) if token.location_id else None,
                "url": "/dashboard/integrations",
            },
        )
    except Exception as exc:
        logger.warning("Failed to notify account %s about OAuth reauth: %s", token.account_id, exc)
        account = db.get(Account, token.account_id)
        notify_active_admins(
            db,
            title="OAuth reauth notification failed",
            message=(
                f"The account could not be notified that the {provider_label} connection needs reconnect."
                f"\n\nAccount: {account.email if account and account.email else token.account_id}"
                f"\nToken ID: {token.id}"
                f"\nLocation ID: {token.location_id if token.location_id else 'Not recorded'}"
                f"\nReason: {exc}"
                f"\nLast token error: {token.last_error or 'Token refresh failed'}"
            ),
            notification_type="oauth_reauth_notification_failed",
        )


async def refresh_google_token(token: OAuthToken) -> dict:
    """Refresh Google OAuth token.
    """
    refresh_token = token.refresh_token_ref
    if not refresh_token:
        raise ValueError("Google refresh token missing; reconnect required")

    new_tokens = await refresh_provider_access_token("google", refresh_token)
    access_token = new_tokens.get("access_token")
    if not access_token:
        raise ValueError("Google token refresh did not return an access token")

    expires_in = int(new_tokens.get("expires_in", 3600))
    return {
        "access_token_ref": access_token,
        "refresh_token_ref": new_tokens.get("refresh_token") or token.refresh_token_ref,
        "expires_at": utc_now_aware() + timedelta(seconds=expires_in),
    }


async def refresh_instagram_token(token: OAuthToken) -> dict:
    """Refresh Instagram/Facebook long-lived token.
    """
    refresh_token = token.refresh_token_ref or token.access_token_ref
    if not refresh_token:
        raise ValueError("Instagram refresh token missing; reconnect required")

    new_tokens = await refresh_provider_access_token("instagram", refresh_token)
    access_token = new_tokens.get("access_token")
    if not access_token:
        raise ValueError("Instagram token refresh did not return an access token")

    expires_in = int(new_tokens.get("expires_in", 5184000))
    return {
        "access_token_ref": access_token,
        "refresh_token_ref": new_tokens.get("refresh_token") or token.refresh_token_ref,
        "expires_at": utc_now_aware() + timedelta(seconds=expires_in),
    }


async def refresh_facebook_token(token: OAuthToken) -> dict:
    """Refresh Facebook OAuth token.
    """
    refresh_token = token.refresh_token_ref or token.access_token_ref
    if not refresh_token:
        raise ValueError("Facebook refresh token missing; reconnect required")

    new_tokens = await refresh_provider_access_token("facebook", refresh_token)
    access_token = new_tokens.get("access_token")
    if not access_token:
        raise ValueError("Facebook token refresh did not return an access token")

    expires_in = int(new_tokens.get("expires_in", 3600))
    return {
        "access_token_ref": access_token,
        "refresh_token_ref": new_tokens.get("refresh_token") or token.refresh_token_ref,
        "expires_at": utc_now_aware() + timedelta(seconds=expires_in),
    }


async def revoke_token(db: Session, token_id: UUID):
    """Revoke an OAuth token."""
    result = db.execute(
        select(OAuthToken).where(OAuthToken.id == token_id)
    )
    token = result.scalar_one_or_none()
    
    if not token:
        return
    
    token.status = OAuthStatus.REVOKED
    
    event = OAuthEvent(
        token_id=token.id,
        event_type=OAuthEventType.REVOKED,
    )
    db.add(event)

    db.commit()
    logger.info("Revoked token %s", token_id)
