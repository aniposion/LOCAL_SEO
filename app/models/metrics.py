"""P1: Attribution & Metrics models."""

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.account import Account


class SnapshotType(str, enum.Enum):
    """Metric snapshot period type."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class MetricSnapshot(BaseModel):
    """Daily/Weekly metric snapshots for attribution."""
    
    __tablename__ = "metric_snapshots"
    __table_args__ = (
        UniqueConstraint('location_id', 'snapshot_date', 'snapshot_type', name='uq_metric_snapshot_unique'),
    )
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    snapshot_type: Mapped[SnapshotType] = mapped_column(
        Enum(
            SnapshotType,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    
    # GBP Core Metrics
    calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    directions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    website_clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    profile_views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    photo_views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Review Metrics
    total_reviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_reviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1), nullable=True)
    
    # Deltas vs previous period
    calls_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    directions_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website_clicks_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Attribution - posts published in this period
    attributed_post_ids: Mapped[list | None] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), nullable=True
    )
    
    # ROI Estimation
    call_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("50.00"), nullable=False
    )
    
    # Raw API response for debugging
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="metric_snapshots")
    
    @property
    def estimated_revenue(self) -> Decimal:
        """Calculate estimated revenue from calls."""
        return Decimal(self.calls) * self.call_value


class UTMLink(BaseModel):
    """UTM tracking links for posts."""
    
    __tablename__ = "utm_links"
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    post_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    utm_url: Mapped[str] = mapped_column(Text, nullable=False)
    
    utm_source: Mapped[str] = mapped_column(String(50), default="gbp", nullable=False)
    utm_medium: Mapped[str] = mapped_column(String(50), default="post", nullable=False)
    utm_campaign: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location")


class WeeklyReport(BaseModel):
    """Generated weekly proof reports."""
    
    __tablename__ = "weekly_reports"
    __table_args__ = (
        UniqueConstraint('location_id', 'report_week', 'report_type', name='uq_weekly_report_unique'),
    )
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False
    )
    
    report_week: Mapped[date] = mapped_column(Date, nullable=False)  # Week start (Monday)
    report_type: Mapped[str] = mapped_column(String(20), default="weekly", nullable=False)
    
    # Snapshot references
    current_snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("metric_snapshots.id"),
        nullable=True
    )
    previous_snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("metric_snapshots.id"),
        nullable=True
    )
    
    # Report content
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Delivery tracking
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_to: Mapped[list | None] = mapped_column(ARRAY(String(255)), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location")
    account: Mapped["Account"] = relationship("Account")
    current_snapshot: Mapped["MetricSnapshot"] = relationship(
        "MetricSnapshot", foreign_keys=[current_snapshot_id]
    )
    previous_snapshot: Mapped["MetricSnapshot"] = relationship(
        "MetricSnapshot", foreign_keys=[previous_snapshot_id]
    )
