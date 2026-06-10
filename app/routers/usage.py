"""
Usage and Credits Router
Rate limiting, quota management, and credit system
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.routers.deps import get_current_account, get_db
from app.models.account import Account
from app.models.credits import (
    CreditPurchaseOrder,
    CreditPurchaseStatus,
    CreditTransaction as CreditTransactionModel,
)
from app.models.subscription import PlanType
from app.services.usage_limiter import (
    UsageType,
)
from app.services.credits import CreditsService, PlanTier as CreditPlanTier, PLAN_CREDITS
from app.models.subscription import PLAN_PRICES

router = APIRouter(prefix="/usage", tags=["Usage & Credits"])

PLAN_TO_CREDIT_TIER = {
    PlanType.FREE: CreditPlanTier.FREE,
    PlanType.MAPS_STARTER: CreditPlanTier.STARTER,
    PlanType.CALLS_GROWTH: CreditPlanTier.PROFESSIONAL,
    PlanType.COMPETITIVE_MARKET: CreditPlanTier.AGENCY,
    PlanType.STARTER: CreditPlanTier.STARTER,
    PlanType.PRO: CreditPlanTier.PROFESSIONAL,
    PlanType.PREMIUM: CreditPlanTier.PROFESSIONAL,
    PlanType.AGENCY: CreditPlanTier.AGENCY,
    PlanType.ENTERPRISE: CreditPlanTier.AGENCY,
}


def _usage_status_for_account(db: Session, account: Account) -> dict:
    return CreditsService(db).get_account_status(str(account.id))


# ============ Schemas ============

class UsageTypeDetail(BaseModel):
    daily_used: int
    daily_limit: int
    daily_remaining: int
    monthly_used: int
    monthly_limit: int
    monthly_remaining: int
    cooldown_seconds: int
    overage_cost_cents: int


class UsageSummaryResponse(BaseModel):
    plan: str
    usage: dict[str, UsageTypeDetail]


class CreditBalance(BaseModel):
    total_credits: int
    used_credits: int
    remaining_credits: int
    bonus_credits: int
    expires_at: Optional[datetime] = None


class CreditTransaction(BaseModel):
    id: str
    type: str  # purchase, usage, bonus, refund
    amount: int
    description: str
    usage_type: Optional[str] = None
    created_at: datetime


class CreditHistoryResponse(BaseModel):
    transactions: list[CreditTransaction]
    total: int


class PurchaseCreditsRequest(BaseModel):
    package_id: str  # e.g. credits_50, credits_100, credits_250, credits_500
    success_url: str
    cancel_url: str


class PurchaseCreditsResponse(BaseModel):
    checkout_url: str
    session_id: str
    order_id: str
    credits_amount: int
    price_cents: int


class CreditPurchaseOrderOut(BaseModel):
    id: str
    package_id: str
    credits_amount: int
    price_cents: int
    status: str
    stripe_session_id: str
    stripe_payment_intent_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None


class CreditPurchaseOrdersResponse(BaseModel):
    orders: list[CreditPurchaseOrderOut]
    total: int


class UsageLimitsResponse(BaseModel):
    sms: dict
    ai_content: dict
    ai_image: dict
    ai_response: dict


# ============ Endpoints ============

@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get usage summary for current account."""
    summary = _usage_status_for_account(db, account)
    return UsageSummaryResponse(
        plan=summary["plan"],
        usage={
            k: UsageTypeDetail(
                daily_used=v["daily_used"],
                daily_limit=v["daily_limit"],
                daily_remaining=v["daily_remaining"],
                monthly_used=v["monthly_used"],
                monthly_limit=v["monthly_limit"],
                monthly_remaining=v["monthly_remaining"],
                cooldown_seconds=v.get("cooldown_seconds", 0),
                overage_cost_cents=v.get("credit_cost", 0),
            )
            for k, v in summary["usage"].items()
        }
    )


