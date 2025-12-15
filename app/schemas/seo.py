"""SEO score and recommendation schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SEOScoreBase(BaseModel):
    """Base SEO score schema."""

    score: float = Field(ge=0, le=100)
    factors: dict | None = None
    rationale: str | None = None
    recommendations: dict | None = None


class SEOScoreCreate(SEOScoreBase):
    """SEO score creation schema."""

    location_id: UUID
    date: date


class SEOScoreResponse(SEOScoreBase):
    """SEO score response schema."""

    id: UUID
    location_id: UUID
    date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class SEORecalcRequest(BaseModel):
    """SEO score recalculation request."""

    location_id: UUID
    from_date: date
    to_date: date


class SEORecommendation(BaseModel):
    """SEO recommendation response."""

    location_id: UUID
    next_best_time: datetime | None = None
    topics: list[str]
    hashtags: list[str]
    rationale: str
    confidence: float = Field(ge=0, le=1)


class SEOTrend(BaseModel):
    """SEO trend data."""

    date: date
    score: float
    change: float | None = None
