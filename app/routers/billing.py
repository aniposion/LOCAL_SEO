"""Billing router."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.billing import BillingAuditAction, BillingAuditLog
from app.models.stripe_event import StripeEvent
from app.models.subscription import FREE_PREVIEW_DAYS, FREE_PREVIEW_PLAN, PaymentHistory, PlanType, Subscription
from app.routers.deps import get_current_user
from app.schemas.subscription import (
    AddPaymentMethodRequest,
    BillingAuditListResponse,
    BillingWebhookEventListResponse,
    BillingInfoRequest,
    BillingInfoResponse,
    CancelSubscriptionRequest,
    CancelSubscriptionResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    DunningStatusResponse,
    InvoiceListResponse,
    PaymentHistoryResponse,
    PaymentMethodResponse,
    PlanInfo,
    PlanLimits,
    PortalSessionRequest,
    PortalSessionResponse,
    ResumeSubscriptionResponse,
    SubscriptionChangeRequest,
    SubscriptionPreviewRequest,
    SubscriptionPreviewResponse,
    SubscriptionResponse,
    TrialStartRequest,
    TrialStartResponse,
    UsageStats,
)
from app.services.billing import BillingService
from app.services.credits import CreditsService
from app.services.dunning_service import DunningService
from app.services.plan_limits import PLAN_LIMITS_BY_PLAN, get_plan_limits as resolve_plan_limits

router = APIRouter(prefix="/billing", tags=["billing"])

# Public catalog is the managed pilot offer. Legacy self-serve plans remain
# addressable for existing customers and internal migrations.
PUBLIC_PLAN_TYPES = (
    PlanType.FREE,
    PlanType.MAPS_STARTER,
    PlanType.CALLS_GROWTH,
    PlanType.COMPETITIVE_MARKET,
)
LEGACY_PLAN_TYPES = (
    PlanType.STARTER,
    PlanType.PRO,
    PlanType.PREMIUM,
    PlanType.AGENCY,
)

# Plan definitions - managed pilot catalog plus legacy compatibility plans.
PLANS = {
    PlanType.FREE: PlanInfo(
        id="free",
        name="Free",
        price_monthly=0,
        price_yearly=0,
        features=["Basic dashboard access"],
        limits=PLAN_LIMITS_BY_PLAN[PlanType.FREE],
    ),
    PlanType.MAPS_STARTER: PlanInfo(
        id="maps_starter",
        name="Maps Starter",
        price_monthly=699,
        price_yearly=6990,
        setup_fee=499,
        sales_motion="managed_3_month_pilot",
        managed_service=True,
        minimum_term_months=3,
        features=[
            "Managed Google Business Profile cleanup",
            "Category and service optimization",
            "Review request link and QR code setup",
            "Google Business Profile post workflow",
            "Basic competitor check",
            "Simple monthly report",
        ],
        limits=PLAN_LIMITS_BY_PLAN[PlanType.MAPS_STARTER],
    ),
    PlanType.CALLS_GROWTH: PlanInfo(
        id="calls_growth",
        name="Calls Growth",
        price_monthly=999,
        price_yearly=9990,
        setup_fee=799,
        sales_motion="managed_3_month_pilot",
        managed_service=True,
        minimum_term_months=3,
        features=[
            "Everything in Maps Starter",
            "Local rank grid tracking",
            "Review request SMS and email workflow",
            "Review reply drafts",
            "Local landing page workflow",
            "Competitor review gap report",
            "Monthly strategy call",
        ],
        limits=PLAN_LIMITS_BY_PLAN[PlanType.CALLS_GROWTH],
    ),
    PlanType.COMPETITIVE_MARKET: PlanInfo(
        id="competitive_market",
        name="Competitive Market",
        price_monthly=1499,
        price_yearly=14990,
        setup_fee=1500,
        sales_motion="managed_3_month_pilot",
        managed_service=True,
        minimum_term_months=3,
        features=[
            "Everything in Calls Growth",
            "Advanced competitor tracking",
            "Multi-location reporting",
            "Website SEO workflows",
            "Priority support",
            "Call tracking setup support",
            "Expanded content and review operations",
        ],
        limits=PLAN_LIMITS_BY_PLAN[PlanType.COMPETITIVE_MARKET],
    ),
    PlanType.STARTER: PlanInfo(
        id="starter",
        name="Starter",
        price_monthly=99,
        price_yearly=990,
        publicly_listed=False,
        features=[
            "Google Maps posts auto-generation",
            "Review collection + AI response drafts",
            "Basic KPI dashboard",
            "Weekly reports",
        ],
        limits=PLAN_LIMITS_BY_PLAN[PlanType.STARTER],
    ),
    PlanType.PRO: PlanInfo(
        id="pro",
        name="Pro",
        price_monthly=149,
        price_yearly=1490,
        publicly_listed=False,
        features=[
            "All Starter features",
            "Instagram Publishing Tools (Beta)",
            "Content Scheduler",
            "Q&A Response Drafts (Beta)",
            "Review Trend Analysis",
            "Website SEO Tools (Beta)",
        ],
        limits=PLAN_LIMITS_BY_PLAN[PlanType.PRO],
    ),
    PlanType.PREMIUM: PlanInfo(
        id="premium",
        name="Premium",
        price_monthly=249,
        price_yearly=2490,
        publicly_listed=False,
        features=[
            "All Pro features",
            "Missed Call Text Back",
            "Review Booster (SMS/Email)",
            "Website SEO Workflows (Beta)",
            "Advanced Response Automation (Beta)",
        ],
        limits=PLAN_LIMITS_BY_PLAN[PlanType.PREMIUM],
    ),
    PlanType.AGENCY: PlanInfo(
        id="agency",
        name="Agency",
        price_monthly=499,
        price_yearly=4990,
        publicly_listed=False,
        features=[
            "All Premium features",
            "White-label reports",
            "Team permission management",
            "Unified dashboard",
            "Multi-location management",
            "Bulk automation",
            "Custom onboarding and support scope",
        ],
        limits=PLAN_LIMITS_BY_PLAN[PlanType.AGENCY],
    ),
}


def _json_search_blob(value: object | None) -> str:
    """Serialize nested values for portable substring search."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    try:
        return json.dumps(value, sort_keys=True, default=str).lower()
    except TypeError:
        return str(value).lower()


