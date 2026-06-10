"""Competitor analysis schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Competitor schemas
class CompetitorBase(BaseModel):
    """Base competitor schema."""

    place_id: str
    name: str
    address: Optional[str] = None
    business_type: Optional[str] = None
    rating: float = 0.0
    review_count: int = 0
    distance_miles: Optional[float] = None


class CompetitorCreate(CompetitorBase):
    """Schema for creating a competitor."""

    location_id: UUID
    raw_data: Optional[dict[str, Any]] = None


class CompetitorUpdate(BaseModel):
    """Schema for updating a competitor."""

    rating: Optional[float] = None
    review_count: Optional[int] = None
    status: Optional[str] = None
    raw_data: Optional[dict[str, Any]] = None


class CompetitorResponse(CompetitorBase):
    """Schema for competitor response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_id: UUID
    status: str
    last_synced_at: Optional[datetime] = None
    last_review_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# Analysis schemas
class ActionItem(BaseModel):
    """Recommended action item."""

    title: str = Field(..., description="Action title")
    description: str = Field(..., description="Detailed description")
    priority: str = Field(..., description="Priority: high, medium, low")
    effort: str = Field(..., description="Effort level: low, medium, high")


class CompetitorAnalysisBase(BaseModel):
    """Base analysis schema."""

    week_start: datetime
    week_end: datetime
    trending_keywords: list[str] = Field(default_factory=list)
    threat_level: str = Field(..., description="Threat level: low, medium, high")
    rating_trend: str = Field(..., description="Rating trend: improving, declining, stable")
    recommended_actions: list[ActionItem] = Field(default_factory=list)
    summary_text: str


class CompetitorAnalysisCreate(CompetitorAnalysisBase):
    """Schema for creating an analysis."""

    location_id: UUID
    competitor_id: Optional[int] = None
    metrics_snapshot: Optional[dict[str, Any]] = None
    generated_by_ai: str = "gemini-1.5-flash"


class CompetitorAnalysisResponse(CompetitorAnalysisBase):
    """Schema for analysis response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_id: UUID
    competitor_id: Optional[int] = None
    metrics_snapshot: Optional[dict[str, Any]] = None
    generated_by_ai: str
    created_at: datetime


class CompetitorReportFreshness(BaseModel):
    """Freshness and trust signals for competitor reporting."""

    last_analysis_at: Optional[datetime] = None
    analysis_age_minutes: Optional[int] = None
    cache_age_minutes: Optional[int] = None
    last_review_sync_at: Optional[datetime] = None
    last_review_sync_age_minutes: Optional[int] = None
    review_sample_size: int = 0
    freshness_status: str = Field(..., description="fresh, attention, stale")
    freshness_notes: list[str] = Field(default_factory=list)


class WeeklyCompetitorReport(BaseModel):
    """Weekly competitor analysis report."""

    location_id: UUID
    week_start: datetime
    week_end: datetime
    competitors: list[CompetitorResponse]
    analysis: CompetitorAnalysisResponse
    overall_threat_level: str
    key_insights: list[str]
    freshness: CompetitorReportFreshness


# Review schemas
class CompetitorReviewBase(BaseModel):
    """Base review schema."""

    review_id: str
    author_name: Optional[str] = None
    rating: int
    text: Optional[str] = None
    publish_time: Optional[datetime] = None


class CompetitorReviewCreate(CompetitorReviewBase):
    """Schema for creating a review."""

    competitor_id: int
    extracted_keywords: Optional[list[str]] = None
    sentiment_score: Optional[float] = None


class CompetitorReviewResponse(CompetitorReviewBase):
    """Schema for review response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    competitor_id: int
    extracted_keywords: Optional[list[str]] = None
    sentiment_score: Optional[float] = None
    created_at: datetime


# Request schemas
class CompetitorSearchRequest(BaseModel):
    """Request to search for competitors."""

    location_id: UUID
    radius_miles: float = Field(default=3.0, ge=0.1, le=10.0)
    business_type: str = Field(..., description="Business type/category to search")
    max_results: int = Field(default=3, ge=1, le=10)


class GenerateAnalysisRequest(BaseModel):
    """Request to generate competitor analysis."""

    location_id: UUID
    force_refresh: bool = Field(default=False, description="Force refresh even if cached")
