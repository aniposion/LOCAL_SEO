"""Social proof models for card news generation."""

import enum
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base, UUID


def utcnow_naive() -> datetime:
    """Return a UTC timestamp without tzinfo for naive DB columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class SocialProofStatus(str, enum.Enum):
    """Status of social proof card."""

    DRAFT = "draft"  # Generated but not approved
    PENDING = "pending"  # Waiting for approval
    APPROVED = "approved"  # Approved by owner
    REJECTED = "rejected"  # Rejected by owner
    PUBLISHED = "published"  # Published to social media


class SocialProofCard(Base):
    """Social proof card news generated from reviews."""

    __tablename__ = "social_proof_cards"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(UUID(), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Source review
    review_id = Column(String(255), nullable=False, index=True)
    review_author = Column(String(255))
    review_rating = Column(Integer, nullable=False)
    review_text = Column(Text, nullable=False)
    review_date = Column(DateTime)
    
    # Generated content
    card_title = Column(String(255))  # Extracted key phrase
    card_text = Column(Text)  # Formatted review text for card
    
    # Image generation
    image_prompt = Column(Text)  # Prompt used for Imagen 3
    image_url = Column(String(500))  # S3 URL of generated image
    background_image_url = Column(String(500))  # AI-generated background
    final_card_url = Column(String(500))  # Final composed card with text overlay
    
    # Design settings
    layout_style = Column(String(50), default="instagram_square")  # instagram_square, story, etc.
    text_color = Column(String(20), default="#FFFFFF")
    background_color = Column(String(20), default="#000000")
    font_family = Column(String(100), default="Arial")
    
    # Approval workflow
    status = Column(
        Enum(
            SocialProofStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=SocialProofStatus.DRAFT,
        nullable=False,
    )
    approved_by = Column(UUID(), ForeignKey("accounts.id"), nullable=True, index=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Publishing
    published_to = Column(String(50), nullable=True)  # instagram, facebook, etc.
    published_at = Column(DateTime, nullable=True)
    platform_post_id = Column(String(255), nullable=True)
    
    # Metadata
    generated_by_ai = Column(String(50), default="imagen-3")
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    location = relationship("Location")
    approver = relationship("Account", foreign_keys=[approved_by])


class SocialProofSchedule(Base):
    """Schedule for automatic social proof generation."""

    __tablename__ = "social_proof_schedules"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(UUID(), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Schedule settings
    enabled = Column(Integer, default=1)  # 0=disabled, 1=enabled
    frequency = Column(String(50), default="weekly")  # daily, weekly, biweekly, monthly
    day_of_week = Column(Integer, default=0)  # 0=Sunday, 6=Saturday
    time_of_day = Column(String(10), default="18:00")  # HH:MM format
    
    # Selection criteria
    min_rating = Column(Integer, default=5)  # Minimum rating to consider
    min_text_length = Column(Integer, default=50)  # Minimum review text length
    max_cards_per_run = Column(Integer, default=1)  # Number of cards to generate
    
    # Auto-approval settings
    auto_approve = Column(Integer, default=0)  # 0=manual approval, 1=auto-approve
    auto_publish = Column(Integer, default=0)  # 0=manual publish, 1=auto-publish
    
    # Last run
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    location = relationship("Location")
