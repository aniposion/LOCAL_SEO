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
from app.services.usage_limiter import (
    UsageLimiterService,
    UsageType,
    PlanTier,
    usage_limiter,
)

router = APIRouter(prefix="/usage", tags=["Usage & Credits"])


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
    amount: int  # Number of credits to purchase
    payment_method_id: Optional[str] = None


class PurchaseCreditsResponse(BaseModel):
    success: bool
    credits_added: int
    new_balance: int
    charge_amount_cents: int


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
    summary = usage_limiter.get_usage_summary(str(account.id))
    return UsageSummaryResponse(
        plan=summary["plan"],
        usage={
            k: UsageTypeDetail(**v) for k, v in summary["usage"].items()
        }
    )


@router.get("/limits", response_model=UsageLimitsResponse)
async def get_usage_limits(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get usage limits for current account's plan."""
    summary = usage_limiter.get_usage_summary(str(account.id))
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
    # In production, fetch from database
    # Demo data
    return CreditBalance(
        total_credits=100,
        used_credits=23,
        remaining_credits=77,
        bonus_credits=10,
        expires_at=datetime.now().replace(month=12, day=31),
    )


@router.get("/credits/history", response_model=CreditHistoryResponse)
async def get_credit_history(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get credit transaction history."""
    # Demo data
    transactions = [
        CreditTransaction(
            id="tx1",
            type="purchase",
            amount=100,
            description="Purchased 100 credits",
            created_at=datetime.now(),
        ),
        CreditTransaction(
            id="tx2",
            type="usage",
            amount=-5,
            description="AI Image Generation",
            usage_type="ai_image",
            created_at=datetime.now(),
        ),
        CreditTransaction(
            id="tx3",
            type="usage",
            amount=-3,
            description="AI Content Generation",
            usage_type="ai_content",
            created_at=datetime.now(),
        ),
        CreditTransaction(
            id="tx4",
            type="bonus",
            amount=10,
            description="Welcome bonus credits",
            created_at=datetime.now(),
        ),
    ]
    
    return CreditHistoryResponse(
        transactions=transactions[offset:offset+limit],
        total=len(transactions),
    )


@router.post("/credits/purchase", response_model=PurchaseCreditsResponse)
async def purchase_credits(
    request: PurchaseCreditsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Purchase additional credits."""
    if request.amount < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Minimum purchase is 10 credits",
        )
    
    if request.amount > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum purchase is 10,000 credits",
        )
    
    # Credit pricing: $0.10 per credit (10 cents)
    charge_amount_cents = request.amount * 10
    
    # In production, process payment via Stripe
    # For now, simulate success
    
    return PurchaseCreditsResponse(
        success=True,
        credits_added=request.amount,
        new_balance=77 + request.amount,  # Demo: 77 + purchased
        charge_amount_cents=charge_amount_cents,
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
    
    result = usage_limiter.check_usage(str(account.id), ut, count)
    
    return {
        "allowed": result.allowed,
        "reason": result.reason,
        "remaining_daily": result.remaining_daily,
        "remaining_monthly": result.remaining_monthly,
        "cooldown_remaining_seconds": result.cooldown_remaining_seconds,
        "overage_available": result.overage_available,
        "overage_cost_cents": result.overage_cost_cents,
    }


# ============ Plan Pricing Info ============

PLAN_PRICING = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "sms_daily": 10,
        "sms_monthly": 50,
        "ai_content_daily": 5,
        "ai_content_monthly": 30,
        "ai_image_daily": 3,
        "ai_image_monthly": 20,
    },
    "starter": {
        "name": "Starter",
        "price_monthly": 29,
        "sms_daily": 50,
        "sms_monthly": 500,
        "ai_content_daily": 20,
        "ai_content_monthly": 200,
        "ai_image_daily": 15,
        "ai_image_monthly": 150,
    },
    "professional": {
        "name": "Professional",
        "price_monthly": 99,
        "sms_daily": 200,
        "sms_monthly": 2000,
        "ai_content_daily": 50,
        "ai_content_monthly": 500,
        "ai_image_daily": 50,
        "ai_image_monthly": 500,
    },
    "agency": {
        "name": "Agency",
        "price_monthly": 299,
        "sms_daily": 1000,
        "sms_monthly": 10000,
        "ai_content_daily": 200,
        "ai_content_monthly": 2000,
        "ai_image_daily": 200,
        "ai_image_monthly": 2000,
    },
}


@router.get("/plans")
async def get_plan_limits():
    """Get usage limits for all plans."""
    return {"plans": PLAN_PRICING}
