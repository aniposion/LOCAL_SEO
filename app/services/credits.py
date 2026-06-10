"""
Credits Service
Handles credit allocation, usage, and monthly reset on payment.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.db.session import SessionLocal
from app.models.account import Account
from app.models.credits import (
    CREDIT_PACKAGES,
    CreditBalance,
    CreditPurchaseOrder,
    CreditPurchaseStatus,
    CreditTransaction,
    CreditTransactionType,
    UsageRecord,
)
from app.models.subscription import PlanType, Subscription
from app.services.account_entitlements import resolve_account_entitlement


class PlanTier(str, Enum):
    """Plan tiers."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    AGENCY = "agency"


SUBSCRIPTION_PLAN_TO_CREDITS_TIER = {
    PlanType.FREE: PlanTier.FREE,
    PlanType.MAPS_STARTER: PlanTier.STARTER,
    PlanType.CALLS_GROWTH: PlanTier.PROFESSIONAL,
    PlanType.COMPETITIVE_MARKET: PlanTier.AGENCY,
    PlanType.STARTER: PlanTier.STARTER,
    PlanType.PRO: PlanTier.PROFESSIONAL,
    PlanType.PREMIUM: PlanTier.PROFESSIONAL,
    PlanType.AGENCY: PlanTier.AGENCY,
    PlanType.ENTERPRISE: PlanTier.AGENCY,
}


# Plan configurations
PLAN_CREDITS = {
    PlanTier.FREE: {
        "monthly_credits": 0,
        "sms_daily": 0,
        "sms_monthly": 0,
        "ai_content_daily": 0,
        "ai_content_monthly": 0,
        "ai_image_daily": 0,
        "ai_image_monthly": 0,
        "ai_response_daily": 0,
        "ai_response_monthly": 0,
        "api_calls_daily": 1000,
        "api_calls_monthly": 10000,
    },
    PlanTier.STARTER: {
        "monthly_credits": 100,
        "sms_daily": 50,
        "sms_monthly": 500,
        "ai_content_daily": 20,
        "ai_content_monthly": 200,
        "ai_image_daily": 15,
        "ai_image_monthly": 150,
        "ai_response_daily": 50,
        "ai_response_monthly": 500,
        "api_calls_daily": 5000,
        "api_calls_monthly": 50000,
    },
    PlanTier.PROFESSIONAL: {
        "monthly_credits": 300,
        "sms_daily": 200,
        "sms_monthly": 2000,
        "ai_content_daily": 50,
        "ai_content_monthly": 500,
        "ai_image_daily": 50,
        "ai_image_monthly": 500,
        "ai_response_daily": 200,
        "ai_response_monthly": 2000,
        "api_calls_daily": 20000,
        "api_calls_monthly": 200000,
    },
    PlanTier.AGENCY: {
        "monthly_credits": 1000,
        "sms_daily": 1000,
        "sms_monthly": 10000,
        "ai_content_daily": 200,
        "ai_content_monthly": 2000,
        "ai_image_daily": 200,
        "ai_image_monthly": 2000,
        "ai_response_daily": 1000,
        "ai_response_monthly": 10000,
        "api_calls_daily": 100000,
        "api_calls_monthly": 1000000,
    },
}

# Credit costs for overage
CREDIT_COSTS = {
    "sms": 5,
    "ai_content": 10,
    "ai_image": 15,
    "ai_response": 2,
    "api_calls": 0,
}

USAGE_COOLDOWNS = {
    PlanTier.FREE: {"sms": 60, "ai_content": 30, "ai_image": 60, "ai_response": 10, "api_calls": 0},
    PlanTier.STARTER: {"sms": 10, "ai_content": 10, "ai_image": 30, "ai_response": 5, "api_calls": 0},
    PlanTier.PROFESSIONAL: {"sms": 5, "ai_content": 5, "ai_image": 15, "ai_response": 2, "api_calls": 0},
    PlanTier.AGENCY: {"sms": 2, "ai_content": 2, "ai_image": 5, "ai_response": 1, "api_calls": 0},
}

USAGE_TYPES = ("sms", "ai_content", "ai_image", "ai_response", "api_calls")
USAGE_LIMIT_OVERRIDE_FIELDS = (
    "sms_daily",
    "sms_monthly",
    "ai_content_daily",
    "ai_content_monthly",
    "ai_image_daily",
    "ai_image_monthly",
    "ai_response_daily",
    "ai_response_monthly",
    "api_calls_daily",
    "api_calls_monthly",
)
ACCOUNT_USAGE_LIMITS_SETTINGS_KEY = "usage_limit_overrides"
USAGE_TRANSACTION_TYPES = {
    "sms": CreditTransactionType.SMS_USAGE,
    "ai_content": CreditTransactionType.AI_CONTENT_USAGE,
    "ai_image": CreditTransactionType.AI_IMAGE_USAGE,
    "ai_response": CreditTransactionType.AI_RESPONSE_USAGE,
}

LEGACY_UNMIGRATED_USAGE_LIMITS = {
    "sms": {"daily_limit": 10, "monthly_limit": 10, "cooldown_seconds": 10, "credit_cost": 5},
    "ai_content": {"daily_limit": 5, "monthly_limit": 5, "cooldown_seconds": 10, "credit_cost": 10},
    "ai_image": {"daily_limit": 3, "monthly_limit": 3, "cooldown_seconds": 30, "credit_cost": 15},
    "ai_response": {"daily_limit": 10, "monthly_limit": 10, "cooldown_seconds": 5, "credit_cost": 2},
    "api_calls": {"daily_limit": 1000, "monthly_limit": 10000, "cooldown_seconds": 0, "credit_cost": 0},
}


