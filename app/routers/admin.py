"""Admin router.

Admin access is restricted to accounts with the ADMIN role.
Read-only and mutating endpoints use persisted product data and audit trails
rather than fabricated demo state.
"""

import csv
from io import StringIO
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.core.config import settings
from app.models.account import Account, AccountRole
from app.models.analytics import Analytics
from app.models.billing import (
    BillingAuditAction,
    BillingAuditLog,
    Dispute as DisputeModel,
    DisputeStatus,
    Payment,
    PaymentStatus,
)
from app.models.credits import (
    CreditBalance,
    CreditPurchaseOrder,
    CreditPurchaseStatus,
    CreditTransaction as CreditTransactionModel,
    CreditTransactionType,
    UsageRecord,
)
from app.models.location import Location
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.oauth import OAuthEvent, OAuthEventType, OAuthStatus, OAuthToken
from app.models.post import Post
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.review_booster import BoosterRequest, RequestStatus
from app.models.subscription import (
    PLAN_PRICES,
    DunningStatus,
    PlanType,
    Subscription,
    SubscriptionStatus,
)
from app.models.upload import UploadAsset
from app.routers.deps import get_current_account
from app.services.credits import CreditsService, PLAN_CREDITS, SUBSCRIPTION_PLAN_TO_CREDITS_TIER
from app.services.billing import BillingService
from app.services.dunning_service import DunningService
from app.services.file_upload import file_upload_service
from app.services.plan_limits import get_plan_limits
from app.services.storage import get_storage_service
from app.services.upload_migration import UploadMigrationService

router = APIRouter(prefix="/admin", tags=["Admin"])


class UserSummary(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    plan: str
    credits: int
    status: str
    created_at: datetime
    last_login: Optional[datetime] = None
    custom_limits: Optional[dict] = None


class UserListResponse(BaseModel):
    users: list[UserSummary]
    total: int
    page: int
    page_size: int


class UserDetail(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    plan: str
    credits: int
    bonus_credits: int
    status: str
    created_at: datetime
    last_login: Optional[datetime] = None
    usage: dict
    custom_limits: Optional[dict] = None


class UpdateUserCreditsRequest(BaseModel):
    credits: int
    reason: str


class UpdateUserPlanRequest(BaseModel):
    plan: str


class UpdateUserLimitsRequest(BaseModel):
    sms_daily: Optional[int] = Field(default=None, ge=0)
    sms_monthly: Optional[int] = Field(default=None, ge=0)
    ai_content_daily: Optional[int] = Field(default=None, ge=0)
    ai_content_monthly: Optional[int] = Field(default=None, ge=0)
    ai_image_daily: Optional[int] = Field(default=None, ge=0)
    ai_image_monthly: Optional[int] = Field(default=None, ge=0)
    ai_response_daily: Optional[int] = Field(default=None, ge=0)
    ai_response_monthly: Optional[int] = Field(default=None, ge=0)
    api_calls_daily: Optional[int] = Field(default=None, ge=0)
    api_calls_monthly: Optional[int] = Field(default=None, ge=0)


class AdminAccountLifecycleResponse(BaseModel):
    account_id: str
    email: str
    is_active: bool
    status: str
    changed: bool
    operator_action: str
    updated_at: datetime


class AdminPlanChangeResponse(BaseModel):
    account_id: str
    email: str
    previous_plan: str
    current_plan: str
    status: str
    stripe_synced: bool
    stripe_subscription_id: Optional[str] = None
    updated_at: datetime


class AdminUsageLimitOverrideResponse(BaseModel):
    account_id: str
    email: str
    plan: str
    usage_overrides: dict[str, int]
    effective_usage_limits: dict[str, int]
    updated_at: datetime


class MonthlyCreditDistributionAccountResult(BaseModel):
    account_id: str
    email: str
    plan: str
    credits_allocated: int = 0
    new_balance: int
    reason: str
    next_allocation_date: Optional[datetime] = None


class MonthlyCreditDistributionResponse(BaseModel):
    considered: int
    processed: int
    skipped: int
    distributed_accounts: list[MonthlyCreditDistributionAccountResult]
    skipped_accounts: list[MonthlyCreditDistributionAccountResult]
    generated_at: datetime


class GrantCreditsRequest(BaseModel):
    user_id: str
    amount: int
    reason: str
    is_bonus: bool = False


class BulkGrantCreditsRequest(BaseModel):
    user_ids: list[str]
    amount: int
    reason: str
    is_bonus: bool = False


class SystemStats(BaseModel):
    total_users: int
    active_users: int
    total_credits_issued: int
    total_credits_used: int
    total_sms_sent: int
    total_ai_content: int
    total_ai_images: int
    revenue_this_month: float


class CreditTransaction(BaseModel):
    id: str
    user_id: str
    user_email: str
    type: str
    amount: int
    reason: str
    admin_id: Optional[str] = None
    created_at: datetime


class PlanConfig(BaseModel):
    name: str
    monthly_credits: int
    sms_daily: int
    sms_monthly: int
    ai_content_daily: int
    ai_content_monthly: int
    ai_image_daily: int
    ai_image_monthly: int
    price_monthly: int


ADMIN_PUBLIC_PLANS = (
    PlanType.FREE,
    PlanType.MAPS_STARTER,
    PlanType.CALLS_GROWTH,
    PlanType.COMPETITIVE_MARKET,
    PlanType.STARTER,
    PlanType.PRO,
    PlanType.PREMIUM,
    PlanType.AGENCY,
)


class RefundRequest(BaseModel):
    payment_id: str
    amount: Optional[float] = None
    reason: str


class RefundResponse(BaseModel):
    id: str
    payment_id: str
    user_id: str
    user_email: str
    amount: float
    reason: str
    status: str
    created_at: datetime
    processed_at: Optional[datetime] = None


class DisputeResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    payment_id: str
    amount: float
    reason: str
    status: str
    evidence: Optional[str] = None
    created_at: datetime
    evidence_due_by: Optional[datetime] = None
    source: str = "stripe_live"


class DisputeListResponse(BaseModel):
    disputes: list[DisputeResponse]
    stripe_available: bool
    data_source: str
    warning: Optional[str] = None


class DisputeEvidenceRequest(BaseModel):
    evidence: str
    proof_checklist: list[str] = []
    attachment_names: list[str] = []
    attachment_urls: list[str] = []
    attachment_note: Optional[str] = None


class DisputeAttachmentUploadResponse(BaseModel):
    filename: str
    url: str
    mime_type: str
    size_bytes: int


class RecoveryActionPlan(BaseModel):
    headline: str
    operator_note: str
    customer_message: str


class RecoveryAccountSummary(BaseModel):
    account_id: str
    email: str
    company_name: Optional[str] = None
    plan: str
    subscription_status: str
    access_state: str
    dunning_status: str
    payment_retry_count: int
    last_payment_error: Optional[str] = None
    next_payment_retry_at: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    action_plan: RecoveryActionPlan


class RecoveryDisputeSummary(BaseModel):
    dispute_id: str
    account_id: str
    user_email: str
    amount: float
    reason: Optional[str] = None
    status: str
    evidence_due_by: Optional[datetime] = None
    created_at: datetime
    action_plan: RecoveryActionPlan


class RecoveryRefundSummary(BaseModel):
    order_id: str
    account_id: str
    user_email: str
    payment_id: str
    amount: float
    status: str
    created_at: datetime
    processed_at: Optional[datetime] = None
    action_plan: RecoveryActionPlan


class RecoveryRunbookItem(BaseModel):
    id: str
    title: str
    priority: str
    summary: str
    steps: list[str]
    cta_label: Optional[str] = None
    cta_href: Optional[str] = None


class RecoveryActivityEntry(BaseModel):
    id: str
    account_id: Optional[str] = None
    account_email: Optional[str] = None
    action: str
    operator_action: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime


class RecoveryQueueResponse(BaseModel):
    dunning_accounts: list[RecoveryAccountSummary]
    disputes: list[RecoveryDisputeSummary]
    recent_refunds: list[RecoveryRefundSummary]
    runbook_items: list[RecoveryRunbookItem]
    recent_operator_actions: list[RecoveryActivityEntry]
    dunning_total: int
    dispute_total: int
    urgent_dispute_total: int
    refunded_total: int
    action_required_total: int
    generated_at: datetime
    source: str = "database"


class DunningRecoveryLinkResponse(BaseModel):
    account_id: str
    email: str
    portal_url: str
    portal_available: bool
    portal_source: str
    portal_error: Optional[str] = None
    action_plan: RecoveryActionPlan
    generated_at: datetime


class OperationsFeedItem(BaseModel):
    id: str
    domain: str
    severity: str
    title: str
    summary: str
    status: str
    account_id: Optional[str] = None
    account_email: Optional[str] = None
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    occurred_at: datetime
    actionable: bool = False
    action_href: Optional[str] = None


class OperationsFeedResponse(BaseModel):
    items: list[OperationsFeedItem]
    total: int
    actionable_total: int
    domain_totals: dict[str, int]
    generated_at: datetime
    source: str = "database"


class UploadMigrationAuditItem(BaseModel):
    source_type: str
    entity_id: str
    field_name: str
    url: str
    recommended_action: str
    storage_key: Optional[str] = None
    account_id: Optional[str] = None
    account_email: Optional[str] = None
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    created_at: datetime


class UploadMigrationBatchSummary(BaseModel):
    recommended_action: str
    priority: str
    reference_total: int
    affected_account_total: int
    affected_location_total: int
    summary: str


class UploadMigrationAuditResponse(BaseModel):
    upload_asset_total: int
    upload_asset_local_total: int
    legacy_post_image_total: int
    legacy_post_ai_image_total: int
    legacy_billing_attachment_total: int
    affected_account_total: int
    actionable_total: int
    cloud_storage_configured: bool
    sample_limit: int
    batch_summaries: list[UploadMigrationBatchSummary]
    runbook_steps: list[str]
    items: list[UploadMigrationAuditItem]
    generated_at: datetime
    source: str = "database"


class UploadMigrationBatchPreviewItem(BaseModel):
    source_type: str
    entity_id: str
    field_name: str
    original_url: str
    destination_key: Optional[str] = None
    status: str
    local_path: Optional[str] = None
    message: Optional[str] = None


class UploadMigrationCleanupPreviewItem(BaseModel):
    local_path: str
    relative_path: str
    destination_keys: list[str]
    migrated_urls: list[str]
    reference_count: int
    reference_fields: list[str]
    reason: str


class UploadMigrationBatchPreviewResponse(BaseModel):
    source_type_filter: Optional[str] = None
    batch_offset: int
    batch_limit: int
    matching_total: int
    candidate_total: int
    planned_total: int
    missing_local_file_total: int
    skipped_total: int
    error_total: int
    has_more: bool
    next_offset: Optional[int] = None
    source_totals: dict[str, int]
    cloud_storage_configured: bool
    cleanup_candidate_total: int
    apply_command: str
    next_apply_command: Optional[str] = None
    cleanup_candidates: list[UploadMigrationCleanupPreviewItem]
    items: list[UploadMigrationBatchPreviewItem]
    generated_at: datetime
    source: str = "database"


class ConversionMetricDelta(BaseModel):
    visitors: Optional[float] = None
    signups: Optional[float] = None
    trials: Optional[float] = None
    paid: Optional[float] = None
    revenue_collected: Optional[float] = None


class ConversionMetricsSnapshot(BaseModel):
    visitors: int
    signups: int
    trials: int
    paid: int
    revenue_collected: float
    current_mrr: float
    visitor_to_signup: float
    signup_to_trial: float
    trial_to_paid: float
    overall_conversion: float
    churn_rate: float
    avg_trial_length_days: float
    top_drop_off_point: str
    payment_recovery_accounts: int
    canceled_subscriptions: int
    changes: ConversionMetricDelta


class ConversionFunnelStep(BaseModel):
    name: str
    count: int
    rate: float
    drop_off: float


class ConversionDropOffReason(BaseModel):
    reason: str
    count: int
    percentage: float


class ConversionInsight(BaseModel):
    id: str
    severity: str
    title: str
    description: str


class ConversionAnalyticsResponse(BaseModel):
    start_date: date
    end_date: date
    period_days: int
    metrics: ConversionMetricsSnapshot
    funnel: list[ConversionFunnelStep]
    drop_off_reasons: list[ConversionDropOffReason]
    insights: list[ConversionInsight]
    notes: list[str]
    generated_at: datetime
    source: str = "database"


PLAN_MONTHLY_CREDITS = {
    PlanType.FREE: 0,
    PlanType.MAPS_STARTER: 100,
    PlanType.CALLS_GROWTH: 300,
    PlanType.COMPETITIVE_MARKET: 1000,
    PlanType.STARTER: 100,
    PlanType.PRO: 300,
    PlanType.PREMIUM: 500,
    PlanType.AGENCY: 1000,
    PlanType.ENTERPRISE: 1000,
}

def _require_admin(account: Account) -> None:
    if account.role != AccountRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def _subscription(db: Session, account: Account) -> Subscription | None:
    return (
        db.query(Subscription)
        .filter(Subscription.account_id == account.id)
        .first()
    )


def _plan_type(db: Session, account: Account) -> PlanType:
    subscription = _subscription(db, account)
    if subscription and subscription.plan_type:
        return subscription.plan_type
    return PlanType.FREE


def _plan_name(db: Session, account: Account) -> str:
    return _plan_type(db, account).value


def _monthly_credits(db: Session, account: Account) -> int:
    return PLAN_MONTHLY_CREDITS.get(_plan_type(db, account), 0)


def _credit_balance(db: Session, account: Account) -> CreditBalance | None:
    return (
        db.query(CreditBalance)
        .filter(CreditBalance.account_id == account.id)
        .first()
    )


def _display_credits(db: Session, account: Account) -> int:
    balance = _credit_balance(db, account)
    if balance is not None:
        return balance.total_available
    return _monthly_credits(db, account)


def _plan_config(plan_type: PlanType) -> PlanConfig:
    credit_tier = SUBSCRIPTION_PLAN_TO_CREDITS_TIER.get(
        plan_type,
        SUBSCRIPTION_PLAN_TO_CREDITS_TIER[PlanType.FREE],
    )
    credit_config = PLAN_CREDITS[credit_tier]
    return PlanConfig(
        name=plan_type.value.title(),
        monthly_credits=int(credit_config.get("monthly_credits", 0)),
        sms_daily=int(credit_config.get("sms_daily", 0)),
        sms_monthly=int(credit_config.get("sms_monthly", 0)),
        ai_content_daily=int(credit_config.get("ai_content_daily", 0)),
        ai_content_monthly=int(credit_config.get("ai_content_monthly", 0)),
        ai_image_daily=int(credit_config.get("ai_image_daily", 0)),
        ai_image_monthly=int(credit_config.get("ai_image_monthly", 0)),
        price_monthly=int(PLAN_PRICES.get(plan_type, 0)),
    )


def _user_status(db: Session, account: Account) -> str:
    if not account.is_active:
        return "suspended"
    subscription = _subscription(db, account)
    if subscription and subscription.status:
        return subscription.status.value
    return "active"


def _subscription_limits(db: Session, account: Account) -> Optional[dict]:
    subscription = _subscription(db, account)
    credits_service = CreditsService(db)
    usage_limit_config = credits_service.get_account_usage_limit_config(str(account.id))

    payload = {
        "plan_type": usage_limit_config["plan"],
        "usage_overrides": usage_limit_config["usage_overrides"],
        "effective_usage_limits": usage_limit_config["effective_usage_limits"],
    }
    if not subscription:
        payload["status"] = "active"
        return payload

    plan_limits = get_plan_limits(subscription.plan_type)
    payload.update(
        {
            "status": subscription.status.value,
            "locations_limit": subscription.locations_limit,
            "posts_per_month": subscription.posts_per_month,
            "api_calls_per_day": plan_limits["api_calls_per_day"],
            "agency_location_count": subscription.agency_location_count,
            "active_addons": subscription.active_addons or [],
        }
    )
    return payload


def _usage_summary(db: Session, account: Account) -> dict:
    return CreditsService(db).get_account_status(str(account.id))["usage"]


def _normalize_admin_plan(plan_value: str) -> PlanType:
    normalized = plan_value.strip().lower()
    aliases = {
        "maps": PlanType.MAPS_STARTER,
        "maps_starter": PlanType.MAPS_STARTER,
        "calls": PlanType.CALLS_GROWTH,
        "calls_growth": PlanType.CALLS_GROWTH,
        "competitive": PlanType.COMPETITIVE_MARKET,
        "competitive_market": PlanType.COMPETITIVE_MARKET,
        "professional": PlanType.PRO,
        "pro": PlanType.PRO,
    }
    if normalized in aliases:
        return aliases[normalized]
    try:
        return PlanType(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported plan. Use one of: free, maps_starter, calls_growth, competitive_market, starter, pro, premium, agency.",
        ) from exc


def _require_existing_user(db: Session, user_id: str) -> Account:
    user = db.query(Account).filter(Account.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _grant_admin_credits(
    db: Session,
    *,
    target_account: Account,
    admin_account: Account,
    amount: int,
    reason: str,
    is_bonus: bool,
) -> dict:
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credit amount must be greater than zero.",
        )

    clean_reason = reason.strip()
    if not clean_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grant reason is required.",
        )

    balance = _credit_balance(db, target_account)
    if balance is None:
        balance = CreditBalance(account_id=target_account.id)
        db.add(balance)
        db.flush()

    if is_bonus:
        balance.bonus_balance += amount
    else:
        balance.balance += amount
    balance.total_credits_received += amount

    transaction = CreditTransactionModel(
        account_id=target_account.id,
        type=CreditTransactionType.ADMIN_GRANT,
        amount=amount,
        balance_after=balance.total_available,
        description=clean_reason,
        reference_type="admin_grant",
        reference_id=str(admin_account.id),
        admin_id=admin_account.id,
    )
    db.add(transaction)
    db.commit()
    db.refresh(balance)
    db.refresh(transaction)

    return {
        "success": True,
        "user_id": str(target_account.id),
        "user_email": target_account.email,
        "amount": amount,
        "reason": clean_reason,
        "is_bonus": is_bonus,
        "balance": balance.balance,
        "bonus_balance": balance.bonus_balance,
        "total_available": balance.total_available,
        "transaction_id": str(transaction.id),
        "created_at": transaction.created_at,
    }


def _set_account_active_state(
    db: Session,
    *,
    target_account: Account,
    admin_account: Account,
    is_active: bool,
) -> AdminAccountLifecycleResponse:
    previous_status = _user_status(db, target_account)
    previous_is_active = bool(target_account.is_active)
    operator_action = "account_reactivated" if is_active else "account_suspended"

    if target_account.id == admin_account.id and not is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot suspend their own account.",
        )

    if previous_is_active == is_active:
        return AdminAccountLifecycleResponse(
            account_id=str(target_account.id),
            email=target_account.email,
            is_active=bool(target_account.is_active),
            status=_user_status(db, target_account),
            changed=False,
            operator_action=operator_action,
            updated_at=target_account.updated_at,
        )

    target_account.is_active = is_active
    db.add(target_account)
    db.commit()
    db.refresh(target_account)

    current_status = _user_status(db, target_account)
    _log_operator_recovery_action(
        db=db,
        operator=admin_account,
        target_account_id=target_account.id,
        action=BillingAuditAction.SUBSCRIPTION_UPDATED,
        entity_type="account",
        entity_id=str(target_account.id),
        description=(
            "Admin reactivated account access."
            if is_active
            else "Admin suspended account access."
        ),
        old_value={
            "is_active": previous_is_active,
            "status": previous_status,
        },
        new_value={
            "is_active": bool(target_account.is_active),
            "status": current_status,
        },
        extra_data={
            "operator_action": operator_action,
            "operator_id": str(admin_account.id),
            "previous_is_active": previous_is_active,
            "current_is_active": bool(target_account.is_active),
            "previous_status": previous_status,
            "current_status": current_status,
        },
    )

    return AdminAccountLifecycleResponse(
        account_id=str(target_account.id),
        email=target_account.email,
        is_active=bool(target_account.is_active),
        status=current_status,
        changed=True,
        operator_action=operator_action,
        updated_at=target_account.updated_at,
    )


