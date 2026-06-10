"""Review response models for AI Smart Review Responder."""

import enum
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base, UUID


def utcnow_naive() -> datetime:
    """Return a UTC timestamp without tzinfo for naive DB columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class ReviewIntent(str, enum.Enum):
    """Intent classification for reviews."""

    PRAISE = "praise"  # Positive feedback
    COMPLAINT = "complaint"  # Negative feedback
    SUGGESTION = "suggestion"  # Constructive feedback
    QUESTION = "question"  # Asking for information
    MISUNDERSTANDING = "misunderstanding"  # Incorrect information


class ResponseStatus(str, enum.Enum):
    """Status of review response."""

    PENDING = "pending"  # Waiting for approval
    APPROVED = "approved"  # Approved by owner
    REJECTED = "rejected"  # Rejected by owner
    PUBLISHED = "published"  # Published to platform
    FAILED = "failed"  # Failed to publish


class ReviewResponse(Base):
    """AI-generated review responses with approval workflow."""

    __tablename__ = "review_responses"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(UUID(), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Review information
    review_id = Column(String(255), unique=True, nullable=False, index=True)
    review_author = Column(String(255))
    review_rating = Column(Integer, nullable=False)
    review_text = Column(Text)
    review_date = Column(DateTime)
    
    # Platform info
    platform = Column(String(50), default="google")  # google, facebook, yelp, etc.
    platform_review_url = Column(String(500))
    
    # AI Analysis
    sentiment_score = Column(Float)  # -1.0 (negative) to 1.0 (positive)
    detected_issues = Column(Text)  # JSON list of detected issues
    
    # AI-generated response
    ai_draft = Column(Text, nullable=False)
    tone = Column(String(50))  # professional, warm, empathetic, apologetic
    generated_by_ai = Column(String(50), default="gemini-1.5-flash")
    
    # Approval workflow
    intent = Column(
        Enum(
            ReviewIntent,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    status = Column(
        Enum(
            ResponseStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=ResponseStatus.PENDING,
        nullable=False,
    )
    approved_by = Column(UUID(), ForeignKey("accounts.id"), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Publishing
    published_at = Column(DateTime, nullable=True)
    platform_response_id = Column(String(255), nullable=True)
    publish_error = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    location = relationship("Location")
    approver = relationship("Account", foreign_keys=[approved_by])


class BulkRetryLog(Base):
    """Persisted record of each bulk-retry operation for health summaries."""

    __tablename__ = "review_bulk_retry_logs"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(UUID(), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    total = Column(Integer, nullable=False)
    succeeded = Column(Integer, nullable=False)
    still_failed = Column(Integer, nullable=False)
    skipped = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)


class ReviewWebhook(Base):
    """Webhook events for new reviews."""

    __tablename__ = "review_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(UUID(), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Webhook data
    platform = Column(String(50), nullable=False)
    event_type = Column(String(100))  # new_review, updated_review, deleted_review
    review_id = Column(String(255), nullable=False)
    payload = Column(Text)  # JSON payload
    
    # Processing
    processed = Column(Integer, default=0)  # 0=pending, 1=processed, 2=failed
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    
    # Relationships
    location = relationship("Location")