def _coerce_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


class CreditsService:
    """Service for managing credits and monthly allocations."""

    def __init__(self, db: Session | None = None):
        self.db = db

    def _normalize_datetime_for_db(self, db: Session, value: datetime | None) -> datetime | None:
        """Normalize timezone-aware datetimes for SQLite-backed tests while keeping UTC semantics."""
        if value is None or value.tzinfo is None:
            return value

        bind = getattr(db, "bind", None)
        dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
        if dialect_name == "sqlite":
            return value.replace(tzinfo=None)

        return value

    @contextmanager
    def _session(self):
        """Yield the configured DB session or a short-lived fallback session."""
        if self.db is not None:
            yield self.db
            return

        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _plan_from_allocation(self, monthly_allocation: int) -> PlanTier:
        for plan, config in PLAN_CREDITS.items():
            if config["monthly_credits"] == monthly_allocation:
                return plan
        return PlanTier.FREE

    def _subscription_for_account(
        self,
        db: Session,
        account_id: str | uuid.UUID,
    ) -> Subscription | None:
        account_uuid = _coerce_uuid(account_id)
        return (
            db.query(Subscription)
            .filter(Subscription.account_id == account_uuid)
            .first()
        )

    def _resolve_plan(
        self,
        db: Session,
        account_id: str | uuid.UUID,
        *,
        balance: CreditBalance | None = None,
    ) -> tuple[str, PlanTier]:
        account_uuid = _coerce_uuid(account_id)
        entitlement = resolve_account_entitlement(db, account_uuid)
        if entitlement.plan_type:
            plan_type = entitlement.plan_type
            return plan_type.value, SUBSCRIPTION_PLAN_TO_CREDITS_TIER.get(plan_type, PlanTier.FREE)

        if balance is not None:
            plan = self._plan_from_allocation(balance.monthly_allocation)
            return plan.value, plan

        return PlanTier.FREE.value, PlanTier.FREE

    def _plan_usage_limits(self, plan: PlanTier) -> dict[str, dict[str, int]]:
        config = PLAN_CREDITS[plan]
        cooldowns = USAGE_COOLDOWNS[plan]
        usage_limits: dict[str, dict[str, int]] = {}

        for usage_type in USAGE_TYPES:
            usage_limits[usage_type] = {
                "daily_limit": int(config.get(f"{usage_type}_daily", 0)),
                "monthly_limit": int(config.get(f"{usage_type}_monthly", 0)),
                "cooldown_seconds": int(cooldowns.get(usage_type, 0)),
                "credit_cost": int(CREDIT_COSTS.get(usage_type, 0)),
            }

        return usage_limits

    def _legacy_unmigrated_usage_limits(self) -> dict[str, dict[str, int]]:
        return {
            usage_type: dict(config)
            for usage_type, config in LEGACY_UNMIGRATED_USAGE_LIMITS.items()
        }

    def _flatten_usage_limits(self, usage_limits: dict[str, dict[str, int]]) -> dict[str, int]:
        flattened: dict[str, int] = {}
        for usage_type, config in usage_limits.items():
            flattened[f"{usage_type}_daily"] = int(config["daily_limit"])
            flattened[f"{usage_type}_monthly"] = int(config["monthly_limit"])
        return flattened

    def _usage_override_key_parts(self, field_name: str) -> tuple[str, str]:
        if field_name.endswith("_daily"):
            return field_name.removesuffix("_daily"), "daily"
        if field_name.endswith("_monthly"):
            return field_name.removesuffix("_monthly"), "monthly"
        raise ValueError(f"Unsupported usage override field: {field_name}")

    def _normalize_usage_limit_overrides(self, overrides: dict | None) -> dict[str, int]:
        normalized: dict[str, int] = {}
        if not overrides:
            return normalized

        for key, value in overrides.items():
            if key not in USAGE_LIMIT_OVERRIDE_FIELDS or value is None:
                continue
            if isinstance(value, bool):
                raise ValueError(f"{key} must be an integer value.")
            try:
                parsed = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be an integer value.") from exc
            if parsed < 0:
                raise ValueError(f"{key} must be greater than or equal to zero.")
            normalized[key] = parsed

        return normalized

    def _get_account_usage_limit_overrides(
        self,
        db: Session,
        account_id: str | uuid.UUID,
    ) -> dict[str, int]:
        account_uuid = _coerce_uuid(account_id)
        account = (
            db.query(Account)
            .filter(Account.id == account_uuid)
            .first()
        )
        if account is None or not account.settings:
            return {}

        stored = account.settings.get(ACCOUNT_USAGE_LIMITS_SETTINGS_KEY)
        return self._normalize_usage_limit_overrides(stored)

    def _apply_usage_limit_overrides(
        self,
        usage_limits: dict[str, dict[str, int]],
        overrides: dict[str, int],
    ) -> dict[str, dict[str, int]]:
        merged = {
            usage_type: dict(config)
            for usage_type, config in usage_limits.items()
        }
        for field_name, value in overrides.items():
            usage_type, period = self._usage_override_key_parts(field_name)
            if usage_type not in merged:
                continue
            merged[usage_type][f"{period}_limit"] = int(value)

        for usage_type, config in merged.items():
            if config["daily_limit"] > config["monthly_limit"]:
                raise ValueError(
                    f"{usage_type} daily limit cannot exceed the monthly limit."
                )

        return merged

    def _effective_usage_limits(
        self,
        db: Session,
        account_id: str | uuid.UUID,
        plan_tier: PlanTier,
    ) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
        entitlement = resolve_account_entitlement(db, _coerce_uuid(account_id))
        overrides = self._get_account_usage_limit_overrides(db, account_id)
        base_limits = (
            self._legacy_unmigrated_usage_limits()
            if entitlement.is_legacy_fallback
            else self._plan_usage_limits(plan_tier)
        )
        merged = self._apply_usage_limit_overrides(base_limits, overrides)
        return overrides, merged

    def get_account_usage_limit_config(self, account_id: str) -> dict:
        with self._session() as db:
            balance = self._get_balance(db, account_id, create=False)
            plan_name, plan_tier = self._resolve_plan(db, account_id, balance=balance)
            overrides, effective_limits = self._effective_usage_limits(db, account_id, plan_tier)
            return {
                "plan": plan_name,
                "usage_overrides": overrides,
                "effective_usage_limits": self._flatten_usage_limits(effective_limits),
            }

    def update_account_usage_limit_overrides(
        self,
        account_id: str,
        overrides: dict[str, Optional[int]],
    ) -> dict:
        if not overrides:
            raise ValueError("At least one usage limit override must be provided.")

        with self._session() as db:
            account_uuid = _coerce_uuid(account_id)
            account = (
                db.query(Account)
                .filter(Account.id == account_uuid)
                .first()
            )
            if account is None:
                raise ValueError("Account not found.")

            settings_payload = dict(account.settings or {})
            current_overrides = self._get_account_usage_limit_overrides(db, account_uuid)
            next_overrides = dict(current_overrides)

            for key, value in overrides.items():
                if key not in USAGE_LIMIT_OVERRIDE_FIELDS:
                    raise ValueError(f"Unsupported usage limit override field: {key}")
                if value is None:
                    next_overrides.pop(key, None)
                    continue
                if isinstance(value, bool):
                    raise ValueError(f"{key} must be an integer value.")
                if int(value) < 0:
                    raise ValueError(f"{key} must be greater than or equal to zero.")
                next_overrides[key] = int(value)

            balance = self._get_balance(db, account_uuid, create=False)
            plan_name, plan_tier = self._resolve_plan(db, account_uuid, balance=balance)
            entitlement = resolve_account_entitlement(db, account_uuid)
            base_limits = (
                self._legacy_unmigrated_usage_limits()
                if entitlement.is_legacy_fallback
                else self._plan_usage_limits(plan_tier)
            )
            effective_limits = self._apply_usage_limit_overrides(base_limits, next_overrides)

            if next_overrides:
                settings_payload[ACCOUNT_USAGE_LIMITS_SETTINGS_KEY] = next_overrides
            else:
                settings_payload.pop(ACCOUNT_USAGE_LIMITS_SETTINGS_KEY, None)

            account.settings = settings_payload or None
            db.add(account)
            db.commit()
            db.refresh(account)

            return {
                "account_id": str(account.id),
                "plan": plan_name,
                "usage_overrides": next_overrides,
                "effective_usage_limits": self._flatten_usage_limits(effective_limits),
            }

    def _get_balance(
        self,
        db: Session,
        account_id: str | uuid.UUID,
        *,
        create: bool = False,
    ) -> CreditBalance | None:
        account_uuid = _coerce_uuid(account_id)
        balance = (
            db.query(CreditBalance)
            .filter(CreditBalance.account_id == account_uuid)
            .first()
        )
        if balance or not create:
            return balance

        balance = CreditBalance(account_id=account_uuid)
        db.add(balance)
        db.flush()
        return balance

    def _get_usage_record(
        self,
        db: Session,
        account_id: str | uuid.UUID,
        usage_type: str,
        *,
        now,
        create: bool = False,
    ) -> UsageRecord | None:
        account_uuid = _coerce_uuid(account_id)
        day_start = self._normalize_datetime_for_db(db, now.replace(hour=0, minute=0, second=0, microsecond=0))
        next_day_start = self._normalize_datetime_for_db(db, day_start + timedelta(days=1))

        record = (
            db.query(UsageRecord)
            .filter(
                UsageRecord.account_id == account_uuid,
                UsageRecord.usage_type == usage_type,
                UsageRecord.date >= day_start,
                UsageRecord.date < next_day_start,
            )
            .order_by(UsageRecord.created_at.desc())
            .first()
        )
        if record or not create:
            return record

        record = UsageRecord(
            account_id=account_uuid,
            usage_type=usage_type,
            date=self._normalize_datetime_for_db(db, now),
            daily_count=0,
            monthly_count=0,
            last_used_at=None,
        )
        db.add(record)
        db.flush()
        return record

    def _usage_totals(
        self,
        db: Session,
        account_id: str | uuid.UUID,
        usage_type: str,
        *,
        now: datetime,
        monthly_start: datetime | None = None,
    ) -> tuple[int, int]:
        account_uuid = _coerce_uuid(account_id)
        day_start = self._normalize_datetime_for_db(db, now.replace(hour=0, minute=0, second=0, microsecond=0))
        month_start = self._normalize_datetime_for_db(db, monthly_start or day_start.replace(day=1))
        next_day_start = self._normalize_datetime_for_db(db, day_start + timedelta(days=1))

        daily_used = (
            db.query(func.coalesce(func.sum(UsageRecord.daily_count), 0))
            .filter(
                UsageRecord.account_id == account_uuid,
                UsageRecord.usage_type == usage_type,
                UsageRecord.date >= day_start,
                UsageRecord.date < next_day_start,
            )
            .scalar()
            or 0
        )
        monthly_used = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(
                UsageRecord.account_id == account_uuid,
                UsageRecord.usage_type == usage_type,
                UsageRecord.date >= month_start,
            )
            .scalar()
            or 0
        )
        return int(daily_used), int(monthly_used)

    def _serialize_transaction(self, transaction: CreditTransaction) -> dict:
        usage_type = None
        if transaction.type.value.endswith("_usage"):
            usage_type = transaction.type.value.removesuffix("_usage")

        return {
            "id": str(transaction.id),
            "type": transaction.type.value,
            "usage_type": usage_type,
            "amount": transaction.amount,
            "balance_after": transaction.balance_after,
            "description": transaction.description or "",
            "reference_type": transaction.reference_type,
            "reference_id": transaction.reference_id,
            "admin_id": str(transaction.admin_id) if transaction.admin_id else None,
            "created_at": transaction.created_at,
        }

    def process_payment(
        self,
        account_id: str,
        plan: PlanTier,
        payment_date: Optional[datetime] = None,
    ) -> dict:
        """
        Process a subscription payment.
        This resets monthly allocation and persists the allocation in the DB.
        """
        payment_date = payment_date or utc_now_aware()

        with self._session() as db:
            balance = self._get_balance(db, account_id, create=True)
            old_plan = self._plan_from_allocation(balance.monthly_allocation)
            monthly_credits = PLAN_CREDITS[plan]["monthly_credits"]
            next_billing = payment_date + timedelta(days=30)

            balance.balance = monthly_credits
            balance.monthly_allocation = monthly_credits
            balance.last_allocation_date = payment_date
            balance.next_allocation_date = next_billing
            balance.total_credits_received += monthly_credits

            db.add(
                CreditTransaction(
                    account_id=balance.account_id,
                    type=CreditTransactionType.MONTHLY_ALLOCATION,
                    amount=monthly_credits,
                    balance_after=balance.total_available,
                    description=f"Monthly credit allocation ({plan.value} plan)",
                    reference_type="subscription",
                    reference_id=None,
                    created_at=payment_date,
                )
            )
            db.commit()
            db.refresh(balance)

            return {
                "success": True,
                "account_id": account_id,
                "old_plan": old_plan.value,
                "new_plan": plan.value,
                "credits_allocated": monthly_credits,
                "new_balance": balance.total_available,
                "billing_cycle_start": payment_date.isoformat(),
                "next_billing_date": next_billing.isoformat(),
                "usage_reset": True,
            }

    def check_and_reset_daily(self, account_id: str) -> bool:
        """No-op for DB-backed usage rows. Kept for compatibility."""
        with self._session():
            return True

    def use_credits(
        self,
        account_id: str,
        usage_type: str,
        count: int = 1,
    ) -> dict:
        """
        Record usage and deduct credits if over the plan limits.
        """
        if usage_type not in USAGE_TYPES:
            raise ValueError(f"Unsupported usage type: {usage_type}")

        with self._session() as db:
            now = utc_now_aware()
            balance = self._get_balance(db, account_id, create=True)
            _, plan_tier = self._resolve_plan(db, account_id, balance=balance)
            _, effective_limits = self._effective_usage_limits(db, account_id, plan_tier)
            monthly_start = balance.last_allocation_date or now.replace(day=1)

            usage_limits = effective_limits[usage_type]
            daily_limit = usage_limits["daily_limit"]
            monthly_limit = usage_limits["monthly_limit"]

            current_daily, current_monthly = self._usage_totals(
                db,
                account_id,
                usage_type,
                now=now,
                monthly_start=monthly_start,
            )
            usage_record = self._get_usage_record(
                db,
                account_id,
                usage_type,
                now=now,
                create=True,
            )

            within_daily = current_daily + count <= daily_limit
            within_monthly = current_monthly + count <= monthly_limit

            credits_used = 0

            if within_daily and within_monthly:
                usage_record.daily_count += count
                usage_record.monthly_count += count
                usage_record.last_used_at = self._normalize_datetime_for_db(db, now)
                db.commit()
            else:
                credit_cost = CREDIT_COSTS.get(usage_type, 5) * count

                if credit_cost <= 0:
                    return {
                        "allowed": False,
                        "reason": "plan_limit_reached",
                        "credits_required": 0,
                        "credits_available": balance.total_available,
                        "remaining_daily": max(0, daily_limit - current_daily),
                        "remaining_monthly": max(0, monthly_limit - current_monthly),
                    }

                if not balance.can_afford(credit_cost):
                    return {
                        "allowed": False,
                        "reason": "insufficient_credits",
                        "credits_required": credit_cost,
                        "credits_available": balance.total_available,
                        "remaining_daily": max(0, daily_limit - current_daily),
                        "remaining_monthly": max(0, monthly_limit - current_monthly),
                    }

                if not balance.deduct(credit_cost):
                    return {
                        "allowed": False,
                        "reason": "insufficient_credits",
                        "credits_required": credit_cost,
                        "credits_available": balance.total_available,
                        "remaining_daily": max(0, daily_limit - current_daily),
                        "remaining_monthly": max(0, monthly_limit - current_monthly),
                    }

                credits_used = credit_cost
                usage_record.daily_count += count
                usage_record.monthly_count += count
                usage_record.last_used_at = self._normalize_datetime_for_db(db, now)
                db.add(
                    CreditTransaction(
                        account_id=balance.account_id,
                        type=USAGE_TRANSACTION_TYPES[usage_type],
                        amount=-credit_cost,
                        balance_after=balance.total_available,
                        description=f"{usage_type} overage charge",
                        reference_type="usage",
                        reference_id=usage_type,
                        created_at=now,
                    )
                )
                db.commit()

            return {
                "allowed": True,
                "credits_used": credits_used,
                "remaining_daily": max(0, daily_limit - (current_daily + count)),
                "remaining_monthly": max(0, monthly_limit - (current_monthly + count)),
                "balance": balance.total_available,
            }

    def get_account_status(self, account_id: str) -> dict:
        """Get full account status including credits and usage."""
        with self._session() as db:
            now = utc_now_aware()
            balance = self._get_balance(db, account_id, create=False)
            if balance is None:
                monthly_start = now.replace(day=1)
                balance_snapshot = {
                    "balance": 0,
                    "bonus_balance": 0,
                    "total_available": 0,
                    "monthly_allocation": 0,
                    "last_allocation_date": None,
                    "next_allocation_date": None,
                    "total_credits_received": 0,
                    "total_credits_used": 0,
                    "total_credits_purchased": 0,
                }
            else:
                monthly_start = balance.last_allocation_date or now.replace(day=1)
                balance_snapshot = {
                    "balance": balance.balance,
                    "bonus_balance": balance.bonus_balance,
                    "total_available": balance.total_available,
                    "monthly_allocation": balance.monthly_allocation,
                    "last_allocation_date": balance.last_allocation_date,
                    "next_allocation_date": balance.next_allocation_date,
                    "total_credits_received": balance.total_credits_received,
                    "total_credits_used": balance.total_credits_used,
                    "total_credits_purchased": balance.total_credits_purchased,
                }
            plan_name, plan_tier = self._resolve_plan(db, account_id, balance=balance)
            _, plan_limits = self._effective_usage_limits(db, account_id, plan_tier)

            usage_status = {}
            for usage_type in USAGE_TYPES:
                limits = plan_limits[usage_type]
                daily_used, monthly_used = self._usage_totals(
                    db,
                    account_id,
                    usage_type,
                    now=now,
                    monthly_start=monthly_start,
                )

                usage_status[usage_type] = {
                    "daily_used": daily_used,
                    "daily_limit": limits["daily_limit"],
                    "daily_remaining": max(0, limits["daily_limit"] - daily_used),
                    "monthly_used": monthly_used,
                    "monthly_limit": limits["monthly_limit"],
                    "monthly_remaining": max(0, limits["monthly_limit"] - monthly_used),
                    "cooldown_seconds": limits["cooldown_seconds"],
                    "credit_cost": limits["credit_cost"],
                }

            return {
                "account_id": account_id,
                "plan": plan_name,
                "credits": {
                    "balance": balance_snapshot["balance"],
                    "bonus_balance": balance_snapshot["bonus_balance"],
                    "total_available": balance_snapshot["total_available"],
                    "monthly_allocation": balance_snapshot["monthly_allocation"],
                },
                "billing": {
                    "last_allocation": (
                        balance_snapshot["last_allocation_date"].isoformat()
                        if balance_snapshot["last_allocation_date"]
                        else None
                    ),
                    "next_allocation": (
                        balance_snapshot["next_allocation_date"].isoformat()
                        if balance_snapshot["next_allocation_date"]
                        else None
                    ),
                    "billing_cycle_start": (
                        balance_snapshot["last_allocation_date"].isoformat()
                        if balance_snapshot["last_allocation_date"]
                        else None
                    ),
                },
                "usage": usage_status,
                "stats": {
                    "total_received": balance_snapshot["total_credits_received"],
                    "total_used": balance_snapshot["total_credits_used"],
                    "total_purchased": balance_snapshot["total_credits_purchased"],
                },
            }

    def preview_usage(
        self,
        account_id: str,
        usage_type: str,
        count: int = 1,
    ) -> dict:
        """Preview whether usage would be allowed without recording it."""
        if usage_type not in USAGE_TYPES:
            raise ValueError(f"Unsupported usage type: {usage_type}")

        with self._session() as db:
            now = utc_now_aware()
            balance = self._get_balance(db, account_id, create=False)
            available_credits = balance.total_available if balance is not None else 0
            _, plan_tier = self._resolve_plan(db, account_id, balance=balance)
            _, effective_limits = self._effective_usage_limits(db, account_id, plan_tier)
            limits = effective_limits[usage_type]
            usage_record = self._get_usage_record(
                db,
                account_id,
                usage_type,
                now=now,
                create=False,
            )
            monthly_start = balance.last_allocation_date if balance and balance.last_allocation_date else now.replace(day=1)
            daily_used, monthly_used = self._usage_totals(
                db,
                account_id,
                usage_type,
                now=now,
                monthly_start=monthly_start,
            )

            remaining_daily = max(0, limits["daily_limit"] - daily_used)
            remaining_monthly = max(0, limits["monthly_limit"] - monthly_used)

            cooldown_remaining = 0
            if limits["cooldown_seconds"] > 0 and usage_record and usage_record.last_used_at:
                last_used_at = usage_record.last_used_at
                if last_used_at.tzinfo is None:
                    last_used_at = last_used_at.replace(tzinfo=now.tzinfo)
                cooldown_end = last_used_at + timedelta(seconds=limits["cooldown_seconds"])
                if now < cooldown_end:
                    cooldown_remaining = int((cooldown_end - now).total_seconds())

            if cooldown_remaining > 0:
                return {
                    "allowed": False,
                    "reason": f"Please wait {cooldown_remaining} seconds before trying again",
                    "remaining_daily": remaining_daily,
                    "remaining_monthly": remaining_monthly,
                    "cooldown_remaining_seconds": cooldown_remaining,
                    "overage_available": False,
                    "overage_cost_cents": 0,
                    "credits_available": available_credits,
                }

            would_exceed_daily = daily_used + count > limits["daily_limit"]
            would_exceed_monthly = monthly_used + count > limits["monthly_limit"]
            overage_cost = limits["credit_cost"] * count
            overage_available = overage_cost > 0

            if would_exceed_daily or would_exceed_monthly:
                reason = (
                    f"Daily limit reached ({limits['daily_limit']}/{limits['daily_limit']}). Resets at midnight UTC."
                    if would_exceed_daily
                    else f"Monthly limit reached ({limits['monthly_limit']}/{limits['monthly_limit']}). Resets on the 1st."
                )
                return {
                    "allowed": False,
                    "reason": reason,
                    "remaining_daily": remaining_daily,
                    "remaining_monthly": remaining_monthly,
                    "cooldown_remaining_seconds": 0,
                    "overage_available": overage_available,
                    "overage_cost_cents": overage_cost,
                    "credits_available": available_credits,
                }

            return {
                "allowed": True,
                "reason": None,
                "remaining_daily": max(0, limits["daily_limit"] - daily_used - count),
                "remaining_monthly": max(0, limits["monthly_limit"] - monthly_used - count),
                "cooldown_remaining_seconds": 0,
                "overage_available": False,
                "overage_cost_cents": 0,
                "credits_available": available_credits,
            }

    def create_purchase_checkout(
        self,
        account_id: str,
        package_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        """Create a Stripe Checkout Session for a one-time credit purchase.

        Credits are NOT applied here – they are applied only after the
        ``checkout.session.completed`` webhook confirms payment.

        Returns::

            {
                "checkout_url": "https://checkout.stripe.com/...",
                "session_id": "cs_...",
                "order_id": "<uuid>",
                "credits_amount": 100,
                "price_cents": 899,
            }

        Raises ``ValueError`` if the package_id is unknown.
        Raises ``RuntimeError`` if Stripe is not configured.
        """
        import stripe

        from app.core.config import settings

        if package_id not in CREDIT_PACKAGES:
            raise ValueError(
                f"Unknown credit package: {package_id!r}. "
                f"Valid packages: {list(CREDIT_PACKAGES)}"
            )

        if not settings.stripe_secret_key:
            raise RuntimeError(
                "Stripe is not configured (STRIPE_SECRET_KEY missing). "
                "Credit purchases are unavailable until Stripe is set up."
            )

        stripe.api_key = settings.stripe_secret_key
        credits_amount, price_cents, label = CREDIT_PACKAGES[package_id]

        # Resolve price ID – use pre-created Stripe price if configured,
        # otherwise fall back to inline price_data (no dashboard setup needed).
        price_id_map: dict[str, str | None] = {
            "credits_50":  settings.stripe_price_credits_50,
            "credits_100": settings.stripe_price_credits_100,
            "credits_250": settings.stripe_price_credits_250,
            "credits_500": settings.stripe_price_credits_500,
        }
        configured_price_id = price_id_map.get(package_id)

        if configured_price_id:
            line_items = [{"price": configured_price_id, "quantity": 1}]
        else:
            line_items = [
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": label},
                        "unit_amount": price_cents,
                    },
                    "quantity": 1,
                }
            ]

        account_id_str = str(account_id)

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "purchase_type": "credits",
                "package_id": package_id,
                "credits_amount": str(credits_amount),
                "account_id": account_id_str,
            },
        )

        with self._session() as db:
            now = utc_now_aware()
            order = CreditPurchaseOrder(
                account_id=_coerce_uuid(account_id),
                stripe_session_id=session.id,
                package_id=package_id,
                credits_amount=credits_amount,
                price_cents=price_cents,
                status=CreditPurchaseStatus.PENDING,
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            order_id = str(order.id)

        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "order_id": order_id,
            "credits_amount": credits_amount,
            "price_cents": price_cents,
        }

    def apply_purchase_from_webhook(
        self,
        stripe_session_id: str,
        stripe_payment_intent_id: str | None = None,
    ) -> dict:
        """Apply credits after Stripe confirms payment.

        Called exclusively from the ``checkout.session.completed`` webhook
        handler.  Idempotent: calling it twice for the same session is safe
        (the second call is a no-op that returns ``already_applied=True``).

        Returns a summary dict suitable for logging.
        """
        with self._session() as db:
            now = utc_now_aware()
            order = (
                db.query(CreditPurchaseOrder)
                .filter(CreditPurchaseOrder.stripe_session_id == stripe_session_id)
                .first()
            )

            if order is None:
                return {
                    "applied": False,
                    "reason": "order_not_found",
                    "stripe_session_id": stripe_session_id,
                }

            if order.status == CreditPurchaseStatus.COMPLETED:
                return {
                    "applied": False,
                    "already_applied": True,
                    "order_id": str(order.id),
                    "account_id": str(order.account_id),
                    "credits_amount": order.credits_amount,
                }

            if order.status != CreditPurchaseStatus.PENDING:
                return {
                    "applied": False,
                    "reason": "order_not_pending",
                    "order_id": str(order.id),
                    "account_id": str(order.account_id),
                    "status": order.status.value,
                }

            balance = self._get_balance(db, order.account_id, create=True)
            balance.balance += order.credits_amount
            balance.total_credits_received += order.credits_amount
            balance.total_credits_purchased += order.credits_amount

            db.add(
                CreditTransaction(
                    account_id=order.account_id,
                    type=CreditTransactionType.PURCHASE,
                    amount=order.credits_amount,
                    balance_after=balance.total_available,
                    description=f"Credit purchase: {order.package_id}",
                    reference_type="credit_purchase",
                    reference_id=str(order.id),
                    created_at=now,
                )
            )

            order.status = CreditPurchaseStatus.COMPLETED
            order.stripe_payment_intent_id = stripe_payment_intent_id
            order.completed_at = utc_now_aware()

            db.commit()
            db.refresh(balance)

            return {
                "applied": True,
                "order_id": str(order.id),
                "account_id": str(order.account_id),
                "credits_amount": order.credits_amount,
                "new_balance": balance.total_available,
            }

    def cancel_purchase_order(
        self,
        stripe_session_id: str,
        target_status: CreditPurchaseStatus = CreditPurchaseStatus.CANCELED,
    ) -> dict:
        """Mark a PENDING purchase order as CANCELED or EXPIRED.

        Called when Stripe fires ``checkout.session.expired`` (or an async
        payment failure) so the order doesn't linger in PENDING forever.
        Idempotent: already-canceled/expired orders return ``already_canceled=True``.
        Credits were never applied, so no balance changes are needed.

        Returns a summary dict suitable for logging.
        """
        with self._session() as db:
            order = (
                db.query(CreditPurchaseOrder)
                .filter(CreditPurchaseOrder.stripe_session_id == stripe_session_id)
                .first()
            )

            if order is None:
                return {
                    "canceled": False,
                    "reason": "order_not_found",
                    "stripe_session_id": stripe_session_id,
                }

            terminal_non_pending = {
                CreditPurchaseStatus.CANCELED,
                CreditPurchaseStatus.EXPIRED,
            }
            if order.status in terminal_non_pending:
                return {
                    "canceled": False,
                    "already_canceled": True,
                    "order_id": str(order.id),
                    "status": order.status.value,
                }

            if order.status == CreditPurchaseStatus.COMPLETED:
                # Cannot cancel a completed (paid) order through this path.
                return {
                    "canceled": False,
                    "reason": "order_already_completed",
                    "order_id": str(order.id),
                }

            if order.status == CreditPurchaseStatus.REFUNDED:
                return {
                    "canceled": False,
                    "reason": "order_already_refunded",
                    "order_id": str(order.id),
                }

            order.status = target_status
            db.commit()

            return {
                "canceled": True,
                "order_id": str(order.id),
                "account_id": str(order.account_id),
                "new_status": target_status.value,
            }

    def refund_purchase(
        self,
        stripe_payment_intent_id: str,
    ) -> dict:
        """Claw back credits when Stripe issues a refund for a credit purchase.

        Called from the ``charge.refunded`` webhook handler.  Idempotent:
        calling it twice for the same payment intent is safe (second call
        returns ``already_refunded=True``).

        Deducts credits from the account balance (bonus first, then regular),
        clamped at zero – the balance cannot go negative.  Records a REFUND
        transaction for the amount actually deducted so the ledger stays honest.

        Returns a summary dict suitable for logging.
        """
        with self._session() as db:
            now = utc_now_aware()

            order = (
                db.query(CreditPurchaseOrder)
                .filter(
                    CreditPurchaseOrder.stripe_payment_intent_id
                    == stripe_payment_intent_id
                )
                .first()
            )

            if order is None:
                return {
                    "refunded": False,
                    "reason": "order_not_found",
                    "stripe_payment_intent_id": stripe_payment_intent_id,
                }

            if order.status == CreditPurchaseStatus.REFUNDED:
                return {
                    "refunded": False,
                    "already_refunded": True,
                    "order_id": str(order.id),
                    "account_id": str(order.account_id),
                }

            if order.status != CreditPurchaseStatus.COMPLETED:
                # Refund on a non-completed order is unexpected – log but don't
                # crash; credits were never applied so there's nothing to deduct.
                return {
                    "refunded": False,
                    "reason": "order_not_completed",
                    "order_id": str(order.id),
                    "status": order.status.value,
                }

            balance = self._get_balance(db, order.account_id, create=False)

            # Deduct purchased credits, clamped at zero (bonus first, then regular)
            credits_to_deduct = order.credits_amount
            actual_deducted = 0

            if balance is not None:
                available = balance.total_available
                actual_deducted = min(credits_to_deduct, available)

                if actual_deducted > 0:
                    remaining = actual_deducted
                    if balance.bonus_balance > 0:
                        bonus_used = min(balance.bonus_balance, remaining)
                        balance.bonus_balance -= bonus_used
                        remaining -= bonus_used
                    if remaining > 0:
                        balance.balance -= remaining

                    # Adjust lifetime purchased counter
                    balance.total_credits_purchased = max(
                        0, balance.total_credits_purchased - order.credits_amount
                    )
                    balance.total_credits_received = max(
                        0, balance.total_credits_received - order.credits_amount
                    )

                db.add(
                    CreditTransaction(
                        account_id=order.account_id,
                        type=CreditTransactionType.REFUND,
                        amount=-actual_deducted,
                        balance_after=balance.total_available,
                        description=f"Refund: {order.package_id}",
                        reference_type="credit_purchase",
                        reference_id=str(order.id),
                        created_at=now,
                    )
                )

            order.status = CreditPurchaseStatus.REFUNDED
            order.refunded_at = now

            db.commit()
            if balance is not None:
                db.refresh(balance)

            return {
                "refunded": True,
                "order_id": str(order.id),
                "account_id": str(order.account_id),
                "credits_deducted": actual_deducted,
                "new_balance": balance.total_available if balance is not None else 0,
            }

    def purchase_credits(
        self,
        account_id: str,
        amount: int,
        payment_id: str = "",
    ) -> dict:
        """Backward-compatible wrapper around Stripe Checkout credit purchases.

        ``amount`` is interpreted as the credit quantity, not cents. Only
        exact configured package amounts are supported so legacy callers
        cannot fabricate arbitrary one-off prices.
        """
        from app.core.config import settings

        package_id = next(
            (
                package_key
                for package_key, (credits_amount, _price_cents, _label) in CREDIT_PACKAGES.items()
                if credits_amount == amount
            ),
            None,
        )
        if package_id is None:
            supported_amounts = sorted(
                credits_amount
                for credits_amount, _price_cents, _label in CREDIT_PACKAGES.values()
            )
            raise ValueError(
                "Legacy credit purchase wrapper only supports exact package sizes. "
                f"Supported amounts: {supported_amounts}."
            )

        base_url = settings.app_url.rstrip("/") or "http://localhost:3000"
        if payment_id:
            success_url = f"{base_url}/dashboard/usage?creditsPurchase=success&payment_id={payment_id}"
            cancel_url = f"{base_url}/dashboard/usage?creditsPurchase=canceled&payment_id={payment_id}"
        else:
            success_url = f"{base_url}/dashboard/usage?creditsPurchase=success"
            cancel_url = f"{base_url}/dashboard/usage?creditsPurchase=canceled"

        result = self.create_purchase_checkout(
            account_id=account_id,
            package_id=package_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        result["package_id"] = package_id
        result["legacy_amount"] = amount
        return result

    def grant_bonus(
        self,
        account_id: str,
        amount: int,
        reason: str = "Bonus credits",
    ) -> dict:
        """Grant bonus credits (admin action)."""
        with self._session() as db:
            now = utc_now_aware()
            balance = self._get_balance(db, account_id, create=True)
            balance.bonus_balance += amount
            balance.total_credits_received += amount
            db.add(
                CreditTransaction(
                    account_id=balance.account_id,
                    type=CreditTransactionType.BONUS,
                    amount=amount,
                    balance_after=balance.total_available,
                    description=reason,
                    reference_type="bonus",
                    reference_id=None,
                    created_at=now,
                )
            )
            db.commit()
            db.refresh(balance)

            return {
                "success": True,
                "bonus_added": amount,
                "new_bonus_balance": balance.bonus_balance,
                "new_total": balance.total_available,
            }

    def get_transactions(
        self,
        account_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Get recent transactions for an account."""
        with self._session() as db:
            account_uuid = _coerce_uuid(account_id)
            type_priority = case(
                (
                    CreditTransaction.type.in_(
                        [
                            CreditTransactionType.SMS_USAGE,
                            CreditTransactionType.AI_CONTENT_USAGE,
                            CreditTransactionType.AI_IMAGE_USAGE,
                            CreditTransactionType.AI_RESPONSE_USAGE,
                            CreditTransactionType.OVERAGE_CHARGE,
                        ]
                    ),
                    0,
                ),
                (
                    CreditTransaction.type == CreditTransactionType.PURCHASE,
                    1,
                ),
                (
                    CreditTransaction.type.in_(
                        [
                            CreditTransactionType.BONUS,
                            CreditTransactionType.REFUND,
                            CreditTransactionType.ADMIN_GRANT,
                        ]
                    ),
                    2,
                ),
                (
                    CreditTransaction.type == CreditTransactionType.MONTHLY_ALLOCATION,
                    3,
                ),
                else_=9,
            )
            transactions = (
                db.query(CreditTransaction)
                .filter(CreditTransaction.account_id == account_uuid)
                .order_by(CreditTransaction.created_at.desc(), type_priority.asc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [self._serialize_transaction(transaction) for transaction in transactions]


# Global instance
credits_service = CreditsService()
