"""Analytics schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class AnalyticsBase(BaseModel):
    """Base analytics schema."""

    platform: str
    date: date
    impressions: int | None = None
    clicks: int | None = None
    calls: int | None = None
    direction_requests: int | None = None
    reach: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    page_views: int | None = None
    unique_visitors: int | None = None


class AnalyticsCreate(AnalyticsBase):
    """Analytics creation schema."""

    location_id: UUID
    post_id: UUID | None = None
    source_raw: dict | None = None


class AnalyticsResponse(AnalyticsBase):
    """Analytics response schema."""

    id: UUID
    location_id: UUID
    post_id: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalyticsSummary(BaseModel):
    """Analytics summary response."""

    location_id: UUID
    period_start: date
    period_end: date
    gbp: dict | None = None
    instagram: dict | None = None
    website: dict | None = None
    totals: dict


class GBPIngestRequest(BaseModel):
    """GBP analytics ingest request."""

    location_id: UUID
    data: list[dict]


class IGIngestRequest(BaseModel):
    """Instagram analytics ingest request."""

    location_id: UUID
    data: list[dict]
