"""APScheduler-based job scheduler."""

from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.analytics import AnalyticsService
from app.services.publisher import PublisherService
from app.services.reporting import ReportingService
from app.services.seo import SEOService
from app.models.location import Location
from app.models.schedule import Schedule


scheduler = AsyncIOScheduler(timezone="UTC")


def get_db() -> Session:
    """Get database session for workers."""
    return SessionLocal()


async def content_generate_job() -> None:
    """Weekly content generation job with approval workflow (Monday 09:00 UTC)."""
    db = get_db()
    try:
        from app.services.approval import ApprovalWorkflowService
        from app.services.notification import NotificationChannel
        
        # Get all active schedules
        schedules = db.query(Schedule).filter(Schedule.is_active == True).all()
        
        for schedule in schedules:
            location = db.query(Location).filter(Location.id == schedule.location_id).first()
            if not location or not location.account:
                continue
            
            approval_service = ApprovalWorkflowService(db)
            
            # Generate content based on schedule preferences
            topic_prefs = schedule.topic_prefs or {}
            theme = topic_prefs.get("theme", "weekly-update")
            
            # Determine notification channel from account preferences
            notification_channel = NotificationChannel.SLACK
            if hasattr(location.account, 'notification_preference'):
                pref = location.account.notification_preference
                if pref == 'kakao':
                    notification_channel = NotificationChannel.KAKAO
                elif pref == 'email':
                    notification_channel = NotificationChannel.EMAIL
            
            try:
                # Create draft with approval workflow
                result = await approval_service.create_draft_with_approval(
                    location_id=location.id,
                    account_id=location.account_id,
                    theme=theme,
                    services=location.services or [],
                    platform_targets=[schedule.platform],
                    tone=schedule.tone or "expert yet friendly",
                    language=schedule.language,
                    notification_channel=notification_channel,
                    generate_image=True,
                )
                print(f"Generated draft for location {location.id}, platform {schedule.platform}")
                print(f"Approval notifications sent: {result['notifications']}")
            except Exception as e:
                print(f"Failed to generate content for {location.id}: {e}")
    finally:
        db.close()


async def publisher_job() -> None:
    """Publish queued posts (Mon/Wed/Fri 10:00 UTC)."""
    db = get_db()
    try:
        publisher = PublisherService(db)
        results = await publisher.publish_queued_posts()
        print(f"Publisher job completed: {results}")
    finally:
        db.close()


async def analytics_collect_job() -> None:
    """Daily analytics collection (01:00 UTC)."""
    db = get_db()
    try:
        analytics_service = AnalyticsService(db)
        results = await analytics_service.collect_all()
        print(f"Analytics collection completed: {results}")
        
        # Update SEO scores after collecting analytics
        from datetime import date, timedelta
        seo_service = SEOService(db)
        
        locations = db.query(Location).all()
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        for location in locations:
            try:
                await seo_service.calculate_score(
                    location_id=location.id,
                    from_date=week_ago,
                    to_date=today,
                )
            except Exception as e:
                print(f"Failed to calculate SEO score for {location.id}: {e}")
    finally:
        db.close()


async def weekly_report_job() -> None:
    """Weekly report generation (Sunday 18:00 UTC)."""
    db = get_db()
    try:
        reporting_service = ReportingService(db)
        
        locations = db.query(Location).all()
        
        for location in locations:
            try:
                await reporting_service.generate_weekly_report(
                    location_id=location.id,
                    send_email=True,
                )
                print(f"Generated weekly report for location {location.id}")
            except Exception as e:
                print(f"Failed to generate report for {location.id}: {e}")
    finally:
        db.close()


def setup_scheduler() -> None:
    """Configure and start the scheduler."""
    # Content generation: Monday 09:00 UTC
    scheduler.add_job(
        content_generate_job,
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="content_generate",
        replace_existing=True,
    )
    
    # Publisher: Mon/Wed/Fri 10:00 UTC
    scheduler.add_job(
        publisher_job,
        CronTrigger(day_of_week="mon,wed,fri", hour=10, minute=0),
        id="publisher",
        replace_existing=True,
    )
    
    # Analytics collection: Daily 01:00 UTC
    scheduler.add_job(
        analytics_collect_job,
        CronTrigger(hour=1, minute=0),
        id="analytics_collect",
        replace_existing=True,
    )
    
    # Weekly report: Sunday 18:00 UTC
    scheduler.add_job(
        weekly_report_job,
        CronTrigger(day_of_week="sun", hour=18, minute=0),
        id="weekly_report",
        replace_existing=True,
    )
    
    scheduler.start()
    print("Scheduler started with jobs:", [job.id for job in scheduler.get_jobs()])


def shutdown_scheduler() -> None:
    """Shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("Scheduler shutdown")