def _billing_audit_matches_search(entry: BillingAuditLog, search_term: str) -> bool:
    """Best-effort search across common audit fields."""
    if not search_term:
        return True
    haystacks = [
        entry.action.value if hasattr(entry.action, "value") else str(entry.action),
        entry.entity_type or "",
        entry.entity_id or "",
        entry.description or "",
        _json_search_blob(entry.old_value),
        _json_search_blob(entry.new_value),
        _json_search_blob(entry.extra_data),
    ]
    needle = search_term.lower()
    return any(needle in haystack.lower() for haystack in haystacks if haystack)


def _extract_stripe_payload_context(payload: dict | None) -> dict[str, str | None]:
    """Extract account/customer/subscription refs from a Stripe event payload."""
    if not isinstance(payload, dict):
        return {
            "account_id": None,
            "customer": None,
            "subscription": None,
            "object_id": None,
        }

    data = payload.get("data")
    if not isinstance(data, dict):
        data = {}
    event_object = data.get("object")
    if not isinstance(event_object, dict):
        event_object = {}
    metadata = event_object.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    subscription_value = event_object.get("subscription")
    object_id = event_object.get("id")

    return {
        "account_id": str(metadata.get("account_id")) if metadata.get("account_id") else None,
        "customer": str(event_object.get("customer")) if event_object.get("customer") else None,
        "subscription": str(subscription_value) if subscription_value else None,
        "object_id": str(object_id) if object_id else None,
    }


def _match_stripe_event_to_account(
    event: StripeEvent,
    account_id: str,
    stripe_customer_id: str | None,
    stripe_subscription_id: str | None,
) -> tuple[bool, str | None, dict[str, str | None]]:
    """Return whether the Stripe event belongs to the current account."""
    context = _extract_stripe_payload_context(event.payload)

    if context["account_id"] == account_id:
        return True, "metadata.account_id", context
    if stripe_customer_id and context["customer"] == stripe_customer_id:
        return True, "customer", context
    if stripe_subscription_id and context["subscription"] == stripe_subscription_id:
        return True, "subscription", context
    if stripe_subscription_id and context["object_id"] == stripe_subscription_id:
        return True, "object.id", context
    return False, None, context


def _stripe_event_matches_search(
    event: StripeEvent,
    context: dict[str, str | None],
    search_term: str,
) -> bool:
    """Best-effort search across event identifiers and payload content."""
    if not search_term:
        return True
    needle = search_term.lower()
    haystacks = [
        event.event_id,
        event.event_type,
        context.get("account_id") or "",
        context.get("customer") or "",
        context.get("subscription") or "",
        context.get("object_id") or "",
        _json_search_blob(event.payload),
    ]
    return any(needle in haystack.lower() for haystack in haystacks if haystack)


@router.get("/plans", response_model=list[PlanInfo])
def get_plans(
    catalog: str = Query(default="public", pattern="^(public|legacy|all)$"),
) -> list[PlanInfo]:
    """Get available subscription plans."""
    if catalog == "legacy":
        plan_types = LEGACY_PLAN_TYPES
    elif catalog == "all":
        plan_types = PUBLIC_PLAN_TYPES + LEGACY_PLAN_TYPES
    else:
        plan_types = PUBLIC_PLAN_TYPES
    return [PLANS[plan_type] for plan_type in plan_types]