async def _set_account_plan(
    db: Session,
    *,
    target_account: Account,
    admin_account: Account,
    requested_plan: str,
) -> AdminPlanChangeResponse:
    new_plan_type = _normalize_admin_plan(requested_plan)
    subscription = _subscription(db, target_account)

    if subscription is None:
        free_plan_limits = get_plan_limits(PlanType.FREE)
        subscription = Subscription(
            account_id=target_account.id,
            plan_type=PlanType.FREE,
            status=SubscriptionStatus.ACTIVE,
            access_state="active",
            locations_limit=free_plan_limits["locations"],
            posts_per_month=free_plan_limits["posts_per_month"],
            api_calls_per_day=free_plan_limits["api_calls_per_day"],
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

    previous_plan = subscription.plan_type.value
    if subscription.plan_type == new_plan_type:
        return AdminPlanChangeResponse(
            account_id=str(target_account.id),
            email=target_account.email,
            previous_plan=previous_plan,
            current_plan=subscription.plan_type.value,
            status=_user_status(db, target_account),
            stripe_synced=bool(subscription.stripe_subscription_id),
            stripe_subscription_id=subscription.stripe_subscription_id,
            updated_at=subscription.updated_at,
        )

    if subscription.stripe_subscription_id:
        if new_plan_type == PlanType.FREE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use the subscription cancellation flow before moving a Stripe-backed account to free.",
            )
        if not _stripe_key_is_configured(settings.stripe_secret_key):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe-backed plan changes require STRIPE_SECRET_KEY to be configured.",
            )

        try:
            await BillingService(db).change_subscription(
                account_id=target_account.id,
                new_plan_type=new_plan_type,
                new_addons=list(subscription.active_addons or []),
                prorate=False,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        db.refresh(subscription)
        stripe_synced = True
    else:
        plan_limits = get_plan_limits(new_plan_type)
        subscription.plan_type = new_plan_type
        subscription.locations_limit = plan_limits["locations"]
        subscription.posts_per_month = plan_limits["posts_per_month"]
        subscription.api_calls_per_day = plan_limits["api_calls_per_day"]
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        stripe_synced = False

    _log_operator_recovery_action(
        db=db,
        operator=admin_account,
        target_account_id=target_account.id,
        action=BillingAuditAction.PLAN_CHANGED,
        entity_type="subscription",
        entity_id=str(subscription.id),
        description=(
            "Admin changed subscription plan with Stripe sync."
            if stripe_synced
            else "Admin changed local subscription plan snapshot."
        ),
        old_value={
            "plan_type": previous_plan,
            "stripe_subscription_id": subscription.stripe_subscription_id,
        },
        new_value={
            "plan_type": subscription.plan_type.value,
            "locations_limit": subscription.locations_limit,
            "posts_per_month": subscription.posts_per_month,
            "api_calls_per_day": subscription.api_calls_per_day,
        },
        extra_data={
            "operator_action": "admin_plan_changed",
            "operator_id": str(admin_account.id),
            "stripe_synced": stripe_synced,
            "stripe_subscription_id": subscription.stripe_subscription_id,
        },
    )

    return AdminPlanChangeResponse(
        account_id=str(target_account.id),
        email=target_account.email,
        previous_plan=previous_plan,
        current_plan=subscription.plan_type.value,
        status=_user_status(db, target_account),
        stripe_synced=stripe_synced,
        stripe_subscription_id=subscription.stripe_subscription_id,
        updated_at=subscription.updated_at,
    )


def _set_account_usage_limit_overrides(
    db: Session,
    *,
    target_account: Account,
    admin_account: Account,
    overrides: dict[str, Optional[int]],
) -> AdminUsageLimitOverrideResponse:
    service = CreditsService(db)
    previous_snapshot = service.get_account_usage_limit_config(str(target_account.id))
    try:
        result = service.update_account_usage_limit_overrides(str(target_account.id), overrides)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.refresh(target_account)
    _log_operator_recovery_action(
        db=db,
        operator=admin_account,
        target_account_id=target_account.id,
        action=BillingAuditAction.SUBSCRIPTION_UPDATED,
        entity_type="account",
        entity_id=str(target_account.id),
        description="Admin updated account-specific usage limit overrides.",
        old_value={
            "usage_overrides": previous_snapshot["usage_overrides"],
            "effective_usage_limits": previous_snapshot["effective_usage_limits"],
        },
        new_value={
            "usage_overrides": result["usage_overrides"],
            "effective_usage_limits": result["effective_usage_limits"],
        },
        extra_data={
            "operator_action": "usage_limit_overrides_updated",
            "operator_id": str(admin_account.id),
            "plan": result["plan"],
        },
    )

    return AdminUsageLimitOverrideResponse(
        account_id=str(target_account.id),
        email=target_account.email,
        plan=result["plan"],
        usage_overrides=result["usage_overrides"],
        effective_usage_limits=result["effective_usage_limits"],
        updated_at=target_account.updated_at,
    )


def _distribute_due_monthly_credits(
    db: Session,
    *,
    admin_account: Account,
) -> MonthlyCreditDistributionResponse:
    now = datetime.now(timezone.utc)
    credits_service = CreditsService(db)
    subscriptions = (
        db.query(Subscription)
        .options(joinedload(Subscription.account))
        .filter(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]))
        .order_by(Subscription.created_at.asc())
        .all()
    )

    distributed_accounts: list[MonthlyCreditDistributionAccountResult] = []
    skipped_accounts: list[MonthlyCreditDistributionAccountResult] = []

    for subscription in subscriptions:
        owner = subscription.account or db.query(Account).filter(Account.id == subscription.account_id).first()
        if owner is None:
            continue

        try:
            subscription_plan = (
                subscription.plan_type
                if isinstance(subscription.plan_type, PlanType)
                else PlanType(str(subscription.plan_type).lower())
            )
        except ValueError:
            subscription_plan = PlanType.FREE

        plan_tier = SUBSCRIPTION_PLAN_TO_CREDITS_TIER.get(subscription_plan)
        monthly_credits = int(PLAN_CREDITS.get(plan_tier, {}).get("monthly_credits", 0)) if plan_tier else 0
        balance = _credit_balance(db, owner)
        current_balance = balance.total_available if balance else 0
        next_allocation_date = balance.next_allocation_date if balance else None
        if next_allocation_date and next_allocation_date.tzinfo is None:
            next_allocation_date = next_allocation_date.replace(tzinfo=timezone.utc)

        if not owner.is_active:
            skipped_accounts.append(
                MonthlyCreditDistributionAccountResult(
                    account_id=str(owner.id),
                    email=owner.email,
                    plan=subscription_plan.value,
                    new_balance=current_balance,
                    reason="account_inactive",
                    next_allocation_date=next_allocation_date,
                )
            )
            continue

        if monthly_credits <= 0:
            skipped_accounts.append(
                MonthlyCreditDistributionAccountResult(
                    account_id=str(owner.id),
                    email=owner.email,
                    plan=subscription_plan.value,
                    new_balance=current_balance,
                    reason="no_monthly_credits",
                    next_allocation_date=next_allocation_date,
                )
            )
            continue

        if next_allocation_date and next_allocation_date > now:
            skipped_accounts.append(
                MonthlyCreditDistributionAccountResult(
                    account_id=str(owner.id),
                    email=owner.email,
                    plan=subscription_plan.value,
                    new_balance=current_balance,
                    reason="not_due",
                    next_allocation_date=next_allocation_date,
                )
            )
            continue

        result = credits_service.process_payment(
            str(owner.id),
            plan_tier,
            payment_date=now,
        )

        updated_balance = _credit_balance(db, owner)
        updated_total = updated_balance.total_available if updated_balance else current_balance
        updated_next_allocation = updated_balance.next_allocation_date if updated_balance else None

        _log_operator_recovery_action(
            db=db,
            operator=admin_account,
            target_account_id=owner.id,
            action=BillingAuditAction.SUBSCRIPTION_UPDATED,
            entity_type="subscription",
            entity_id=str(subscription.id),
            description="Admin triggered monthly credit distribution.",
            old_value={
                "balance": current_balance,
                "next_allocation_date": next_allocation_date.isoformat() if next_allocation_date else None,
            },
            new_value={
                "balance": updated_total,
                "credits_allocated": int(result.get("credits_allocated", 0)),
                "next_allocation_date": (
                    updated_next_allocation.isoformat() if updated_next_allocation else None
                ),
            },
            extra_data={
                "operator_action": "monthly_credits_distributed",
                "operator_id": str(admin_account.id),
                "plan": subscription_plan.value,
                "credits_allocated": int(result.get("credits_allocated", 0)),
            },
        )

        distributed_accounts.append(
            MonthlyCreditDistributionAccountResult(
                account_id=str(owner.id),
                email=owner.email,
                plan=subscription_plan.value,
                credits_allocated=int(result.get("credits_allocated", 0)),
                new_balance=updated_total,
                reason="distributed",
                next_allocation_date=updated_next_allocation,
            )
        )

    return MonthlyCreditDistributionResponse(
        considered=len(subscriptions),
        processed=len(distributed_accounts),
        skipped=len(skipped_accounts),
        distributed_accounts=distributed_accounts,
        skipped_accounts=skipped_accounts,
        generated_at=now,
    )


