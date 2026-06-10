"""Recommendation model for action plans and ROI tracking."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


class RecommendationType(str, enum.Enum):
    """Action recommendation types."""
    PHOTO_UPLOAD = "photo_upload"
    POST_PUBLISH = "post_publish"
    HOURS_UPDATE = "hours_update"
    CATEGORY_FIX = "category_fix"
    DESCRIPTION_UPDATE = "description_update"
    REVIEW_RESPONSE = "review_response"
    QA_RESPONSE = "qa_response"
    WEBSITE_UPDATE = "website_update"


class EffortLevel(str, enum.Enum):
    """Effort level for recommendations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationStatus(str, enum.Enum):
    """Recommendation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class Recommendation(BaseModel):
    """Action recommendation with ROI prediction."""

    __tablename__ = "recommendations"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
    )
    audit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_audits.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Action details
    type: Mapped[RecommendationType] = mapped_column(
        Enum(RecommendationType), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Priority scoring
    impact_score: Mapped[int] = mapped_column(Integer, default=50)  # 1-100
    effort: Mapped[EffortLevel] = mapped_column(
        Enum(EffortLevel), default=EffortLevel.MEDIUM
    )
    autopilot_possible: Mapped[bool] = mapped_column(Boolean, default=False)

    # Expected ROI (percentage lift)
    expected_calls_lift: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    expected_directions_lift: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    expected_views_lift: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # Status tracking
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus), default=RecommendationStatus.PENDING
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Week assignment
    week_of: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="recommendations")

    def __repr__(self) -> str:
        return f"<Recommendation {self.type.value}: {self.title}>"

    @property
    def is_auto(self) -> bool:
        """Check if this can be auto-executed."""
        return self.autopilot_possible

    @property
    def priority_score(self) -> float:
        """Calculate priority score (impact / effort)."""
        effort_weights = {
            EffortLevel.LOW: 1,
            EffortLevel.MEDIUM: 2,
            EffortLevel.HIGH: 3,
        }
        return self.impact_score / effort_weights[self.effort]


class PerformanceTracking(BaseModel):
    """Weekly performance metrics tracking."""

    __tablename__ = "performance_tracking"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
    )

    week_of: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Absolute metrics
    calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    directions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1), nullable=True)

    # Week-over-week change (percentage)
    calls_change: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    directions_change: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    views_change: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    def __repr__(self) -> str:
        return f"<PerformanceTracking {self.week_of}: calls={self.calls}>"
