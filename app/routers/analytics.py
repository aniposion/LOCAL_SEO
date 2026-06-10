"""Analytics router."""

from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.analytics import Analytics
from app.models.location import Location
from app.routers.deps import get_current_user
from app.schemas.analytics import (
    AnalyticsResponse,
    AnalyticsSummary,
    GBPIngestRequest,
    IGIngestRequest,
    ROIReport,
    TimeSeriesData,
)
from app.services.roi_service import ROIService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _json_safe(value: Any) -> Any:
    """Convert analytics provider payloads into JSON-safe values."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _parse_analytics_date(value: Any) -> date:
    """Accept API/provider dates as date, datetime, or ISO string."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    return date.today()


def _upsert_analytics(
    db: Session,
    *,
    location_id: UUID,
    platform: str,
    item: dict,
    fields: list[str],
) -> Analytics:
    """Create or update one daily analytics row for a location/platform/date."""
    analytics_date = _parse_analytics_date(item.get("date"))
    normalized_platform = platform.upper()
    analytics = (
        db.query(Analytics)
        .filter(
            Analytics.location_id == location_id,
            Analytics.platform == normalized_platform,
            Analytics.date == analytics_date,
        )
        .first()
    )
    if not analytics:
        analytics = Analytics(
            location_id=location_id,
            platform=normalized_platform,
            date=analytics_date,
        )
        db.add(analytics)

    for field in fields:
        setattr(analytics, field, item.get(field))
    analytics.source_raw = _json_safe(item)
    return analytics


@router.get("/summary", response_model=AnalyticsSummary)
def get_analytics_summary(
    location_id: UUID,
    from_date: date = Query(default_factory=lambda: date.today() - timedelta(days=7)),
    to_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> AnalyticsSummary:
    """Get analytics summary for a location."""
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Query analytics
    analytics = (
        db.query(Analytics)
        .filter(
            Analytics.location_id == location_id,
            Analytics.date >= from_date,
            Analytics.date <= to_date,
        )
        .all()
    )

    # Aggregate by platform
    gbp_data = {"impressions": 0, "clicks": 0, "calls": 0, "direction_requests": 0}
    ig_data = {"reach": 0, "likes": 0, "comments": 0, "shares": 0, "saves": 0}
    web_data = {"page_views": 0, "unique_visitors": 0}

    for a in analytics:
        platform = (a.platform or "").upper()
        if platform == "GBP":
            gbp_data["impressions"] += a.impressions or 0
            gbp_data["clicks"] += a.clicks or 0
            gbp_data["calls"] += a.calls or 0
            gbp_data["direction_requests"] += a.direction_requests or 0
        elif platform == "INSTAGRAM":
            ig_data["reach"] += a.reach or 0
            ig_data["likes"] += a.likes or 0
            ig_data["comments"] += a.comments or 0
            ig_data["shares"] += a.shares or 0
            ig_data["saves"] += a.saves or 0
        elif platform == "WEBSITE":
            web_data["page_views"] += a.page_views or 0
            web_data["unique_visitors"] += a.unique_visitors or 0

    totals = {
        "total_impressions": gbp_data["impressions"] + ig_data["reach"] + web_data["page_views"],
        "total_engagement": gbp_data["clicks"] + ig_data["likes"] + ig_data["comments"],
        "total_conversions": gbp_data["calls"] + gbp_data["direction_requests"],
    }

    return AnalyticsSummary(
        location_id=location_id,
        period_start=from_date,
        period_end=to_date,
        gbp=gbp_data,
        instagram=ig_data,
        website=web_data,
        totals=totals,
    )


@router.post("/ingest/gbp", status_code=status.HTTP_201_CREATED)
def ingest_gbp_analytics(
    request: GBPIngestRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Ingest GBP analytics data."""
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == request.location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    count = 0
    for item in request.data:
        _upsert_analytics(
            db,
            location_id=request.location_id,
            platform="GBP",
            item=item,
            fields=["impressions", "clicks", "calls", "direction_requests"],
        )
        count += 1

    db.commit()
    return {"ingested": count}


@router.post("/ingest/ig", status_code=status.HTTP_201_CREATED)
def ingest_ig_analytics(
    request: IGIngestRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Ingest Instagram analytics data."""
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == request.location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    count = 0
    for item in request.data:
        _upsert_analytics(
            db,
            location_id=request.location_id,
            platform="INSTAGRAM",
            item=item,
            fields=["reach", "likes", "comments", "shares", "saves"],
        )
        count += 1

    db.commit()
    return {"ingested": count}


@router.get("/roi", response_model=ROIReport)
async def get_roi_report(
    location_id: UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> ROIReport:
    """
    Get ROI report for a location.
    
    Calculates time saved, money saved, and engagement boost from AI automation.
    """
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Generate ROI report
    roi_service = ROIService(db)
    report = roi_service.generate_roi_report(location_id, start_date, end_date)

    return report


@router.get("/roi/time-series", response_model=TimeSeriesData)
async def get_roi_time_series(
    location_id: UUID,
    metric: str = Query(..., description="Metric name: review_responses, posts, or time_saved"),
    days_back: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> TimeSeriesData:
    """
    Get time series data for ROI metrics.
    
    Useful for charts and trend visualization.
    """
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Get time series data
    roi_service = ROIService(db)
    data = roi_service.get_time_series_data(location_id, metric, days_back)

    return data