def _looks_like_local_upload_url(value: str | None) -> bool:
    """Identify URLs that still point at legacy local upload paths."""
    if not value:
        return False

    candidate = value.strip()
    if not candidate:
        return False

    lowered = candidate.lower()
    if lowered.startswith("/uploads/"):
        return True

    parsed = urlparse(candidate)
    if parsed.hostname in {"localhost", "127.0.0.1"} and parsed.path.startswith("/uploads/"):
        return True

    return False


def _upload_migration_recommended_action(source_type: str, field_name: str) -> str:
    """Return a short operator-facing action label for each legacy upload reference."""
    if source_type == "upload_asset":
        return "reupload_asset_to_cloud"
    if source_type == "billing_attachment":
        return "replace_billing_attachment_reference"
    if field_name == "ai_image_url":
        return "regenerate_or_reupload_ai_image"
    return "replace_post_image_reference"


def _upload_migration_priority(recommended_action: str) -> str:
    """Return operator priority for a migration action."""
    if recommended_action == "replace_billing_attachment_reference":
        return "high"
    if recommended_action in {"replace_post_image_reference", "regenerate_or_reupload_ai_image"}:
        return "normal"
    return "monitor"


UPLOAD_MIGRATION_ALLOWED_SOURCE_TYPES = {"upload_asset", "post", "billing_attachment"}


def _normalize_upload_migration_source_type(source_type: Optional[str]) -> Optional[str]:
    if source_type in {None, "", "all"}:
        return None
    if source_type not in UPLOAD_MIGRATION_ALLOWED_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported source_type. Use one of: all, upload_asset, post, billing_attachment.",
        )
    return source_type


def _upload_migration_cleanup_manifest_filename(
    source_type: Optional[str],
    offset: int,
    limit: int,
) -> str:
    source_slug = source_type or "all"
    return f"upload-migration-cleanup-{source_slug}-offset-{offset}-limit-{limit}.json"


def _build_upload_migration_apply_command(
    *,
    source_type: Optional[str],
    offset: int,
    limit: int,
) -> str:
    parts = [
        "python",
        "scripts/migrate_upload_assets.py",
        "--apply",
        "--offset",
        str(offset),
        "--limit",
        str(limit),
        "--cleanup-manifest",
        _upload_migration_cleanup_manifest_filename(source_type, offset, limit),
        "--json",
    ]
    if source_type:
        parts.extend(["--source-type", source_type])
    return " ".join(parts)


def _build_upload_migration_audit(
    db: Session,
    *,
    sample_limit: int,
) -> UploadMigrationAuditResponse:
    """Summarize legacy local-upload references that still need migration work."""
    account_map = {str(item.id): item for item in db.query(Account).all()}
    sample_items: list[UploadMigrationAuditItem] = []
    affected_accounts: set[str] = set()
    batch_counts: dict[str, int] = {}
    batch_account_sets: dict[str, set[str]] = {}
    batch_location_sets: dict[str, set[str]] = {}

    def _append_item(item: UploadMigrationAuditItem) -> None:
        if item.account_id:
            affected_accounts.add(item.account_id)
            batch_account_sets.setdefault(item.recommended_action, set()).add(item.account_id)
        else:
            batch_account_sets.setdefault(item.recommended_action, set())
        if item.location_id:
            batch_location_sets.setdefault(item.recommended_action, set()).add(item.location_id)
        else:
            batch_location_sets.setdefault(item.recommended_action, set())
        batch_counts[item.recommended_action] = batch_counts.get(item.recommended_action, 0) + 1
        if len(sample_items) < sample_limit:
            sample_items.append(item)

    upload_assets = (
        db.query(UploadAsset)
        .order_by(UploadAsset.created_at.desc())
        .all()
    )
    upload_asset_local_total = 0
    for asset in upload_assets:
        if not _looks_like_local_upload_url(asset.url):
            continue
        upload_asset_local_total += 1
        account_id = str(asset.account_id) if asset.account_id else None
        linked_account = account_map.get(account_id) if account_id else None
        _append_item(
            UploadMigrationAuditItem(
                source_type="upload_asset",
                entity_id=str(asset.id),
                field_name="url",
                url=asset.url,
                recommended_action=_upload_migration_recommended_action("upload_asset", "url"),
                storage_key=asset.storage_key,
                account_id=account_id,
                account_email=linked_account.email if linked_account else None,
                created_at=asset.created_at,
            )
        )

    posts = (
        db.query(Post)
        .options(joinedload(Post.location).joinedload(Location.account))
        .filter(or_(Post.image_url.isnot(None), Post.ai_image_url.isnot(None)))
        .order_by(Post.created_at.desc())
        .all()
    )
    legacy_post_image_total = 0
    legacy_post_ai_image_total = 0
    for post in posts:
        location = post.location
        linked_account = location.account if location and location.account else None
        account_id = str(linked_account.id) if linked_account else None
        location_id = str(location.id) if location else None

        if _looks_like_local_upload_url(post.image_url):
            legacy_post_image_total += 1
            _append_item(
                UploadMigrationAuditItem(
                    source_type="post",
                    entity_id=str(post.id),
                    field_name="image_url",
                    url=post.image_url or "",
                    recommended_action=_upload_migration_recommended_action("post", "image_url"),
                    account_id=account_id,
                    account_email=linked_account.email if linked_account else None,
                    location_id=location_id,
                    location_name=location.name if location else None,
                    created_at=post.created_at,
                )
            )

        if _looks_like_local_upload_url(post.ai_image_url):
            legacy_post_ai_image_total += 1
            _append_item(
                UploadMigrationAuditItem(
                    source_type="post",
                    entity_id=str(post.id),
                    field_name="ai_image_url",
                    url=post.ai_image_url or "",
                    recommended_action=_upload_migration_recommended_action("post", "ai_image_url"),
                    account_id=account_id,
                    account_email=linked_account.email if linked_account else None,
                    location_id=location_id,
                    location_name=location.name if location else None,
                    created_at=post.created_at,
                )
            )

    billing_audits = (
        db.query(BillingAuditLog)
        .filter(BillingAuditLog.extra_data.isnot(None))
        .order_by(BillingAuditLog.created_at.desc())
        .all()
    )
    legacy_billing_attachment_total = 0
    for audit in billing_audits:
        payload = audit.extra_data if isinstance(audit.extra_data, dict) else {}
        attachment_urls = payload.get("attachment_urls")
        if not isinstance(attachment_urls, list):
            continue

        account_id = str(audit.account_id) if audit.account_id else None
        linked_account = account_map.get(account_id) if account_id else None
        for url in attachment_urls:
            if not _looks_like_local_upload_url(url):
                continue
            legacy_billing_attachment_total += 1
            _append_item(
                UploadMigrationAuditItem(
                    source_type="billing_attachment",
                    entity_id=str(audit.id),
                    field_name="attachment_urls",
                    url=url,
                    recommended_action=_upload_migration_recommended_action("billing_attachment", "attachment_urls"),
                    account_id=account_id,
                    account_email=linked_account.email if linked_account else None,
                    created_at=audit.created_at,
                )
            )

    actionable_total = (
        upload_asset_local_total
        + legacy_post_image_total
        + legacy_post_ai_image_total
        + legacy_billing_attachment_total
    )
    batch_summaries = [
        UploadMigrationBatchSummary(
            recommended_action=action,
            priority=_upload_migration_priority(action),
            reference_total=count,
            affected_account_total=len(batch_account_sets.get(action, set())),
            affected_location_total=len(batch_location_sets.get(action, set())),
            summary=(
                f"{count} reference(s) across "
                f"{len(batch_account_sets.get(action, set()))} account(s) and "
                f"{len(batch_location_sets.get(action, set()))} location(s)."
            ),
        )
        for action, count in sorted(
            batch_counts.items(),
            key=lambda item: (
                {"high": 0, "normal": 1, "monitor": 2}.get(_upload_migration_priority(item[0]), 3),
                -item[1],
                item[0],
            ),
        )
    ]
    runbook_steps = [
        "Export the CSV manifest and start with high-priority billing attachment references so dispute evidence does not depend on localhost URLs.",
        "Migrate post image references next, because published and approval-facing content should not rely on local upload paths.",
        "After each apply batch, confirm the JSON or cleanup manifest reports verification_failed_total = 0 before approving any file cleanup.",
        "Handle AI image references after post images, then clean up remaining persisted upload assets that no longer back active product flows.",
    ]

    return UploadMigrationAuditResponse(
        upload_asset_total=len(upload_assets),
        upload_asset_local_total=upload_asset_local_total,
        legacy_post_image_total=legacy_post_image_total,
        legacy_post_ai_image_total=legacy_post_ai_image_total,
        legacy_billing_attachment_total=legacy_billing_attachment_total,
        affected_account_total=len(affected_accounts),
        actionable_total=actionable_total,
        cloud_storage_configured=get_storage_service().is_configured(),
        sample_limit=sample_limit,
        batch_summaries=batch_summaries,
        runbook_steps=runbook_steps,
        items=sample_items,
        generated_at=datetime.now(timezone.utc),
    )


def _build_upload_migration_batch_preview(
    db: Session,
    *,
    source_type: Optional[str],
    offset: int,
    limit: int,
) -> UploadMigrationBatchPreviewResponse:
    resolved_source_type = _normalize_upload_migration_source_type(source_type)
    upload_migration_service = UploadMigrationService(
        db,
        upload_root=file_upload_service.upload_dir,
        storage_service=get_storage_service(),
    )
    run_result = upload_migration_service.run(
        apply=False,
        source_types=[resolved_source_type] if resolved_source_type else None,
        offset=offset,
        limit=limit,
    )
    items = [
        UploadMigrationBatchPreviewItem(
            source_type=item.source_type,
            entity_id=item.entity_id,
            field_name=item.field_name,
            original_url=item.original_url,
            destination_key=item.destination_key,
            status=item.status,
            local_path=item.message if item.status == "planned" else None,
            message=None if item.status == "planned" else item.message,
        )
        for item in run_result.results
    ]
    planned_total = sum(1 for item in run_result.results if item.status == "planned")
    missing_local_file_total = sum(
        1 for item in run_result.results if item.status == "missing_local_file"
    )
    skipped_total = sum(1 for item in run_result.results if item.status == "skipped")
    error_total = sum(1 for item in run_result.results if item.status == "error")
    return UploadMigrationBatchPreviewResponse(
        source_type_filter=resolved_source_type,
        batch_offset=run_result.batch_offset,
        batch_limit=limit,
        matching_total=run_result.matching_total,
        candidate_total=run_result.candidate_total,
        planned_total=planned_total,
        missing_local_file_total=missing_local_file_total,
        skipped_total=skipped_total,
        error_total=error_total,
        has_more=run_result.has_more,
        next_offset=run_result.next_offset,
        source_totals=run_result.source_totals,
        cloud_storage_configured=get_storage_service().is_configured(),
        cleanup_candidate_total=run_result.cleanup_candidate_total,
        apply_command=_build_upload_migration_apply_command(
            source_type=resolved_source_type,
            offset=run_result.batch_offset,
            limit=limit,
        ),
        next_apply_command=(
            _build_upload_migration_apply_command(
                source_type=resolved_source_type,
                offset=run_result.next_offset,
                limit=limit,
            )
            if run_result.next_offset is not None
            else None
        ),
        cleanup_candidates=[
            UploadMigrationCleanupPreviewItem(
                local_path=item.local_path,
                relative_path=item.relative_path,
                destination_keys=item.destination_keys,
                migrated_urls=item.migrated_urls,
                reference_count=item.reference_count,
                reference_fields=item.reference_fields,
                reason=item.reason,
            )
            for item in run_result.cleanup_candidates
        ],
        items=items,
        generated_at=datetime.now(timezone.utc),
    )


def _stripe_key_is_configured(raw_key: Optional[str]) -> bool:
    """Treat obvious placeholder values as unconfigured for admin Stripe actions."""
    key = (raw_key or "").strip()
    if not key:
        return False
    lowered = key.lower()
    if key.endswith("..."):
        return False
    if "your_stripe" in lowered or "changeme" in lowered or "placeholder" in lowered:
        return False
    return True


def _serialize_local_dispute(
    dispute: DisputeModel,
    *,
    user_email: str,
    source: str = "local_cache",
) -> DisputeResponse:
    """Convert a persisted dispute row into the admin response shape."""
    return DisputeResponse(
        id=dispute.stripe_dispute_id,
        user_id=str(dispute.account_id),
        user_email=user_email,
        payment_id=dispute.stripe_payment_intent_id or dispute.stripe_charge_id or "",
        amount=round(dispute.amount / 100.0, 2),
        reason=dispute.reason.value if dispute.reason else "unknown",
        status=dispute.status.value,
        evidence=dispute.internal_notes,
        created_at=dispute.created_at,
        evidence_due_by=dispute.evidence_due_by,
        source=source,
    )


