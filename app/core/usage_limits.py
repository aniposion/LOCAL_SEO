"""Usage limits and upsell middleware for AI features."""

import logging
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.account import Account
from app.models.competitor import CompetitorAnalysis
from app.models.location import Location
from app.models.notification import NotificationEvent
from app.models.post import Post
from app.models.review_response import ReviewResponse
from app.models.social_proof import SocialProofCard
from app.models.subscription import PlanType
from app.services.notification import NotificationService
from app.services.account_entitlements import resolve_account_entitlement

logger = logging.getLogger(__name__)


class FeatureName(str, Enum):
    """AI feature names for usage tracking."""

    COMPETITOR_ANALYSIS = "competitor_analysis"
    REVIEW_RESPONSE = "review_response"
    SOCIAL_PROOF_CARD = "social_proof_card"
    AI_CONTENT = "ai_content"


FEATURE_LIMITS = {
    PlanType.FREE: {
        FeatureName.COMPETITOR_ANALYSIS: 0,
        FeatureName.REVIEW_RESPONSE: 0,
        FeatureName.SOCIAL_PROOF_CARD: 0,
        FeatureName.AI_CONTENT: 0,
    },
    PlanType.MAPS_STARTER: {
        FeatureName.COMPETITOR_ANALYSIS: 4,
        FeatureName.REVIEW_RESPONSE: 50,
        FeatureName.SOCIAL_PROOF_CARD: 4,
        FeatureName.AI_CONTENT: 20,
    },
    PlanType.CALLS_GROWTH: {
        FeatureName.COMPETITOR_ANALYSIS: 8,
        FeatureName.REVIEW_RESPONSE: 150,
        FeatureName.SOCIAL_PROOF_CARD: 8,
        FeatureName.AI_CONTENT: 100,
    },
    PlanType.COMPETITIVE_MARKET: {
        FeatureName.COMPETITOR_ANALYSIS: 20,
        FeatureName.REVIEW_RESPONSE: 500,
        FeatureName.SOCIAL_PROOF_CARD: 20,
        FeatureName.AI_CONTENT: 500,
    },
    PlanType.STARTER: {
        FeatureName.COMPETITOR_ANALYSIS: 4,
        FeatureName.REVIEW_RESPONSE: 50,
        FeatureName.SOCIAL_PROOF_CARD: 4,
        FeatureName.AI_CONTENT: 20,
    },
    PlanType.PRO: {
        FeatureName.COMPETITOR_ANALYSIS: 4,
        FeatureName.REVIEW_RESPONSE: 150,
        FeatureName.SOCIAL_PROOF_CARD: 8,
        FeatureName.AI_CONTENT: 100,
    },
    PlanType.PREMIUM: {
        FeatureName.COMPETITOR_ANALYSIS: 4,
        FeatureName.REVIEW_RESPONSE: 500,
        FeatureName.SOCIAL_PROOF_CARD: 20,
        FeatureName.AI_CONTENT: 500,
    },
    PlanType.AGENCY: {
        FeatureName.COMPETITOR_ANALYSIS: 999999,
        FeatureName.REVIEW_RESPONSE: 999999,
        FeatureName.SOCIAL_PROOF_CARD: 999999,
        FeatureName.AI_CONTENT: 999999,
    },
}


