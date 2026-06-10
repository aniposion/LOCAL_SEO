"""P2: Compliance-Safe Review Booster models."""

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.account import Account


def utcnow_aware() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class CampaignStatus(str, enum.Enum):
    """Review campaign status."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class RequestChannel(str, enum.Enum):
    """Review request delivery channel."""
    SMS = "sms"
    EMAIL = "email"


class RequestStatus(str, enum.Enum):
    """Review request status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    OPTED_OUT = "opted_out"


class FeedbackStatus(str, enum.Enum):
    """Private feedback handling status."""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ReviewCampaign(BaseModel):
    """Review request campaign settings."""
    
    __tablename__ = "review_campaigns"
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(
            CampaignStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=CampaignStatus.ACTIVE,
        nullable=False
    )
    
    # Templates
    sms_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Settings
    delay_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    channels: Mapped[list] = mapped_column(
        ARRAY(String(10)), default=["sms"], nullable=False
    )
    
    # Links - Google link is ALWAYS provided (compliance)
    google_review_url: Mapped[str] = mapped_column(Text, nullable=False)
    private_feedback_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Stats (denormalized)
    total_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_clicked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_reviews_estimated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="review_campaigns")
    requests: Mapped[list["BoosterRequest"]] = relationship(
        "BoosterRequest", back_populates="campaign", cascade="all, delete-orphan"
    )


class BoosterRequest(BaseModel):
    """Individual review request - with compliance logging.
    
    COMPLIANCE REQUIREMENTS:
    - google_link_included MUST always be TRUE
    - No gating: all customers get the same Google review link
    - Message content preserved for 7 years (audit trail)
    """
    
    __tablename__ = "booster_requests"
    __table_args__ = (
        # Compliance constraint: Google link must ALWAYS be included
        CheckConstraint('google_link_included = TRUE', name='compliance_google_link'),
    )
    
    campaign_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("review_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Customer info (encrypt in production)
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Consent - REQUIRED for compliance
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Request details
    channel: Mapped[RequestChannel] = mapped_column(
        Enum(
            RequestChannel,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(
            RequestStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=RequestStatus.PENDING,
        nullable=False
    )
    
    # Message content - PRESERVED FOR AUDIT (7 years)
    message_content: Mapped[str] = mapped_column(Text, nullable=False)
    google_link_included: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    feedback_link_included: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    
    # Tracking
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_link_clicked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    feedback_link_clicked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Opt-out
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # External IDs
    twilio_message_sid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sendgrid_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Relationships
    campaign: Mapped["ReviewCampaign"] = relationship("ReviewCampaign", back_populates="requests")
    location: Mapped["Location"] = relationship("Location")


class ReviewOptout(BaseModel):
    """Opt-out management for review requests."""
    
    __tablename__ = "review_optouts"
    __table_args__ = (
        UniqueConstraint('location_id', 'phone', name='uq_optout_phone'),
        UniqueConstraint('location_id', 'email', name='uq_optout_email'),
    )
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    opted_out_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow_aware, nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location")


class PrivateFeedback(BaseModel):
    """Private feedback collected instead of public review."""
    
    __tablename__ = "private_feedbacks"
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    booster_request_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("booster_requests.id", ondelete="SET NULL"),
        nullable=True
    )
    
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Internal handling
    status: Mapped[FeedbackStatus] = mapped_column(
        Enum(
            FeedbackStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=FeedbackStatus.NEW,
        nullable=False
    )
    assigned_to: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location")
    request: Mapped["BoosterRequest"] = relationship("BoosterRequest")
    assignee: Mapped["Account"] = relationship("Account")
