"""
Usage limiter compatibility layer.

Historically this module tracked usage in-memory, which breaks across multiple
API instances. It now delegates to the DB-backed CreditsService by default and
keeps a narrow legacy fallback only when tests explicitly set an override plan.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from app.services.credits import (
    CREDIT_COSTS,
    PLAN_CREDITS,
    USAGE_COOLDOWNS,
    CreditsService,
    PlanTier as CreditsPlanTier,
)


class UsageType(str, Enum):
    SMS = "sms"
    AI_CONTENT = "ai_content"
    AI_IMAGE = "ai_image"
    AI_RESPONSE = "ai_response"
    API_CALLS = "api_calls"


class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    AGENCY = "agency"


@dataclass
class UsageLimit:
    """Usage limit configuration."""

    daily_limit: int
    monthly_limit: int
    cooldown_seconds: int = 0
    overage_cost_cents: int = 0


@dataclass
class UsageRecord:
    """Track usage for an account."""

    account_id: str
    usage_type: UsageType
    daily_count: int = 0
    monthly_count: int = 0
    last_used_at: Optional[datetime] = None
    daily_reset_at: Optional[datetime] = None
    monthly_reset_at: Optional[datetime] = None


PLAN_TIER_TO_CREDITS_TIER = {
    PlanTier.FREE: CreditsPlanTier.FREE,
    PlanTier.STARTER: CreditsPlanTier.STARTER,
    PlanTier.PROFESSIONAL: CreditsPlanTier.PROFESSIONAL,
    PlanTier.AGENCY: CreditsPlanTier.AGENCY,
}

PLAN_NAME_TO_TIER = {
    PlanTier.FREE.value: PlanTier.FREE,
    PlanTier.STARTER.value: PlanTier.STARTER,
    PlanTier.PROFESSIONAL.value: PlanTier.PROFESSIONAL,
    PlanTier.AGENCY.value: PlanTier.AGENCY,
}


def _build_plan_limits() -> dict[PlanTier, dict[UsageType, UsageLimit]]:
    plan_limits: dict[PlanTier, dict[UsageType, UsageLimit]] = {}
    for plan_tier, credits_tier in PLAN_TIER_TO_CREDITS_TIER.items():
        limits: dict[UsageType, UsageLimit] = {}
        cooldowns = USAGE_COOLDOWNS[credits_tier]
        credits_config = PLAN_CREDITS[credits_tier]
        for usage_type in UsageType:
            usage_key = usage_type.value
            limits[usage_type] = UsageLimit(
                daily_limit=int(credits_config.get(f"{usage_key}_daily", 0)),
                monthly_limit=int(credits_config.get(f"{usage_key}_monthly", 0)),
                cooldown_seconds=int(cooldowns.get(usage_key, 0)),
                overage_cost_cents=int(CREDIT_COSTS.get(usage_key, 0)),
            )
        plan_limits[plan_tier] = limits
    return plan_limits


PLAN_LIMITS: dict[PlanTier, dict[UsageType, UsageLimit]] = _build_plan_limits()


@dataclass
class UsageCheckResult:
    """Result of a usage check."""

    allowed: bool
    reason: Optional[str] = None
    remaining_daily: int = 0
    remaining_monthly: int = 0
    cooldown_remaining_seconds: int = 0
    overage_available: bool = False
    overage_cost_cents: int = 0


class UsageLimiterService:
    """Compatibility wrapper around the DB-backed usage service."""

    def __init__(self, credits_service: CreditsService | None = None):
        self._credits_service = credits_service or CreditsService()
        self._legacy_usage_records: dict[str, dict[UsageType, UsageRecord]] = defaultdict(dict)
        self._legacy_account_plans: dict[str, PlanTier] = {}

    def set_account_plan(self, account_id: str, plan: PlanTier) -> None:
        """Set an explicit legacy override plan for compatibility tests."""
        self._legacy_account_plans[account_id] = plan

    def _uses_legacy_override(self, account_id: str) -> bool:
        return account_id in self._legacy_account_plans

    def get_account_plan(self, account_id: str) -> PlanTier:
        """Get the plan tier for an account."""
        if self._uses_legacy_override(account_id):
            return self._legacy_account_plans[account_id]

        status = self._credits_service.get_account_status(account_id)
        return PLAN_NAME_TO_TIER.get(str(status.get("plan", PlanTier.FREE.value)), PlanTier.FREE)

    def get_limits(self, account_id: str, usage_type: UsageType) -> UsageLimit:
        """Get usage limits for an account and usage type."""
        plan = self.get_account_plan(account_id)
        return PLAN_LIMITS[plan][usage_type]

    def _get_legacy_usage_record(self, account_id: str, usage_type: UsageType) -> UsageRecord:
        """Get or create an in-memory compatibility record."""
        if usage_type not in self._legacy_usage_records[account_id]:
            now = datetime.now(timezone.utc)
            self._legacy_usage_records[account_id][usage_type] = UsageRecord(
                account_id=account_id,
                usage_type=usage_type,
                daily_reset_at=now + timedelta(days=1),
                monthly_reset_at=now.replace(day=1) + timedelta(days=32),
            )

        record = self._legacy_usage_records[account_id][usage_type]
        self._reset_if_needed(record)
        return record

    def get_usage_record(self, account_id: str, usage_type: UsageType) -> UsageRecord:
        """Get the current usage record for an account."""
        if self._uses_legacy_override(account_id):
            return self._get_legacy_usage_record(account_id, usage_type)

        status = self._credits_service.get_account_status(account_id)
        usage = status.get("usage", {}).get(usage_type.value, {})
        return UsageRecord(
            account_id=account_id,
            usage_type=usage_type,
            daily_count=int(usage.get("daily_used", 0)),
            monthly_count=int(usage.get("monthly_used", 0)),
        )

    def _reset_if_needed(self, record: UsageRecord) -> None:
        """Reset counters if period has passed for legacy in-memory overrides."""
        now = datetime.now(timezone.utc)

        if record.daily_reset_at and now >= record.daily_reset_at:
            record.daily_count = 0
            record.daily_reset_at = now + timedelta(days=1)

        if record.monthly_reset_at and now >= record.monthly_reset_at:
            record.monthly_count = 0
            record.monthly_reset_at = now.replace(day=1) + timedelta(days=32)

    def _legacy_check_usage(
        self,
        account_id: str,
        usage_type: UsageType,
        count: int = 1,
    ) -> UsageCheckResult:
        limits = self.get_limits(account_id, usage_type)
        record = self._get_legacy_usage_record(account_id, usage_type)
        now = datetime.now(timezone.utc)

        if limits.cooldown_seconds > 0 and record.last_used_at:
            cooldown_end = record.last_used_at + timedelta(seconds=limits.cooldown_seconds)
            if now < cooldown_end:
                remaining = (cooldown_end - now).total_seconds()
                return UsageCheckResult(
                    allowed=False,
                    reason=f"Please wait {int(remaining)} seconds before trying again",
                    remaining_daily=limits.daily_limit - record.daily_count,
                    remaining_monthly=limits.monthly_limit - record.monthly_count,
                    cooldown_remaining_seconds=int(remaining),
                )

        if record.daily_count + count > limits.daily_limit:
            return UsageCheckResult(
                allowed=False,
                reason=f"Daily limit reached ({limits.daily_limit}/{limits.daily_limit}). Resets at midnight UTC.",
                remaining_daily=0,
                remaining_monthly=limits.monthly_limit - record.monthly_count,
                overage_available=limits.overage_cost_cents > 0,
                overage_cost_cents=limits.overage_cost_cents * count,
            )

        if record.monthly_count + count > limits.monthly_limit:
            return UsageCheckResult(
                allowed=False,
                reason=f"Monthly limit reached ({limits.monthly_limit}/{limits.monthly_limit}). Resets on the 1st.",
                remaining_daily=limits.daily_limit - record.daily_count,
                remaining_monthly=0,
                overage_available=limits.overage_cost_cents > 0,
                overage_cost_cents=limits.overage_cost_cents * count,
            )

        return UsageCheckResult(
            allowed=True,
            remaining_daily=limits.daily_limit - record.daily_count - count,
            remaining_monthly=limits.monthly_limit - record.monthly_count - count,
        )

    def check_usage(
        self,
        account_id: str,
        usage_type: UsageType,
        count: int = 1,
    ) -> UsageCheckResult:
        """Check if usage is allowed."""
        if self._uses_legacy_override(account_id):
            return self._legacy_check_usage(account_id, usage_type, count)

        preview = self._credits_service.preview_usage(account_id, usage_type.value, count)
        return UsageCheckResult(
            allowed=bool(preview.get("allowed")),
            reason=preview.get("reason"),
            remaining_daily=int(preview.get("remaining_daily", 0)),
            remaining_monthly=int(preview.get("remaining_monthly", 0)),
            cooldown_remaining_seconds=int(preview.get("cooldown_remaining_seconds", 0)),
            overage_available=bool(preview.get("overage_available", False)),
            overage_cost_cents=int(preview.get("overage_cost_cents", 0)),
        )

    def record_usage(
        self,
        account_id: str,
        usage_type: UsageType,
        count: int = 1,
    ) -> UsageRecord:
        """Record usage after successful operation."""
        if self._uses_legacy_override(account_id):
            record = self._get_legacy_usage_record(account_id, usage_type)
            record.daily_count += count
            record.monthly_count += count
            record.last_used_at = datetime.now(timezone.utc)
            return record

        result = self._credits_service.use_credits(account_id, usage_type.value, count)
        if not result.get("allowed"):
            raise RuntimeError(f"Usage recording failed: {result.get('reason', 'unknown_error')}")
        return self.get_usage_record(account_id, usage_type)

    def _legacy_usage_summary(self, account_id: str) -> dict:
        """Legacy in-memory usage summary for compatibility-only plan overrides."""
        plan = self.get_account_plan(account_id)
        summary = {
            "plan": plan.value,
            "usage": {},
        }

        for usage_type in UsageType:
            limits = self.get_limits(account_id, usage_type)
            record = self._get_legacy_usage_record(account_id, usage_type)
            summary["usage"][usage_type.value] = {
                "daily_used": record.daily_count,
                "daily_limit": limits.daily_limit,
                "daily_remaining": max(0, limits.daily_limit - record.daily_count),
                "monthly_used": record.monthly_count,
                "monthly_limit": limits.monthly_limit,
                "monthly_remaining": max(0, limits.monthly_limit - record.monthly_count),
                "cooldown_seconds": limits.cooldown_seconds,
                "overage_cost_cents": limits.overage_cost_cents,
            }

        return summary

    def get_usage_summary(self, account_id: str) -> dict:
        """Get usage summary for all types."""
        if self._uses_legacy_override(account_id):
            return self._legacy_usage_summary(account_id)

        status = self._credits_service.get_account_status(account_id)
        usage_summary = {}
        for usage_type, details in status.get("usage", {}).items():
            usage_summary[usage_type] = {
                "daily_used": int(details.get("daily_used", 0)),
                "daily_limit": int(details.get("daily_limit", 0)),
                "daily_remaining": int(details.get("daily_remaining", 0)),
                "monthly_used": int(details.get("monthly_used", 0)),
                "monthly_limit": int(details.get("monthly_limit", 0)),
                "monthly_remaining": int(details.get("monthly_remaining", 0)),
                "cooldown_seconds": int(details.get("cooldown_seconds", 0)),
                "overage_cost_cents": int(details.get("credit_cost", 0)),
            }
        return {
            "plan": str(status.get("plan", PlanTier.FREE.value)),
            "usage": usage_summary,
        }

    def use_with_check(
        self,
        account_id: str,
        usage_type: UsageType,
        count: int = 1,
    ) -> UsageCheckResult:
        """Check and record usage in one call."""
        result = self.check_usage(account_id, usage_type, count)
        if result.allowed:
            self.record_usage(account_id, usage_type, count)
        return result


usage_limiter = UsageLimiterService()


def rate_limit(usage_type: UsageType, count: int = 1):
    """Decorator to apply usage checks before executing a coroutine."""

    def decorator(func):
        async def wrapper(*args, account_id: str = None, **kwargs):
            resolved_account_id = account_id or kwargs.get("account_id") or (args[0] if args else None)

            if resolved_account_id:
                result = usage_limiter.check_usage(str(resolved_account_id), usage_type, count)
                if not result.allowed:
                    from fastapi import HTTPException, status

                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error": "Rate limit exceeded",
                            "message": result.reason,
                            "remaining_daily": result.remaining_daily,
                            "remaining_monthly": result.remaining_monthly,
                            "cooldown_seconds": result.cooldown_remaining_seconds,
                        },
                    )

                response = await func(*args, **kwargs)
                usage_limiter.record_usage(str(resolved_account_id), usage_type, count)
                return response

            return await func(*args, **kwargs)

        return wrapper

    return decorator
