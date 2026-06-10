"""APScheduler configuration for background jobs."""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()


def configure_jobs():
    """Configure scheduled jobs."""
    from app.jobs.metric_jobs import enqueue_daily_snapshots, enqueue_weekly_reports
    from app.jobs.token_jobs import check_expiring_tokens
    from app.jobs.review_booster_jobs import process_pending_review_requests
    
    # Daily metric snapshot - 06:00 UTC
    scheduler.add_job(
        enqueue_daily_snapshots,
        CronTrigger(hour=6, minute=0),
        id="daily_snapshots",
        name="Enqueue daily metric snapshots for all locations",
        replace_existing=True,
    )
    
    # Weekly report generation - Monday 07:00 UTC
    scheduler.add_job(
        enqueue_weekly_reports,
        CronTrigger(day_of_week="mon", hour=7, minute=0),
        id="weekly_reports",
        name="Generate weekly reports for all locations",
        replace_existing=True,
    )
    
    # Token refresh check - Every hour
    scheduler.add_job(
        check_expiring_tokens,
        CronTrigger(minute=0),
        id="token_refresh_check",
        name="Check and refresh expiring OAuth tokens",
        replace_existing=True,
    )
    
    # P2: Process pending review requests - Every 5 minutes
    scheduler.add_job(
        process_pending_review_requests,
        CronTrigger(minute="*/5"),
        id="review_request_processor",
        name="Process pending review requests (SMS/Email)",
        replace_existing=True,
    )
    
    logger.info("Scheduled jobs configured")


def start_scheduler():
    """Start the scheduler."""
    if not scheduler.running:
        configure_jobs()
        scheduler.start()
        logger.info("Scheduler started")


def shutdown_scheduler():
    """Shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


@asynccontextmanager
async def lifespan_scheduler():
    """Context manager for scheduler lifecycle."""
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()
