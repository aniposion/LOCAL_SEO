"""Subscription model for billing management."""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.billing import SubscriptionAddon


class PlanType(str, enum.Enum):
    """Subscription plan types."""

    FREE = "free"
    MAPS_STARTER = "maps_starter"  # Managed pilot, $699/mo
    CALLS_GROWTH = "calls_growth"  # Managed pilot, $999/mo
    COMPETITIVE_MARKET = "competitive_market"  # Managed pilot, $1499/mo
    STARTER = "starter"  # $99/mo
    PRO = "pro"          # $149/mo (Best Value)
    PREMIUM = "premium"  # $249/mo
    AGENCY = "agency"    # $499/location/mo
    ENTERPRISE = "enterprise"  # Legacy enum kept for backward compatibility


FREE_PREVIEW_DAYS = 3
FREE_PREVIEW_PLAN = PlanType.FREE


class AddOnType(str, enum.Enum):
    """Add-on types."""

    MISSED_CALL_TEXT_BACK = "missed_call_text_back"  # $29/mo
    REVIEW_BOOSTER = "review_booster"                # $39/mo
    WEBSITE_SEO = "website_seo"                      # $49/mo
    SOCIAL_AUTO_RESPONDER = "social_auto_responder"  # $29/mo
    VIDEO_GENERATOR = "video_generator"              # $49/mo


# Plan pricing
PLAN_PRICES = {
    PlanType.FREE: 0,
    PlanType.MAPS_STARTER: 699,
    PlanType.CALLS_GROWTH: 999,
    PlanType.COMPETITIVE_MARKET: 1499,
    PlanType.STARTER: 99,
    PlanType.PRO: 149,
    PlanType.PREMIUM: 249,
    PlanType.AGENCY: 499,  # per location
    PlanType.ENTERPRISE: 999,
}

# Add-on pricing
ADDON_PRICES = {
    AddOnType.MISSED_CALL_TEXT_BACK: 29,
    AddOnType.REVIEW_BOOSTER: 39,
    AddOnType.WEBSITE_SEO: 49,
    AddOnType.SOCIAL_AUTO_RESPONDER: 29,
    AddOnType.VIDEO_GENERATOR: 49,
}

