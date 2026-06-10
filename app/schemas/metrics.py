"""P1: Metrics & Attribution schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ====================
# MetricSnapshot Schemas
# ====================

class MetricSnapshotBase(BaseModel):
    """Base metrics data."""
    calls: int = 0
    directions: int = 0
    website_clicks: int = 0
    profile_views: int = 0
    photo_views: int = 0
    total_reviews: int = 0
    new_reviews: int = 0
    avg_rating: Optional[Decimal] = None


class MetricSnapshotCreate(MetricSnapshotBase):
    """Create snapshot manually."""
    location_id: UUID
    snapshot_date: date
    snapshot_type: str = "daily"  # daily, weekly, monthly
    call_value: Decimal = Decimal("50.00")


class MetricSnapshotResponse(MetricSnapshotBase):
    """Snapshot response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    snapshot_date: date
    snapshot_type: str
    calls_delta: Optional[int] = None
    directions_delta: Optional[int] = None
    website_clicks_delta: Optional[int] = None
    attributed_post_ids: list[UUID] = []
    call_value: Decimal
    estimated_revenue: Decimal
    created_at: datetime


class MetricSnapshotList(BaseModel):
    """List of snapshots."""
    items: list[MetricSnapshotResponse]
    total: int


# ====================
# Dashboard Schemas
# ====================

class MetricDelta(BaseModel):
    """Metric change between periods."""
    current: int
    previous: int
    delta: int
    percent_change: float


class DashboardMetrics(BaseModel):
    """Current period metrics summary."""
    calls: MetricDelta
    directions: MetricDelta
    website_clicks: MetricDelta
    profile_views: MetricDelta
    new_reviews: MetricDelta
    avg_rating: Optional[Decimal] = None
    estimated_revenue: Decimal


class DashboardHighlight(BaseModel):
    """Dashboard highlight item."""
    type: str  # "increase", "decrease", "milestone"
    metric: str
    message: str
    value: int
    percent: float


class TopPost(BaseModel):
    """Top contributing post."""
    id: UUID
    title: str
    published_at: Optional[datetime]
    platform: str
    estimated_impact: str  # "high", "medium", "low"


class ChartDataPoint(BaseModel):
    """Single point for chart."""
    date: date
    calls: int
    directions: int
    website_clicks: int


class DashboardResponse(BaseModel):
    """Full dashboard data."""
    location_id: UUID
    period_start: date
    period_end: date
    metrics: DashboardMetrics
    highlights: list[DashboardHighlight]
    top_posts: list[TopPost]
    chart_data: list[ChartDataPoint]


# ====================
# Weekly Report Schemas
# ====================

class WeeklyReportSummary(BaseModel):
    """Report summary data."""
    calls_total: int
    calls_delta: int
    calls_percent: float
    directions_total: int
    directions_delta: int
    directions_percent: float
    website_clicks_total: int
    new_reviews: int
    avg_rating: Optional[Decimal]
    estimated_revenue: Decimal
    top_day: str
    highlights: list[str]


class WeeklyReportCreate(BaseModel):
    """Create weekly report."""
    location_id: UUID
    report_week: date  # Monday of the week


class WeeklyReportResponse(BaseModel):
    """Weekly report response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    report_week: date
    report_type: str
    summary: WeeklyReportSummary
    pdf_url: Optional[str] = None
    sent_at: Optional[datetime] = None
    sent_to: list[str] = []
    created_at: datetime


class WeeklyReportList(BaseModel):
    """List of reports."""
    items: list[WeeklyReportResponse]
    total: int


class SendReportRequest(BaseModel):
    """Send report via email."""
    email_addresses: list[str]


# ====================
# UTM Link Schemas
# ====================

class UTMGenerateRequest(BaseModel):
    """Generate UTM link."""
    original_url: str
    campaign: Optional[str] = None
    post_id: Optional[UUID] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None


class UTMLinkResponse(BaseModel):
    """UTM link response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_url: str
    utm_url: str
    utm_source: str
    utm_medium: str
    utm_campaign: Optional[str]
    utm_content: Optional[str]
    clicks: int
    created_at: datetime


class UTMStatsResponse(BaseModel):
    """UTM stats."""
    total_links: int
    total_clicks: int
    links: list[UTMLinkResponse]