class UsageLimitChecker:
    """Check and enforce usage limits for AI features."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _feature_label(feature_name: FeatureName) -> str:
        """Return a readable label for user-facing copy."""
        return feature_name.value.replace("_", " ").title()

    @staticmethod
    def _usage_warning_threshold(usage_percentage: float) -> int | None:
        """Bucket warnings so repeated checks do not spam the inbox."""
        if usage_percentage >= 100:
            return 100
        if usage_percentage >= 90:
            return 90
        if usage_percentage >= 80:
            return 80
        return None

    def _usage_warning_notification_type(
        self,
        feature_name: FeatureName,
        threshold: int,
    ) -> str:
        """Build a stable notification type for a threshold bucket."""
        return f"usage_warning_{feature_name.value}_{threshold}"

    def _performance_alerts_enabled(self, account: Account) -> bool:
        """Respect persisted performance alert preferences when available."""
        settings = account.settings if isinstance(account.settings, dict) else {}
        notification_preferences = settings.get("notification_preferences")
        if not isinstance(notification_preferences, dict):
            return True
        return bool(notification_preferences.get("performance_alerts", True))

    def _has_usage_warning_for_current_period(
        self,
        account_id: UUID,
        notification_type: str,
    ) -> bool:
        """Check whether this warning bucket was already emitted this month."""
        now = utc_now_naive()
        month_start = datetime(now.year, now.month, 1)
        return (
            self.db.query(NotificationEvent)
            .filter(
                NotificationEvent.account_id == account_id,
                NotificationEvent.type == notification_type,
                NotificationEvent.created_at >= month_start,
            )
            .first()
            is not None
        )

    def _maybe_record_usage_warning(
        self,
        *,
        account: Account,
        feature_name: FeatureName,
        current_usage: int,
        usage_limit: int,
        usage_percentage: float,
    ) -> None:
        """Persist threshold usage warnings into the inbox and audit trail."""
        threshold = self._usage_warning_threshold(usage_percentage)
        if threshold is None and usage_limit <= 0:
            threshold = 100
        if threshold is None:
            return
        if not self._performance_alerts_enabled(account):
            return

        notification_type = self._usage_warning_notification_type(feature_name, threshold)
        if self._has_usage_warning_for_current_period(account.id, notification_type):
            return

        feature_label = self._feature_label(feature_name)
        if usage_limit <= 0:
            message = (
                f"Your current plan does not include {feature_label.lower()} generations. "
                "Upgrade before using this workflow."
            )
        else:
            message = (
                f"You've used {current_usage} of {usage_limit} monthly {feature_label.lower()} generations "
                f"({round(usage_percentage, 1)}%). Review usage or upgrade before work is blocked."
            )
        NotificationService(self.db).send_inbox_notification(
            account_id=account.id,
            title=f"{feature_label} usage at {threshold}%",
            message=message,
            notification_type=notification_type,
            url="/dashboard/usage",
        )

    def get_current_usage(
        self,
        account_id: UUID,
        feature_name: FeatureName,
        location_id: Optional[UUID] = None,
    ) -> int:
        """Get current month usage for a feature."""
        now = utc_now_naive()
        month_start = datetime(now.year, now.month, 1)

        if feature_name == FeatureName.COMPETITOR_ANALYSIS:
            query = (
                self.db.query(func.count(CompetitorAnalysis.id))
                .join(Location, CompetitorAnalysis.location_id == Location.id)
                .filter(
                    Location.account_id == account_id,
                    CompetitorAnalysis.created_at >= month_start,
                )
            )
            if location_id:
                query = query.filter(CompetitorAnalysis.location_id == location_id)
        elif feature_name == FeatureName.REVIEW_RESPONSE:
            query = (
                self.db.query(func.count(ReviewResponse.id))
                .join(Location, ReviewResponse.location_id == Location.id)
                .filter(
                    Location.account_id == account_id,
                    ReviewResponse.created_at >= month_start,
                )
            )
            if location_id:
                query = query.filter(ReviewResponse.location_id == location_id)
        elif feature_name == FeatureName.SOCIAL_PROOF_CARD:
            query = (
                self.db.query(func.count(SocialProofCard.id))
                .join(Location, SocialProofCard.location_id == Location.id)
                .filter(
                    Location.account_id == account_id,
                    SocialProofCard.created_at >= month_start,
                )
            )
            if location_id:
                query = query.filter(SocialProofCard.location_id == location_id)
        elif feature_name == FeatureName.AI_CONTENT:
            account_location_ids = [
                item[0]
                for item in self.db.query(Location.id)
                .filter(Location.account_id == account_id)
                .all()
            ]
            if not account_location_ids:
                return 0
            query = (
                self.db.query(func.count(Post.id))
                .filter(
                    Post.created_at >= month_start,
                    Post.generated_by.isnot(None),
                    Post.location_id.in_(account_location_ids),
                )
            )
            if location_id:
                if location_id not in account_location_ids:
                    return 0
                query = query.filter(Post.location_id == location_id)
        else:
            return 0

        count = query.scalar()
        return count or 0

    def get_usage_limit(self, account_id: UUID, feature_name: FeatureName) -> int:
        """Get usage limit for a feature based on the account's subscription tier."""
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise ValueError(f"Account {account_id} not found")

        entitlement = resolve_account_entitlement(self.db, account_id)
        tier = entitlement.plan_type
        tier_limits = FEATURE_LIMITS.get(tier, {})
        return tier_limits.get(feature_name, 0)

    def check_usage_limit(
        self,
        account_id: UUID,
        feature_name: FeatureName,
        location_id: Optional[UUID] = None,
        raise_exception: bool = True,
    ) -> dict:
        """Check whether an account has reached its monthly feature limit."""
        current_usage = self.get_current_usage(account_id, feature_name, location_id)
        usage_limit = self.get_usage_limit(account_id, feature_name)
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise ValueError(f"Account {account_id} not found")

        usage_percentage = (current_usage / usage_limit * 100) if usage_limit > 0 else 0
        remaining = max(0, usage_limit - current_usage)

        usage_status = {
            "feature": feature_name,
            "current_usage": current_usage,
            "usage_limit": usage_limit,
            "remaining": remaining,
            "usage_percentage": round(usage_percentage, 1),
            "limit_reached": current_usage >= usage_limit,
        }

        if current_usage >= usage_limit:
            self._maybe_record_usage_warning(
                account=account,
                feature_name=feature_name,
                current_usage=current_usage,
                usage_limit=usage_limit,
                usage_percentage=usage_percentage,
            )
            if raise_exception:
                upgrade_message = self._get_upgrade_message(account, feature_name)
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error": "usage_limit_reached",
                        "message": f"You've reached your monthly limit for {feature_name.value}",
                        "usage_status": usage_status,
                        "upgrade_message": upgrade_message,
                        "upgrade_url": "/billing/upgrade",
                    },
                )
        elif usage_percentage >= 80:
            logger.warning(
                "Account %s has used %s%% of %s limit",
                account_id,
                usage_percentage,
                feature_name.value,
            )
            self._maybe_record_usage_warning(
                account=account,
                feature_name=feature_name,
                current_usage=current_usage,
                usage_limit=usage_limit,
                usage_percentage=usage_percentage,
            )

        return usage_status

    def _get_upgrade_message(self, account: Account, feature_name: FeatureName) -> str:
        """Get a personalized upgrade message."""
        entitlement = resolve_account_entitlement(self.db, account.id)
        current_tier = entitlement.plan_type

        if current_tier == PlanType.FREE:
            return "Upgrade to Maps Starter ($699/mo) to use managed AI automation."
        if current_tier == PlanType.MAPS_STARTER:
            next_limit = FEATURE_LIMITS[PlanType.CALLS_GROWTH][feature_name]
            return f"Upgrade to Calls Growth ($999/mo) to get {next_limit} {feature_name.value} per month"
        if current_tier == PlanType.CALLS_GROWTH:
            next_limit = FEATURE_LIMITS[PlanType.COMPETITIVE_MARKET][feature_name]
            return f"Upgrade to Competitive Market ($1499/mo) to get {next_limit} {feature_name.value} per month"
        if current_tier == PlanType.COMPETITIVE_MARKET:
            return "Contact us for a custom managed scope."
        if current_tier == PlanType.STARTER:
            next_limit = FEATURE_LIMITS[PlanType.PRO][feature_name]
            return f"Upgrade to Pro ($149/mo) to get {next_limit} {feature_name.value} per month"
        if current_tier == PlanType.PRO:
            next_limit = FEATURE_LIMITS[PlanType.PREMIUM][feature_name]
            return f"Upgrade to Premium ($249/mo) to get {next_limit} {feature_name.value} per month"
        if current_tier == PlanType.PREMIUM:
            return "Upgrade to Agency ($499/mo) for unlimited usage"
        return "Contact us for custom limits"

    async def send_usage_warning(
        self,
        account_id: UUID,
        feature_name: FeatureName,
        usage_percentage: float,
    ) -> None:
        """Send a direct usage warning notification."""
        notification_service = NotificationService(self.db)
        message = (
            f"Usage Alert: {self._feature_label(feature_name)}\n\n"
            f"You've used {usage_percentage}% of your monthly limit.\n\n"
            "Upgrade your plan to get more capacity and avoid interruptions."
        )

        await notification_service.send_notification(
            account_id=account_id,
            title=f"Usage Alert: {usage_percentage}% Used",
            message=message,
            notification_type="usage_warning",
            data={
                "feature": feature_name,
                "usage_percentage": usage_percentage,
                "upgrade_url": "/billing/upgrade",
            },
        )


async def check_usage_limit(
    account_id: UUID,
    feature_name: FeatureName,
    db: Session,
    location_id: Optional[UUID] = None,
) -> dict:
    """FastAPI dependency to check usage limits."""
    checker = UsageLimitChecker(db)
    return checker.check_usage_limit(account_id, feature_name, location_id)