@router.get("/plans/{plan_id}", response_model=PlanInfo)
def get_plan(plan_id: str) -> PlanInfo:
    """Get specific plan details."""
    try:
        plan_type = PlanType(plan_id)
        return PLANS[plan_type]
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )


def _resolve_subscription_billing_cycle(subscription: Subscription) -> str:
    """Infer the current billing cycle from the stored Stripe price reference."""
    stripe_price_id = (subscription.stripe_price_id or "").lower()
    if "yearly" in stripe_price_id or "annual" in stripe_price_id:
        return "yearly"
    return "monthly"


def _serialize_subscription(subscription: Subscription) -> SubscriptionResponse:
    """Return subscription data with billing metadata for frontend billing UI."""
    billing_cycle = _resolve_subscription_billing_cycle(subscription)
    plan_info = PLANS.get(subscription.plan_type)
    current_price = None
    if plan_info is not None:
        current_price = (
            plan_info.price_yearly if billing_cycle == "yearly" else plan_info.price_monthly
        )

    return SubscriptionResponse(
        id=subscription.id,
        account_id=subscription.account_id,
        plan_type=subscription.plan_type,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        locations_limit=subscription.locations_limit,
        posts_per_month=subscription.posts_per_month,
        billing_cycle=billing_cycle,
        current_price=current_price,
        trial_end=subscription.trial_end,
        active_addons=list(subscription.active_addons or []),
        created_at=subscription.created_at,
    )


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> SubscriptionResponse:
    """Get current user's subscription."""
    subscription = db.query(Subscription).filter(
        Subscription.account_id == current_user.id
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    return _serialize_subscription(subscription)


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CheckoutSessionRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> CheckoutSessionResponse:
    """Create a Stripe checkout session for subscription."""
    if request.plan_type == PlanType.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot checkout for free plan",
        )

    billing_service = BillingService(db)

    try:
        checkout_url, session_id = await billing_service.create_checkout_session(
            account_id=current_user.id,
            plan_type=request.plan_type,
            billing_cycle=request.billing_cycle,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        )

    return CheckoutSessionResponse(checkout_url=checkout_url, session_id=session_id)