# Features included in each plan
PLAN_FEATURES = {
    PlanType.FREE: {
        "google_posts": False,
        "review_collection": False,
        "ai_review_response": False,
        "basic_dashboard": True,
        "weekly_report": False,
        "instagram_upload": False,
        "content_scheduler": False,
        "qa_auto_response": False,
        "competitor_analysis": False,
        "website_seo_basic": False,
        "website_seo_full": False,
        "missed_call_text_back": False,
        "review_booster": False,
        "social_auto_responder": False,
        "video_generator": False,
        "white_label": False,
        "team_management": False,
        "multi_location": False,
        "locations_limit": 1,
        "posts_per_month": 0,
    },
    PlanType.MAPS_STARTER: {
        "google_posts": True,
        "review_collection": True,
        "ai_review_response": True,
        "basic_dashboard": True,
        "weekly_report": True,
        "instagram_upload": False,
        "content_scheduler": True,
        "qa_auto_response": False,
        "competitor_analysis": True,
        "website_seo_basic": False,
        "website_seo_full": False,
        "missed_call_text_back": False,
        "review_booster": False,
        "social_auto_responder": False,
        "video_generator": False,
        "white_label": False,
        "team_management": False,
        "multi_location": False,
        "locations_limit": 1,
        "posts_per_month": 30,
    },
    PlanType.CALLS_GROWTH: {
        "google_posts": True,
        "review_collection": True,
        "ai_review_response": True,
        "basic_dashboard": True,
        "weekly_report": True,
        "instagram_upload": False,
        "content_scheduler": True,
        "qa_auto_response": True,
        "competitor_analysis": True,
        "website_seo_basic": True,
        "website_seo_full": False,
        "missed_call_text_back": True,
        "review_booster": True,
        "social_auto_responder": False,
        "video_generator": False,
        "white_label": False,
        "team_management": False,
        "multi_location": False,
        "locations_limit": 1,
        "posts_per_month": 60,
    },
    PlanType.COMPETITIVE_MARKET: {
        "google_posts": True,
        "review_collection": True,
        "ai_review_response": True,
        "basic_dashboard": True,
        "weekly_report": True,
        "instagram_upload": True,
        "content_scheduler": True,
        "qa_auto_response": True,
        "competitor_analysis": True,
        "website_seo_basic": True,
        "website_seo_full": True,
        "missed_call_text_back": True,
        "review_booster": True,
        "social_auto_responder": True,
        "video_generator": False,
        "white_label": False,
        "team_management": False,
        "multi_location": True,
        "locations_limit": 3,
        "posts_per_month": 120,
    },
    PlanType.STARTER: {
        "google_posts": True,
        "review_collection": True,
        "ai_review_response": True,
        "basic_dashboard": True,
        "weekly_report": True,
        "instagram_upload": False,
        "content_scheduler": False,
        "qa_auto_response": False,
        "competitor_analysis": False,
        "website_seo_basic": False,
        "website_seo_full": False,
        "missed_call_text_back": False,
        "review_booster": False,
        "social_auto_responder": False,
        "video_generator": False,
        "white_label": False,
        "team_management": False,
        "multi_location": False,
        "locations_limit": 1,
        "posts_per_month": 30,
    },
    PlanType.PRO: {
        "google_posts": True,
        "review_collection": True,
        "ai_review_response": True,
        "basic_dashboard": True,
        "weekly_report": True,
        "instagram_upload": True,
        "content_scheduler": True,
        "qa_auto_response": True,
        "competitor_analysis": True,
        "website_seo_basic": True,
        "website_seo_full": False,
        "missed_call_text_back": False,  # Add-on
        "review_booster": False,          # Add-on
        "social_auto_responder": False,   # Add-on
        "video_generator": False,         # Add-on
        "white_label": False,
        "team_management": False,
        "multi_location": False,
        "locations_limit": 1,
        "posts_per_month": 60,
    },
    PlanType.PREMIUM: {
        "google_posts": True,
        "review_collection": True,
        "ai_review_response": True,
        "basic_dashboard": True,
        "weekly_report": True,
        "instagram_upload": True,
        "content_scheduler": True,
        "qa_auto_response": True,
        "competitor_analysis": True,
        "website_seo_basic": True,
        "website_seo_full": True,
        "missed_call_text_back": True,   # Included
        "review_booster": True,           # Included
        "social_auto_responder": True,    # Included
        "video_generator": False,         # Add-on
        "white_label": False,
        "team_management": False,
        "multi_location": False,
        "locations_limit": 1,
        "posts_per_month": 120,
    },
    PlanType.AGENCY: {
        "google_posts": True,
        "review_collection": True,
        "ai_review_response": True,
        "basic_dashboard": True,
        "weekly_report": True,
        "instagram_upload": True,
        "content_scheduler": True,
        "qa_auto_response": True,
        "competitor_analysis": True,
        "website_seo_basic": True,
        "website_seo_full": True,
        "missed_call_text_back": True,
        "review_booster": True,
        "social_auto_responder": True,
        "video_generator": True,
        "white_label": True,
        "team_management": True,
        "multi_location": True,
        "locations_limit": -1,  # Unlimited
        "posts_per_month": -1,  # Unlimited
    },
    PlanType.ENTERPRISE: {
        "google_posts": True,
        "review_collection": True,
        "ai_review_response": True,
        "basic_dashboard": True,
        "weekly_report": True,
        "instagram_upload": True,
        "content_scheduler": True,
        "qa_auto_response": True,
        "competitor_analysis": True,
        "website_seo_basic": True,
        "website_seo_full": True,
        "missed_call_text_back": True,
        "review_booster": True,
        "social_auto_responder": True,
        "video_generator": True,
        "white_label": True,
        "team_management": True,
        "multi_location": True,
        "locations_limit": -1,
        "posts_per_month": -1,
    },
}


class SubscriptionStatus(str, enum.Enum):
    """Subscription status."""

    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    PAUSED = "paused"
    EXPIRED = "expired"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    UNPAID = "unpaid"


class DunningStatus(str, enum.Enum):
    """Dunning (payment failure handling) status."""
    
    NONE = "none"
    RETRYING = "retrying"          # Automatic retries in progress
    GRACE_PERIOD = "grace_period"  # Grace period after retries exhausted
    RESTRICTED = "restricted"      # Features restricted (read-only mode)
    SUSPENDED = "suspended"        # Account suspended


