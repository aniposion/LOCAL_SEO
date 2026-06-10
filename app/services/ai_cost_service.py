"""AI usage cost tracking and cap enforcement."""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.time import utc_now_naive
from app.models.ai_cost import AiUsageCost
from app.models.subscription import Subscription, PlanType

logger = logging.getLogger(__name__)

# Monthly cost caps per plan (USD)
COST_CAPS = {
    PlanType.FREE: Decimal("0.00"),      # No AI features
    PlanType.MAPS_STARTER: Decimal("5.00"),
    PlanType.CALLS_GROWTH: Decimal("10.00"),
    PlanType.COMPETITIVE_MARKET: Decimal("20.00"),
    PlanType.STARTER: Decimal("5.00"),   # $5/month
    PlanType.PRO: Decimal("10.00"),      # $10/month
    PlanType.PREMIUM: Decimal("20.00"),  # $20/month
    PlanType.AGENCY: Decimal("50.00"),   # $50/month
}

# API cost rates (USD)
GEMINI_INPUT_COST_PER_1M = Decimal("0.15")   # $0.15 per 1M input tokens
GEMINI_OUTPUT_COST_PER_1M = Decimal("0.60")  # $0.60 per 1M output tokens
IMAGEN_COST_PER_IMAGE = Decimal("0.04")      # $0.04 per image
GOOGLE_PLACES_NEARBY_PER_1K = Decimal("6.40")  # $6.40 per 1K requests


class AiCostService:
    """
    AI cost tracking and cap enforcement.
    
    CRITICAL: check_cost_limit() must be called BEFORE any AI API call
    to prevent overspending.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_cost_limit(
        self,
        user_id: UUID,
        account_id: UUID,
        estimated_cost: Decimal
    ) -> None:
        """
        Check if user is within monthly cost limit.
        
        CRITICAL: Call this BEFORE making AI API call.
        Raises HTTPException 402 if limit exceeded.
        
        Args:
            user_id: User UUID
            account_id: Account UUID
            estimated_cost: Estimated cost of upcoming API call
        
        Raises:
            HTTPException: 402 if cost limit exceeded
        """
        # Get subscription
        from app.models.account import Account
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account or not account.subscription:
            raise HTTPException(400, "No active subscription found")
        
        subscription = account.subscription
        cost_cap = COST_CAPS.get(subscription.plan_type, Decimal("0.00"))
        
        # Calculate current month usage
        month_start = utc_now_naive().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        current_usage = self.db.query(
            func.sum(AiUsageCost.cost_usd)
        ).filter(
            AiUsageCost.user_id == user_id,
            AiUsageCost.created_at >= month_start
        ).scalar() or Decimal("0.00")
        
        # Check if adding estimated cost would exceed limit
        projected_usage = current_usage + estimated_cost
        
        if projected_usage > cost_cap:
            logger.warning(
                f"AI cost limit exceeded for user {user_id}. "
                f"Current: ${current_usage}, Cap: ${cost_cap}, "
                f"Projected: ${projected_usage}"
            )
            
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "ai_cost_limit_reached",
                    "message": "Monthly AI cost limit reached",
                    "current_cost": float(current_usage),
                    "cost_cap": float(cost_cap),
                    "plan_type": subscription.plan_type.value,
                    "upgrade_message": f"Upgrade to {self._get_next_plan(subscription.plan_type)} for higher limits",
                    "upgrade_url": "/billing/upgrade"
                }
            )
    
    def record_cost(
        self,
        user_id: UUID,
        account_id: UUID,
        feature: str,
        api_provider: str,
        cost_usd: Decimal,
        location_id: Optional[UUID] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        api_calls: int = 1
    ) -> AiUsageCost:
        """
        Record AI API cost.
        
        Call this AFTER successful API call to track actual cost.
        
        Args:
            user_id: User UUID
            account_id: Account UUID
            feature: Feature name (e.g., 'competitor_analysis')
            api_provider: API provider (e.g., 'gemini', 'imagen')
            cost_usd: Actual cost in USD
            location_id: Optional location UUID
            tokens_input: Input tokens (for LLMs)
            tokens_output: Output tokens (for LLMs)
            api_calls: Number of API calls (default 1)
        
        Returns:
            AiUsageCost: Created cost record
        """
        cost_record = AiUsageCost(
            user_id=user_id,
            account_id=account_id,
            location_id=location_id,
            feature=feature,
            api_provider=api_provider,
            cost_usd=cost_usd,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            api_calls=api_calls
        )
        
        self.db.add(cost_record)
        self.db.flush()
        
        logger.info(
            f"AI cost recorded: {feature} via {api_provider} = ${cost_usd} "
            f"(user={user_id}, account={account_id})"
        )
        
        return cost_record
    
    def calculate_gemini_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> Decimal:
        """Calculate Gemini API cost."""
        input_cost = (Decimal(input_tokens) / Decimal("1000000")) * GEMINI_INPUT_COST_PER_1M
        output_cost = (Decimal(output_tokens) / Decimal("1000000")) * GEMINI_OUTPUT_COST_PER_1M
        return input_cost + output_cost
    
    def calculate_imagen_cost(self, image_count: int = 1) -> Decimal:
        """Calculate Imagen API cost."""
        return IMAGEN_COST_PER_IMAGE * Decimal(image_count)
    
    def calculate_google_places_cost(self, request_count: int = 1) -> Decimal:
        """Calculate Google Places API cost."""
        return (Decimal(request_count) / Decimal("1000")) * GOOGLE_PLACES_NEARBY_PER_1K
    
    def get_monthly_usage(
        self,
        user_id: UUID,
        month: Optional[datetime] = None
    ) -> dict:
        """
        Get monthly AI usage summary.
        
        Args:
            user_id: User UUID
            month: Optional month (defaults to current month)
        
        Returns:
            dict with usage breakdown
        """
        if month is None:
            month = utc_now_naive()
        
        month_start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get total cost
        total_cost = self.db.query(
            func.sum(AiUsageCost.cost_usd)
        ).filter(
            AiUsageCost.user_id == user_id,
            AiUsageCost.created_at >= month_start,
            func.date_trunc('month', AiUsageCost.created_at) == month_start
        ).scalar() or Decimal("0.00")
        
        # Get breakdown by feature
        breakdown = self.db.query(
            AiUsageCost.feature,
            func.sum(AiUsageCost.cost_usd).label('cost'),
            func.sum(AiUsageCost.api_calls).label('calls')
        ).filter(
            AiUsageCost.user_id == user_id,
            AiUsageCost.created_at >= month_start,
            func.date_trunc('month', AiUsageCost.created_at) == month_start
        ).group_by(AiUsageCost.feature).all()
        
        return {
            "month": month_start.strftime("%Y-%m"),
            "total_cost": float(total_cost),
            "breakdown": [
                {
                    "feature": row.feature,
                    "cost": float(row.cost),
                    "api_calls": row.calls
                }
                for row in breakdown
            ]
        }
    
    def _get_next_plan(self, current_plan: PlanType) -> str:
        """Get next plan tier for upgrade message."""
        if current_plan == PlanType.FREE:
            return "Maps Starter"
        elif current_plan == PlanType.MAPS_STARTER:
            return "Calls Growth"
        elif current_plan == PlanType.CALLS_GROWTH:
            return "Competitive Market"
        elif current_plan == PlanType.COMPETITIVE_MARKET:
            return "custom managed scope"
        elif current_plan == PlanType.STARTER:
            return "Pro"
        elif current_plan == PlanType.PRO:
            return "Premium"
        elif current_plan == PlanType.PREMIUM:
            return "Agency"
        return "Premium"
