"""Shared account entitlement resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.subscription import PlanType, Subscription


LEGACY_UNMIGRATED_PLAN = PlanType.PREMIUM


@dataclass(frozen=True)
class AccountEntitlement:
    """Resolved plan access for an account."""

    plan_type: PlanType
    source: str
    subscription: Subscription | None = None

    @property
    def is_legacy_fallback(self) -> bool:
        return self.source == "legacy_unmigrated"


def latest_subscription_for_account(db: Session, account_id: UUID) -> Subscription | None:
    """Return the newest subscription row for an account, if present."""
    return (
        db.query(Subscription)
        .filter(Subscription.account_id == account_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )


def resolve_account_entitlement(db: Session, account_id: UUID) -> AccountEntitlement:
    """Resolve the effective plan for an account.

    Rules:
    - Active/trialing subscriptions are the source of truth.
    - Inactive subscriptions do not grant paid feature access.
    - Legacy accounts with no subscription row keep a premium-equivalent fallback
      until billing migration explicitly attaches a subscription snapshot.
    """

    subscription = latest_subscription_for_account(db, account_id)
    if subscription and subscription.plan_type and subscription.is_active:
        return AccountEntitlement(
            plan_type=subscription.plan_type,
            source="subscription",
            subscription=subscription,
        )

    if subscription is not None:
        return AccountEntitlement(
            plan_type=PlanType.FREE,
            source="inactive_subscription",
            subscription=subscription,
        )

    account_exists = (
        db.query(Account.id)
        .filter(Account.id == account_id)
        .first()
        is not None
    )
    if account_exists:
        return AccountEntitlement(
            plan_type=LEGACY_UNMIGRATED_PLAN,
            source="legacy_unmigrated",
            subscription=None,
        )

    return AccountEntitlement(
        plan_type=PlanType.FREE,
        source="account_missing",
        subscription=None,
    )
