"""Lead management models for Review Booster and Missed Call Text Back."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


# ============================================================================
# Review Booster Models
# ============================================================================

class ReviewRequestChannel(str, enum.Enum):
    """Review request delivery channel."""
    SMS = "sms"
    EMAIL = "email"
    BOTH = "both"


class GateSentiment(str, enum.Enum):
    """Rating gate sentiment."""
    POSITIVE = "positive"   # 4-5 stars
    NEUTRAL = "neutral"     # 3 stars
    NEGATIVE = "negative"   # 1-2 stars


class ReviewRequest(BaseModel):
    """Track review requests and conversions."""

    __tablename__ = "review_requests"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
    )

    # Customer info
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Delivery channel
    channel: Mapped[ReviewRequestChannel] = mapped_column(
        Enum(ReviewRequestChannel), default=ReviewRequestChannel.SMS
    )

    # Tracking timestamps
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    clicked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rating_gate_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Gate results
    gate_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    gate_sentiment: Mapped[GateSentiment | None] = mapped_column(
        Enum(GateSentiment), nullable=True
    )

    # Conversion tracking
    google_review_clicked: Mapped[bool] = mapped_column(Boolean, default=False)
    google_review_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    internal_feedback_submitted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Resolution
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    support_ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Metadata
    visit_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    service_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    location: Mapped["Location"] = relationship("Location")

    def __repr__(self) -> str:
        return f"<ReviewRequest {self.customer_name} sentiment={self.gate_sentiment}>"


class IssueCategory(str, enum.Enum):
    """Support ticket issue categories."""
    SERVICE = "service"
    STAFF = "staff"
    CLEANLINESS = "cleanliness"
    PRICE = "price"
    RESULT = "result"
    ATMOSPHERE = "atmosphere"
    WAIT_TIME = "wait_time"
    OTHER = "other"


class TicketStatus(str, enum.Enum):
    """Support ticket status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ResolutionType(str, enum.Enum):
    """Ticket resolution types."""
    CALLBACK = "callback"
    COUPON = "coupon"
    REFUND = "refund"
    APOLOGY = "apology"
    REDO_SERVICE = "redo_service"
    NO_ACTION = "no_action"


class SupportTicket(BaseModel):
    """Internal support ticket for negative feedback handling."""

    __tablename__ = "support_tickets"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
    )

    # Source
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'review_booster', 'google_review', 'direct', 'missed_call'
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Customer info
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Issue details
    issue_category: Mapped[IssueCategory | None] = mapped_column(
        Enum(IssueCategory), nullable=True
    )
    issue_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Status
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.OPEN
    )
    priority: Mapped[int] = mapped_column(Integer, default=2)  # 1=high, 2=medium, 3=low

    # Resolution
    resolution_type: Mapped[ResolutionType | None] = mapped_column(
        Enum(ResolutionType), nullable=True
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Follow-up actions
    coupon_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    coupon_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    callback_scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    callback_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    callback_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Assignment
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    location: Mapped["Location"] = relationship("Location")

    def __repr__(self) -> str:
        return f"<SupportTicket {self.status.value} category={self.issue_category}>"


# ============================================================================
# Missed Call Text Back - Lead Conversion Models
# ============================================================================

class CallIntent(str, enum.Enum):
    """Classified call/message intent."""
    BOOKING = "booking"
    PRICING = "pricing"
    INQUIRY = "inquiry"
    COMPLAINT = "complaint"
    OTHER = "other"


class FollowupType(str, enum.Enum):
    """Follow-up action types."""
    BOOKING_LINK = "booking_link"
    PRICE_INFO = "price_info"
    CALLBACK = "callback"
    AI_RESPONSE = "ai_response"
    HUMAN_HANDOFF = "human_handoff"


class CallLead(BaseModel):
    """Missed call lead tracking and conversion."""

    __tablename__ = "call_leads"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
    )

    # Call info
    caller_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    call_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    call_status: Mapped[str] = mapped_column(String(30), nullable=False)
    # 'answered', 'missed', 'voicemail'
    call_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # seconds

    # SMS sent
    sms_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sms_template_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sms_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Customer response
    customer_replied: Mapped[bool] = mapped_column(Boolean, default=False)
    customer_reply_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    customer_reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Intent classification (AI)
    intent: Mapped[CallIntent | None] = mapped_column(Enum(CallIntent), nullable=True)
    intent_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    intent_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Follow-up action
    followup_type: Mapped[FollowupType | None] = mapped_column(
        Enum(FollowupType), nullable=True
    )
    followup_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    followup_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Conversion tracking
    booking_link_clicked: Mapped[bool] = mapped_column(Boolean, default=False)
    booking_link_clicked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    booking_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    booking_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Revenue estimation
    estimated_revenue: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    actual_revenue: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    # Metadata
    twilio_call_sid: Mapped[str | None] = mapped_column(String(50), nullable=True)
    twilio_sms_sid: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    location: Mapped["Location"] = relationship("Location")

    def __repr__(self) -> str:
        return f"<CallLead {self.caller_phone} intent={self.intent}>"

    @property
    def converted(self) -> bool:
        """Check if lead converted to booking."""
        return self.booking_completed

    @property
    def response_rate(self) -> bool:
        """Check if customer responded."""
        return self.customer_replied
