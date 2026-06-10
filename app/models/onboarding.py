"""Onboarding audit models."""

import enum
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import JSON, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from sqlalchemy.dialects.postgresql import JSONB


class OnboardingStatus(str, enum.Enum):
    """Onboarding process status."""
    PENDING = "pending"
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditGrade(str, enum.Enum):
    """Audit score grade."""
    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"
    B_MINUS = "B-"
    C_PLUS = "C+"
    C = "C"
    D = "D"
    F = "F"


class OnboardingAudit(Base):
    """Onboarding audit results for new users."""

    __tablename__ = "onboarding_audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True)
    contact_email = Column(String(255), nullable=True)
    
    # Business input
    business_name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=False)
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(50), default="US")
    phone = Column(String(50))
    website_url = Column(String(500))
    
    # Google Places matching
    place_id = Column(String(255))
    matched_name = Column(String(255))
    matched_address = Column(String(500))
    category = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    place_candidates = Column(JSON)  # Multiple candidates if ambiguous
    
    # Collected data
    review_count = Column(Integer, default=0)
    average_rating = Column(Float)
    latest_review_date = Column(DateTime(timezone=True))
    photo_count = Column(Integer, default=0)
    has_hours = Column(Boolean, default=False)
    has_phone = Column(Boolean, default=False)
    has_website = Column(Boolean, default=False)
    has_description = Column(Boolean, default=False)
    
    # Post/activity data
    latest_post_date = Column(DateTime(timezone=True))
    post_count_30_days = Column(Integer, default=0)
    
    # Competitor data
    competitor_avg_reviews = Column(Float)
    competitor_avg_rating = Column(Float)
    competitor_count = Column(Integer, default=0)
    competitors_data = Column(JSON)  # Top 5 competitors
    
    # Social presence
    has_instagram = Column(Boolean)
    instagram_handle = Column(String(100))
    has_facebook = Column(Boolean)
    has_yelp = Column(Boolean)
    
    # Scores
    total_score = Column(Float)  # 0-100
    grade = Column(
        Enum(AuditGrade, values_callable=lambda enum_cls: [item.value for item in enum_cls])
    )
    review_score = Column(Float)
    activity_score = Column(Float)
    completeness_score = Column(Float)
    competition_score = Column(Float)
    
    # AI Analysis
    estimated_monthly_loss = Column(Float)  # Estimated $ loss
    estimated_missed_calls = Column(Integer)  # Missed phone calls
    summary = Column(Text)  # AI-generated summary
    recommendations = Column(JSON)  # List of recommendations
    recommended_plan = Column(String(50))  # starter, pro, agency
    
    # Status
    status = Column(
        Enum(
            OnboardingStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=OnboardingStatus.PENDING,
    )
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    account = relationship("Account", back_populates="onboarding_audit")

    def to_result_dict(self) -> dict[str, Any]:
        """Convert to result dictionary for API response."""
        return {
            "business": {
                "name": self.matched_name or self.business_name,
                "address": self.matched_address or self.address,
                "category": self.category,
                "rating": self.average_rating,
                "review_count": self.review_count,
                "photo_count": self.photo_count,
            },
            "scores": {
                "total": self.total_score,
                "grade": self.grade.value if self.grade else None,
                "review": self.review_score,
                "activity": self.activity_score,
                "completeness": self.completeness_score,
                "competition": self.competition_score,
            },
            "diagnosis": {
                "review_gap": max(0, (self.competitor_avg_reviews or 0) - self.review_count),
                "days_since_post": self._days_since_post(),
                "missing_info": self._get_missing_info(),
            },
            "estimated_loss": {
                "monthly_dollars": self.estimated_monthly_loss,
                "missed_calls": self.estimated_missed_calls,
            },
            "summary": self.summary,
            "recommendations": self.recommendations or [],
            "recommended_plan": self.recommended_plan,
        }

    def _days_since_post(self) -> int | None:
        """Calculate days since last post."""
        if not self.latest_post_date:
            return None
        delta = datetime.now(self.latest_post_date.tzinfo) - self.latest_post_date
        return delta.days

    def _get_missing_info(self) -> list[str]:
        """Get list of missing profile information."""
        missing = []
        if not self.has_hours:
            missing.append("business_hours")
        if not self.has_phone:
            missing.append("phone_number")
        if not self.has_website:
            missing.append("website")
        if not self.has_description:
            missing.append("description")
        if (self.photo_count or 0) < 5:
            missing.append("photos")
        return missing


class OnboardingProgress(Base):
    """
    User onboarding progress tracking.
    
    Tracks completion of key activation steps to measure time-to-activation.
    """
    __tablename__ = "onboarding_progress"
    
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    completed_steps = Column(Integer, nullable=False, default=0)
    total_steps = Column(Integer, nullable=False, default=4)
    current_step = Column(String(50), nullable=True)
    steps_data = Column(JSONB, nullable=False, server_default='{}')
    # steps_data: {"run_audit": "2026-01-05T10:00:00Z", "view_insights": null, ...}
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now())
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(), onupdate=lambda: datetime.now())
    
    # Relationships
    account = relationship("Account", back_populates="onboarding_progress")
    
    def __repr__(self):
        return f"<OnboardingProgress account={self.account_id} {self.completed_steps}/{self.total_steps}>"
    
    @property
    def is_completed(self) -> bool:
        """Check if onboarding is completed."""
        return self.completed_steps >= self.total_steps
    
    @property
    def completion_percentage(self) -> float:
        """Get completion percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100