def _compose_dispute_evidence(request: DisputeEvidenceRequest) -> str:
    sections = [request.evidence.strip()]

    checklist = [item.strip() for item in request.proof_checklist if item and item.strip()]
    if checklist:
        sections.extend(["", "Proof checklist:", *[f"- {item}" for item in checklist]])

    attachment_names = [name.strip() for name in request.attachment_names if name and name.strip()]
    attachment_urls = [url.strip() for url in request.attachment_urls if url and url.strip()]
    attachment_note = (request.attachment_note or "").strip()
    if attachment_names or attachment_urls or attachment_note:
        sections.append("")
        sections.append("Attachment references:")
        attachment_count = max(len(attachment_names), len(attachment_urls))
        for idx in range(attachment_count):
            name = attachment_names[idx] if idx < len(attachment_names) else f"Attachment {idx + 1}"
            url = attachment_urls[idx] if idx < len(attachment_urls) else ""
            sections.append(f"- {name}: {url}" if url else f"- {name}")
        if attachment_note:
            sections.append(f"- Notes: {attachment_note}")

    return "\n".join(sections).strip()


def _account_for_payment_intent(
    db: Session,
    payment_intent_id: Optional[str],
) -> tuple[Optional[UUID], Optional[str]]:
    if not payment_intent_id or not isinstance(payment_intent_id, str):
        return None, None

    order = (
        db.query(CreditPurchaseOrder)
        .options(joinedload(CreditPurchaseOrder.account))
        .filter(CreditPurchaseOrder.stripe_payment_intent_id == payment_intent_id)
        .first()
    )
    if not order:
        return None, None

    email = order.account.email if order.account else None
    return order.account_id, email


def _log_operator_recovery_action(
    db: Session,
    operator: Account,
    target_account_id: Optional[UUID],
    action: BillingAuditAction,
    entity_type: str,
    entity_id: str,
    description: str,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
    extra_data: Optional[dict] = None,
) -> None:
    audit = BillingAuditLog(
        account_id=target_account_id,
        user_id=operator.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        description=description,
        extra_data=extra_data,
    )
    db.add(audit)
    db.commit()


def _display_name(account: Account | None) -> str:
    if not account:
        return "the customer"
    return account.company_name or account.full_name or account.email


def _format_datetime_for_ops(value: Optional[datetime]) -> str:
    if value is None:
        return "Not recorded"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_label(value: Optional[str]) -> str:
    if not value:
        return "not recorded"
    return value.replace("_", " ")


def _build_dunning_action_plan(
    owner: Account | None,
    subscription: Subscription,
) -> RecoveryActionPlan:
    display_name = _display_name(owner)
    next_retry = _format_datetime_for_ops(subscription.next_payment_retry_at)
    current_period_end = _format_datetime_for_ops(subscription.current_period_end)
    last_error = subscription.last_payment_error or "No payment processor error was stored."

    if subscription.dunning_status in {DunningStatus.RETRYING, DunningStatus.GRACE_PERIOD}:
        headline = "Request a billing update before the next retry window."
    else:
        headline = "Resolve the billing restriction before access stays limited."

    operator_note = "\n".join(
        [
            f"Account: {display_name} ({owner.email if owner else 'email not recorded'})",
            f"Plan: {subscription.plan_type.value}",
            (
                "Billing state: "
                f"{subscription.access_state} / {subscription.dunning_status.value}"
            ),
            f"Retry count: {subscription.payment_retry_count}",
            f"Next retry: {next_retry}",
            f"Current period end: {current_period_end}",
            f"Last payment error: {last_error}",
            "Recommended next step: ask the customer to update the billing method, then confirm access_state returns to active after payment succeeds.",
        ]
    )

    customer_message = "\n".join(
        [
            f"Hi {display_name},",
            "",
            (
                f"We could not complete the latest subscription payment for your {subscription.plan_type.value} plan. "
                f"Your account is currently in {subscription.access_state} status."
            ),
            (
                f"Please update the billing method before {next_retry} so the next retry has the best chance to succeed."
                if subscription.next_payment_retry_at
                else "Please update the billing method as soon as possible so we can retry the payment safely."
            ),
            "Reply to this message if you want us to confirm the billing update after it is submitted.",
        ]
    )

    return RecoveryActionPlan(
        headline=headline,
        operator_note=operator_note,
        customer_message=customer_message,
    )


def _build_dunning_recovery_link_action_plan(
    owner: Account | None,
    subscription: Subscription,
    portal_info: dict[str, object],
) -> RecoveryActionPlan:
    base_plan = _build_dunning_action_plan(owner, subscription)
    portal_url = str(portal_info.get("portal_url") or "")
    portal_source = str(portal_info.get("portal_source") or "not_recorded")
    portal_error = portal_info.get("portal_error")
    portal_available = bool(portal_info.get("portal_available"))

    portal_status = (
        "Direct Stripe customer portal is available for billing recovery."
        if portal_available
        else (
            "Using the in-app billing page fallback because a direct Stripe portal link "
            f"is unavailable ({portal_error or 'no extra detail recorded'})."
        )
    )

    operator_note = "\n".join(
        [
            base_plan.operator_note,
            f"Recovery link: {portal_url or 'not recorded'}",
            f"Portal source: {portal_source}",
            f"Portal status: {portal_status}",
        ]
    )

    customer_lines = [base_plan.customer_message]
    if portal_url:
        customer_lines.extend(["", f"Billing update link: {portal_url}"])
    if not portal_available:
        customer_lines.extend(
            [
                "",
                "If the page does not show the payment update prompt right away, reply here and our team will help manually.",
            ]
        )

    return RecoveryActionPlan(
        headline="Open the live billing recovery destination and send the updated customer note.",
        operator_note=operator_note,
        customer_message="\n".join(customer_lines),
    )


def _build_dispute_action_plan(
    owner: Account | None,
    dispute: DisputeModel,
) -> RecoveryActionPlan:
    display_name = _display_name(owner)
    reason = _format_label(dispute.reason.value if dispute.reason else None)
    evidence_due = _format_datetime_for_ops(dispute.evidence_due_by)
    urgent_statuses = {
        DisputeStatus.NEEDS_RESPONSE,
        DisputeStatus.WARNING_NEEDS_RESPONSE,
    }

    if dispute.status in urgent_statuses:
        headline = "Prepare a Stripe evidence response now."
    else:
        headline = "Review the dispute status and confirm the next operator decision."

    operator_note = "\n".join(
        [
            f"Customer: {display_name} ({owner.email if owner else 'email not recorded'})",
            f"Dispute: {dispute.stripe_dispute_id}",
            f"Status: {dispute.status.value}",
            f"Reason: {reason}",
            f"Amount: ${round(dispute.amount / 100.0, 2):.2f}",
            f"Evidence due: {evidence_due}",
            (
                "Recommended next step: respond only when purchase authorization, delivery, and follow-up records can be proven. "
                "If proof is weak, accept the dispute intentionally and close the support loop."
            ),
        ]
    )

    if dispute.status in urgent_statuses:
        customer_message = "\n".join(
            [
                f"Hi {display_name},",
                "",
                (
                    f"We received a payment dispute from your bank for ${round(dispute.amount / 100.0, 2):.2f}. "
                    "Our team is reviewing the purchase timeline and any support history before responding."
                ),
                "If you already resolved this with our team, reply with the latest context so we can keep our records aligned.",
            ]
        )
    else:
        customer_message = "\n".join(
            [
                f"Hi {display_name},",
                "",
                (
                    f"We have already submitted or reviewed the payment dispute for ${round(dispute.amount / 100.0, 2):.2f}. "
                    "We will update you again once the payment processor finishes the current review."
                ),
                "Reply if there is any additional context that should be attached to the support record.",
            ]
        )

    return RecoveryActionPlan(
        headline=headline,
        operator_note=operator_note,
        customer_message=customer_message,
    )


def _build_refund_action_plan(
    owner: Account | None,
    order: CreditPurchaseOrder,
    audit_entry: BillingAuditLog | None = None,
) -> RecoveryActionPlan:
    display_name = _display_name(owner)
    extra_data = audit_entry.extra_data if audit_entry and isinstance(audit_entry.extra_data, dict) else {}
    support_reason = extra_data.get("support_reason") or "Not recorded"
    stripe_refund_id = extra_data.get("stripe_refund_id")
    stripe_error = extra_data.get("stripe_error")
    processed_at = _format_datetime_for_ops(order.refunded_at)
    refund_amount = round(order.price_cents / 100.0, 2)

    if stripe_error:
        headline = "Confirm the manual payment-side refund and close the support loop."
    else:
        headline = "Confirm the refund settlement and send the customer closeout note."

    operator_note = "\n".join(
        [
            f"Customer: {display_name} ({owner.email if owner else 'email not recorded'})",
            f"Refunded order: {order.id}",
            f"Payment reference: {order.stripe_payment_intent_id or 'Not recorded'}",
            f"Refund amount: ${refund_amount:.2f}",
            f"Processed at: {processed_at}",
            f"Support reason: {support_reason}",
            (
                f"Stripe refund reference: {stripe_refund_id}"
                if stripe_refund_id
                else "Stripe refund reference: not recorded"
            ),
            (
                f"Payment follow-up: {stripe_error}"
                if stripe_error
                else "Payment follow-up: Stripe refund completed or no extra payment action was recorded."
            ),
            "Recommended next step: confirm the payment-side refund state, verify the credit clawback, and send the customer a short closure update.",
        ]
    )

    if stripe_error:
        customer_message = "\n".join(
            [
                f"Hi {display_name},",
                "",
                (
                    f"We processed your refund for ${refund_amount:.2f} and removed the related credits from the account. "
                    "The payment-side refund still needs final confirmation, and our team is tracking that manually."
                ),
                "We will send a final confirmation as soon as the card-side posting is fully verified.",
            ]
        )
    else:
        customer_message = "\n".join(
            [
                f"Hi {display_name},",
                "",
                (
                    f"We processed your refund for ${refund_amount:.2f}. "
                    "Any credits tied to that purchase were removed from the account so billing and product state stay aligned."
                ),
                "If you need a written receipt or follow-up confirmation, reply here and our team will send it.",
            ]
        )

    return RecoveryActionPlan(
        headline=headline,
        operator_note=operator_note,
        customer_message=customer_message,
    )


def _operations_summary(details: list[str]) -> str:
    return " ".join(part.strip() for part in details if part and part.strip())


def _severity_rank(severity: str) -> int:
    order = {"critical": 0, "warning": 1, "info": 2}
    return order.get(severity, 3)


def _action_href_for_domain(domain: str, entity_id: Optional[str] = None) -> Optional[str]:
    if domain == "publish" and entity_id:
        return f"/dashboard/content/{entity_id}"
    if domain == "oauth":
        return "/dashboard/integrations"
    if domain == "notifications":
        return "/dashboard/notifications"
    if domain == "worker_ops":
        return "/dashboard/notifications"
    if domain == "review_booster":
        return "/dashboard/reviews"
    return None


OPERATIONAL_NOTIFICATION_SEVERITY: dict[str, str] = {
    "analytics_collection_failed": "warning",
    "analytics_collection_job_failed": "critical",
    "billing_access_restricted": "critical",
    "content_generation_job_failed": "critical",
    "billing_grace_period_started": "warning",
    "daily_snapshot_failed": "warning",
    "daily_snapshot_unavailable": "warning",
    "daily_snapshot_job_failed": "critical",
    "scheduled_content_generation_failed": "warning",
    "seo_score_calculation_failed": "warning",
    "weekly_report_failed": "warning",
    "weekly_report_job_failed": "critical",
    "billing_dunning_job_failed": "critical",
    "billing_lifecycle_email_failed": "warning",
    "billing_payment_failed": "warning",
    "billing_payment_recovered": "info",
    "billing_receipt_email_failed": "warning",
    "billing_payment_retry_job_failed": "warning",
    "billing_payment_retry_worker_failed": "critical",
    "billing_subscription_suspended": "critical",
    "billing_trial_ending_email_failed": "warning",
    "missed_call_text_back_failed": "warning",
    "missed_call_text_back_skipped": "warning",
    "oauth_reauth_required": "warning",
    "oauth_reauth_notification_failed": "warning",
    "oauth_token_refresh_job_failed": "critical",
    "publish_job_failed": "warning",
    "publish_worker_failed": "critical",
    "publish_reauth_required": "warning",
    "review_booster_delivery_failed": "warning",
    "review_booster_job_failed": "critical",
    "review_booster_negative_review": "warning",
    "review_response_publish_failed": "warning",
    "stripe_credit_purchase_apply_failed": "critical",
    "stripe_credit_purchase_close_failed": "warning",
    "stripe_webhook_processing_failed": "critical",
    "stripe_refund_unmatched": "warning",
    "website_publish_failed": "warning",
}


def _operational_notification_severity(event_type: str) -> Optional[str]:
    """Resolve severity for exact and patterned operational notification types."""
    exact = OPERATIONAL_NOTIFICATION_SEVERITY.get(event_type)
    if exact:
        return exact
    if event_type == "usage_warning" or event_type.startswith("usage_warning_"):
        return "warning"
    return None


