"""Analytics router."""

from datetime import date, timedelta
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
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


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
        if a.platform == "GBP":
            gbp_data["impressions"] += a.impressions or 0
            gbp_data["clicks"] += a.clicks or 0
            gbp_data["calls"] += a.calls or 0
            gbp_data["direction_requests"] += a.direction_requests or 0
        elif a.platform == "INSTAGRAM":
            ig_data["reach"] += a.reach or 0
            ig_data["likes"] += a.likes or 0
            ig_data["comments"] += a.comments or 0
            ig_data["shares"] += a.shares or 0
            ig_data["saves"] += a.saves or 0
        elif a.platform == "WEBSITE":
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
        analytics = Analytics(
            location_id=request.location_id,
            platform="GBP",
            date=item.get("date", date.today()),
            impressions=item.get("impressions"),
            clicks=item.get("clicks"),
            calls=item.get("calls"),
            direction_requests=item.get("direction_requests"),
            source_raw=item,
        )
        db.add(analytics)
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
        analytics = Analytics(
            location_id=request.location_id,
            platform="INSTAGRAM",
            date=item.get("date", date.today()),
            reach=item.get("reach"),
            likes=item.get("likes"),
            comments=item.get("comments"),
            shares=item.get("shares"),
            saves=item.get("saves"),
            source_raw=item,
        )
        db.add(analytics)
        count += 1

    db.commit()
    return {"ingested": count}
