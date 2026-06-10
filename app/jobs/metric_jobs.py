"""P1: Metric collection and reporting jobs."""

import logging
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.db.session import SessionLocal
from app.jobs.ops_alerts import notify_active_admins
from app.models.location import Location
from app.models.notification import NotificationEvent
from app.services.metrics_service import MetricsService
from app.services.notification import NotificationService
from app.schemas.metrics import MetricSnapshotCreate

logger = logging.getLogger(__name__)


def _session() -> Session:
    return SessionLocal()


async def _notify_weekly_report_failure(
    db: Session,
    *,
    location_id: UUID,
    account_id: UUID,
    report_week: date,
    error_message: str,
) -> None:
    """Persist an operator-facing alert when the weekly report job fails."""
    location = db.get(Location, location_id)
    location_name = location.name if location else "your location"
    week_end = report_week + timedelta(days=6)
    await NotificationService(db).send_notification(
        account_id=account_id,
        title="Weekly report generation failed",
        message=(
            f"The weekly report for {location_name} covering "
            f"{report_week.isoformat()} to {week_end.isoformat()} could not be generated."
            f"\n\nReason: {error_message}"
        ),
        notification_type="weekly_report_failed",
        data={
            "url": f"/dashboard/reports?locationId={location_id}",
            "location_id": str(location_id),
            "report_week": report_week.isoformat(),
            "error_message": error_message,
        },
    )


async def _notify_daily_snapshot_failure(
    db: Session,
    *,
    location_id: UUID,
    account_id: UUID,
    snapshot_date: date,
    error_message: str,
) -> None:
    """Persist an operator-facing alert when daily metric collection fails."""
    location = db.get(Location, location_id)
    location_name = location.name if location else "your location"
    await NotificationService(db).send_notification(
        account_id=account_id,
        title="Daily metrics collection failed",
        message=(
            f"The daily metric snapshot for {location_name} on "
            f"{snapshot_date.isoformat()} could not be collected."
            f"\n\nReason: {error_message}"
        ),
        notification_type="daily_snapshot_failed",
        data={
            "url": "/dashboard/analytics",
            "location_id": str(location_id),
            "snapshot_date": snapshot_date.isoformat(),
            "error_message": error_message,
        },
    )


async def _notify_daily_snapshot_unavailable(
    db: Session,
    *,
    location_id: UUID,
    account_id: UUID,
    snapshot_date: date,
) -> None:
    """Persist a throttled warning when no daily snapshot can be created at all."""
    location = db.get(Location, location_id)
    location_name = location.name if location else "your location"
    url = f"/dashboard/analytics?locationId={location_id}"
    now = utc_now_aware()
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    existing = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == account_id,
            NotificationEvent.type == "daily_snapshot_unavailable",
            NotificationEvent.url == url,
            NotificationEvent.created_at >= week_start,
        )
        .first()
    )
    if existing:
        return

    await NotificationService(db).send_notification(
        account_id=account_id,
        title="Daily snapshot unavailable",
        message=(
            f"The daily metric snapshot for {location_name} on {snapshot_date.isoformat()} "
            "could not be created because Google Business Profile metrics are unavailable and "
            "there is no previous snapshot to carry forward yet."
        ),
        notification_type="daily_snapshot_unavailable",
        data={
            "url": url,
            "location_id": str(location_id),
            "snapshot_date": snapshot_date.isoformat(),
        },
    )