def _resolve_conversion_window(
    start_date: Optional[date],
    end_date: Optional[date],
) -> tuple[date, date, datetime, datetime, int]:
    today = datetime.now(timezone.utc).date()
    resolved_end = end_date or today
    resolved_start = start_date or (resolved_end - timedelta(days=29))

    if resolved_start > resolved_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be on or before end_date",
        )

    day_count = (resolved_end - resolved_start).days + 1
    if day_count > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range must be 366 days or less",
        )

    start_dt = datetime.combine(resolved_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(resolved_end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return resolved_start, resolved_end, start_dt, end_dt, day_count


def _percentage(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _percentage_change(current: int | float, previous: int | float) -> Optional[float]:
    if previous <= 0:
        return None if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def _plan_monthly_amount(subscription: Subscription) -> float:
    base_price = float(PLAN_PRICES.get(subscription.plan_type, 0))
    if subscription.plan_type == PlanType.AGENCY:
        return round(base_price * max(subscription.agency_location_count or 1, 1), 2)
    return round(base_price, 2)


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _subscription_is_billable_at(subscription: Subscription, snapshot_at: datetime) -> bool:
    if subscription.plan_type == PlanType.FREE:
        return False
    created_at = _normalize_datetime(subscription.created_at)
    ended_at = _normalize_datetime(subscription.ended_at)
    canceled_at = _normalize_datetime(subscription.canceled_at)
    current_period_end = _normalize_datetime(subscription.current_period_end)

    if created_at and created_at > snapshot_at:
        return False
    if ended_at and ended_at <= snapshot_at:
        return False
    if canceled_at and not subscription.cancel_at_period_end and canceled_at <= snapshot_at:
        return False
    if subscription.status in {SubscriptionStatus.INCOMPLETE_EXPIRED, SubscriptionStatus.UNPAID}:
        return False
    if (
        subscription.status == SubscriptionStatus.EXPIRED
        and current_period_end
        and current_period_end <= snapshot_at
    ):
        return False
    return True


def _summarize_conversion_period(
    db: Session,
    start_dt: datetime,
    end_dt: datetime,
    non_admin_account_ids: list[UUID],
) -> dict[str, float | int]:
    visitors = (
        db.query(func.coalesce(func.sum(Analytics.unique_visitors), 0))
        .filter(
            Analytics.unique_visitors.isnot(None),
            Analytics.date >= start_dt.date(),
            Analytics.date < end_dt.date(),
        )
        .scalar()
        or 0
    )

    signups = (
        db.query(func.count(Account.id))
        .filter(
            Account.role != AccountRole.ADMIN,
            Account.created_at >= start_dt,
            Account.created_at < end_dt,
        )
        .scalar()
        or 0
    )

    subscription_rows = (
        db.query(Subscription)
        .filter(Subscription.account_id.in_(non_admin_account_ids))
        .all()
        if non_admin_account_ids
        else []
    )
    trials = sum(
        1
        for subscription in subscription_rows
        if (
            subscription.plan_type != PlanType.FREE
            and (trial_start := _normalize_datetime(subscription.trial_start)) is not None
            and start_dt <= trial_start < end_dt
        )
    )

    paid = (
        db.query(func.count(func.distinct(Payment.account_id)))
        .filter(
            Payment.status == PaymentStatus.SUCCEEDED,
            Payment.created_at >= start_dt,
            Payment.created_at < end_dt,
            or_(Payment.invoice_id.isnot(None), Payment.stripe_invoice_id.isnot(None)),
            Payment.account_id.in_(non_admin_account_ids) if non_admin_account_ids else False,
        )
        .scalar()
        or 0
    )

    revenue_cents = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(
            Payment.status == PaymentStatus.SUCCEEDED,
            Payment.created_at >= start_dt,
            Payment.created_at < end_dt,
            or_(Payment.invoice_id.isnot(None), Payment.stripe_invoice_id.isnot(None)),
            Payment.account_id.in_(non_admin_account_ids) if non_admin_account_ids else False,
        )
        .scalar()
        or 0
    )

    return {
        "visitors": int(visitors),
        "signups": int(signups),
        "trials": int(trials),
        "paid": int(paid),
        "revenue_collected": round(float(revenue_cents) / 100.0, 2),
    }


def _build_conversion_funnel(metrics: dict[str, float | int]) -> list[ConversionFunnelStep]:
    raw_steps = [
        ("Website visitors", int(metrics["visitors"])),
        ("New signups", int(metrics["signups"])),
        ("Trial starts", int(metrics["trials"])),
        ("Paid accounts", int(metrics["paid"])),
    ]

    base = raw_steps[0][1]
    previous_count: Optional[int] = None
    steps: list[ConversionFunnelStep] = []
    for name, count in raw_steps:
        drop_off = _percentage(max((previous_count or 0) - count, 0), previous_count or 0) if previous_count is not None else 0.0
        steps.append(
            ConversionFunnelStep(
                name=name,
                count=count,
                rate=_percentage(count, base) if base > 0 else 0.0,
                drop_off=drop_off,
            )
        )
        previous_count = count
    return steps


def _top_drop_off_point(funnel: list[ConversionFunnelStep]) -> str:
    largest_name = "No material drop-off recorded"
    largest_delta = 0
    for index in range(1, len(funnel)):
        previous_step = funnel[index - 1]
        step = funnel[index]
        delta = max(previous_step.count - step.count, 0)
        if delta > largest_delta:
            largest_delta = delta
            largest_name = f"{previous_step.name} -> {step.name}"
    return largest_name


def _build_drop_off_reasons(
    funnel: list[ConversionFunnelStep],
    canceled_subscriptions: int,
    payment_recovery_accounts: int,
) -> list[ConversionDropOffReason]:
    reason_candidates: list[tuple[str, int]] = []

    for index in range(1, len(funnel)):
        previous_step = funnel[index - 1]
        step = funnel[index]
        lost_accounts = max(previous_step.count - step.count, 0)
        if lost_accounts <= 0:
            continue
        reason_candidates.append(
            (
                f"{previous_step.name} are not consistently reaching {step.name.lower()}",
                lost_accounts,
            )
        )

    if canceled_subscriptions > 0:
        reason_candidates.append(
            ("Paid accounts canceled in the selected range", canceled_subscriptions)
        )
    if payment_recovery_accounts > 0:
        reason_candidates.append(
            ("Accounts are in dunning or payment recovery right now", payment_recovery_accounts)
        )

    if not reason_candidates:
        return [
            ConversionDropOffReason(
                reason="No major drop-off signal was recorded in the selected range",
                count=0,
                percentage=0.0,
            )
        ]

    total = sum(count for _, count in reason_candidates) or 1
    return [
        ConversionDropOffReason(
            reason=reason,
            count=count,
            percentage=round((count / total) * 100, 1),
        )
        for reason, count in sorted(reason_candidates, key=lambda item: item[1], reverse=True)[:4]
    ]


def _build_conversion_insights(
    metrics: ConversionMetricsSnapshot,
    notes: list[str],
) -> list[ConversionInsight]:
    insights: list[ConversionInsight] = []

    if metrics.visitors == 0:
        insights.append(
            ConversionInsight(
                id="missing-visitor-analytics",
                severity="warning",
                title="Website visitor analytics are missing for this range.",
                description="Connected website analytics snapshots did not report unique visitors, so top-of-funnel conversion rates will stay near zero until those feeds are populated.",
            )
        )
    if metrics.trials > 0 and metrics.trial_to_paid < 25:
        insights.append(
            ConversionInsight(
                id="trial-to-paid-low",
                severity="critical",
                title="Trial to paid conversion is below the target band.",
                description="This range has active trial volume, but too few accounts reached invoice-backed payment. Review onboarding and billing prompts before scaling traffic.",
            )
        )
    if metrics.signup_to_trial < 40 and metrics.signups > 0:
        insights.append(
            ConversionInsight(
                id="signup-to-trial-gap",
                severity="warning",
                title="New signups are not consistently activating a trial.",
                description="Signup completion is outpacing trial starts. Check onboarding, product activation steps, and trial CTA placement.",
            )
        )
    if metrics.payment_recovery_accounts > 0:
        insights.append(
            ConversionInsight(
                id="payment-recovery-active",
                severity="warning",
                title="Some accounts are still in payment recovery.",
                description=f"{metrics.payment_recovery_accounts} account(s) are in dunning or warning access state and may churn without operator follow-up.",
            )
        )
    if metrics.visitor_to_signup >= 8:
        insights.append(
            ConversionInsight(
                id="healthy-visitor-to-signup",
                severity="info",
                title="Visitor to signup conversion is holding above the healthy baseline.",
                description="Top-of-funnel conversion is keeping pace with the 8-12% target range, so the biggest leverage is likely deeper in onboarding or billing.",
            )
        )

    if not insights:
        insights.append(
            ConversionInsight(
                id="stable-range",
                severity="info",
                title="No major conversion alert fired for this range.",
                description="The selected window does not show a single standout failure mode, so use the funnel and notes below to inspect where to tighten instrumentation next.",
            )
        )

    if metrics.visitors == 0 and not any("Website visitors" in note for note in notes):
        notes.append("Website visitor snapshots are empty for this date range.")

    return insights[:4]


@router.post("/disputes/attachments", response_model=DisputeAttachmentUploadResponse)
async def upload_dispute_attachment(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Upload a dispute evidence attachment to cloud storage.

    This path intentionally requires cloud storage. It does not fall back to
    local uploads because dispute evidence should be accessible through a
    stable public link policy suitable for operator workflows.
    """
    _require_admin(account)
    file_upload_service.validate_document(file)

    try:
        content = await file.read()
        storage = get_storage_service()
        url = storage.upload_file(
            file_data=content,
            filename=file.filename or "dispute-attachment",
            content_type=file.content_type or "application/octet-stream",
            folder=f"disputes/{account.id}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Cloud storage is unavailable for dispute attachments. "
                f"Configure GCS before uploading evidence files. ({exc})"
            ),
        )

    return DisputeAttachmentUploadResponse(
        filename=file.filename or "dispute-attachment",
        url=url,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    plan: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """List users from the real account database."""
    _require_admin(account)

    accounts = (
        db.query(Account)
        .options(joinedload(Account.subscription))
        .order_by(Account.created_at.desc())
        .all()
    )

    if search:
        search_lower = search.lower()
        accounts = [
            item
            for item in accounts
            if search_lower in item.email.lower()
            or (item.full_name and search_lower in item.full_name.lower())
            or (item.company_name and search_lower in item.company_name.lower())
        ]

    if plan:
        accounts = [item for item in accounts if _plan_name(db, item) == plan]

    if status_filter:
        accounts = [item for item in accounts if _user_status(db, item) == status_filter]

    total = len(accounts)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = accounts[start:end]

    return UserListResponse(
        users=[
            UserSummary(
                id=str(item.id),
                email=item.email,
                full_name=item.full_name,
                plan=_plan_name(db, item),
                credits=_display_credits(db, item),
                status=_user_status(db, item),
                created_at=item.created_at,
                last_login=item.last_login_at,
                custom_limits=_subscription_limits(db, item),
            )
            for item in paginated
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get detailed user information from the real account database."""
    _require_admin(account)

    user = (
        db.query(Account)
        .options(joinedload(Account.subscription))
        .filter(Account.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    balance = _credit_balance(db, user)
    return UserDetail(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        plan=_plan_name(db, user),
        credits=_display_credits(db, user),
        bonus_credits=(balance.bonus_balance if balance else 0),
        status=_user_status(db, user),
        created_at=user.created_at,
        last_login=user.last_login_at,
        usage=_usage_summary(db, user),
        custom_limits=_subscription_limits(db, user),
    )


@router.post("/users/{user_id}/credits")
async def update_user_credits(
    user_id: str,
    request: UpdateUserCreditsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    _require_admin(account)
    user = _require_existing_user(db, user_id)
    return _grant_admin_credits(
        db,
        target_account=user,
        admin_account=account,
        amount=request.credits,
        reason=request.reason,
        is_bonus=True,
    )


@router.post("/users/{user_id}/plan", response_model=AdminPlanChangeResponse)
async def update_user_plan(
    user_id: str,
    request: UpdateUserPlanRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    _require_admin(account)
    user = _require_existing_user(db, user_id)
    return await _set_account_plan(
        db,
        target_account=user,
        admin_account=account,
        requested_plan=request.plan,
    )


@router.post("/users/{user_id}/limits", response_model=AdminUsageLimitOverrideResponse)
async def update_user_limits(
    user_id: str,
    request: UpdateUserLimitsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    _require_admin(account)
    user = _require_existing_user(db, user_id)
    return _set_account_usage_limit_overrides(
        db,
        target_account=user,
        admin_account=account,
        overrides=request.model_dump(exclude_unset=True),
    )


@router.post("/users/{user_id}/suspend", response_model=AdminAccountLifecycleResponse)
async def suspend_user(
    user_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    _require_admin(account)
    user = _require_existing_user(db, user_id)
    return _set_account_active_state(
        db,
        target_account=user,
        admin_account=account,
        is_active=False,
    )


@router.post("/users/{user_id}/activate", response_model=AdminAccountLifecycleResponse)
async def activate_user(
    user_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    _require_admin(account)
    user = _require_existing_user(db, user_id)
    return _set_account_active_state(
        db,
        target_account=user,
        admin_account=account,
        is_active=True,
    )


@router.post("/credits/grant")
async def grant_credits(
    request: GrantCreditsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    _require_admin(account)
    user = _require_existing_user(db, request.user_id)
    return _grant_admin_credits(
        db,
        target_account=user,
        admin_account=account,
        amount=request.amount,
        reason=request.reason,
        is_bonus=request.is_bonus,
    )


@router.post("/credits/bulk-grant")
async def bulk_grant_credits(
    request: BulkGrantCreditsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    _require_admin(account)
    results = []
    for user_id in request.user_ids:
        user = _require_existing_user(db, user_id)
        results.append(
            _grant_admin_credits(
                db,
                target_account=user,
                admin_account=account,
                amount=request.amount,
                reason=request.reason,
                is_bonus=request.is_bonus,
            )
        )
    return {
        "success": True,
        "processed": len(results),
        "results": results,
    }


@router.get("/credits/transactions")
async def get_credit_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    _require_admin(account)
    query = db.query(CreditTransactionModel).join(
        Account, Account.id == CreditTransactionModel.account_id
    )
    if user_id:
        query = query.filter(CreditTransactionModel.account_id == user_id)
    if type:
        try:
            transaction_type = CreditTransactionType(type)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid credit transaction type: {type}",
            ) from exc
        query = query.filter(CreditTransactionModel.type == transaction_type)

    total = query.count()
    transactions = (
        query.order_by(CreditTransactionModel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    account_ids = {transaction.account_id for transaction in transactions}
    account_map = {
        item.id: item
        for item in db.query(Account).filter(Account.id.in_(account_ids)).all()
    } if account_ids else {}

    return {
        "transactions": [
            CreditTransaction(
                id=str(transaction.id),
                user_id=str(transaction.account_id),
                user_email=account_map.get(transaction.account_id).email if account_map.get(transaction.account_id) else "",
                type=transaction.type.value,
                amount=transaction.amount,
                reason=transaction.description or "",
                admin_id=str(transaction.admin_id) if transaction.admin_id else None,
                created_at=transaction.created_at,
            ).model_dump()
            for transaction in transactions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get system-wide statistics from real database state."""
    _require_admin(account)

    accounts = db.query(Account).all()
    balances = db.query(CreditBalance).all()
    usage_totals = {
        usage_type: int(total or 0)
        for usage_type, total in db.query(
            UsageRecord.usage_type,
            func.coalesce(func.sum(UsageRecord.daily_count), 0),
        )
        .group_by(UsageRecord.usage_type)
        .all()
    }
    total_users = len(accounts)
    active_users = sum(1 for item in accounts if item.is_active)
    total_credits_issued = sum(int(item.total_credits_received or 0) for item in balances)
    total_credits_used = sum(int(item.total_credits_used or 0) for item in balances)
    revenue_this_month = 0.0

    for item in accounts:
        subscription = _subscription(db, item)
        if not subscription:
            continue

        if subscription.status not in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING}:
            continue

        plan_price = PLAN_PRICES.get(subscription.plan_type, 0)
        if subscription.plan_type == PlanType.AGENCY:
            location_count = max(len(item.locations), 1)
            revenue_this_month += float(plan_price * location_count)
        else:
            revenue_this_month += float(plan_price)

    return SystemStats(
        total_users=total_users,
        active_users=active_users,
        total_credits_issued=total_credits_issued,
        total_credits_used=total_credits_used,
        total_sms_sent=usage_totals.get("sms", 0),
        total_ai_content=usage_totals.get("ai_content", 0),
        total_ai_images=usage_totals.get("ai_image", 0),
        revenue_this_month=round(revenue_this_month, 2),
    )


@router.get("/recovery-queue", response_model=RecoveryQueueResponse)
async def get_recovery_queue(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return the highest-signal recovery queue for operators.

    Uses persisted database state so the queue is still useful even when an
    external provider dashboard is temporarily unavailable.
    """
    _require_admin(account)

    account_map = {str(item.id): item for item in db.query(Account).all()}

    dunning_query = db.query(Subscription).filter(
        or_(
            Subscription.access_state != "active",
            Subscription.dunning_status != DunningStatus.NONE,
        )
    )
    dunning_total = dunning_query.count()
    dunning_rows = (
        dunning_query.order_by(
            Subscription.dunning_started_at.desc(),
            Subscription.created_at.desc(),
        )
        .limit(limit)
        .all()
    )

    actionable_statuses = [
        DisputeStatus.NEEDS_RESPONSE,
        DisputeStatus.WARNING_NEEDS_RESPONSE,
        DisputeStatus.UNDER_REVIEW,
        DisputeStatus.WARNING_UNDER_REVIEW,
    ]
    urgent_statuses = [
        DisputeStatus.NEEDS_RESPONSE,
        DisputeStatus.WARNING_NEEDS_RESPONSE,
    ]
    disputes_query = db.query(DisputeModel).filter(
        DisputeModel.status.in_(actionable_statuses)
    )
    dispute_total = disputes_query.count()
    urgent_dispute_total = (
        db.query(DisputeModel)
        .filter(DisputeModel.status.in_(urgent_statuses))
        .count()
    )
    dispute_rows = (
        disputes_query.order_by(
            DisputeModel.evidence_due_by.asc(),
            DisputeModel.created_at.desc(),
        )
        .limit(limit)
        .all()
    )

    refunded_query = db.query(CreditPurchaseOrder).filter(
        CreditPurchaseOrder.status == CreditPurchaseStatus.REFUNDED
    )
    refunded_total = refunded_query.count()
    refunded_rows = (
        refunded_query.order_by(
            CreditPurchaseOrder.refunded_at.desc(),
            CreditPurchaseOrder.created_at.desc(),
        )
        .limit(limit)
        .all()
    )

    refund_audit_map: dict[str, BillingAuditLog] = {}
    if refunded_rows:
        refund_order_ids = [str(order.id) for order in refunded_rows]
        refund_audits = (
            db.query(BillingAuditLog)
            .filter(
                BillingAuditLog.action == BillingAuditAction.REFUND_CREATED,
                BillingAuditLog.entity_type == "credit_purchase_order",
                BillingAuditLog.entity_id.in_(refund_order_ids),
            )
            .order_by(BillingAuditLog.created_at.desc())
            .all()
        )
        for entry in refund_audits:
            if entry.entity_id and entry.entity_id not in refund_audit_map:
                refund_audit_map[entry.entity_id] = entry

    recent_audit_candidates = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.action.in_(
                [
                    BillingAuditAction.REFUND_CREATED,
                    BillingAuditAction.DISPUTE_UPDATED,
                    BillingAuditAction.SUBSCRIPTION_UPDATED,
                ]
            )
        )
        .order_by(BillingAuditLog.created_at.desc())
        .limit(50)
        .all()
    )
    recent_operator_actions = []
    for entry in recent_audit_candidates:
        extra_data = entry.extra_data if isinstance(entry.extra_data, dict) else {}
        operator_action = extra_data.get("operator_action")
        if not operator_action:
            continue
        owner = account_map.get(str(entry.account_id)) if entry.account_id else None
        recent_operator_actions.append(
            RecoveryActivityEntry(
                id=str(entry.id),
                account_id=str(entry.account_id) if entry.account_id else None,
                account_email=owner.email if owner else None,
                action=entry.action.value if hasattr(entry.action, "value") else str(entry.action),
                operator_action=str(operator_action),
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                description=entry.description,
                created_at=entry.created_at,
            )
        )
        if len(recent_operator_actions) >= limit:
            break

    runbook_items = [
        RecoveryRunbookItem(
            id="dunning-follow-up",
            title="Recover dunning accounts",
            priority="high" if dunning_total > 0 else "monitor",
            summary=(
                f"{dunning_total} account(s) are in warning or suspended billing states."
                if dunning_total > 0
                else "No accounts are currently waiting on dunning follow-up."
            ),
            steps=[
                "Open the billing page or customer portal link and confirm whether payment recovery is possible now.",
                "Contact the customer with the next retry or billing-update instruction before access remains restricted too long.",
                "After payment succeeds, confirm access_state returns to active and remove any manual support flags.",
            ],
            cta_label="Review recovery queue",
            cta_href="/admin",
        ),
        RecoveryRunbookItem(
            id="dispute-response",
            title="Handle Stripe disputes",
            priority="high" if urgent_dispute_total > 0 else "normal",
            summary=(
                f"{urgent_dispute_total} dispute(s) still need an immediate operator response."
                if urgent_dispute_total > 0
                else "No urgent dispute responses are waiting right now."
            ),
            steps=[
                "Confirm the dispute is still actionable before responding or accepting it.",
                "Build one fact-based timeline with purchase, fulfillment, and customer communication evidence.",
                "Submit evidence only when you can prove the timeline, otherwise accept the dispute intentionally and close the support loop.",
            ],
            cta_label="Open disputes workflow",
            cta_href="/admin/disputes",
        ),
        RecoveryRunbookItem(
            id="refund-support-loop",
            title="Close the refund support loop",
            priority="normal" if refunded_total > 0 else "monitor",
            summary=(
                f"{refunded_total} refunded order(s) are tracked for support verification."
                if refunded_total > 0
                else "No refunded orders need follow-up confirmation right now."
            ),
            steps=[
                "Confirm both the Stripe-side refund result and the internal credit clawback result.",
                "If Stripe was unavailable, issue the payment refund manually and note the external reference.",
                "Send the customer a short closure update so support, billing, and product state all match.",
            ],
            cta_label="Open refunds workflow",
            cta_href="/admin/disputes",
        ),
    ]

    dunning_accounts = []
    for subscription in dunning_rows:
        owner = account_map.get(str(subscription.account_id))
        dunning_accounts.append(
            RecoveryAccountSummary(
                account_id=str(subscription.account_id),
                email=owner.email if owner else "",
                company_name=owner.company_name if owner else None,
                plan=subscription.plan_type.value,
                subscription_status=subscription.status.value,
                access_state=subscription.access_state,
                dunning_status=subscription.dunning_status.value,
                payment_retry_count=subscription.payment_retry_count,
                last_payment_error=subscription.last_payment_error,
                next_payment_retry_at=subscription.next_payment_retry_at,
                current_period_end=subscription.current_period_end,
                action_plan=_build_dunning_action_plan(owner, subscription),
            )
        )

    disputes = []
    for dispute in dispute_rows:
        owner = account_map.get(str(dispute.account_id))
        disputes.append(
            RecoveryDisputeSummary(
                dispute_id=dispute.stripe_dispute_id,
                account_id=str(dispute.account_id),
                user_email=owner.email if owner else "",
                amount=round(dispute.amount / 100.0, 2),
                reason=dispute.reason.value if dispute.reason else None,
                status=dispute.status.value,
                evidence_due_by=dispute.evidence_due_by,
                created_at=dispute.created_at,
                action_plan=_build_dispute_action_plan(owner, dispute),
            )
        )

    recent_refunds = []
    for order in refunded_rows:
        owner = account_map.get(str(order.account_id))
        recent_refunds.append(
            RecoveryRefundSummary(
                order_id=str(order.id),
                account_id=str(order.account_id),
                user_email=owner.email if owner else "",
                payment_id=order.stripe_payment_intent_id or "",
                amount=round(order.price_cents / 100.0, 2),
                status=order.status.value,
                created_at=order.created_at,
                processed_at=order.refunded_at,
                action_plan=_build_refund_action_plan(
                    owner,
                    order,
                    refund_audit_map.get(str(order.id)),
                ),
            )
        )

    return RecoveryQueueResponse(
        dunning_accounts=dunning_accounts,
        disputes=disputes,
        recent_refunds=recent_refunds,
        runbook_items=runbook_items,
        recent_operator_actions=recent_operator_actions,
        dunning_total=dunning_total,
        dispute_total=dispute_total,
        urgent_dispute_total=urgent_dispute_total,
        refunded_total=refunded_total,
        action_required_total=dunning_total + urgent_dispute_total,
        generated_at=datetime.now(timezone.utc),
    )


@router.post("/dunning/{account_id}/recovery-link", response_model=DunningRecoveryLinkResponse)
async def create_dunning_recovery_link(
    account_id: UUID,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Generate the best available billing recovery destination for an account in dunning."""
    _require_admin(account)

    owner = db.get(Account, account_id)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
        )

    subscription = (
        db.query(Subscription)
        .filter(Subscription.account_id == account_id)
        .first()
    )
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found for this account.",
        )

    dunning_status = DunningService(db).get_dunning_status(subscription)
    if not dunning_status.get("in_dunning"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This account is not currently in a dunning recovery state.",
        )

    portal_url = str(dunning_status.get("portal_url") or "")
    portal_available = bool(dunning_status.get("portal_available"))
    portal_source = str(dunning_status.get("portal_source") or "not_recorded")
    portal_error = dunning_status.get("portal_error")

    action_plan = _build_dunning_recovery_link_action_plan(
        owner,
        subscription,
        {
            "portal_url": portal_url,
            "portal_available": portal_available,
            "portal_source": portal_source,
            "portal_error": portal_error,
        },
    )

    _log_operator_recovery_action(
        db=db,
        operator=account,
        target_account_id=owner.id,
        action=BillingAuditAction.SUBSCRIPTION_UPDATED,
        entity_type="subscription",
        entity_id=str(subscription.id),
        description="Admin prepared a dunning recovery link for operator follow-up.",
        old_value={
            "access_state": subscription.access_state,
            "dunning_status": subscription.dunning_status.value,
        },
        new_value={
            "access_state": subscription.access_state,
            "dunning_status": subscription.dunning_status.value,
            "portal_source": portal_source,
            "portal_available": portal_available,
        },
        extra_data={
            "operator_action": "dunning_recovery_link_generated",
            "operator_id": str(account.id),
            "portal_url": portal_url,
            "portal_source": portal_source,
            "portal_available": portal_available,
            "portal_error": portal_error,
        },
    )

    return DunningRecoveryLinkResponse(
        account_id=str(owner.id),
        email=owner.email,
        portal_url=portal_url,
        portal_available=portal_available,
        portal_source=portal_source,
        portal_error=str(portal_error) if portal_error else None,
        action_plan=action_plan,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/operations-feed", response_model=OperationsFeedResponse)
async def get_operations_feed(
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return a cross-domain operations feed for recent persisted events."""
    _require_admin(account)

    per_domain_limit = max(limit, 10)
    items: list[OperationsFeedItem] = []
    account_map = {str(item.id): item for item in db.query(Account).all()}
    location_map = {str(item.id): item for item in db.query(Location).all()}
    post_map = {
        str(item.id): item
        for item in (
            db.query(Post)
            .options(joinedload(Post.location).joinedload(Location.account))
            .all()
        )
    }
    oauth_token_map = {
        str(item.id): item
        for item in (
            db.query(OAuthToken)
            .options(
                joinedload(OAuthToken.account),
                joinedload(OAuthToken.location),
            )
            .all()
        )
    }

    publish_rows = (
        db.query(PublishJob)
        .options(
            joinedload(PublishJob.post)
            .joinedload(Post.location)
            .joinedload(Location.account)
        )
        .filter(
            or_(
                PublishJob.status.in_([PublishJobStatus.FAILED, PublishJobStatus.COMPLETED]),
                PublishJob.last_error.isnot(None),
            )
        )
        .order_by(PublishJob.updated_at.desc())
        .limit(per_domain_limit)
        .all()
    )
    for job in publish_rows:
        post = job.post if job.post else post_map.get(str(job.post_id))
        location = post.location if post and post.location else (
            location_map.get(str(post.location_id)) if post else None
        )
        owner = location.account if location and location.account else (
            account_map.get(str(location.account_id)) if location else None
        )
        if job.status == PublishJobStatus.FAILED:
            severity = "critical" if not job.can_retry else "warning"
            title = f"{job.platform.upper()} publish failed"
        elif job.last_error and job.status == PublishJobStatus.PENDING:
            severity = "warning"
            title = f"{job.platform.upper()} publish retry scheduled"
        else:
            severity = "info"
            title = f"{job.platform.upper()} publish completed"

        items.append(
            OperationsFeedItem(
                id=f"publish:{job.id}",
                domain="publish",
                severity=severity,
                title=title,
                summary=_operations_summary(
                    [
                        f"Location: {location.name if location else 'Not recorded'}.",
                        f"Post: {post.title or '(untitled post)' if post else 'Not recorded'}.",
                        f"Status: {job.status.value}.",
                        f"Retries: {job.tries}/{job.max_tries}.",
                        f"Last error: {job.last_error or 'None recorded'}.",
                    ]
                ),
                status=job.status.value,
                account_id=str(owner.id) if owner else None,
                account_email=owner.email if owner else None,
                location_id=str(location.id) if location else None,
                location_name=location.name if location else None,
                entity_type="publish_job",
                entity_id=str(job.id),
                occurred_at=job.completed_at or job.updated_at,
                actionable=severity != "info",
                action_href=_action_href_for_domain("publish", str(post.id) if post else None),
            )
        )

    oauth_rows = (
        db.query(OAuthEvent)
        .options(
            joinedload(OAuthEvent.token).joinedload(OAuthToken.account),
            joinedload(OAuthEvent.token).joinedload(OAuthToken.location),
        )
        .order_by(OAuthEvent.created_at.desc())
        .limit(per_domain_limit)
        .all()
    )
    for event in oauth_rows:
        token = event.token if event.token else oauth_token_map.get(str(event.token_id))
        owner = token.account if token and token.account else (
            account_map.get(str(token.account_id)) if token else None
        )
        location = token.location if token and token.location else (
            location_map.get(str(token.location_id)) if token and token.location_id else None
        )
        event_type = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
        token_status = token.status.value if token and hasattr(token.status, "value") else (
            str(token.status) if token and token.status else "unknown"
        )

        if event.event_type in {OAuthEventType.REFRESH_FAILED, OAuthEventType.REVOKED}:
            severity = "critical" if token and token.status in {OAuthStatus.NEEDS_REAUTH, OAuthStatus.REVOKED} else "warning"
        elif event.event_type == OAuthEventType.SCOPES_CHANGED:
            severity = "warning"
        else:
            severity = "info"

        items.append(
            OperationsFeedItem(
                id=f"oauth:{event.id}",
                domain="oauth",
                severity=severity,
                title=f"{token.provider.value if token else 'oauth'} {event_type.replace('_', ' ')}",
                summary=_operations_summary(
                    [
                        f"Location: {location.name if location else 'Not recorded'}.",
                        f"Provider status: {token_status}.",
                        (
                            f"Error: {event.error_message}."
                            if event.error_message
                            else f"Last token error: {token.last_error}."
                            if token and token.last_error
                            else ""
                        ),
                        (
                            f"Next refresh: {_format_datetime_for_ops(token.next_refresh_at)}."
                            if token and token.next_refresh_at
                            else ""
                        ),
                    ]
                ),
                status=token_status,
                account_id=str(owner.id) if owner else None,
                account_email=owner.email if owner else None,
                location_id=str(location.id) if location else None,
                location_name=location.name if location else None,
                entity_type="oauth_token",
                entity_id=str(token.id) if token else None,
                occurred_at=event.created_at,
                actionable=severity != "info",
                action_href=_action_href_for_domain("oauth"),
            )
        )

    operational_notification_rows = (
        db.query(NotificationEvent)
        .order_by(NotificationEvent.created_at.desc())
        .limit(per_domain_limit)
        .all()
    )
    for event in operational_notification_rows:
        severity = _operational_notification_severity(event.type)
        if severity is None:
            continue
        owner = account_map.get(str(event.account_id))
        items.append(
            OperationsFeedItem(
                id=f"worker_ops:{event.id}",
                domain="worker_ops",
                severity=severity,
                title=event.title,
                summary=_operations_summary(
                    [
                        f"Account: {owner.email if owner else 'Not recorded'}.",
                        event.body,
                    ]
                ),
                status=event.type,
                account_id=str(owner.id) if owner else None,
                account_email=owner.email if owner else None,
                entity_type="notification_event",
                entity_id=str(event.id),
                occurred_at=event.created_at,
                actionable=severity != "info",
                action_href=event.url or _action_href_for_domain("worker_ops"),
            )
        )

    notification_rows = (
        db.query(NotificationDeliveryLog)
        .order_by(NotificationDeliveryLog.attempted_at.desc())
        .limit(per_domain_limit)
        .all()
    )
    for log in notification_rows:
        owner = account_map.get(str(log.account_id))
        severity = "info" if log.delivery_status == "delivered" else "warning"

        items.append(
            OperationsFeedItem(
                id=f"notification:{log.id}",
                domain="notifications",
                severity=severity,
                title=f"{log.channel.upper()} notification {log.delivery_status.replace('_', ' ')}",
                summary=_operations_summary(
                    [
                        f"Account: {owner.email if owner else 'Not recorded'}.",
                        (
                            f"Failure reason: {log.failure_reason}."
                            if log.failure_reason
                            else "No failure reason recorded."
                        ),
                    ]
                ),
                status=log.delivery_status,
                account_id=str(owner.id) if owner else None,
                account_email=owner.email if owner else None,
                entity_type="notification_delivery",
                entity_id=str(log.id),
                occurred_at=log.attempted_at,
                actionable=severity != "info",
                action_href=_action_href_for_domain("notifications"),
            )
        )

    review_rows = (
        db.query(BoosterRequest)
        .options(joinedload(BoosterRequest.location).joinedload(Location.account))
        .filter(BoosterRequest.status.in_([RequestStatus.FAILED, RequestStatus.DELIVERED, RequestStatus.OPTED_OUT]))
        .order_by(BoosterRequest.updated_at.desc())
        .limit(per_domain_limit)
        .all()
    )
    for request in review_rows:
        location = request.location if request.location else location_map.get(str(request.location_id))
        owner = location.account if location and location.account else (
            account_map.get(str(location.account_id)) if location else None
        )
        severity = "warning" if request.status == RequestStatus.FAILED else "info"

        items.append(
            OperationsFeedItem(
                id=f"review_booster:{request.id}",
                domain="review_booster",
                severity=severity,
                title=f"Review booster {request.status.value.replace('_', ' ')}",
                summary=_operations_summary(
                    [
                        f"Location: {location.name if location else 'Not recorded'}.",
                        f"Customer: {request.customer_name or request.customer_email or request.customer_phone or 'Not recorded'}.",
                        f"Channel: {request.channel.value}.",
                        (
                            f"Last error: {request.last_error}."
                            if request.last_error
                            else ""
                        ),
                    ]
                ),
                status=request.status.value,
                account_id=str(owner.id) if owner else None,
                account_email=owner.email if owner else None,
                location_id=str(location.id) if location else None,
                location_name=location.name if location else None,
                entity_type="booster_request",
                entity_id=str(request.id),
                occurred_at=request.delivered_at or request.last_attempt_at or request.sent_at or request.updated_at,
                actionable=severity != "info",
                action_href=_action_href_for_domain("review_booster"),
            )
        )

    items.sort(
        key=lambda item: (
            item.occurred_at,
            -_severity_rank(item.severity),
        ),
        reverse=True,
    )
    items = items[:limit]

    domain_totals: dict[str, int] = {}
    for item in items:
        domain_totals[item.domain] = domain_totals.get(item.domain, 0) + 1

    return OperationsFeedResponse(
        items=items,
        total=len(items),
        actionable_total=sum(1 for item in items if item.actionable),
        domain_totals=domain_totals,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/upload-migration-audit/export")
def export_upload_migration_audit(
    limit: int = Query(5000, ge=1, le=20000),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Export the current upload migration manifest as CSV for operator follow-up."""
    _require_admin(account)

    audit = _build_upload_migration_audit(db, sample_limit=limit)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "source_type",
            "entity_id",
            "field_name",
            "recommended_action",
            "account_id",
            "account_email",
            "location_id",
            "location_name",
            "storage_key",
            "url",
            "created_at",
        ]
    )
    for item in audit.items:
        writer.writerow(
            [
                item.source_type,
                item.entity_id,
                item.field_name,
                item.recommended_action,
                item.account_id or "",
                item.account_email or "",
                item.location_id or "",
                item.location_name or "",
                item.storage_key or "",
                item.url,
                item.created_at.isoformat(),
            ]
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="upload-migration-audit.csv"'
        },
    )


@router.get("/upload-migration-audit", response_model=UploadMigrationAuditResponse)
def get_upload_migration_audit(
    sample_limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return the remaining legacy local-upload footprint that still needs migration."""
    _require_admin(account)
    return _build_upload_migration_audit(db, sample_limit=sample_limit)


@router.get("/upload-migration-batch-preview", response_model=UploadMigrationBatchPreviewResponse)
def get_upload_migration_batch_preview(
    limit: int = Query(25, ge=1, le=250),
    offset: int = Query(0, ge=0),
    source_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return a safe dry-run preview for the next upload migration batch."""
    _require_admin(account)
    return _build_upload_migration_batch_preview(
        db,
        source_type=source_type,
        offset=offset,
        limit=limit,
    )


@router.get("/conversions", response_model=ConversionAnalyticsResponse)
def get_conversion_analytics(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return admin-level conversion analytics using persisted production data only."""
    _require_admin(account)

    resolved_start, resolved_end, start_dt, end_dt, period_days = _resolve_conversion_window(
        start_date,
        end_date,
    )
    previous_start_dt = start_dt - timedelta(days=period_days)
    previous_end_dt = start_dt
    non_admin_account_ids = [
        account_id
        for account_id, in db.query(Account.id).filter(Account.role != AccountRole.ADMIN).all()
    ]

    current_period = _summarize_conversion_period(
        db,
        start_dt,
        end_dt,
        non_admin_account_ids,
    )
    previous_period = _summarize_conversion_period(
        db,
        previous_start_dt,
        previous_end_dt,
        non_admin_account_ids,
    )

    billable_subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.account_id.in_(non_admin_account_ids),
            Subscription.plan_type != PlanType.FREE,
        )
        .all()
        if non_admin_account_ids
        else []
    )

    current_mrr = round(
        sum(
            _plan_monthly_amount(subscription)
            for subscription in billable_subscriptions
            if _subscription_is_billable_at(subscription, end_dt)
        ),
        2,
    )
    active_paid_base = sum(
        1
        for subscription in billable_subscriptions
        if _subscription_is_billable_at(subscription, start_dt)
    )

    trial_subscriptions = [
        subscription
        for subscription in billable_subscriptions
        if (
            (trial_start := _normalize_datetime(subscription.trial_start)) is not None
            and start_dt <= trial_start < end_dt
        )
    ]
    trial_lengths: list[float] = []
    for subscription in trial_subscriptions:
        if not subscription.trial_start:
            continue
        trial_start_value = _normalize_datetime(subscription.trial_start)
        trial_end_value = _normalize_datetime(subscription.trial_end) or min(end_dt, datetime.now(timezone.utc))
        if not trial_start_value:
            continue
        duration_seconds = max((trial_end_value - trial_start_value).total_seconds(), 0.0)
        trial_lengths.append(duration_seconds / 86400.0)
    avg_trial_length_days = round(sum(trial_lengths) / len(trial_lengths), 1) if trial_lengths else 0.0

    canceled_subscriptions = sum(
        1
        for subscription in billable_subscriptions
        if (
            (canceled_at := _normalize_datetime(subscription.canceled_at)) is not None
            and start_dt <= canceled_at < end_dt
        )
    )
    payment_recovery_accounts = sum(
        1
        for subscription in billable_subscriptions
        if subscription.dunning_status != DunningStatus.NONE
    )

    funnel = _build_conversion_funnel(current_period)
    metrics = ConversionMetricsSnapshot(
        visitors=int(current_period["visitors"]),
        signups=int(current_period["signups"]),
        trials=int(current_period["trials"]),
        paid=int(current_period["paid"]),
        revenue_collected=float(current_period["revenue_collected"]),
        current_mrr=current_mrr,
        visitor_to_signup=_percentage(int(current_period["signups"]), int(current_period["visitors"])),
        signup_to_trial=_percentage(int(current_period["trials"]), int(current_period["signups"])),
        trial_to_paid=_percentage(int(current_period["paid"]), int(current_period["trials"])),
        overall_conversion=_percentage(int(current_period["paid"]), int(current_period["visitors"])),
        churn_rate=_percentage(int(canceled_subscriptions), active_paid_base),
        avg_trial_length_days=avg_trial_length_days,
        top_drop_off_point=_top_drop_off_point(funnel),
        payment_recovery_accounts=int(payment_recovery_accounts),
        canceled_subscriptions=int(canceled_subscriptions),
        changes=ConversionMetricDelta(
            visitors=_percentage_change(
                int(current_period["visitors"]),
                int(previous_period["visitors"]),
            ),
            signups=_percentage_change(
                int(current_period["signups"]),
                int(previous_period["signups"]),
            ),
            trials=_percentage_change(
                int(current_period["trials"]),
                int(previous_period["trials"]),
            ),
            paid=_percentage_change(
                int(current_period["paid"]),
                int(previous_period["paid"]),
            ),
            revenue_collected=_percentage_change(
                float(current_period["revenue_collected"]),
                float(previous_period["revenue_collected"]),
            ),
        ),
    )

    notes = [
        "Website visitors are summed from connected website analytics snapshots in the selected range.",
        "Paid accounts and revenue collected are based on successful invoice-backed payments in the selected range.",
        "Signup-started and payment-method-added micro-steps are intentionally omitted until event coverage is production-complete.",
    ]
    drop_off_reasons = _build_drop_off_reasons(
        funnel,
        int(canceled_subscriptions),
        int(payment_recovery_accounts),
    )
    insights = _build_conversion_insights(metrics, notes)

    return ConversionAnalyticsResponse(
        start_date=resolved_start,
        end_date=resolved_end,
        period_days=period_days,
        metrics=metrics,
        funnel=funnel,
        drop_off_reasons=drop_off_reasons,
        insights=insights,
        notes=notes,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/plans")
async def get_plan_configs(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get current public plan configuration."""
    _require_admin(account)
    return {
        "plans": {
            plan_type.value: _plan_config(plan_type)
            for plan_type in ADMIN_PUBLIC_PLANS
        }
    }


@router.post("/monthly-credits", response_model=MonthlyCreditDistributionResponse)
async def distribute_monthly_credits(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    _require_admin(account)
    return _distribute_due_monthly_credits(
        db,
        admin_account=account,
    )


@router.get("/refunds")
async def get_refunds(
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """List credit purchase orders from the database.

    By default returns only REFUNDED orders. Pass ``status_filter`` to see
    other lifecycle states (pending, completed, canceled, expired, refunded).
    """
    _require_admin(account)

    query = (
        db.query(CreditPurchaseOrder)
        .options(joinedload(CreditPurchaseOrder.account))
    )

    if status_filter:
        try:
            status_enum = CreditPurchaseStatus(status_filter.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid status_filter {status_filter!r}. "
                    f"Valid values: {[s.value for s in CreditPurchaseStatus]}"
                ),
            )
        query = query.filter(CreditPurchaseOrder.status == status_enum)
    else:
        # Default: show refunded orders only
        query = query.filter(CreditPurchaseOrder.status == CreditPurchaseStatus.REFUNDED)

    orders = query.order_by(CreditPurchaseOrder.created_at.desc()).limit(limit).all()

    return {
        "refunds": [
            {
                "id": str(order.id),
                "payment_id": order.stripe_payment_intent_id or "",
                "user_id": str(order.account_id),
                "user_email": order.account.email if order.account else "",
                "amount": round(order.price_cents / 100.0, 2),
                "reason": f"Credit purchase refund – {order.package_id}",
                "status": order.status.value,
                "package_id": order.package_id,
                "credits_amount": order.credits_amount,
                "created_at": order.created_at,
                "processed_at": order.refunded_at,
            }
            for order in orders
        ]
    }


@router.get("/credit-orders")
async def get_credit_orders(
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """List all credit purchase orders across all users (admin view).

    Unlike ``/refunds`` (which defaults to REFUNDED), this returns all orders
    and supports filtering by any status.
    """
    _require_admin(account)

    query = (
        db.query(CreditPurchaseOrder)
        .options(joinedload(CreditPurchaseOrder.account))
    )

    if status_filter:
        try:
            status_enum = CreditPurchaseStatus(status_filter.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status {status_filter!r}.",
            )
        query = query.filter(CreditPurchaseOrder.status == status_enum)

    orders = query.order_by(CreditPurchaseOrder.created_at.desc()).limit(limit).all()
    return {
        "orders": [
            {
                "id": str(order.id),
                "stripe_session_id": order.stripe_session_id,
                "stripe_payment_intent_id": order.stripe_payment_intent_id or "",
                "package_id": order.package_id,
                "credits_amount": order.credits_amount,
                "price_cents": order.price_cents,
                "status": order.status.value,
                "user_id": str(order.account_id),
                "user_email": order.account.email if order.account else "",
                "created_at": order.created_at,
                "completed_at": order.completed_at,
                "refunded_at": order.refunded_at,
            }
            for order in orders
        ]
    }


@router.post("/refunds")
async def process_refund(
    request: RefundRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Process a refund for a credit purchase order.

    Looks up the order by ``payment_id`` (Stripe payment-intent ID).
    Claws back the purchased credits from the user's balance, then attempts
    to issue a refund in Stripe if ``STRIPE_SECRET_KEY`` is configured.
    If Stripe is not configured, the credit clawback still takes effect and
    the order is marked REFUNDED – the operator must issue the payment refund
    manually.
    """
    _require_admin(account)

    order = (
        db.query(CreditPurchaseOrder)
        .options(joinedload(CreditPurchaseOrder.account))
        .filter(CreditPurchaseOrder.stripe_payment_intent_id == request.payment_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credit purchase order found for payment_id {request.payment_id!r}.",
        )

    if order.status == CreditPurchaseStatus.REFUNDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order has already been refunded.",
        )

    if order.status != CreditPurchaseStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot refund an order in {order.status.value!r} state. "
                "Only COMPLETED orders are eligible for refund."
            ),
        )

    # Attempt Stripe refund; surface errors as a warning rather than a hard failure
    stripe_refund_id: Optional[str] = None
    stripe_error: Optional[str] = None
    try:
        import stripe
        from app.core.config import settings

        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key
            refund_obj = stripe.Refund.create(
                payment_intent=request.payment_id,
                reason="requested_by_customer",
            )
            stripe_refund_id = refund_obj.id
        else:
            stripe_error = "Stripe not configured; payment refund must be issued manually."
    except Exception as exc:
        stripe_error = str(exc)

    # Clawback credits (idempotent; safe to call even if Stripe failed)
    result = CreditsService(db).refund_purchase(stripe_payment_intent_id=request.payment_id)

    if not result.get("refunded") and not result.get("already_refunded"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Credit clawback failed: {result.get('reason', 'unknown')}",
        )

    db.refresh(order)

    _log_operator_recovery_action(
        db=db,
        operator=account,
        target_account_id=order.account_id,
        action=BillingAuditAction.REFUND_CREATED,
        entity_type="credit_purchase_order",
        entity_id=str(order.id),
        description=(
            "Admin refund processed."
            if not stripe_error
            else "Admin refund processed with manual Stripe follow-up required."
        ),
        new_value={
            "payment_id": request.payment_id,
            "status": order.status.value,
            "credits_deducted": result.get("credits_deducted", 0),
        },
        extra_data={
            "operator_action": "refund_processed",
            "operator_id": str(account.id),
            "support_reason": request.reason,
            "stripe_refund_id": stripe_refund_id,
            "stripe_error": stripe_error,
        },
    )

    return {
        "id": str(order.id),
        "payment_id": order.stripe_payment_intent_id or "",
        "user_id": str(order.account_id),
        "user_email": order.account.email if order.account else "",
        "amount": round(order.price_cents / 100.0, 2),
        "reason": request.reason,
        "status": order.status.value,
        "package_id": order.package_id,
        "credits_amount": order.credits_amount,
        "credits_deducted": result.get("credits_deducted", 0),
        "created_at": order.created_at,
        "processed_at": order.refunded_at,
        "stripe_refund_id": stripe_refund_id,
        "stripe_error": stripe_error,
    }


@router.get("/disputes", response_model=DisputeListResponse)
async def get_disputes(
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """List disputes with live Stripe data when available, local cache otherwise."""
    _require_admin(account)

    local_account_map = {
        str(item.id): item.email
        for item in db.query(Account.id, Account.email).all()
    }

    def _local_dispute_payload(warning: str) -> DisputeListResponse:
        query = db.query(DisputeModel).order_by(
            DisputeModel.evidence_due_by.asc(),
            DisputeModel.created_at.desc(),
        )
        if status_filter and status_filter in DisputeStatus._value2member_map_:
            query = query.filter(
                DisputeModel.status == DisputeStatus(status_filter)
            )

        local_disputes = (
            query
            .limit(limit)
            .all()
        )
        return DisputeListResponse(
            disputes=[
                _serialize_local_dispute(
                    dispute,
                    user_email=local_account_map.get(str(dispute.account_id), ""),
                )
                for dispute in local_disputes
            ],
            stripe_available=False,
            data_source="local_cache",
            warning=warning,
        )

    try:
        import stripe

        if not _stripe_key_is_configured(settings.stripe_secret_key):
            return _local_dispute_payload(
                "Stripe is not configured, so this page is showing the persisted local dispute ledger only. "
                "Connect Stripe to respond to or accept disputes from this workspace."
            )

        stripe.api_key = settings.stripe_secret_key
        params: dict = {"limit": limit}
        if status_filter:
            params["status"] = status_filter

        disputes_list = stripe.Dispute.list(**params)
        local_dispute_map = {
            dispute.stripe_dispute_id: dispute
            for dispute in (
                db.query(DisputeModel)
                .filter(DisputeModel.stripe_dispute_id.in_([d.id for d in disputes_list.data]))
                .all()
            )
        }

        disputes: list[DisputeResponse] = []
        for d in disputes_list.data:
            # Try to resolve user info from local credit purchase orders
            user_id = ""
            user_email = ""
            local_dispute = local_dispute_map.get(d.id)
            if d.payment_intent:
                local_order = (
                    db.query(CreditPurchaseOrder)
                    .options(joinedload(CreditPurchaseOrder.account))
                    .filter(
                        CreditPurchaseOrder.stripe_payment_intent_id == d.payment_intent
                    )
                    .first()
                )
                if local_order and local_order.account:
                    user_id = str(local_order.account_id)
                    user_email = local_order.account.email
            elif local_dispute:
                user_id = str(local_dispute.account_id)
                user_email = local_account_map.get(user_id, "")

            disputes.append(
                DisputeResponse(
                    id=d.id,
                    user_id=user_id,
                    user_email=user_email,
                    payment_id=d.payment_intent or d.charge or "",
                    amount=round(d.amount / 100.0, 2),
                    reason=d.reason,
                    status=d.status,
                    created_at=datetime.fromtimestamp(d.created, tz=timezone.utc),
                    evidence_due_by=local_dispute.evidence_due_by if local_dispute else None,
                    source="stripe_live",
                )
            )

        return DisputeListResponse(
            disputes=disputes,
            stripe_available=True,
            data_source="stripe_live",
            warning=None,
        )

    except stripe.error.AuthenticationError as exc:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Stripe authentication failed: {exc}",
        )
    except HTTPException:
        raise
    except ImportError:
        return _local_dispute_payload(
            "Stripe is unavailable in this environment, so this page is showing the persisted local dispute ledger only."
        )


@router.post("/disputes/{dispute_id}/respond")
async def respond_to_dispute(
    dispute_id: str,
    request: DisputeEvidenceRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Submit evidence to Stripe for a dispute.

    Only disputes in ``needs_response`` or ``warning_needs_response`` state
    can have evidence submitted.  Returns 503 when Stripe is not configured
    and 422 when the dispute is not in an actionable state.
    """
    _require_admin(account)

    try:
        import stripe
        from app.core.config import settings

        if not _stripe_key_is_configured(settings.stripe_secret_key):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Dispute evidence submission requires Stripe to be configured. "
                    "Set STRIPE_SECRET_KEY to enable this feature."
                ),
            )

        stripe.api_key = settings.stripe_secret_key

        try:
            dispute = stripe.Dispute.retrieve(dispute_id)
        except stripe.error.InvalidRequestError as exc:  # type: ignore[attr-defined]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dispute not found: {exc}",
            )

        actionable = {"needs_response", "warning_needs_response"}
        if dispute.status not in actionable:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot submit evidence for a dispute in '{dispute.status}' state. "
                    f"Evidence can only be submitted for: {sorted(actionable)}."
                ),
            )

        updated = stripe.Dispute.modify(  # type: ignore[attr-defined]
            dispute_id,
            evidence={"uncategorized_text": _compose_dispute_evidence(request)},
            submit=True,
        )

        # Persist updated status to local DB if we have a local record
        target_account_id: Optional[UUID] = None
        local = (
            db.query(DisputeModel)
            .filter(DisputeModel.stripe_dispute_id == dispute_id)
            .first()
        )
        if local:
            target_account_id = local.account_id
            try:
                local.status = DisputeStatus(updated.status)
                db.commit()
            except (ValueError, Exception):
                db.rollback()
        if target_account_id is None:
            target_account_id, _ = _account_for_payment_intent(
                db, getattr(dispute, "payment_intent", None)
            )

        _log_operator_recovery_action(
            db=db,
            operator=account,
            target_account_id=target_account_id,
            action=BillingAuditAction.DISPUTE_UPDATED,
            entity_type="dispute",
            entity_id=dispute_id,
            description="Admin submitted dispute evidence to Stripe.",
            old_value={"status": dispute.status},
            new_value={"status": updated.status},
            extra_data={
                "operator_action": "dispute_evidence_submitted",
                "operator_id": str(account.id),
                "proof_checklist": request.proof_checklist,
                "attachment_names": request.attachment_names,
                "attachment_urls": request.attachment_urls,
            },
        )

        return {
            "id": updated.id,
            "status": updated.status,
            "message": "Evidence submitted successfully to Stripe.",
        }

    except stripe.error.AuthenticationError as exc:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Stripe authentication failed: {exc}",
        )
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe library not available.",
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {exc}",
        )


@router.post("/disputes/{dispute_id}/accept")
async def accept_dispute(
    dispute_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Accept (concede) a dispute in Stripe, refunding the customer.

    Only disputes in ``needs_response`` or ``warning_needs_response`` state
    can be accepted.  Returns 503 when Stripe is not configured and 422 when
    the dispute is not in an actionable state.
    """
    _require_admin(account)

    try:
        import stripe
        from app.core.config import settings

        if not _stripe_key_is_configured(settings.stripe_secret_key):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Dispute acceptance requires Stripe to be configured. "
                    "Set STRIPE_SECRET_KEY to enable this feature."
                ),
            )

        stripe.api_key = settings.stripe_secret_key

        try:
            dispute = stripe.Dispute.retrieve(dispute_id)
        except stripe.error.InvalidRequestError as exc:  # type: ignore[attr-defined]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dispute not found: {exc}",
            )

        closeable = {"needs_response", "warning_needs_response"}
        if dispute.status not in closeable:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot accept a dispute in '{dispute.status}' state. "
                    f"Disputes can only be accepted when in: {sorted(closeable)}."
                ),
            )

        updated = stripe.Dispute.close(dispute_id)  # type: ignore[attr-defined]

        # Persist updated status to local DB if we have a local record
        target_account_id: Optional[UUID] = None
        local = (
            db.query(DisputeModel)
            .filter(DisputeModel.stripe_dispute_id == dispute_id)
            .first()
        )
        if local:
            target_account_id = local.account_id
            try:
                local.status = DisputeStatus(updated.status)
                db.commit()
            except (ValueError, Exception):
                db.rollback()
        if target_account_id is None:
            target_account_id, _ = _account_for_payment_intent(
                db, getattr(dispute, "payment_intent", None)
            )

        _log_operator_recovery_action(
            db=db,
            operator=account,
            target_account_id=target_account_id,
            action=BillingAuditAction.DISPUTE_UPDATED,
            entity_type="dispute",
            entity_id=dispute_id,
            description="Admin accepted a dispute in Stripe.",
            old_value={"status": dispute.status},
            new_value={"status": updated.status},
            extra_data={
                "operator_action": "dispute_accepted",
                "operator_id": str(account.id),
            },
        )

        return {
            "id": updated.id,
            "status": updated.status,
            "message": "Dispute accepted. The customer will be refunded.",
        }

    except stripe.error.AuthenticationError as exc:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Stripe authentication failed: {exc}",
        )
    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe library not available.",
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {exc}",
        )
