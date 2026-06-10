"""Content Calendar model for Autopilot scheduling."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


def utcnow_aware() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class ContentCalendar(BaseModel):
    """Monthly/weekly content calendar for autopilot."""

    __tablename__ = "content_calendar"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
    )

    # Time period
    week_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    month_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Content plan
    theme: Mapped[str | None] = mapped_column(String(200), nullable=True)
    offer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cta: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_platforms: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # ["GBP", "INSTAGRAM", "WEBSITE"]
    image_concept: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Generation metadata
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Linked posts
    post_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="content_calendars")

    def __repr__(self) -> str:
        return f"<ContentCalendar {self.week_of}: {self.theme}>"


class ContentUsageHistory(BaseModel):
    """Track content usage for duplicate prevention."""

    __tablename__ = "content_usage_history"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
    )

    # Content details
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'theme', 'offer', 'cta', 'hashtag'
    content_value: Mapped[str] = mapped_column(Text, nullable=False)

    # Embedding for similarity check (stored as JSONB for simplicity)
    # In production, use pgvector extension
    embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Usage tracking
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow_aware
    )
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ContentUsage {self.content_type}: {self.content_value[:30]}>"


class AutopilotSettings(BaseModel):
    """Autopilot configuration per location."""

    __tablename__ = "autopilot_settings"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # Enabled
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Frequency
    posts_per_week: Mapped[int] = mapped_column(default=2)
    preferred_days: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # ["tuesday", "thursday"]
    preferred_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # "11:00"

    # Target platforms
    platforms: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # ["GBP", "INSTAGRAM"]

    # Content preferences
    theme_preferences: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # ["seasonal", "promotion", "educational"]

    # Exclusions
    excluded_topics: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Auto-approval
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="autopilot_settings")

    def __repr__(self) -> str:
        return f"<AutopilotSettings location={self.location_id} enabled={self.enabled}>"
