"""Competitor analysis models for Stealth Watch feature."""

import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base, UUID


def utcnow_naive() -> datetime:
    """Return a UTC timestamp without tzinfo for naive DB columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class CompetitorStatus(str, enum.Enum):
    """Status of competitor tracking."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    REMOVED = "removed"


class Competitor(Base):
    """Competitor business tracked for analysis."""

    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(UUID(), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Google Places data
    place_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    address = Column(String(500))
    business_type = Column(String(100))
    
    # Metrics
    rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    distance_miles = Column(Float)  # Distance from user's business
    
    # Status
    status = Column(
        Enum(
            CompetitorStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=CompetitorStatus.ACTIVE,
        nullable=False,
    )
    
    # Metadata
    raw_data = Column(JSON)  # Store full Google Places response
    last_synced_at = Column(DateTime, nullable=True)
    last_review_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    location = relationship("Location", back_populates="competitors")
    analyses = relationship("CompetitorAnalysis", back_populates="competitor", cascade="all, delete-orphan")


class CompetitorAnalysis(Base):
    """Weekly competitor analysis report."""

    __tablename__ = "competitor_analyses"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(UUID(), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id", ondelete="CASCADE"), nullable=True)
    
    # Analysis period
    week_start = Column(DateTime, nullable=False)
    week_end = Column(DateTime, nullable=False)
    
    # AI-generated insights
    trending_keywords = Column(JSON)  # List of trending keywords from reviews
    threat_level = Column(String(20))  # "low", "medium", "high"
    rating_trend = Column(String(20))  # "improving", "declining", "stable"
    
    # Recommendations
    recommended_actions = Column(JSON)  # List of 3 action items
    summary_text = Column(Text)  # AI-generated summary
    
    # Metrics comparison
    metrics_snapshot = Column(JSON)  # Store competitor metrics at analysis time
    
    # Metadata
    generated_by_ai = Column(String(50), default="gemini-1.5-flash")
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    
    # Relationships
    location = relationship("Location")
    competitor = relationship("Competitor", back_populates="analyses")


class CompetitorReview(Base):
    """Cached competitor reviews for analysis."""

    __tablename__ = "competitor_reviews"

    id = Column(Integer, primary_key=True, index=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id", ondelete="CASCADE"), nullable=False)
    
    # Review data
    review_id = Column(String(255), unique=True, nullable=False, index=True)
    author_name = Column(String(255))
    rating = Column(Integer, nullable=False)
    text = Column(Text)
    publish_time = Column(DateTime)
    
    # Analysis cache (7 days)
    extracted_keywords = Column(JSON)
    sentiment_score = Column(Float)  # -1.0 to 1.0
    
    # Metadata
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    
    # Relationships
    competitor = relationship("Competitor")