async def enqueue_daily_snapshots():
    """Enqueue daily snapshot jobs for all active locations."""
    logger.info("Starting daily snapshot collection")

    try:
        with _session() as db:
            # Get all active locations
            result = db.execute(select(Location.id, Location.account_id))
            locations = result.all()

            logger.info("Found %s locations for daily snapshots", len(locations))

            for location_id, account_id in locations:
                try:
                    await process_daily_snapshot(location_id)
                except Exception as exc:
                    logger.error("Failed to process snapshot for location %s: %s", location_id, exc)
                    await _notify_daily_snapshot_failure(
                        db,
                        location_id=location_id,
                        account_id=account_id,
                        snapshot_date=date.today(),
                        error_message=str(exc),
                    )
                    continue
    except Exception as exc:
        logger.error("Daily snapshot worker failed: %s", exc)
        try:
            with _session() as alert_db:
                notify_active_admins(
                    alert_db,
                    title="Daily snapshot worker failed",
                    message=(
                        "The scheduled daily metrics snapshot worker could not complete its run."
                        f"\n\nReason: {exc}"
                    ),
                    notification_type="daily_snapshot_job_failed",
                )
        except Exception as notify_exc:
            logger.warning("Failed to notify admins about daily snapshot worker failure: %s", notify_exc)

    logger.info("Daily snapshot collection completed")


async def process_daily_snapshot(location_id: UUID):
    """Process daily snapshot for a single location.

    The job prefers real GBP data. If that is unavailable, it carries forward
    the latest known snapshot with explicit raw_data markers. If neither exists,
    it skips without writing a fake zero snapshot.
    """
    logger.info("Processing daily snapshot for location %s", location_id)

    with _session() as db:
        service = MetricsService(db)
        today = date.today()

        existing = service.get_snapshots(
            location_id, "daily", today, today, limit=1
        )
        if existing:
            logger.info("Snapshot already exists for %s on %s", location_id, today)
            return existing[0]

        payload = await fetch_gbp_metrics(location_id)
        if payload:
            data = _snapshot_create_from_payload(location_id, today, payload)
            raw_data = {
                "source": "gbp_api",
                "source_kind": "metric_jobs",
                "collected_at": utc_now_aware().isoformat(),
                "payload": payload,
            }
            snapshot = service.create_snapshot(data, raw_data=raw_data)
            logger.info(
                "Created daily snapshot %s for location %s from GBP data",
                snapshot.id,
                location_id,
            )
            return snapshot

        previous = service.get_latest_snapshot_before(
            location_id=location_id,
            before_date=today - timedelta(days=1),
            snapshot_type="daily",
        )
        if previous:
            data = _snapshot_create_from_previous(location_id, today, previous)
            raw_data = {
                "source": "carry_forward",
                "source_kind": "metric_jobs",
                "reason": "gbp_metrics_unavailable",
                "source_snapshot_id": str(previous.id),
                "source_snapshot_date": previous.snapshot_date.isoformat(),
                "carried_forward_at": utc_now_aware().isoformat(),
            }
            snapshot = service.create_snapshot(data, raw_data=raw_data)
            logger.info(
                "Created carry-forward snapshot %s for location %s from %s",
                snapshot.id,
                location_id,
                previous.id,
            )
            return snapshot

        logger.info(
            "Skipping daily snapshot for location %s: no GBP data and no prior snapshot to carry forward",
            location_id,
        )
        location = db.get(Location, location_id)
        if not location:
            return None
        await _notify_daily_snapshot_unavailable(
            db,
            location_id=location_id,
            account_id=location.account_id,
            snapshot_date=today,
        )
        return None


async def enqueue_weekly_reports():
    """Enqueue weekly report generation for all active locations."""
    logger.info("Starting weekly report generation")

    # Calculate week start (previous Monday)
    today = date.today()
    days_since_monday = today.weekday()
    week_start = today - timedelta(days=days_since_monday + 7)  # Previous week's Monday

    try:
        with _session() as db:
            # Get all locations with their account
            result = db.execute(
                select(Location.id, Location.account_id)
            )
            locations = result.all()

            logger.info("Found %s locations for weekly reports", len(locations))

            for location_id, account_id in locations:
                try:
                    await process_weekly_report(location_id, account_id, week_start)
                except Exception as exc:
                    logger.error("Failed to generate report for location %s: %s", location_id, exc)
                    await _notify_weekly_report_failure(
                        db,
                        location_id=location_id,
                        account_id=account_id,
                        report_week=week_start,
                        error_message=str(exc),
                    )
                    continue
    except Exception as exc:
        logger.error("Weekly report worker failed: %s", exc)
        try:
            with _session() as alert_db:
                notify_active_admins(
                    alert_db,
                    title="Weekly report worker failed",
                    message=(
                        "The scheduled weekly report worker could not complete its run."
                        f"\n\nReason: {exc}"
                    ),
                    notification_type="weekly_report_job_failed",
                )
        except Exception as notify_exc:
            logger.warning("Failed to notify admins about weekly report worker failure: %s", notify_exc)

    logger.info("Weekly report generation completed")


