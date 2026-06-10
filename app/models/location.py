"""Location (business) model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.analytics import Analytics
    from app.models.channel import Channel
    from app.models.content_calendar import AutopilotSettings, ContentCalendar
    from app.models.feedback import BrandVoiceProfile
    from app.models.recommendation import Recommendation
    from app.models.revenue import RevenueProfile
    from app.models.post import Post
    from app.models.report import Report
    from app.models.schedule import Schedule
    from app.models.seo_score import SEOScore
    from app.models.metrics import MetricSnapshot
    from app.models.review_booster import ReviewCampaign
    from app.models.calls import TwilioNumber, SMSThread
    from app.models.oauth import OAuthToken
    from app.models.social_response import SocialAutomationSettings, SocialResponseLog
    from app.models.website_seo import WebsiteSEODraft
    from app.models.qa import QADraft
    from app.models.vault import EntityVault
    from app.models.competitor import Competitor


class Location(BaseModel):
    """Business location model."""

    __tablename__ = "locations"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="US", nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Contact
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Business details
    business_hours: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    services: Mapped[list | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Platform IDs
    gbp_location_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ig_business_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="locations")
    channels: Mapped[list["Channel"]] = relationship(
        "Channel", back_populates="location", cascade="all, delete-orphan"
    )
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="location", cascade="all, delete-orphan"
    )
    analytics: Mapped[list["Analytics"]] = relationship(
        "Analytics", back_populates="location", cascade="all, delete-orphan"
    )
    seo_scores: Mapped[list["SEOScore"]] = relationship(
        "SEOScore", back_populates="location", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="location", cascade="all, delete-orphan"
    )
    content_calendars: Mapped[list["ContentCalendar"]] = relationship(
        "ContentCalendar", back_populates="location", cascade="all, delete-orphan"
    )
    autopilot_settings: Mapped["AutopilotSettings | None"] = relationship(
        "AutopilotSettings", back_populates="location", uselist=False, cascade="all, delete-orphan"
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="location", cascade="all, delete-orphan"
    )
    brand_voice_profile: Mapped["BrandVoiceProfile | None"] = relationship(
        "BrandVoiceProfile", back_populates="location", uselist=False, cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        "Recommendation", back_populates="location", cascade="all, delete-orphan"
    )
    
    # P1: Metrics
    metric_snapshots: Mapped[list["MetricSnapshot"]] = relationship(
        "MetricSnapshot", back_populates="location", cascade="all, delete-orphan"
    )
    revenue_profile: Mapped["RevenueProfile | None"] = relationship(
        "RevenueProfile", back_populates="location", uselist=False, cascade="all, delete-orphan"
    )
    
    # P2: Review Booster
    review_campaigns: Mapped[list["ReviewCampaign"]] = relationship(
        "ReviewCampaign", back_populates="location", cascade="all, delete-orphan"
    )
    
    # P3: Calls
    twilio_numbers: Mapped[list["TwilioNumber"]] = relationship(
        "TwilioNumber", back_populates="location", cascade="all, delete-orphan"
    )
    sms_threads: Mapped[list["SMSThread"]] = relationship(
        "SMSThread", back_populates="location", cascade="all, delete-orphan"
    )
    
    # P4: OAuth
    oauth_tokens: Mapped[list["OAuthToken"]] = relationship(
        "OAuthToken", back_populates="location", cascade="all, delete-orphan"
    )
    social_response_logs: Mapped[list["SocialResponseLog"]] = relationship(
        "SocialResponseLog", back_populates="location", cascade="all, delete-orphan"
    )
    social_automation_settings: Mapped["SocialAutomationSettings | None"] = relationship(
        "SocialAutomationSettings", back_populates="location", uselist=False, cascade="all, delete-orphan"
    )
    website_seo_drafts: Mapped[list["WebsiteSEODraft"]] = relationship(
        "WebsiteSEODraft", back_populates="location", cascade="all, delete-orphan"
    )
    qa_drafts: Mapped[list["QADraft"]] = relationship(
        "QADraft", back_populates="location", cascade="all, delete-orphan"
    )
    
    # P5: Vault
    entity_vault: Mapped["EntityVault | None"] = relationship(
        "EntityVault", back_populates="location", uselist=False, cascade="all, delete-orphan"
    )
    
    # P6: Competitor Analysis
    competitors: Mapped[list["Competitor"]] = relationship(
        "Competitor", back_populates="location", cascade="all, delete-orphan"
    )
    
    @property
    def latitude(self) -> float | None:
        """Get latitude."""
        return self.lat
    
    @property
    def longitude(self) -> float | None:
        """Get longitude."""
        return self.lng
    
    @property
    def business_name(self) -> str:
        """Get business name."""
        return self.name

    def __repr__(self) -> str:
        return f"<Location {self.name}>"
