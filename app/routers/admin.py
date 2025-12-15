"""
Admin Router
Manage users, credits, usage limits, and system settings
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.routers.deps import get_current_account, get_db
from app.models.account import Account
from app.services.usage_limiter import (
    UsageLimiterService,
    UsageType,
    PlanTier,
    usage_limiter,
    PLAN_LIMITS,
)
from app.services.credits import credits_service, PlanTier as CreditPlanTier

router = APIRouter(prefix="/admin", tags=["Admin"])


# ============ Schemas ============

class UserSummary(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    plan: str
    credits: int
    status: str
    created_at: datetime
    last_login: Optional[datetime] = None


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
    plan: str  # free, starter, professional, agency


class UpdateUserLimitsRequest(BaseModel):
    sms_daily: Optional[int] = None
    sms_monthly: Optional[int] = None
    ai_content_daily: Optional[int] = None
    ai_content_monthly: Optional[int] = None
    ai_image_daily: Optional[int] = None
    ai_image_monthly: Optional[int] = None
    ai_response_daily: Optional[int] = None
    ai_response_monthly: Optional[int] = None


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
    type: str  # grant, usage, purchase, bonus, refund
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


# ============ In-Memory Storage (Demo) ============

# Demo user data
DEMO_USERS = {
    "user1": {
        "id": "user1",
        "email": "kim@koreanbbq.com",
        "full_name": "김사장",
        "plan": "starter",
        "credits": 77,
        "bonus_credits": 10,
        "status": "active",
        "created_at": datetime.now() - timedelta(days=30),
        "last_login": datetime.now() - timedelta(hours=2),
        "custom_limits": None,
    },
    "user2": {
        "id": "user2",
        "email": "lee@sushiplace.com",
        "full_name": "이대표",
        "plan": "professional",
        "credits": 250,
        "bonus_credits": 0,
        "status": "active",
        "created_at": datetime.now() - timedelta(days=60),
        "last_login": datetime.now() - timedelta(days=1),
        "custom_limits": None,
    },
    "user3": {
        "id": "user3",
        "email": "park@cafeseoul.com",
        "full_name": "박매니저",
        "plan": "free",
        "credits": 0,
        "bonus_credits": 5,
        "status": "active",
        "created_at": datetime.now() - timedelta(days=7),
        "last_login": datetime.now(),
        "custom_limits": None,
    },
    "user4": {
        "id": "user4",
        "email": "choi@agency.com",
        "full_name": "최에이전시",
        "plan": "agency",
        "credits": 500,
        "bonus_credits": 50,
        "status": "active",
        "created_at": datetime.now() - timedelta(days=90),
        "last_login": datetime.now() - timedelta(hours=5),
        "custom_limits": {
            "sms_daily": 2000,
            "ai_image_daily": 300,
        },
    },
    "user5": {
        "id": "user5",
        "email": "inactive@test.com",
        "full_name": "비활성 유저",
        "plan": "starter",
        "credits": 100,
        "bonus_credits": 0,
        "status": "suspended",
        "created_at": datetime.now() - timedelta(days=45),
        "last_login": datetime.now() - timedelta(days=30),
        "custom_limits": None,
    },
}

CREDIT_TRANSACTIONS: list[dict] = [
    {
        "id": "tx1",
        "user_id": "user1",
        "user_email": "kim@koreanbbq.com",
        "type": "grant",
        "amount": 100,
        "reason": "Monthly credit allocation",
        "admin_id": "admin1",
        "created_at": datetime.now() - timedelta(days=1),
    },
    {
        "id": "tx2",
        "user_id": "user1",
        "user_email": "kim@koreanbbq.com",
        "type": "usage",
        "amount": -23,
        "reason": "AI image generation overage",
        "admin_id": None,
        "created_at": datetime.now() - timedelta(hours=5),
    },
    {
        "id": "tx3",
        "user_id": "user2",
        "user_email": "lee@sushiplace.com",
        "type": "purchase",
        "amount": 250,
        "reason": "Credit purchase",
        "admin_id": None,
        "created_at": datetime.now() - timedelta(days=3),
    },
]


# ============ Helper Functions ============

def check_admin(account: Account) -> bool:
    """Check if user is admin. In production, check role/permission."""
    # For demo, allow all authenticated users
    # In production: return account.role == "admin"
    return True


# ============ Endpoints ============

@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    plan: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """List all users with pagination and filters."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = list(DEMO_USERS.values())
    
    # Apply filters
    if search:
        search_lower = search.lower()
        users = [u for u in users if search_lower in u["email"].lower() or 
                 (u["full_name"] and search_lower in u["full_name"].lower())]
    
    if plan:
        users = [u for u in users if u["plan"] == plan]
    
    if status:
        users = [u for u in users if u["status"] == status]
    
    total = len(users)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = users[start:end]
    
    return UserListResponse(
        users=[UserSummary(
            id=u["id"],
            email=u["email"],
            full_name=u["full_name"],
            plan=u["plan"],
            credits=u["credits"] + u["bonus_credits"],
            status=u["status"],
            created_at=u["created_at"],
            last_login=u["last_login"],
        ) for u in paginated],
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
    """Get detailed user information."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if user_id not in DEMO_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = DEMO_USERS[user_id]
    
    # Get usage data
    usage_summary = usage_limiter.get_usage_summary(user_id)
    
    return UserDetail(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        plan=user["plan"],
        credits=user["credits"],
        bonus_credits=user["bonus_credits"],
        status=user["status"],
        created_at=user["created_at"],
        last_login=user["last_login"],
        usage=usage_summary["usage"],
        custom_limits=user["custom_limits"],
    )


@router.post("/users/{user_id}/credits")
async def update_user_credits(
    user_id: str,
    request: UpdateUserCreditsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Add or remove credits from a user."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if user_id not in DEMO_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = DEMO_USERS[user_id]
    old_credits = user["credits"]
    user["credits"] = max(0, user["credits"] + request.credits)
    
    # Log transaction
    CREDIT_TRANSACTIONS.append({
        "id": f"tx{len(CREDIT_TRANSACTIONS)+1}",
        "user_id": user_id,
        "user_email": user["email"],
        "type": "grant" if request.credits > 0 else "deduct",
        "amount": request.credits,
        "reason": request.reason,
        "admin_id": str(account.id),
        "created_at": datetime.now(),
    })
    
    return {
        "success": True,
        "old_credits": old_credits,
        "new_credits": user["credits"],
        "change": request.credits,
    }


@router.post("/users/{user_id}/plan")
async def update_user_plan(
    user_id: str,
    request: UpdateUserPlanRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Change user's plan."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if user_id not in DEMO_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    valid_plans = ["free", "starter", "professional", "agency"]
    if request.plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Must be one of: {valid_plans}")
    
    user = DEMO_USERS[user_id]
    old_plan = user["plan"]
    user["plan"] = request.plan
    
    # Update usage limiter
    usage_limiter.set_account_plan(user_id, PlanTier(request.plan))
    
    return {
        "success": True,
        "old_plan": old_plan,
        "new_plan": request.plan,
    }


@router.post("/users/{user_id}/limits")
async def update_user_limits(
    user_id: str,
    request: UpdateUserLimitsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Set custom usage limits for a user."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if user_id not in DEMO_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = DEMO_USERS[user_id]
    
    # Build custom limits dict
    custom_limits = {}
    if request.sms_daily is not None:
        custom_limits["sms_daily"] = request.sms_daily
    if request.sms_monthly is not None:
        custom_limits["sms_monthly"] = request.sms_monthly
    if request.ai_content_daily is not None:
        custom_limits["ai_content_daily"] = request.ai_content_daily
    if request.ai_content_monthly is not None:
        custom_limits["ai_content_monthly"] = request.ai_content_monthly
    if request.ai_image_daily is not None:
        custom_limits["ai_image_daily"] = request.ai_image_daily
    if request.ai_image_monthly is not None:
        custom_limits["ai_image_monthly"] = request.ai_image_monthly
    if request.ai_response_daily is not None:
        custom_limits["ai_response_daily"] = request.ai_response_daily
    if request.ai_response_monthly is not None:
        custom_limits["ai_response_monthly"] = request.ai_response_monthly
    
    user["custom_limits"] = custom_limits if custom_limits else None
    
    return {
        "success": True,
        "custom_limits": user["custom_limits"],
    }


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Suspend a user account."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if user_id not in DEMO_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    DEMO_USERS[user_id]["status"] = "suspended"
    
    return {"success": True, "status": "suspended"}


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Activate a suspended user account."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if user_id not in DEMO_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    DEMO_USERS[user_id]["status"] = "active"
    
    return {"success": True, "status": "active"}


@router.post("/credits/grant")
async def grant_credits(
    request: GrantCreditsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Grant credits to a single user."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if request.user_id not in DEMO_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = DEMO_USERS[request.user_id]
    
    if request.is_bonus:
        user["bonus_credits"] += request.amount
    else:
        user["credits"] += request.amount
    
    CREDIT_TRANSACTIONS.append({
        "id": f"tx{len(CREDIT_TRANSACTIONS)+1}",
        "user_id": request.user_id,
        "user_email": user["email"],
        "type": "bonus" if request.is_bonus else "grant",
        "amount": request.amount,
        "reason": request.reason,
        "admin_id": str(account.id),
        "created_at": datetime.now(),
    })
    
    return {
        "success": True,
        "user_id": request.user_id,
        "credits_added": request.amount,
        "is_bonus": request.is_bonus,
        "new_total": user["credits"] + user["bonus_credits"],
    }


@router.post("/credits/bulk-grant")
async def bulk_grant_credits(
    request: BulkGrantCreditsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Grant credits to multiple users at once."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    results = []
    for user_id in request.user_ids:
        if user_id in DEMO_USERS:
            user = DEMO_USERS[user_id]
            if request.is_bonus:
                user["bonus_credits"] += request.amount
            else:
                user["credits"] += request.amount
            
            CREDIT_TRANSACTIONS.append({
                "id": f"tx{len(CREDIT_TRANSACTIONS)+1}",
                "user_id": user_id,
                "user_email": user["email"],
                "type": "bonus" if request.is_bonus else "grant",
                "amount": request.amount,
                "reason": request.reason,
                "admin_id": str(account.id),
                "created_at": datetime.now(),
            })
            
            results.append({"user_id": user_id, "success": True})
        else:
            results.append({"user_id": user_id, "success": False, "error": "User not found"})
    
    return {
        "success": True,
        "total_users": len(request.user_ids),
        "successful": len([r for r in results if r["success"]]),
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
    """Get credit transaction history."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    transactions = CREDIT_TRANSACTIONS.copy()
    
    if user_id:
        transactions = [t for t in transactions if t["user_id"] == user_id]
    
    if type:
        transactions = [t for t in transactions if t["type"] == type]
    
    # Sort by date descending
    transactions.sort(key=lambda x: x["created_at"], reverse=True)
    
    total = len(transactions)
    start = (page - 1) * page_size
    end = start + page_size
    
    return {
        "transactions": [CreditTransaction(**t) for t in transactions[start:end]],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get system-wide statistics."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = list(DEMO_USERS.values())
    
    return SystemStats(
        total_users=len(users),
        active_users=len([u for u in users if u["status"] == "active"]),
        total_credits_issued=sum(u["credits"] + u["bonus_credits"] for u in users),
        total_credits_used=sum(abs(t["amount"]) for t in CREDIT_TRANSACTIONS if t["amount"] < 0),
        total_sms_sent=1234,
        total_ai_content=567,
        total_ai_images=234,
        revenue_this_month=2499.00,
    )


@router.get("/plans")
async def get_plan_configs(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get all plan configurations."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    plans = {
        "free": PlanConfig(
            name="Free",
            monthly_credits=0,
            sms_daily=10,
            sms_monthly=50,
            ai_content_daily=5,
            ai_content_monthly=30,
            ai_image_daily=3,
            ai_image_monthly=20,
            price_monthly=0,
        ),
        "starter": PlanConfig(
            name="Starter",
            monthly_credits=100,
            sms_daily=50,
            sms_monthly=500,
            ai_content_daily=20,
            ai_content_monthly=200,
            ai_image_daily=15,
            ai_image_monthly=150,
            price_monthly=29,
        ),
        "professional": PlanConfig(
            name="Professional",
            monthly_credits=300,
            sms_daily=200,
            sms_monthly=2000,
            ai_content_daily=50,
            ai_content_monthly=500,
            ai_image_daily=50,
            ai_image_monthly=500,
            price_monthly=99,
        ),
        "agency": PlanConfig(
            name="Agency",
            monthly_credits=1000,
            sms_daily=1000,
            sms_monthly=10000,
            ai_content_daily=200,
            ai_content_monthly=2000,
            ai_image_daily=200,
            ai_image_monthly=2000,
            price_monthly=299,
        ),
    }
    
    return {"plans": plans}


@router.post("/monthly-credits")
async def distribute_monthly_credits(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Distribute monthly credits to all active users based on their plan."""
    if not check_admin(account):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    plan_credits = {
        "free": 0,
        "starter": 100,
        "professional": 300,
        "agency": 1000,
    }
    
    results = []
    for user_id, user in DEMO_USERS.items():
        if user["status"] == "active":
            credits_to_add = plan_credits.get(user["plan"], 0)
            if credits_to_add > 0:
                user["credits"] += credits_to_add
                
                CREDIT_TRANSACTIONS.append({
                    "id": f"tx{len(CREDIT_TRANSACTIONS)+1}",
                    "user_id": user_id,
                    "user_email": user["email"],
                    "type": "grant",
                    "amount": credits_to_add,
                    "reason": "Monthly credit allocation",
                    "admin_id": str(account.id),
                    "created_at": datetime.now(),
                })
                
                results.append({
                    "user_id": user_id,
                    "email": user["email"],
                    "credits_added": credits_to_add,
                })
    
    return {
        "success": True,
        "users_processed": len(results),
        "total_credits_distributed": sum(r["credits_added"] for r in results),
        "results": results,
    }
