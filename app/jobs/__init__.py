"""Background jobs module."""

from app.jobs.scheduler import scheduler, start_scheduler, shutdown_scheduler
from app.jobs.metric_jobs import (
    enqueue_daily_snapshots,
    enqueue_weekly_reports,
    process_daily_snapshot,
    process_weekly_report,
)
from app.jobs.review_booster_jobs import (
    process_pending_review_requests,
    send_review_request,
    handle_sms_status_callback,
)

__all__ = [
    "scheduler",
    "start_scheduler",
    "shutdown_scheduler",
    # P1: Metrics
    "enqueue_daily_snapshots",
    "enqueue_weekly_reports",
    "process_daily_snapshot",
    "process_weekly_report",
    # P2: Review Booster
    "process_pending_review_requests",
    "send_review_request",
    "handle_sms_status_callback",
]
