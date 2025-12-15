"""
Usage Limiter Service
Rate limiting and quota management to prevent abuse
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


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
    cooldown_seconds: int = 0  # Cooldown between requests
    overage_cost_cents: int = 0  # Cost per overage in cents


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


# Default limits by plan tier
PLAN_LIMITS: dict[PlanTier, dict[UsageType, UsageLimit]] = {
    PlanTier.FREE: {
        UsageType.SMS: UsageLimit(daily_limit=10, monthly_limit=50, cooldown_seconds=60),
        UsageType.AI_CONTENT: UsageLimit(daily_limit=5, monthly_limit=30, cooldown_seconds=30),
        UsageType.AI_IMAGE: UsageLimit(daily_limit=3, monthly_limit=20, cooldown_seconds=60),
        UsageType.AI_RESPONSE: UsageLimit(daily_limit=10, monthly_limit=100, cooldown_seconds=10),
        UsageType.API_CALLS: UsageLimit(daily_limit=1000, monthly_limit=10000, cooldown_seconds=0),
    },
    PlanTier.STARTER: {
        UsageType.SMS: UsageLimit(daily_limit=50, monthly_limit=500, cooldown_seconds=10, overage_cost_cents=5),
        UsageType.AI_CONTENT: UsageLimit(daily_limit=20, monthly_limit=200, cooldown_seconds=10, overage_cost_cents=10),
        UsageType.AI_IMAGE: UsageLimit(daily_limit=15, monthly_limit=150, cooldown_seconds=30, overage_cost_cents=15),
        UsageType.AI_RESPONSE: UsageLimit(daily_limit=50, monthly_limit=500, cooldown_seconds=5, overage_cost_cents=2),
        UsageType.API_CALLS: UsageLimit(daily_limit=5000, monthly_limit=50000, cooldown_seconds=0),
    },
    PlanTier.PROFESSIONAL: {
        UsageType.SMS: UsageLimit(daily_limit=200, monthly_limit=2000, cooldown_seconds=5, overage_cost_cents=3),
        UsageType.AI_CONTENT: UsageLimit(daily_limit=50, monthly_limit=500, cooldown_seconds=5, overage_cost_cents=8),
        UsageType.AI_IMAGE: UsageLimit(daily_limit=50, monthly_limit=500, cooldown_seconds=15, overage_cost_cents=10),
        UsageType.AI_RESPONSE: UsageLimit(daily_limit=200, monthly_limit=2000, cooldown_seconds=2, overage_cost_cents=1),
        UsageType.API_CALLS: UsageLimit(daily_limit=20000, monthly_limit=200000, cooldown_seconds=0),
    },
    PlanTier.AGENCY: {
        UsageType.SMS: UsageLimit(daily_limit=1000, monthly_limit=10000, cooldown_seconds=2, overage_cost_cents=2),
        UsageType.AI_CONTENT: UsageLimit(daily_limit=200, monthly_limit=2000, cooldown_seconds=2, overage_cost_cents=5),
        UsageType.AI_IMAGE: UsageLimit(daily_limit=200, monthly_limit=2000, cooldown_seconds=5, overage_cost_cents=8),
        UsageType.AI_RESPONSE: UsageLimit(daily_limit=1000, monthly_limit=10000, cooldown_seconds=1, overage_cost_cents=1),
        UsageType.API_CALLS: UsageLimit(daily_limit=100000, monthly_limit=1000000, cooldown_seconds=0),
    },
}


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
    """Service for managing usage limits and quotas."""
    
    def __init__(self):
        # In production, use Redis or database
        self._usage_records: dict[str, dict[UsageType, UsageRecord]] = defaultdict(dict)
        self._account_plans: dict[str, PlanTier] = {}
    
    def set_account_plan(self, account_id: str, plan: PlanTier) -> None:
        """Set the plan tier for an account."""
        self._account_plans[account_id] = plan
    
    def get_account_plan(self, account_id: str) -> PlanTier:
        """Get the plan tier for an account."""
        return self._account_plans.get(account_id, PlanTier.FREE)
    
    def get_limits(self, account_id: str, usage_type: UsageType) -> UsageLimit:
        """Get usage limits for an account and usage type."""
        plan = self.get_account_plan(account_id)
        return PLAN_LIMITS[plan][usage_type]
    
    def get_usage_record(self, account_id: str, usage_type: UsageType) -> UsageRecord:
        """Get or create usage record for an account."""
        if usage_type not in self._usage_records[account_id]:
            now = datetime.now(timezone.utc)
            self._usage_records[account_id][usage_type] = UsageRecord(
                account_id=account_id,
                usage_type=usage_type,
                daily_reset_at=now + timedelta(days=1),
                monthly_reset_at=now.replace(day=1) + timedelta(days=32),
            )
        
        record = self._usage_records[account_id][usage_type]
        self._reset_if_needed(record)
        return record
    
    def _reset_if_needed(self, record: UsageRecord) -> None:
        """Reset counters if period has passed."""
        now = datetime.now(timezone.utc)
        
        if record.daily_reset_at and now >= record.daily_reset_at:
            record.daily_count = 0
            record.daily_reset_at = now + timedelta(days=1)
        
        if record.monthly_reset_at and now >= record.monthly_reset_at:
            record.monthly_count = 0
            record.monthly_reset_at = now.replace(day=1) + timedelta(days=32)
    
    def check_usage(
        self,
        account_id: str,
        usage_type: UsageType,
        count: int = 1,
    ) -> UsageCheckResult:
        """Check if usage is allowed."""
        limits = self.get_limits(account_id, usage_type)
        record = self.get_usage_record(account_id, usage_type)
        now = datetime.now(timezone.utc)
        
        # Check cooldown
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
        
        # Check daily limit
        if record.daily_count + count > limits.daily_limit:
            return UsageCheckResult(
                allowed=False,
                reason=f"Daily limit reached ({limits.daily_limit}/{limits.daily_limit}). Resets at midnight UTC.",
                remaining_daily=0,
                remaining_monthly=limits.monthly_limit - record.monthly_count,
                overage_available=limits.overage_cost_cents > 0,
                overage_cost_cents=limits.overage_cost_cents * count,
            )
        
        # Check monthly limit
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
    
    def record_usage(
        self,
        account_id: str,
        usage_type: UsageType,
        count: int = 1,
    ) -> UsageRecord:
        """Record usage after successful operation."""
        record = self.get_usage_record(account_id, usage_type)
        record.daily_count += count
        record.monthly_count += count
        record.last_used_at = datetime.now(timezone.utc)
        return record
    
    def get_usage_summary(self, account_id: str) -> dict:
        """Get usage summary for all types."""
        plan = self.get_account_plan(account_id)
        summary = {
            "plan": plan.value,
            "usage": {},
        }
        
        for usage_type in UsageType:
            limits = self.get_limits(account_id, usage_type)
            record = self.get_usage_record(account_id, usage_type)
            
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
    
    def use_with_check(
        self,
        account_id: str,
        usage_type: UsageType,
        count: int = 1,
    ) -> UsageCheckResult:
        """Check and record usage in one call. Returns result with allowed status."""
        result = self.check_usage(account_id, usage_type, count)
        if result.allowed:
            self.record_usage(account_id, usage_type, count)
        return result


# Global instance
usage_limiter = UsageLimiterService()


# Decorator for rate limiting
def rate_limit(usage_type: UsageType, count: int = 1):
    """Decorator to apply rate limiting to a function."""
    def decorator(func):
        async def wrapper(*args, account_id: str = None, **kwargs):
            if not account_id:
                # Try to get from kwargs or first arg
                account_id = kwargs.get('account_id') or (args[0] if args else None)
            
            if account_id:
                result = usage_limiter.check_usage(account_id, usage_type, count)
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
                        }
                    )
                
                # Execute function
                response = await func(*args, **kwargs)
                
                # Record usage after success
                usage_limiter.record_usage(account_id, usage_type, count)
                
                return response
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
