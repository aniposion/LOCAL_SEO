"""Billing router."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.subscription import PaymentHistory, PlanType, Subscription
from app.routers.deps import get_current_user
from app.schemas.subscription import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PaymentHistoryResponse,
    PlanInfo,
    PlanLimits,
    PortalSessionRequest,
    PortalSessionResponse,
    SubscriptionResponse,
    UsageStats,
)
from app.services.billing import BillingService
from app.services.credits import credits_service, PlanTier

router = APIRouter(prefix="/billing", tags=["billing"])

# Plan definitions - Updated pricing v1.0
PLANS = {
    PlanType.FREE: PlanInfo(
        id="free",
        name="Free",
        price_monthly=0,
        price_yearly=0,
        features=[
            "기본 대시보드",
        ],
        limits={"locations": 1, "posts_per_month": 0, "api_calls_per_day": 10},
    ),
    PlanType.STARTER: PlanInfo(
        id="starter",
        name="Starter",
        price_monthly=99,
        price_yearly=990,
        features=[
            "Google Maps 포스트 자동 생성 & 업로드",
            "리뷰 자동 수집 + AI 답변 초안",
            "기본 KPI 대시보드 (Calls, Directions, Reviews)",
            "주간 리포트",
        ],
        limits={"locations": 1, "posts_per_month": 30, "api_calls_per_day": 500},
    ),
    PlanType.PRO: PlanInfo(
        id="pro",
        name="Pro",
        price_monthly=149,
        price_yearly=1490,
        features=[
            "Starter 기능 전부",
            "Instagram 자동 업로드",
            "콘텐츠 예약 (Scheduler)",
            "Q&A 자동 응답 초안",
            "리뷰 트렌드 분석 (경쟁사 포함)",
            "Website SEO 기본 (메타태그 자동 생성)",
        ],
        limits={"locations": 1, "posts_per_month": 60, "api_calls_per_day": 2000},
    ),
    PlanType.PREMIUM: PlanInfo(
        id="premium",
        name="Premium",
        price_monthly=249,
        price_yearly=2490,
        features=[
            "Pro 기능 전부",
            "Missed Call Text Back",
            "Review Booster (SMS/Email 리뷰 요청)",
            "Website SEO Full (키워드 분석 + 블로그 자동 생성)",
            "Social Auto-Responder (DM/댓글 자동 응답)",
        ],
        limits={"locations": 1, "posts_per_month": 120, "api_calls_per_day": 5000},
    ),
    PlanType.AGENCY: PlanInfo(
        id="agency",
        name="Agency",
        price_monthly=499,
        price_yearly=4990,
        features=[
            "Premium 기능 전부",
            "White Label 보고서",
            "팀 계정 권한 관리",
            "대시보드 통합",
            "다중 매장 운영 (프랜차이즈용)",
            "작업 자동 배포",
            "Video Generator",
        ],
        limits={"locations": -1, "posts_per_month": -1, "api_calls_per_day": -1},
    ),
}


@router.get("/plans", response_model=list[PlanInfo])
def get_plans() -> list[PlanInfo]:
    """Get available subscription plans."""
    return list(PLANS.values())


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


@router.get("/subscription", response_model=SubscriptionResponse)
def get_subscription(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Subscription:
    """Get current user's subscription."""
    subscription = db.query(Subscription).filter(
        Subscription.account_id == current_user.id
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    return subscription


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


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Handle Stripe webhook events."""
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
    from datetime import date, timedelta
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

    return UsageStats(
        locations_used=locations_count,
        locations_limit=subscription.locations_limit,
        posts_this_month=posts_count,
        posts_limit=subscription.posts_per_month,
        api_calls_today=0,  # Would need to implement API call tracking
        api_calls_limit=subscription.api_calls_per_day,
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

    return PlanLimits(
        plan_type=subscription.plan_type,
        locations=subscription.locations_limit,
        posts_per_month=subscription.posts_per_month,
        api_calls_per_day=subscription.api_calls_per_day,
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


@router.get("/credits")
def get_credit_status(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """
    Get current credit balance and usage status.
    Credits are reset monthly when subscription payment is processed.
    """
    account_status = credits_service.get_account_status(str(current_user.id))
    return account_status


@router.get("/credits/transactions")
def get_credit_transactions(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> list[dict]:
    """Get credit transaction history."""
    return credits_service.get_transactions(str(current_user.id), limit=limit)


@router.post("/credits/purchase")
def purchase_credits(
    amount: int = Query(..., ge=10, le=10000),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """
    Purchase additional credits.
    These credits do NOT reset monthly - they carry over.
    """
    # In production, this would integrate with Stripe for payment
    result = credits_service.purchase_credits(
        account_id=str(current_user.id),
        amount=amount,
        payment_id=f"demo_{current_user.id}_{amount}",
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
