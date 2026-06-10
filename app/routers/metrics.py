"""P1: Metrics & Attribution API routes."""

import asyncio
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.models.metrics import UTMLink, WeeklyReport
from app.routers.deps import get_current_user
from app.services.notification import NotificationService
from app.services.metrics_service import MetricsService, get_metrics_service
from app.schemas.metrics import (
    DashboardResponse,
    MetricSnapshotCreate,
    MetricSnapshotList,
    MetricSnapshotResponse,
    SendReportRequest,
    UTMGenerateRequest,
    UTMLinkResponse,
    UTMStatsResponse,
    WeeklyReportCreate,
    WeeklyReportList,
    WeeklyReportResponse,
)

router = APIRouter(prefix="/metrics", tags=["Metrics"])
reports_router = APIRouter(prefix="/reports", tags=["Reports"])
utm_router = APIRouter(prefix="/utm", tags=["UTM"])


def _require_owned_location(db: Session, location_id: UUID, account_id: UUID) -> Location:
    """Ensure the location belongs to the authenticated account."""
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == account_id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


def _require_owned_report(db: Session, report_id: UUID, account_id: UUID) -> WeeklyReport:
    """Ensure the weekly report belongs to the authenticated account."""
    report = (
        db.query(WeeklyReport)
        .filter(WeeklyReport.id == report_id, WeeklyReport.account_id == account_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


# ====================
# Metrics Endpoints
# ====================

@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    location_id: UUID = Query(..., description="Location ID"),
    period_days: int = Query(7, ge=1, le=90, description="Period in days"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Get dashboard data with metrics, highlights, and chart."""
    _require_owned_location(db, location_id, current_user.id)
    service = get_metrics_service(db)
    return service.get_dashboard(location_id, period_days)


@router.get("/snapshots", response_model=MetricSnapshotList)
def get_snapshots(
    location_id: UUID = Query(..., description="Location ID"),
    snapshot_type: Optional[str] = Query(None, description="daily, weekly, or monthly"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Get metric snapshots for location."""
    _require_owned_location(db, location_id, current_user.id)
    service = get_metrics_service(db)
    snapshots = service.get_snapshots(
        location_id, snapshot_type, start_date, end_date, limit
    )
    return MetricSnapshotList(
        items=[MetricSnapshotResponse.model_validate(s) for s in snapshots],
        total=len(snapshots),
    )


@router.get("/snapshots/{snapshot_id}", response_model=MetricSnapshotResponse)
def get_snapshot(
    snapshot_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Get single snapshot by ID."""
    service = get_metrics_service(db)
    snapshot = service.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    _require_owned_location(db, snapshot.location_id, current_user.id)
    return MetricSnapshotResponse.model_validate(snapshot)


@router.post("/snapshots/generate", response_model=MetricSnapshotResponse)
def generate_snapshot(
    data: MetricSnapshotCreate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Manually create a metric snapshot."""
    _require_owned_location(db, data.location_id, current_user.id)
    service = get_metrics_service(db)
    snapshot = service.create_snapshot(data)
    return MetricSnapshotResponse.model_validate(snapshot)


# ====================
# Reports Endpoints
# ====================

@reports_router.get("/weekly", response_model=WeeklyReportList)
def get_weekly_reports(
    location_id: UUID = Query(..., description="Location ID"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Get weekly reports for location."""
    _require_owned_location(db, location_id, current_user.id)
    service = get_metrics_service(db)
    reports = service.get_reports(location_id, limit)
    return WeeklyReportList(
        items=[WeeklyReportResponse.model_validate(r) for r in reports],
        total=len(reports),
    )


@reports_router.get("/weekly/{report_id}", response_model=WeeklyReportResponse)
def get_weekly_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Get single report by ID."""
    _require_owned_report(db, report_id, current_user.id)
    service = get_metrics_service(db)
    report = service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return WeeklyReportResponse.model_validate(report)


@reports_router.post("/weekly/generate", response_model=WeeklyReportResponse)
def generate_weekly_report(
    data: WeeklyReportCreate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Generate weekly report for location."""
    _require_owned_location(db, data.location_id, current_user.id)
    service = get_metrics_service(db)
    report = service.generate_weekly_report(
        data.location_id, current_user.id, data.report_week
    )
    return WeeklyReportResponse.model_validate(report)


@reports_router.post("/weekly/{report_id}/send", response_model=WeeklyReportResponse)
def send_weekly_report(
    report_id: UUID,
    data: SendReportRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Send report via email."""
    report = _require_owned_report(db, report_id, current_user.id)
    service = get_metrics_service(db)

    summary = report.summary or {}
    email_subject = f"Weekly Performance Report - Week of {report.report_week.isoformat()}"
    email_text = (
        f"Weekly report for location {report.location_id}\n\n"
        f"Calls: {summary.get('calls_total', 0)}\n"
        f"Directions: {summary.get('directions_total', 0)}\n"
        f"Website Clicks: {summary.get('website_clicks_total', 0)}\n"
        f"New Reviews: {summary.get('new_reviews', 0)}\n"
        f"Estimated Revenue: {summary.get('estimated_revenue', 0)}\n"
    )
    email_html = (
        "<h2>Weekly Performance Report</h2>"
        f"<p>Week of {report.report_week.isoformat()}</p>"
        "<ul>"
        f"<li>Calls: {summary.get('calls_total', 0)}</li>"
        f"<li>Directions: {summary.get('directions_total', 0)}</li>"
        f"<li>Website Clicks: {summary.get('website_clicks_total', 0)}</li>"
        f"<li>New Reviews: {summary.get('new_reviews', 0)}</li>"
        f"<li>Estimated Revenue: {summary.get('estimated_revenue', 0)}</li>"
        "</ul>"
    )

    notification_service = NotificationService(db)
    for email in data.email_addresses:
        notification_service_result = asyncio.run(
            notification_service.send_email(
                to_email=email,
                subject=email_subject,
                html_body=email_html,
                text_body=email_text,
            )
        )
        if notification_service_result.get("success"):
            continue

        error_message = (
            str(notification_service_result.get("error") or "Email delivery failed")
            .strip()
        )
        lowered_error = error_message.lower()
        status_code = 503 if "not configured" in lowered_error or "unavailable" in lowered_error else 502
        raise HTTPException(
            status_code=status_code,
            detail=f"Failed to send report email to {email}: {error_message}",
        )

    report = service.send_report(report_id, data.email_addresses)

    return WeeklyReportResponse.model_validate(report)


# ====================
# UTM Endpoints
# ====================

@utm_router.post("/generate", response_model=UTMLinkResponse)
def generate_utm_link(
    data: UTMGenerateRequest,
    location_id: UUID = Query(..., description="Location ID"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Generate UTM tracked link."""
    _require_owned_location(db, location_id, current_user.id)
    service = get_metrics_service(db)
    link = service.generate_utm_link(
        location_id,
        data.original_url,
        data.campaign,
        data.post_id,
        data.utm_source,
        data.utm_medium,
    )
    return UTMLinkResponse.model_validate(link)


@utm_router.get("/stats", response_model=UTMStatsResponse)
def get_utm_stats(
    location_id: UUID = Query(..., description="Location ID"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Get UTM link statistics."""
    _require_owned_location(db, location_id, current_user.id)
    service = get_metrics_service(db)
    stats = service.get_utm_stats(location_id)
    return UTMStatsResponse(
        total_links=stats["total_links"],
        total_clicks=stats["total_clicks"],
        links=[UTMLinkResponse.model_validate(l) for l in stats["links"]],
    )


@utm_router.delete("/links/{link_id}", status_code=204)
def delete_utm_link(
    link_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Delete one tracked UTM link owned by the current account."""
    link = db.query(UTMLink).filter(UTMLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="UTM link not found")

    _require_owned_location(db, link.location_id, current_user.id)
    service = get_metrics_service(db)
    deleted = service.delete_utm_link(link_id, link.location_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="UTM link not found")