@router.post("/portal", response_model=PortalSessionResponse)
async def create_portal_session(
    request: PortalSessionRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> PortalSessionResponse:
    """Create a Stripe customer portal session."""
    billing_service = BillingService(db)

    try:
        portal_url = await billing_service.create_portal_session(
            account_id=current_user.id,
            return_url=request.return_url,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create portal session: {str(e)}",
        )

    return PortalSessionResponse(portal_url=portal_url)


@router.get("/dunning-status", response_model=DunningStatusResponse)
def get_dunning_status(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> DunningStatusResponse:
    """Get the current account's dunning status for billing UI."""
    subscription = db.query(Subscription).filter(
        Subscription.account_id == current_user.id
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    dunning_status = DunningService(db).get_dunning_status(subscription)
    return DunningStatusResponse(**dunning_status)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Handle Stripe webhook events.
    
    Deprecated:
    - External Stripe endpoint should use `/webhooks/stripe`
    - This route remains for backward compatibility with older billing flows
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature",
        )

    billing_service = BillingService(db)

    try:
        await billing_service.handle_webhook(payload=payload, sig_header=sig_header)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return {"status": "success"}


@router.post("/cancel")
async def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Cancel current subscription at period end."""
    billing_service = BillingService(db)

    try:
        await billing_service.cancel_subscription(account_id=current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}",
        )

    return {"status": "canceled", "message": "Subscription will be canceled at the end of the billing period"}


@router.post("/reactivate")
async def reactivate_subscription(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Reactivate a canceled subscription."""
    billing_service = BillingService(db)

    try:
        await billing_service.reactivate_subscription(account_id=current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reactivate subscription: {str(e)}",
        )

    return {"status": "reactivated"}


@router.get("/usage", response_model=UsageStats)
def get_usage_stats(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> UsageStats:
    """Get current usage statistics."""
    from datetime import date
    from app.models.location import Location
    from app.models.post import Post

    subscription = db.query(Subscription).filter(
        Subscription.account_id == current_user.id
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    # Count locations
    locations_count = db.query(Location).filter(
        Location.account_id == current_user.id
    ).count()

    # Count posts this month
    first_of_month = date.today().replace(day=1)
    posts_count = db.query(Post).join(Location).filter(
        Location.account_id == current_user.id,
        Post.created_at >= first_of_month,
    ).count()

    account_status = CreditsService(db).get_account_status(str(current_user.id))
    api_call_usage = account_status.get("usage", {}).get("api_calls", {})
    plan_limits = resolve_plan_limits(subscription.plan_type)

    return UsageStats(
        plan=subscription.plan_type.value,
        locations_used=locations_count,
        locations_limit=subscription.locations_limit,
        posts_this_month=posts_count,
        posts_limit=subscription.posts_per_month,
        api_calls_today=int(api_call_usage.get("daily_used", 0)),
        api_calls_limit=plan_limits["api_calls_per_day"],
    )


@router.get("/limits", response_model=PlanLimits)
def get_plan_limits(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> PlanLimits:
    """Get current plan limits."""
    subscription = db.query(Subscription).filter(
        Subscription.account_id == current_user.id
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    plan_info = PLANS.get(subscription.plan_type, PLANS[PlanType.FREE])
    plan_limits = resolve_plan_limits(subscription.plan_type)

    return PlanLimits(
        plan_type=subscription.plan_type,
        locations=subscription.locations_limit,
        posts_per_month=subscription.posts_per_month,
        api_calls_per_day=plan_limits["api_calls_per_day"],
        features=plan_info.features,
    )


@router.get("/payments", response_model=list[PaymentHistoryResponse])
def get_payment_history(
    limit: int = Query(10, le=50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> list[PaymentHistory]:
    """Get payment history."""
    return (
        db.query(PaymentHistory)
        .filter(PaymentHistory.account_id == current_user.id)
        .order_by(PaymentHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/audit", response_model=BillingAuditListResponse)
def get_billing_audit(
    action: BillingAuditAction | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> BillingAuditListResponse:
    """Return recent billing audit entries for the current account."""
    query = db.query(BillingAuditLog).filter(
        BillingAuditLog.account_id == current_user.id
    )
    if action:
        query = query.filter(BillingAuditLog.action == action)

    if search:
        candidate_limit = min(max(limit + offset, 20) * 5, 500)
        recent_entries = (
            query.order_by(BillingAuditLog.created_at.desc())
            .limit(candidate_limit)
            .all()
        )
        filtered_entries = [
            entry
            for entry in recent_entries
            if _billing_audit_matches_search(entry, search)
        ]
        total = len(filtered_entries)
        items = filtered_entries[offset : offset + limit]
    else:
        total = query.count()
        items = (
            query.order_by(BillingAuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    return BillingAuditListResponse(items=items, total=total)


@router.get("/webhook-events", response_model=BillingWebhookEventListResponse)
def get_billing_webhook_events(
    event_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> BillingWebhookEventListResponse:
    """Return recent Stripe webhook receipts associated with the current account."""
    subscription = db.query(Subscription).filter(
        Subscription.account_id == current_user.id
    ).first()
    stripe_customer_id = subscription.stripe_customer_id if subscription else None
    stripe_subscription_id = (
        subscription.stripe_subscription_id if subscription else None
    )

    query = db.query(StripeEvent)
    if event_type:
        query = query.filter(StripeEvent.event_type == event_type)

    candidate_limit = min(max(limit + offset, 20) * 10, 500)
    recent_events = (
        query.order_by(StripeEvent.created_at.desc())
        .limit(candidate_limit)
        .all()
    )

    matched_items: list[dict] = []
    current_account_id = str(current_user.id)
    for event in recent_events:
        is_match, match_source, context = _match_stripe_event_to_account(
            event=event,
            account_id=current_account_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
        )
        if not is_match or not match_source:
            continue
        if not _stripe_event_matches_search(event, context, search or ""):
            continue
        matched_items.append(
            {
                "id": event.id,
                "event_id": event.event_id,
                "event_type": event.event_type,
                "account_match_source": match_source,
                "related_customer": context.get("customer"),
                "related_subscription": context.get("subscription")
                or context.get("object_id"),
                "created_at": event.created_at,
                "processed_at": event.processed_at,
            }
        )

    total = len(matched_items)
    return BillingWebhookEventListResponse(
        items=matched_items[offset : offset + limit],
        total=total,
    )


@router.get("/credits")
def get_credit_status(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """
    Get current credit balance and usage status.
    Credits are reset monthly when subscription payment is processed.
    """
    from app.models.credits import CREDIT_PACKAGES

    account_status = CreditsService(db).get_account_status(str(current_user.id))
    packages = [
        {
            "package_id": pkg_id,
            "credits": amt,
            "price_cents": cents,
            "label": label,
        }
        for pkg_id, (amt, cents, label) in CREDIT_PACKAGES.items()
    ]
    return {
        **account_status,
        "storage_mode": "database_persistent",
        "purchase_available": True,
        "credit_packages": packages,
    }


@router.get("/credits/transactions")
def get_credit_transactions(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> list[dict]:
    """Get credit transaction history."""
    return CreditsService(db).get_transactions(str(current_user.id), limit=limit)


@router.post("/credits/purchase")
def purchase_credits(
    package_id: str = Query(..., description="Credit package ID: credits_50 | credits_100 | credits_250 | credits_500"),
    success_url: str = Query(..., description="URL to redirect to on successful payment"),
    cancel_url: str = Query(..., description="URL to redirect to if user cancels"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """
    Initiate a Stripe Checkout session for a one-time credit purchase.

    Returns a ``checkout_url`` the client must redirect the user to.
    Credits are applied only after Stripe confirms payment via webhook.
    """
    service = CreditsService(db)
    try:
        result = service.create_purchase_checkout(
            account_id=str(current_user.id),
            package_id=package_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    return result


# ============ Feature Access Endpoints ============

@router.get("/features")
def get_account_features(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Get all features available to the current user based on subscription."""
    from app.services.feature_access import FeatureAccessService
    service = FeatureAccessService(db)
    return service.get_account_features(current_user)


@router.get("/features/{feature}")
def check_feature_access(
    feature: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Check if user has access to a specific feature."""
    from app.services.feature_access import FeatureAccessService
    service = FeatureAccessService(db)
    has_access = service.check_feature_access(current_user, feature, raise_exception=False)
    return {"feature": feature, "has_access": has_access}


@router.get("/upgrade-options")
def get_upgrade_options(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Get available upgrade options for the current user."""
    from app.services.feature_access import FeatureAccessService
    service = FeatureAccessService(db)
    return service.get_upgrade_options(current_user)


@router.get("/pricing")
def get_pricing_data() -> dict:
    """Get complete pricing data for frontend display."""
    from app.services.feature_access import get_pricing_data
    return get_pricing_data()


# ============================================
# TRIAL MANAGEMENT
# ============================================

@router.post("/trial/start", response_model=TrialStartResponse)
async def start_trial(
    request: TrialStartRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> TrialStartResponse:
    """Start a 3-day Free-plan preview without a credit card."""
    billing_service = BillingService(db)
    
    try:
        subscription = await billing_service.start_trial(
            account_id=current_user.id,
            plan_type=request.plan_type or FREE_PREVIEW_PLAN,
            trial_days=FREE_PREVIEW_DAYS,
        )
        
        return TrialStartResponse(
            status="trialing",
            plan_type=subscription.plan_type,
            trial_end=subscription.trial_end,
            message=(
                f"Your {FREE_PREVIEW_DAYS}-day free preview has started. "
                "Paid AI, SMS, publishing, and automation features stay locked until you choose a paid plan."
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================
# SUBSCRIPTION PREVIEW & CHANGE
# ============================================

@router.post("/subscription/preview", response_model=SubscriptionPreviewResponse)
async def preview_subscription_change(
    request: SubscriptionPreviewRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> SubscriptionPreviewResponse:
    """Preview subscription change with proration calculation."""
    billing_service = BillingService(db)
    
    try:
        preview = await billing_service.preview_subscription_change(
            account_id=current_user.id,
            new_plan_type=request.new_plan_type,
            new_addons=request.add_ons,
        )
        return SubscriptionPreviewResponse(**preview)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/subscription/change", response_model=SubscriptionResponse)
async def change_subscription(
    request: SubscriptionChangeRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Subscription:
    """Change subscription plan. Upgrades are immediate, downgrades at next billing cycle."""
    billing_service = BillingService(db)
    
    try:
        subscription = await billing_service.change_subscription(
            account_id=current_user.id,
            new_plan_type=request.new_plan_type,
            new_addons=request.add_ons,
            prorate=request.prorate,
        )
        return subscription
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================
# CANCEL / RESUME
# ============================================

@router.post("/subscription/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription_endpoint(
    request: CancelSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> CancelSubscriptionResponse:
    """Cancel subscription. Recommended: cancel at period end."""
    billing_service = BillingService(db)
    
    try:
        result = await billing_service.cancel_subscription_with_reason(
            account_id=current_user.id,
            cancel_at_period_end=request.cancel_at_period_end,
            reason=request.reason,
            feedback=request.feedback,
        )
        return CancelSubscriptionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/subscription/resume", response_model=ResumeSubscriptionResponse)
async def resume_subscription_endpoint(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> ResumeSubscriptionResponse:
    """Resume a subscription scheduled for cancellation."""
    billing_service = BillingService(db)
    
    try:
        result = await billing_service.resume_subscription(account_id=current_user.id)
        return ResumeSubscriptionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================
# INVOICES
# ============================================

@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    status: str = Query(None, description="Filter by status: paid, open, void"),
    from_date: str = Query(None, description="From date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="To date (YYYY-MM-DD)"),
    limit: int = Query(10, le=50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> InvoiceListResponse:
    """List invoices with filtering."""
    from datetime import datetime
    
    billing_service = BillingService(db)
    
    from_dt = datetime.fromisoformat(from_date) if from_date else None
    to_dt = datetime.fromisoformat(to_date) if to_date else None
    
    result = await billing_service.list_invoices(
        account_id=current_user.id,
        status=status,
        from_date=from_dt,
        to_date=to_dt,
        limit=limit,
        offset=offset,
    )
    
    return InvoiceListResponse(**result)


@router.get("/invoices/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Get invoice PDF download URL."""
    billing_service = BillingService(db)
    
    try:
        pdf_url = await billing_service.get_invoice_pdf_url(
            account_id=current_user.id,
            invoice_id=invoice_id,
        )
        return {"pdf_url": pdf_url}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/invoices/{invoice_id}/resend")
async def resend_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Resend invoice email."""
    billing_service = BillingService(db)
    
    try:
        await billing_service.resend_invoice(
            account_id=current_user.id,
            invoice_id=invoice_id,
        )
        return {"success": True, "message": "Invoice sent successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ============================================
# PAYMENT METHODS
# ============================================

@router.get("/payment-methods", response_model=list[PaymentMethodResponse])
async def list_payment_methods(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> list[PaymentMethodResponse]:
    """List customer payment methods."""
    billing_service = BillingService(db)
    
    methods = await billing_service.list_payment_methods(account_id=current_user.id)
    return [PaymentMethodResponse(**m) for m in methods]


@router.post("/payment-methods")
async def add_payment_method(
    request: AddPaymentMethodRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Add a payment method."""
    billing_service = BillingService(db)
    
    try:
        result = await billing_service.add_payment_method(
            account_id=current_user.id,
            payment_method_id=request.payment_method_id,
            set_as_default=request.set_as_default,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/payment-methods/{payment_method_id}")
async def remove_payment_method(
    payment_method_id: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Remove a payment method."""
    billing_service = BillingService(db)
    
    try:
        await billing_service.remove_payment_method(
            account_id=current_user.id,
            payment_method_id=payment_method_id,
        )
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/payment-methods/{payment_method_id}/default")
async def set_default_payment_method(
    payment_method_id: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Set default payment method."""
    billing_service = BillingService(db)
    
    try:
        await billing_service.set_default_payment_method(
            account_id=current_user.id,
            payment_method_id=payment_method_id,
        )
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================
# BILLING INFO
# ============================================

@router.get("/billing-info", response_model=BillingInfoResponse | None)
async def get_billing_info(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> BillingInfoResponse | None:
    """Get billing/tax information."""
    billing_service = BillingService(db)
    
    info = await billing_service.get_billing_info(account_id=current_user.id)
    if not info:
        return None
    return BillingInfoResponse(**info)


@router.put("/billing-info", response_model=BillingInfoResponse)
async def update_billing_info(
    request: BillingInfoRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> BillingInfoResponse:
    """Update billing/tax information."""
    billing_service = BillingService(db)
    
    info = await billing_service.update_billing_info(
        account_id=current_user.id,
        company_name=request.company_name,
        tax_id=request.tax_id,
        tax_id_type=request.tax_id_type,
        address=request.address,
        billing_email=request.billing_email,
    )
    return BillingInfoResponse(**info)


# ============================================
# EXPORT
# ============================================

@router.get("/payments/export")
async def export_payments_csv(
    from_date: str = Query(None, description="From date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="To date (YYYY-MM-DD)"),
    status: str = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Export payment history as CSV."""
    from datetime import datetime
    from fastapi.responses import Response
    
    billing_service = BillingService(db)
    
    from_dt = datetime.fromisoformat(from_date) if from_date else None
    to_dt = datetime.fromisoformat(to_date) if to_date else None
    
    csv_content = await billing_service.export_payments_csv(
        account_id=current_user.id,
        from_date=from_dt,
        to_date=to_dt,
        status=status,
    )
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=payments_{current_user.id}.csv"
        }
    )


# ============================================
# ADD-ONS
# ============================================

@router.get("/addons")
async def list_addons(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """List all available add-ons with current subscription status."""
    from app.models.billing import AddonDefinition, SubscriptionAddon, AddonStatus
    
    # Get subscription
    subscription = db.query(Subscription).filter(
        Subscription.account_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")
    
    # Get all active addon definitions
    addons = db.query(AddonDefinition).filter(
        AddonDefinition.is_active == True
    ).order_by(AddonDefinition.sort_order).all()
    
    # Get currently attached addons
    attached_addons = db.query(SubscriptionAddon).filter(
        SubscriptionAddon.subscription_id == subscription.id,
        SubscriptionAddon.status.in_([AddonStatus.ACTIVE, AddonStatus.PENDING_CANCEL])
    ).all()
    
    attached_ids = {a.addon_id for a in attached_addons}
    pending_cancel_ids = {a.addon_id for a in attached_addons if a.status == AddonStatus.PENDING_CANCEL}
    
    # Plan hierarchy for eligibility check
    plan_order = ["free", "starter", "pro", "premium", "agency"]
    current_plan_index = plan_order.index(subscription.plan_type.value)
    
    result = []
    for addon in addons:
        min_plan_index = plan_order.index(addon.min_plan)
        is_eligible = current_plan_index >= min_plan_index
        
        result.append({
            "id": addon.id,
            "name": addon.name,
            "description": addon.description,
            "price_monthly": float(addon.price_monthly),
            "price_yearly": float(addon.price_yearly),
            "min_plan": addon.min_plan,
            "is_attached": addon.id in attached_ids,
            "is_pending_cancel": addon.id in pending_cancel_ids,
            "is_eligible": is_eligible,
            "feature_flag": addon.feature_flag,
        })
    
    return {
        "addons": result,
        "current_plan": subscription.plan_type.value,
        "active_addon_ids": list(attached_ids),
    }


@router.post("/addons/preview")
async def preview_addon_attachment(
    addon_id: str = Query(..., description="Add-on ID to preview"),
    action: str = Query("attach", description="Action: attach or detach"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Preview the cost of attaching or detaching an add-on."""
    from app.models.billing import AddonDefinition, SubscriptionAddon, AddonStatus
    import stripe
    from app.core.config import settings
    
    stripe.api_key = settings.stripe_secret_key
    
    subscription = db.query(Subscription).filter(
        Subscription.account_id == current_user.id
    ).first()
    
    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active Stripe subscription")
    
    addon = db.query(AddonDefinition).filter(AddonDefinition.id == addon_id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add-on not found")
    
    # Check eligibility
    plan_order = ["free", "starter", "pro", "premium", "agency"]
    current_plan_index = plan_order.index(subscription.plan_type.value)
    min_plan_index = plan_order.index(addon.min_plan)
    
    if current_plan_index < min_plan_index:
        raise HTTPException(
            status_code=400, 
            detail=f"This add-on requires {addon.min_plan.title()} plan or higher"
        )
    
    # Check if already attached
    existing = db.query(SubscriptionAddon).filter(
        SubscriptionAddon.subscription_id == subscription.id,
        SubscriptionAddon.addon_id == addon_id,
        SubscriptionAddon.status == AddonStatus.ACTIVE
    ).first()
    
    if action == "attach" and existing:
        raise HTTPException(status_code=400, detail="Add-on already attached")
    if action == "detach" and not existing:
        raise HTTPException(status_code=400, detail="Add-on not attached")
    
    # Get Stripe price ID based on subscription interval
    stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
    is_yearly = stripe_sub.items.data[0].price.recurring.interval == "year"
    price_id = addon.stripe_price_id_yearly if is_yearly else addon.stripe_price_id_monthly
    
    if not price_id:
        # Return estimate without Stripe preview
        return {
            "addon_id": addon_id,
            "action": action,
            "proration_amount": float(addon.price_monthly) if action == "attach" else 0,
            "next_invoice_amount": None,
            "next_invoice_date": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "note": "Stripe price not configured - estimate only"
        }
    
    try:
        if action == "attach":
            # Preview adding the item
            upcoming = stripe.Invoice.upcoming(
                customer=subscription.stripe_customer_id,
                subscription=subscription.stripe_subscription_id,
                subscription_items=[
                    {"price": price_id, "quantity": 1}
                ],
                subscription_proration_behavior="create_prorations",
            )
        else:
            # Preview removing the item
            upcoming = stripe.Invoice.upcoming(
                customer=subscription.stripe_customer_id,
                subscription=subscription.stripe_subscription_id,
            )
        
        return {
            "addon_id": addon_id,
            "action": action,
            "proration_amount": upcoming.amount_due / 100,
            "next_invoice_amount": upcoming.total / 100,
            "next_invoice_date": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/addons/attach")
async def attach_addon(
    addon_id: str = Query(..., description="Add-on ID to attach"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Attach an add-on to the current subscription."""
    from app.models.billing import AddonDefinition, SubscriptionAddon, AddonStatus
    import stripe
    from app.core.config import settings
    from datetime import datetime, timezone
    
    stripe.api_key = settings.stripe_secret_key
    
    subscription = db.query(Subscription).filter(
        Subscription.account_id == current_user.id
    ).first()
    
    if not subscription or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No active Stripe subscription")
    
    addon = db.query(AddonDefinition).filter(AddonDefinition.id == addon_id).first()
    if not addon:
        raise HTTPException(status_code=404, detail="Add-on not found")
    
    # Check eligibility
    plan_order = ["free", "starter", "pro", "premium", "agency"]
    current_plan_index = plan_order.index(subscription.plan_type.value)
    min_plan_index = plan_order.index(addon.min_plan)
    
    if current_plan_index < min_plan_index:
        raise HTTPException(
            status_code=400, 
            detail=f"This add-on requires {addon.min_plan.title()} plan or higher"
        )
    
    # Check if already attached
    existing = db.query(SubscriptionAddon).filter(
        SubscriptionAddon.subscription_id == subscription.id,
        SubscriptionAddon.addon_id == addon_id,
        SubscriptionAddon.status.in_([AddonStatus.ACTIVE, AddonStatus.PENDING_CANCEL])
    ).first()
    
    if existing:
        if existing.status == AddonStatus.PENDING_CANCEL:
            # Reactivate
            existing.status = AddonStatus.ACTIVE
            existing.cancel_at = None
            db.commit()
            return {"success": True, "message": "Add-on reactivated", "addon_id": addon_id}
        raise HTTPException(status_code=400, detail="Add-on already attached")
    
    # Get Stripe price ID
    stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
    is_yearly = stripe_sub.items.data[0].price.recurring.interval == "year"
    price_id = addon.stripe_price_id_yearly if is_yearly else addon.stripe_price_id_monthly
    
    stripe_item_id = None
    charged_amount = 0
    
    if price_id:
        try:
            # Add to Stripe subscription
            item = stripe.SubscriptionItem.create(
                subscription=subscription.stripe_subscription_id,
                price=price_id,
                quantity=1,
                proration_behavior="create_prorations",
            )
            stripe_item_id = item.id
            
            # Get the prorated charge amount
            invoices = stripe.Invoice.list(
                subscription=subscription.stripe_subscription_id,
                limit=1,
            )
            if invoices.data:
                charged_amount = invoices.data[0].amount_due / 100
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # Create subscription addon record
    sub_addon = SubscriptionAddon(
        subscription_id=subscription.id,
        addon_id=addon_id,
        stripe_subscription_item_id=stripe_item_id,
        status=AddonStatus.ACTIVE,
        attached_at=datetime.now(timezone.utc),
    )
    db.add(sub_addon)
    
    # Update active_addons JSON field
    if subscription.active_addons is None:
        subscription.active_addons = []
    if addon.feature_flag and addon.feature_flag not in subscription.active_addons:
        subscription.active_addons = subscription.active_addons + [addon.feature_flag]
    
    db.commit()
    
    return {
        "success": True,
        "addon_id": addon_id,
        "subscription_item_id": stripe_item_id,
        "charged_amount": charged_amount,
        "effective_date": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/addons/detach")
async def detach_addon(
    addon_id: str = Query(..., description="Add-on ID to detach"),
    immediate: bool = Query(False, description="Remove immediately vs at period end"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Detach an add-on from the current subscription."""
    from app.models.billing import AddonDefinition, SubscriptionAddon, AddonStatus
    import stripe
    from app.core.config import settings
    from datetime import datetime, timezone
    
    stripe.api_key = settings.stripe_secret_key
    
    subscription = db.query(Subscription).filter(
        Subscription.account_id == current_user.id
    ).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")
    
    # Find attached addon
    sub_addon = db.query(SubscriptionAddon).filter(
        SubscriptionAddon.subscription_id == subscription.id,
        SubscriptionAddon.addon_id == addon_id,
        SubscriptionAddon.status == AddonStatus.ACTIVE
    ).first()
    
    if not sub_addon:
        raise HTTPException(status_code=404, detail="Add-on not attached")
    
    addon = db.query(AddonDefinition).filter(AddonDefinition.id == addon_id).first()
    
    if immediate and sub_addon.stripe_subscription_item_id:
        try:
            # Remove from Stripe immediately
            stripe.SubscriptionItem.delete(
                sub_addon.stripe_subscription_item_id,
                proration_behavior="create_prorations",
            )
            sub_addon.status = AddonStatus.CANCELED
            sub_addon.canceled_at = datetime.now(timezone.utc)
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # Mark as pending cancel - will be removed at period end
        sub_addon.status = AddonStatus.PENDING_CANCEL
        sub_addon.cancel_at = subscription.current_period_end
        
        if sub_addon.stripe_subscription_item_id:
            try:
                # Tell Stripe to cancel at period end by setting quantity to 0 at renewal
                # Note: Stripe handles this via subscription update with cancel_at_period_end on item
                stripe.SubscriptionItem.modify(
                    sub_addon.stripe_subscription_item_id,
                    metadata={"cancel_at_period_end": "true"}
                )
            except stripe.error.StripeError:
                pass  # Best effort
    
    # Update active_addons JSON field
    if addon and addon.feature_flag and subscription.active_addons:
        subscription.active_addons = [
            f for f in subscription.active_addons if f != addon.feature_flag
        ]
    
    db.commit()
    
    return {
        "success": True,
        "addon_id": addon_id,
        "immediate": immediate,
        "end_date": sub_addon.cancel_at.isoformat() if sub_addon.cancel_at else None,
    }
