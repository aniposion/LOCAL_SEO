"""Persistent rate limiting for AI feature routes."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.credits import UsageRecord
from app.models.subscription import PlanType, Subscription
from app.services.account_entitlements import resolve_account_entitlement

logger = logging.getLogger(__name__)


class RateLimiter:
    """Persistent rate limiter for AI feature usage based on subscription plans."""

    PLAN_LIMITS = {
        PlanType.FREE: {
            "competitor_analysis": 0,
            "review_responses": 0,
            "social_proof_cards": 0,
        },
        PlanType.MAPS_STARTER: {
            "competitor_analysis": 4,
            "review_responses": 50,
            "social_proof_cards": 4,
        },
        PlanType.CALLS_GROWTH: {
            "competitor_analysis": 8,
            "review_responses": 150,
            "social_proof_cards": 8,
        },
        PlanType.COMPETITIVE_MARKET: {
            "competitor_analysis": 20,
            "review_responses": 500,
            "social_proof_cards": 20,
        },
        PlanType.STARTER: {
            "competitor_analysis": 4,
            "review_responses": 50,
            "social_proof_cards": 4,
        },
        PlanType.PRO: {
            "competitor_analysis": 4,
            "review_responses": 150,
            "social_proof_cards": 8,
        },
        PlanType.PREMIUM: {
            "competitor_analysis": 4,
            "review_responses": 500,
            "social_proof_cards": 20,
        },
        PlanType.AGENCY: {
            "competitor_analysis": -1,
            "review_responses": -1,
            "social_proof_cards": -1,
        },
        PlanType.ENTERPRISE: {
            "competitor_analysis": -1,
            "review_responses": -1,
            "social_proof_cards": -1,
        },
    }

    def __init__(self, db: Session):
        self.db = db

    def _subscription_for_account(self, account_id: UUID) -> Subscription | None:
        return (
            self.db.query(Subscription)
            .filter(Subscription.account_id == account_id)
            .order_by(Subscription.created_at.desc())
            .first()
        )

    def _feature_limit(self, account_id: UUID, feature: str) -> int:
        entitlement = resolve_account_entitlement(self.db, account_id)
        plan_limits = self.PLAN_LIMITS.get(entitlement.plan_type, {})
        return int(plan_limits.get(feature, 0))

    def _day_window(self, now: datetime) -> tuple[datetime, datetime]:
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return day_start, day_start + timedelta(days=1)

    def _month_start(self, now: datetime) -> datetime:
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _get_daily_record(self, account_id: UUID, feature: str, now: datetime) -> UsageRecord | None:
        day_start, next_day_start = self._day_window(now)
        return (
            self.db.query(UsageRecord)
            .filter(
                UsageRecord.account_id == account_id,
                UsageRecord.usage_type == feature,
                UsageRecord.date >= day_start,
                UsageRecord.date < next_day_start,
            )
            .order_by(UsageRecord.created_at.desc())
            .first()
        )

    def _current_month_usage(self, account_id: UUID, feature: str, now: datetime) -> int:
        month_start = self._month_start(now)
        return int(
            self.db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(
                UsageRecord.account_id == account_id,
                UsageRecord.usage_type == feature,
                UsageRecord.date >= month_start,
            )
            .scalar()
            or 0
        )

    def check_limit(
        self,
        account_id: UUID,
        feature: str,
        count: int = 1,
        increment: bool = True,
    ) -> tuple[bool, Optional[str]]:
        """Check and optionally record usage for a feature."""
        subscription = self._subscription_for_account(account_id)
        entitlement = resolve_account_entitlement(self.db, account_id)
        if entitlement.plan_type == PlanType.FREE and (not subscription or not subscription.is_active):
            return False, "Choose a paid plan to unlock this feature."

        feature_limit = self._feature_limit(account_id, feature)
        now = utc_now_naive()
        current_usage = self._current_month_usage(account_id, feature, now)

        if feature_limit != -1 and current_usage + count > feature_limit:
            return (
                False,
                f"Monthly limit exceeded for {feature}. "
                f"Used: {current_usage}/{feature_limit}. "
                f"Upgrade your plan for higher limits.",
            )

        if increment:
            self._record_usage(account_id, feature, count=count, now=now)
            current_usage += count

        if feature_limit == -1:
            return True, f"Usage recorded for {feature} (unlimited plan)"

        remaining = max(0, feature_limit - current_usage)
        return True, f"Usage: {current_usage}/{feature_limit} (Remaining: {remaining})"

    def _record_usage(
        self,
        account_id: UUID,
        feature: str,
        *,
        count: int = 1,
        now: datetime | None = None,
    ) -> None:
        """Persist feature usage in the shared usage_records table."""
        current_time = now or utc_now_naive()
        usage = self._get_daily_record(account_id, feature, current_time)
        if usage is None:
            usage = UsageRecord(
                account_id=account_id,
                usage_type=feature,
                date=current_time,
                daily_count=0,
                monthly_count=0,
                last_used_at=None,
            )
            self.db.add(usage)
            self.db.flush()

        usage.daily_count += count
        usage.monthly_count += count
        usage.last_used_at = current_time
        self.db.commit()

    def record_usage(self, account_id: UUID, feature: str, count: int = 1) -> None:
        """Persist successful feature usage after the downstream action completes."""
        self._record_usage(account_id, feature, count=count)

    def get_usage_stats(self, account_id: UUID) -> dict[str, dict[str, int | str]]:
        """Get feature usage statistics for the current subscription plan."""
        subscription = self._subscription_for_account(account_id)
        if not subscription:
            entitlement = resolve_account_entitlement(self.db, account_id)
            plan_limits = self.PLAN_LIMITS.get(entitlement.plan_type, {})
            if not plan_limits:
                return {}
            now = utc_now_naive()
            stats: dict[str, dict[str, int | str]] = {}
            for feature, limit in plan_limits.items():
                current_usage = self._current_month_usage(account_id, feature, now)
                stats[feature] = {
                    "used": current_usage,
                    "limit": limit if limit != -1 else "unlimited",
                    "remaining": max(0, limit - current_usage) if limit != -1 else "unlimited",
                    "percentage": int((current_usage / limit) * 100) if limit > 0 else 0,
                }
            return stats

        now = utc_now_naive()
        plan_limits = self.PLAN_LIMITS.get(subscription.plan_type, {})
        stats: dict[str, dict[str, int | str]] = {}
        for feature, limit in plan_limits.items():
            current_usage = self._current_month_usage(account_id, feature, now)
            stats[feature] = {
                "used": current_usage,
                "limit": limit if limit != -1 else "unlimited",
                "remaining": max(0, limit - current_usage) if limit != -1 else "unlimited",
                "percentage": int((current_usage / limit) * 100) if limit > 0 else 0,
            }
        return stats


async def check_rate_limit(
    request: Request | None,
    db: Session,
    account_id: UUID,
    feature: str,
    count: int = 1,
    increment: bool = False,
) -> None:
    """Preview or consume route usage, raising 429 when a limit is exceeded."""
    limiter = RateLimiter(db)
    allowed, message = limiter.check_limit(account_id, feature, count=count, increment=increment)

    if not allowed:
        logger.warning("Rate limit exceeded for account %s, feature %s", account_id, feature)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
        )

    if request is not None and message:
        request.state.usage_info = message


def record_rate_limit_usage(
    db: Session,
    account_id: UUID,
    feature: str,
    count: int = 1,
) -> None:
    """Record usage only after the downstream action succeeds."""
    RateLimiter(db).record_usage(account_id, feature, count=count)
