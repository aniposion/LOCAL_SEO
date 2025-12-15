"""
Credits Service
Handles credit allocation, usage, and monthly reset on payment
"""
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum


class PlanTier(str, Enum):
    """Plan tiers."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    AGENCY = "agency"


# Plan configurations
PLAN_CREDITS = {
    PlanTier.FREE: {
        "monthly_credits": 0,
        "sms_daily": 10,
        "sms_monthly": 50,
        "ai_content_daily": 5,
        "ai_content_monthly": 30,
        "ai_image_daily": 3,
        "ai_image_monthly": 20,
        "ai_response_daily": 10,
        "ai_response_monthly": 100,
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
    },
}

# Credit costs for overage
CREDIT_COSTS = {
    "sms": 5,
    "ai_content": 10,
    "ai_image": 15,
    "ai_response": 2,
}


class CreditAccount:
    """In-memory credit account for demo."""
    
    def __init__(
        self,
        account_id: str,
        plan: PlanTier = PlanTier.FREE,
        balance: int = 0,
        bonus_balance: int = 0,
    ):
        self.account_id = account_id
        self.plan = plan
        self.balance = balance
        self.bonus_balance = bonus_balance
        self.monthly_allocation = PLAN_CREDITS[plan]["monthly_credits"]
        self.last_allocation_date: Optional[datetime] = None
        self.next_allocation_date: Optional[datetime] = None
        self.billing_cycle_start: Optional[datetime] = None
        self.total_received = 0
        self.total_used = 0
        self.transactions: list[dict] = []
        
        # Usage tracking (resets monthly)
        self.usage = {
            "sms": {"daily": 0, "monthly": 0, "last_reset": datetime.now()},
            "ai_content": {"daily": 0, "monthly": 0, "last_reset": datetime.now()},
            "ai_image": {"daily": 0, "monthly": 0, "last_reset": datetime.now()},
            "ai_response": {"daily": 0, "monthly": 0, "last_reset": datetime.now()},
        }
    
    @property
    def total_available(self) -> int:
        return self.balance + self.bonus_balance
    
    def can_afford(self, amount: int) -> bool:
        return self.total_available >= amount
    
    def deduct(self, amount: int, usage_type: str, description: str = "") -> bool:
        """Deduct credits. Uses bonus first."""
        if not self.can_afford(amount):
            return False
        
        remaining = amount
        bonus_used = 0
        regular_used = 0
        
        # Use bonus credits first
        if self.bonus_balance > 0:
            bonus_used = min(self.bonus_balance, remaining)
            self.bonus_balance -= bonus_used
            remaining -= bonus_used
        
        # Use regular balance
        if remaining > 0:
            regular_used = remaining
            self.balance -= remaining
        
        self.total_used += amount
        
        # Log transaction
        self.transactions.append({
            "type": f"{usage_type}_usage",
            "amount": -amount,
            "balance_after": self.total_available,
            "description": description or f"{usage_type} overage charge",
            "created_at": datetime.now(),
        })
        
        return True
    
    def add_credits(
        self,
        amount: int,
        transaction_type: str,
        is_bonus: bool = False,
        description: str = "",
    ):
        """Add credits to account."""
        if is_bonus:
            self.bonus_balance += amount
        else:
            self.balance += amount
        
        self.total_received += amount
        
        self.transactions.append({
            "type": transaction_type,
            "amount": amount,
            "balance_after": self.total_available,
            "description": description,
            "created_at": datetime.now(),
        })


class CreditsService:
    """Service for managing credits and monthly allocations."""
    
    def __init__(self):
        # In-memory storage for demo
        self._accounts: dict[str, CreditAccount] = {}
    
    def get_or_create_account(self, account_id: str, plan: PlanTier = PlanTier.FREE) -> CreditAccount:
        """Get or create a credit account."""
        if account_id not in self._accounts:
            self._accounts[account_id] = CreditAccount(account_id, plan)
        return self._accounts[account_id]
    
    def process_payment(
        self,
        account_id: str,
        plan: PlanTier,
        payment_date: Optional[datetime] = None,
    ) -> dict:
        """
        Process a subscription payment.
        This resets usage counters and allocates monthly credits.
        
        Called when:
        1. User subscribes to a paid plan
        2. Monthly billing cycle renews
        """
        payment_date = payment_date or datetime.now()
        account = self.get_or_create_account(account_id, plan)
        
        # Update plan
        old_plan = account.plan
        account.plan = plan
        account.monthly_allocation = PLAN_CREDITS[plan]["monthly_credits"]
        
        # Calculate next billing date (1 month from now)
        next_billing = payment_date + timedelta(days=30)
        
        # Reset and allocate credits
        result = self._reset_monthly_allocation(account, payment_date, next_billing)
        
        return {
            "success": True,
            "account_id": account_id,
            "old_plan": old_plan.value,
            "new_plan": plan.value,
            "credits_allocated": result["credits_allocated"],
            "new_balance": account.total_available,
            "billing_cycle_start": payment_date.isoformat(),
            "next_billing_date": next_billing.isoformat(),
            "usage_reset": True,
        }
    
    def _reset_monthly_allocation(
        self,
        account: CreditAccount,
        billing_start: datetime,
        next_billing: datetime,
    ) -> dict:
        """
        Reset monthly allocation and usage counters.
        This is called on each billing cycle.
        """
        monthly_credits = PLAN_CREDITS[account.plan]["monthly_credits"]
        
        # Reset credit balance to monthly allocation
        # Note: Purchased credits carry over, but monthly allocation resets
        old_balance = account.balance
        
        # Keep purchased/bonus credits, reset monthly allocation
        # For simplicity in demo: just add monthly credits
        account.balance = monthly_credits
        
        # Update allocation tracking
        account.last_allocation_date = billing_start
        account.next_allocation_date = next_billing
        account.billing_cycle_start = billing_start
        
        # Reset usage counters
        for usage_type in account.usage:
            account.usage[usage_type]["daily"] = 0
            account.usage[usage_type]["monthly"] = 0
            account.usage[usage_type]["last_reset"] = billing_start
        
        # Log transaction
        account.transactions.append({
            "type": "monthly_allocation",
            "amount": monthly_credits,
            "balance_after": account.total_available,
            "description": f"Monthly credit allocation ({account.plan.value} plan)",
            "created_at": billing_start,
        })
        
        return {
            "credits_allocated": monthly_credits,
            "old_balance": old_balance,
            "new_balance": account.balance,
        }
    
    def check_and_reset_daily(self, account_id: str) -> bool:
        """Check and reset daily usage if needed."""
        account = self.get_or_create_account(account_id)
        now = datetime.now()
        
        for usage_type, usage in account.usage.items():
            last_reset = usage.get("last_reset", now)
            if isinstance(last_reset, datetime):
                # Reset if it's a new day
                if last_reset.date() < now.date():
                    usage["daily"] = 0
                    usage["last_reset"] = now
        
        return True
    
    def use_credits(
        self,
        account_id: str,
        usage_type: str,
        count: int = 1,
    ) -> dict:
        """
        Record usage and deduct credits if over limit.
        
        Returns:
            - allowed: bool - whether the action is allowed
            - credits_used: int - credits deducted (0 if within limit)
            - remaining_daily: int - remaining daily limit
            - remaining_monthly: int - remaining monthly limit
        """
        account = self.get_or_create_account(account_id)
        plan_limits = PLAN_CREDITS[account.plan]
        
        # Check and reset daily counters
        self.check_and_reset_daily(account_id)
        
        daily_limit = plan_limits.get(f"{usage_type}_daily", 0)
        monthly_limit = plan_limits.get(f"{usage_type}_monthly", 0)
        
        current_daily = account.usage[usage_type]["daily"]
        current_monthly = account.usage[usage_type]["monthly"]
        
        # Check if within limits
        within_daily = current_daily + count <= daily_limit
        within_monthly = current_monthly + count <= monthly_limit
        
        credits_used = 0
        
        if within_daily and within_monthly:
            # Within limits, no credit charge
            account.usage[usage_type]["daily"] += count
            account.usage[usage_type]["monthly"] += count
        else:
            # Over limit, charge credits
            credit_cost = CREDIT_COSTS.get(usage_type, 5) * count
            
            if not account.can_afford(credit_cost):
                return {
                    "allowed": False,
                    "reason": "insufficient_credits",
                    "credits_required": credit_cost,
                    "credits_available": account.total_available,
                    "remaining_daily": max(0, daily_limit - current_daily),
                    "remaining_monthly": max(0, monthly_limit - current_monthly),
                }
            
            # Deduct credits
            account.deduct(credit_cost, usage_type)
            credits_used = credit_cost
            
            # Still count the usage
            account.usage[usage_type]["daily"] += count
            account.usage[usage_type]["monthly"] += count
        
        return {
            "allowed": True,
            "credits_used": credits_used,
            "remaining_daily": max(0, daily_limit - account.usage[usage_type]["daily"]),
            "remaining_monthly": max(0, monthly_limit - account.usage[usage_type]["monthly"]),
            "balance": account.total_available,
        }
    
    def get_account_status(self, account_id: str) -> dict:
        """Get full account status including credits and usage."""
        account = self.get_or_create_account(account_id)
        plan_limits = PLAN_CREDITS[account.plan]
        
        # Check and reset daily counters
        self.check_and_reset_daily(account_id)
        
        usage_status = {}
        for usage_type in ["sms", "ai_content", "ai_image", "ai_response"]:
            daily_limit = plan_limits.get(f"{usage_type}_daily", 0)
            monthly_limit = plan_limits.get(f"{usage_type}_monthly", 0)
            current = account.usage.get(usage_type, {"daily": 0, "monthly": 0})
            
            usage_status[usage_type] = {
                "daily_used": current["daily"],
                "daily_limit": daily_limit,
                "daily_remaining": max(0, daily_limit - current["daily"]),
                "monthly_used": current["monthly"],
                "monthly_limit": monthly_limit,
                "monthly_remaining": max(0, monthly_limit - current["monthly"]),
                "credit_cost": CREDIT_COSTS.get(usage_type, 5),
            }
        
        return {
            "account_id": account_id,
            "plan": account.plan.value,
            "credits": {
                "balance": account.balance,
                "bonus_balance": account.bonus_balance,
                "total_available": account.total_available,
                "monthly_allocation": account.monthly_allocation,
            },
            "billing": {
                "last_allocation": account.last_allocation_date.isoformat() if account.last_allocation_date else None,
                "next_allocation": account.next_allocation_date.isoformat() if account.next_allocation_date else None,
                "billing_cycle_start": account.billing_cycle_start.isoformat() if account.billing_cycle_start else None,
            },
            "usage": usage_status,
            "stats": {
                "total_received": account.total_received,
                "total_used": account.total_used,
            },
        }
    
    def purchase_credits(
        self,
        account_id: str,
        amount: int,
        payment_id: str = "",
    ) -> dict:
        """Purchase additional credits."""
        account = self.get_or_create_account(account_id)
        
        account.add_credits(
            amount,
            "purchase",
            is_bonus=False,
            description=f"Purchased {amount} credits",
        )
        
        return {
            "success": True,
            "credits_added": amount,
            "new_balance": account.total_available,
            "payment_id": payment_id,
        }
    
    def grant_bonus(
        self,
        account_id: str,
        amount: int,
        reason: str = "Bonus credits",
    ) -> dict:
        """Grant bonus credits (admin action)."""
        account = self.get_or_create_account(account_id)
        
        account.add_credits(
            amount,
            "bonus",
            is_bonus=True,
            description=reason,
        )
        
        return {
            "success": True,
            "bonus_added": amount,
            "new_bonus_balance": account.bonus_balance,
            "new_total": account.total_available,
        }
    
    def get_transactions(
        self,
        account_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """Get recent transactions for an account."""
        account = self.get_or_create_account(account_id)
        return sorted(
            account.transactions,
            key=lambda x: x["created_at"],
            reverse=True,
        )[:limit]


# Global instance
credits_service = CreditsService()