class Subscription(BaseModel):
    """User subscription model."""

    __tablename__ = "subscriptions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # Plan details
    plan_type: Mapped[PlanType] = mapped_column(
        Enum(PlanType), default=PlanType.FREE, nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False
    )

    # Stripe integration
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Billing period
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)

    # Usage limits based on plan
    locations_limit: Mapped[int] = mapped_column(Integer, default=1)
    posts_per_month: Mapped[int] = mapped_column(Integer, default=0)
    api_calls_per_day: Mapped[int] = mapped_column(Integer, default=1000)

    # Active add-ons (JSON array of AddOnType values)
    active_addons: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)

    # Agency-specific: number of locations for billing
    agency_location_count: Mapped[int] = mapped_column(Integer, default=1)

    # Trial
    trial_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Cancellation tracking
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cancellation_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Dunning (payment failure handling)
    dunning_status: Mapped[DunningStatus] = mapped_column(
        Enum(DunningStatus), default=DunningStatus.NONE, nullable=False
    )
    dunning_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_payment_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_payment_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    grace_period_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # P0: Internal access control (decoupled from Stripe status)
    access_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default='active'
    )
    # Values: 'active', 'warning', 'suspended'
    # WHY: Separate from Stripe status for immediate control without webhook delays

    # Billing cycle anchor (for consistent billing dates)
    billing_cycle_anchor: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="subscription")
    addons: Mapped[list["SubscriptionAddon"]] = relationship(
        "SubscriptionAddon", back_populates="subscription", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Subscription {self.plan_type.value} - {self.status.value}>"

    @property
    def is_active(self) -> bool:
        """Check if subscription allows access (based on access_state)."""
        if self.access_state != 'active':
            return False
        if self.status not in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING}:
            return False
        if self.status == SubscriptionStatus.TRIALING and self.has_trial_ended:
            return False
        return True
    
    @property
    def is_in_dunning(self) -> bool:
        """Check if subscription is in dunning state."""
        return self.access_state in ['warning', 'suspended']

    @property
    def is_trial(self) -> bool:
        """Check if subscription is in trial."""
        return self.status == SubscriptionStatus.TRIALING and not self.has_trial_ended

    @property
    def has_trial_ended(self) -> bool:
        """Return True when a trial subscription is past its configured end."""
        if self.status != SubscriptionStatus.TRIALING or self.trial_end is None:
            return False
        trial_end = self.trial_end
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        return trial_end <= datetime.now(timezone.utc)

    def has_feature(self, feature: str) -> bool:
        """Check if the subscription has access to a specific feature."""
        plan_features = PLAN_FEATURES.get(self.plan_type, PLAN_FEATURES[PlanType.FREE])
        
        # Check plan features first
        if plan_features.get(feature, False):
            return True
        
        # Check add-ons for features that can be purchased separately
        addon_feature_map = {
            "missed_call_text_back": AddOnType.MISSED_CALL_TEXT_BACK,
            "review_booster": AddOnType.REVIEW_BOOSTER,
            "website_seo_full": AddOnType.WEBSITE_SEO,
            "social_auto_responder": AddOnType.SOCIAL_AUTO_RESPONDER,
            "video_generator": AddOnType.VIDEO_GENERATOR,
        }
        
        if feature in addon_feature_map and self.active_addons:
            return addon_feature_map[feature].value in self.active_addons
        
        return False

    def get_features(self) -> dict:
        """Get all features for current plan including add-ons."""
        features = PLAN_FEATURES.get(self.plan_type, PLAN_FEATURES[PlanType.FREE]).copy()
        
        # Apply add-ons
        if self.active_addons:
            addon_feature_map = {
                AddOnType.MISSED_CALL_TEXT_BACK.value: "missed_call_text_back",
                AddOnType.REVIEW_BOOSTER.value: "review_booster",
                AddOnType.WEBSITE_SEO.value: "website_seo_full",
                AddOnType.SOCIAL_AUTO_RESPONDER.value: "social_auto_responder",
                AddOnType.VIDEO_GENERATOR.value: "video_generator",
            }
            for addon in self.active_addons:
                if addon in addon_feature_map:
                    features[addon_feature_map[addon]] = True
        
        return features

    def get_monthly_price(self) -> int:
        """Calculate total monthly price including add-ons."""
        base_price = PLAN_PRICES.get(self.plan_type, 0)
        
        # Agency plan is per location
        if self.plan_type == PlanType.AGENCY:
            base_price = base_price * self.agency_location_count
        
        # Add add-on prices
        addon_total = 0
        if self.active_addons:
            for addon in self.active_addons:
                try:
                    addon_type = AddOnType(addon)
                    addon_total += ADDON_PRICES.get(addon_type, 0)
                except ValueError:
                    pass
        
        return base_price + addon_total


class PaymentHistory(BaseModel):
    """Payment history model."""

    __tablename__ = "payment_history"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )

    # Payment details
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # succeeded, failed, pending
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Invoice URL
    invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Payment {self.amount} {self.currency} - {self.status}>"