async def process_weekly_report(
    location_id: UUID,
    account_id: UUID,
    report_week: date,
):
    """Generate weekly report for a single location."""
    logger.info("Generating weekly report for location %s, week of %s", location_id, report_week)

    with _session() as db:
        service = MetricsService(db)

        current_snapshots = service.get_snapshots(
            location_id, "daily", report_week, report_week + timedelta(days=6)
        )
        if not current_snapshots:
            logger.info(
                "Skipping weekly report for location %s week %s: no metric snapshots available",
                location_id,
                report_week,
            )
            return None

        # Check if report already exists
        existing_reports = service.get_reports(location_id, limit=1)
        if existing_reports and existing_reports[0].report_week == report_week:
            logger.info("Report already exists for %s week %s", location_id, report_week)
            return existing_reports[0]

        # Generate report
        report = service.generate_weekly_report(
            location_id, account_id, report_week
        )

        logger.info("Created weekly report %s for location %s", report.id, location_id)
        location = db.get(Location, location_id)
        week_end = report_week + timedelta(days=6)
        location_name = location.name if location else "your location"
        await NotificationService(db).send_notification(
            account_id=account_id,
            title="Weekly report ready",
            message=(
                f"The weekly report for {location_name} covering "
                f"{report_week.isoformat()} to {week_end.isoformat()} is ready to review."
            ),
            notification_type="weekly_report_ready",
            data={
                "url": f"/dashboard/reports?locationId={location_id}",
                "report_id": str(report.id),
                "location_id": str(location_id),
                "report_week": report_week.isoformat(),
            },
        )

        return report


async def fetch_gbp_metrics(location_id: UUID) -> dict | None:
    """Fetch metrics from Google Business Profile API.

    This integration is not wired in this code path yet. Returning ``None``
    keeps the job honest so it can skip or carry forward instead of writing
    fake zero snapshots.
    """
    logger.info("GBP metrics fetch is not wired for location %s", location_id)
    return None


def _snapshot_create_from_payload(
    location_id: UUID,
    snapshot_date: date,
    payload: dict,
) -> MetricSnapshotCreate:
    """Build a snapshot create payload from real GBP data."""
    return MetricSnapshotCreate(
        location_id=location_id,
        snapshot_date=snapshot_date,
        snapshot_type="daily",
        calls=int(payload.get("calls", 0)),
        directions=int(payload.get("directions", 0)),
        website_clicks=int(payload.get("website_clicks", 0)),
        profile_views=int(payload.get("profile_views", 0)),
        photo_views=int(payload.get("photo_views", 0)),
        total_reviews=int(payload.get("total_reviews", 0)),
        new_reviews=int(payload.get("new_reviews", 0)),
        avg_rating=payload.get("avg_rating"),
        call_value=Decimal(str(payload.get("call_value", "50.00"))),
    )


def _snapshot_create_from_previous(
    location_id: UUID,
    snapshot_date: date,
    previous,
) -> MetricSnapshotCreate:
    """Build a carry-forward snapshot payload from the last known values."""
    return MetricSnapshotCreate(
        location_id=location_id,
        snapshot_date=snapshot_date,
        snapshot_type="daily",
        calls=previous.calls,
        directions=previous.directions,
        website_clicks=previous.website_clicks,
        profile_views=previous.profile_views,
        photo_views=previous.photo_views,
        total_reviews=previous.total_reviews,
        new_reviews=previous.new_reviews,
        avg_rating=previous.avg_rating,
        call_value=previous.call_value or Decimal("50.00"),
    )