@router.get("/limits", response_model=UsageLimitsResponse)
async def get_usage_limits(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get usage limits for current account's plan."""
    summary = _usage_status_for_account(db, account)
    return UsageLimitsResponse(
        sms=summary["usage"].get("sms", {}),
        ai_content=summary["usage"].get("ai_content", {}),
        ai_image=summary["usage"].get("ai_image", {}),
        ai_response=summary["usage"].get("ai_response", {}),
    )


@router.get("/credits", response_model=CreditBalance)
async def get_credit_balance(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get credit balance for current account."""
    status = CreditsService(db).get_account_status(str(account.id))
    credits = status["credits"]
    return CreditBalance(
        total_credits=credits["total_available"],
        used_credits=status["stats"]["total_used"],
        remaining_credits=credits["total_available"],
        bonus_credits=credits["bonus_balance"],
        expires_at=None,
    )


@router.get("/credits/history", response_model=CreditHistoryResponse)
async def get_credit_history(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get credit transaction history."""
    total = (
        db.query(CreditTransactionModel)
        .filter(CreditTransactionModel.account_id == account.id)
        .count()
    )
    transactions = [
        CreditTransaction(**transaction)
        for transaction in CreditsService(db).get_transactions(
            str(account.id),
            limit=limit,
            offset=offset,
        )
    ]
    
    return CreditHistoryResponse(
        transactions=transactions,
        total=total,
    )


@router.post("/credits/purchase", response_model=PurchaseCreditsResponse)
async def purchase_credits(
    request: PurchaseCreditsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Initiate a Stripe Checkout session for a credit package purchase.

    Returns a ``checkout_url``; redirect the user there.
    Credits are applied only after Stripe confirms payment via webhook.
    """
    service = CreditsService(db)
    try:
        result = service.create_purchase_checkout(
            account_id=str(account.id),
            package_id=request.package_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    return result


@router.get("/credits/orders", response_model=CreditPurchaseOrdersResponse)
async def get_credit_orders(
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return the current account's credit purchase order history.

    Statuses: pending, completed, canceled, expired, refunded.
    """
    query = (
        db.query(CreditPurchaseOrder)
        .filter(CreditPurchaseOrder.account_id == account.id)
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

    total = query.count()
    orders = (
        query
        .order_by(CreditPurchaseOrder.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return CreditPurchaseOrdersResponse(
        orders=[
            CreditPurchaseOrderOut(
                id=str(o.id),
                package_id=o.package_id,
                credits_amount=o.credits_amount,
                price_cents=o.price_cents,
                status=o.status.value,
                stripe_session_id=o.stripe_session_id,
                stripe_payment_intent_id=o.stripe_payment_intent_id,
                created_at=o.created_at,
                completed_at=o.completed_at,
                refunded_at=o.refunded_at,
            )
            for o in orders
        ],
        total=total,
    )


@router.post("/check/{usage_type}")
async def check_usage_allowed(
    usage_type: str,
    count: int = 1,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Check if a specific usage is allowed."""
    try:
        ut = UsageType(usage_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid usage type: {usage_type}",
        )

    try:
        result = CreditsService(db).preview_usage(str(account.id), ut.value, count)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "allowed": result["allowed"],
        "reason": result["reason"],
        "remaining_daily": result["remaining_daily"],
        "remaining_monthly": result["remaining_monthly"],
        "cooldown_remaining_seconds": result["cooldown_remaining_seconds"],
        "overage_available": result["overage_available"],
        "overage_cost_cents": result["overage_cost_cents"],
    }


# ============ Plan Pricing Info ============

PLAN_DISPLAY_NAMES = {
    PlanType.FREE: "Free",
    PlanType.MAPS_STARTER: "Maps Starter",
    PlanType.CALLS_GROWTH: "Calls Growth",
    PlanType.COMPETITIVE_MARKET: "Competitive Market",
    PlanType.STARTER: "Starter",
    PlanType.PRO: "Pro",
    PlanType.PREMIUM: "Premium",
    PlanType.AGENCY: "Agency",
    PlanType.ENTERPRISE: "Enterprise",
}


def _serialize_usage_plan(plan_type: PlanType) -> dict:
    usage_tier = PLAN_TO_CREDIT_TIER[plan_type]
    limits = PLAN_CREDITS[usage_tier]
    return {
        "name": PLAN_DISPLAY_NAMES[plan_type],
        "price_monthly": PLAN_PRICES[plan_type],
        "sms_daily": limits["sms_daily"],
        "sms_monthly": limits["sms_monthly"],
        "ai_content_daily": limits["ai_content_daily"],
        "ai_content_monthly": limits["ai_content_monthly"],
        "ai_image_daily": limits["ai_image_daily"],
        "ai_image_monthly": limits["ai_image_monthly"],
        "ai_response_daily": limits["ai_response_daily"],
        "ai_response_monthly": limits["ai_response_monthly"],
        "api_calls_daily": limits["api_calls_daily"],
        "api_calls_monthly": limits["api_calls_monthly"],
    }


PLAN_PRICING = {
    plan_type.value: _serialize_usage_plan(plan_type)
    for plan_type in (
        PlanType.FREE,
        PlanType.MAPS_STARTER,
        PlanType.CALLS_GROWTH,
        PlanType.COMPETITIVE_MARKET,
        PlanType.STARTER,
        PlanType.PRO,
        PlanType.PREMIUM,
        PlanType.AGENCY,
        PlanType.ENTERPRISE,
    )
}


@router.get("/plans")
async def get_plan_limits():
    """Get usage limits for all plans."""
    return {"plans": PLAN_PRICING}
