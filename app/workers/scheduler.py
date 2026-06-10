"""APScheduler-based job scheduler."""

import logging
from datetime import date, datetime, timezone
from types import SimpleNamespace

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.notification import NotificationService
from app.services.analytics import AnalyticsService
from app.services.publisher import PublisherService
from app.services.reporting import ReportingService
from app.services.seo import SEOService
from app.models.account import Account, AccountRole
from app.models.location import Location
from app.models.schedule import Schedule


scheduler = AsyncIOScheduler(timezone="UTC")
logger = logging.getLogger(__name__)


def get_db() -> Session:
    """Get database session for workers."""
    return SessionLocal()


async def _notify_content_generation_failure(
    db: Session,
    *,
    location: Location,
    schedule: Schedule,
    theme: str,
    error_message: str,
) -> None:
    """Persist an operator-facing alert when scheduled draft generation fails."""
    await NotificationService(db).send_notification(
        account_id=location.account_id,
        title="Scheduled content generation failed",
        message=(
            f"The scheduled {schedule.platform} draft for {location.name} could not be generated."
            f"\n\nTheme: {theme}"
            f"\nReason: {error_message}"
        ),
        notification_type="scheduled_content_generation_failed",
        data={
            "url": f"/dashboard/content/new?locationId={location.id}",
            "location_id": str(location.id),
            "schedule_id": str(schedule.id),
            "platform": schedule.platform,
            "theme": theme,
            "error_message": error_message,
        },
    )


async def _notify_weekly_report_failure(
    db: Session,
    *,
    location: Location,
    error_message: str,
) -> None:
    """Persist an operator-facing alert when the worker weekly report job fails."""
    await NotificationService(db).send_notification(
        account_id=location.account_id,
        title="Weekly report generation failed",
        message=(
            f"The scheduled weekly report for {location.name} could not be generated."
            f"\n\nReason: {error_message}"
        ),
        notification_type="weekly_report_failed",
        data={
            "url": f"/dashboard/reports?locationId={location.id}",
            "location_id": str(location.id),
            "error_message": error_message,
            "source": "worker_scheduler",
        },
    )


async def _notify_payment_retry_job_failure(
    db: Session,
    *,
    subscription_id: str,
    account_id,
    error_message: str,
) -> None:
    """Persist an alert when the automatic retry job cannot complete its work."""
    await NotificationService(db).send_notification(
        account_id=account_id,
        title="Automatic payment retry failed to run",
        message=(
            "A scheduled payment retry could not be completed because the billing "
            f"service returned an unexpected error.\n\nReason: {error_message}"
        ),
        notification_type="billing_payment_retry_job_failed",
        data={
            "url": "/dashboard/billing",
            "subscription_id": subscription_id,
            "error_message": error_message,
        },
    )


def _active_admin_accounts(db: Session) -> list[Account]:
    """Return active admin accounts that can receive worker alerts."""
    return (
        db.query(Account)
        .filter(
            Account.role == AccountRole.ADMIN,
            Account.is_active == True,  # noqa: E712
        )
        .all()
    )


async def _notify_admin_job_failure(
    db: Session,
    *,
    title: str,
    message: str,
    notification_type: str,
    url: str = "/admin",
) -> None:
    """Persist an inbox-only alert for active admin operators."""
    admins = _active_admin_accounts(db)
    if not admins:
        logger.warning("No active admin accounts available for worker alert %s", notification_type)
        return

    notification_service = NotificationService(db)
    for admin in admins:
        notification_service.send_inbox_notification(
            account_id=admin.id,
            title=title,
            message=message,
            notification_type=notification_type,
            url=url,
        )


async def _notify_analytics_collection_failure(
    db: Session,
    *,
    location: Location,
    error_message: str,
) -> None:
    """Persist an operator-facing alert when analytics collection fails."""
    NotificationService(db).send_inbox_notification(
        account_id=location.account_id,
        title="Analytics collection failed",
        message=(
            f"The scheduled analytics collection for {location.name} could not finish."
            f"\n\nReason: {error_message}"
        ),
        notification_type="analytics_collection_failed",
        url=f"/dashboard/analytics?locationId={location.id}",
    )


async def _notify_seo_score_failure(
    db: Session,
    *,
    location: Location,
    from_date: date,
    to_date: date,
    error_message: str,
) -> None:
    """Persist an operator-facing alert when scheduled SEO scoring fails."""
    NotificationService(db).send_inbox_notification(
        account_id=location.account_id,
        title="SEO score refresh failed",
        message=(
            f"The scheduled SEO score refresh for {location.name} covering "
            f"{from_date.isoformat()} to {to_date.isoformat()} could not finish."
            f"\n\nReason: {error_message}"
        ),
        notification_type="seo_score_calculation_failed",
        url=f"/dashboard/seo?locationId={location.id}",
    )


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
            if not location:
                continue
            account = (
                location.account
                if getattr(location, "account", None) is not None
                else db.query(Account).filter(Account.id == location.account_id).first()
            )
            if not account:
                continue
            
            approval_service = ApprovalWorkflowService(db)
            
            # Generate content based on schedule preferences
            topic_prefs = schedule.topic_prefs or {}
            theme = topic_prefs.get("theme", "weekly-update")
            
            # Approval requests should follow the persisted account channel.
            # "both" is not a valid approval enum, so email is the safe fallback.
            account_channel = (getattr(account, "notification_channel", None) or "email").lower()
            if account_channel == "sms":
                notification_channel = NotificationChannel.SMS
            else:
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
                logger.info(
                    "Generated scheduled draft for location %s, platform %s with notifications %s",
                    location.id,
                    schedule.platform,
                    result.get("notifications"),
                )
            except Exception as e:
                logger.error("Failed to generate scheduled content for %s: %s", location.id, e)
                await _notify_content_generation_failure(
                    db,
                    location=location,
                    schedule=schedule,
                    theme=theme,
                    error_message=str(e),
                )
    except Exception as e:
        logger.error("Content generation job failed: %s", e)
        await _notify_admin_job_failure(
            db,
            title="Scheduled content generation worker failed",
            message=(
                "The scheduled content generation worker could not complete its run."
                f"\n\nReason: {e}"
            ),
            notification_type="content_generation_job_failed",
        )
    finally:
        db.close()


async def publisher_job() -> None:
    """Publish queued posts (Mon/Wed/Fri 10:00 UTC)."""
    db = get_db()
    try:
        publisher = PublisherService(db)
        results = await publisher.publish_queued_posts()
        logger.info("Publisher job completed: %s", results)
    except Exception as e:
        logger.error("Publisher job failed: %s", e)
        await _notify_admin_job_failure(
            db,
            title="Publisher worker failed",
            message=(
                "The scheduled publisher worker could not complete its run."
                f"\n\nReason: {e}"
            ),
            notification_type="publish_worker_failed",
        )
    finally:
        db.close()


async def analytics_collect_job() -> None:
    """Daily analytics collection (01:00 UTC)."""
    db = get_db()
    try:
        analytics_service = AnalyticsService(db)
        results = await analytics_service.collect_all()
        logger.info("Analytics collection completed: %s", results)

        for error in results.get("errors", []):
            location_id = error.get("location_id")
            if not location_id:
                continue
            location = db.query(Location).filter(Location.id == location_id).first()
            if not location:
                continue
            await _notify_analytics_collection_failure(
                db,
                location=location,
                error_message=str(error.get("error") or "Unknown analytics collection error"),
            )

        # Update SEO scores after collecting analytics
        from datetime import timedelta
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
                logger.error("Failed to calculate SEO score for %s: %s", location.id, e)
                await _notify_seo_score_failure(
                    db,
                    location=location,
                    from_date=week_ago,
                    to_date=today,
                    error_message=str(e),
                )
    except Exception as e:
        logger.error("Analytics collection job failed: %s", e)
        await _notify_admin_job_failure(
            db,
            title="Analytics collection worker failed",
            message=(
                "The scheduled analytics collection worker could not complete its run."
                f"\n\nReason: {e}"
            ),
            notification_type="analytics_collection_job_failed",
        )
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
                logger.info("Generated weekly report for location %s", location.id)
            except Exception as e:
                logger.error("Failed to generate weekly report for %s: %s", location.id, e)
                await _notify_weekly_report_failure(
                    db,
                    location=location,
                    error_message=str(e),
                )
    except Exception as e:
        logger.error("Weekly report job failed: %s", e)
        await _notify_admin_job_failure(
            db,
            title="Weekly report worker failed",
            message=(
                "The scheduled weekly report worker could not complete its run."
                f"\n\nReason: {e}"
            ),
            notification_type="weekly_report_job_failed",
        )
    finally:
        db.close()


async def dunning_check_job() -> None:
    """Daily dunning check for payment failures (02:00 UTC).
    
    Checks for:
    1. Grace period expiry -> restrict account
    2. Suspension threshold -> suspend account
    """
    db = get_db()
    try:
        from app.services.dunning_service import DunningService

        dunning_service = DunningService(db)

        restricted_ids = await dunning_service.check_grace_period_expiry()
        suspended_ids = await dunning_service.check_suspension()
        db.commit()

        for subscription_id in restricted_ids:
            logger.info("Subscription %s moved to restricted mode", subscription_id)

        for subscription_id in suspended_ids:
            logger.info("Subscription %s suspended due to non-payment", subscription_id)

        logger.info(
            "Dunning check completed: %s restricted, %s suspended",
            len(restricted_ids),
            len(suspended_ids),
        )
    except Exception as e:
        db.rollback()
        logger.error("Dunning check job failed: %s", e)
        await _notify_admin_job_failure(
            db,
            title="Dunning check worker failed",
            message=(
                "The scheduled dunning check could not complete."
                f"\n\nReason: {e}"
            ),
            notification_type="billing_dunning_job_failed",
        )
    finally:
        db.close()


async def payment_retry_job() -> None:
    """Daily payment retry for failed invoices (06:00 UTC).
    
    Retries payment on scheduled retry dates.
    """
    db = get_db()
    try:
        from app.models.subscription import Subscription, DunningStatus
        from app.services.dunning_service import DunningService
        import stripe
        
        now = datetime.now(timezone.utc)
        dunning_service = DunningService(db)
        
        # Get subscriptions due for retry
        subscriptions = db.query(Subscription).filter(
            Subscription.dunning_status == DunningStatus.RETRYING,
            Subscription.next_payment_retry_at <= now,
        ).all()
        
        for subscription in subscriptions:
            if not subscription.stripe_subscription_id:
                continue
            invoice = None
            
            try:
                # Get latest unpaid invoice
                invoices = stripe.Invoice.list(
                    subscription=subscription.stripe_subscription_id,
                    status='open',
                    limit=1,
                )
                
                if invoices.data:
                    invoice = invoices.data[0]
                    # Attempt to pay the invoice
                    paid_invoice = stripe.Invoice.pay(invoice.id)
                    await dunning_service.handle_payment_success(subscription)
                    db.commit()
                    logger.info(
                        "Payment retry succeeded for subscription %s via invoice %s",
                        subscription.id,
                        getattr(paid_invoice, "id", getattr(invoice, "id", None)),
                    )
            except stripe.error.CardError as e:
                retry_attempt = max(
                    getattr(invoice, "attempt_count", 0) + 1 if invoice is not None else 1,
                    subscription.payment_retry_count + 1,
                )
                invoice_payload = invoice if invoice is not None else SimpleNamespace()
                if not hasattr(invoice_payload, "amount_due"):
                    invoice_payload.amount_due = 0
                if not hasattr(invoice_payload, "currency"):
                    invoice_payload.currency = "usd"
                if not hasattr(invoice_payload, "id"):
                    invoice_payload.id = f"retry-{subscription.id}"
                invoice_payload.last_finalization_error = SimpleNamespace(
                    message=getattr(e, "user_message", None) or str(e)
                )
                await dunning_service.handle_payment_failure(
                    subscription,
                    failure_message=invoice_payload.last_finalization_error.message,
                    attempt_count=retry_attempt,
                )
                db.commit()
                logger.warning(
                    "Payment retry failed for subscription %s on attempt %s: %s",
                    subscription.id,
                    retry_attempt,
                    invoice_payload.last_finalization_error.message,
                )
            except Exception as e:
                logger.error("Payment retry error for subscription %s: %s", subscription.id, e)
                await _notify_payment_retry_job_failure(
                    db,
                    subscription_id=str(subscription.id),
                    account_id=subscription.account_id,
                    error_message=str(e),
                )
        
        logger.info("Payment retry job completed: %s subscriptions processed", len(subscriptions))
    except Exception as e:
        logger.error("Payment retry job failed: %s", e)
        await _notify_admin_job_failure(
            db,
            title="Payment retry worker failed",
            message=(
                "The scheduled payment retry worker could not complete."
                f"\n\nReason: {e}"
            ),
            notification_type="billing_payment_retry_worker_failed",
        )
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
    
    # Dunning check: Daily 02:00 UTC
    scheduler.add_job(
        dunning_check_job,
        CronTrigger(hour=2, minute=0),
        id="dunning_check",
        replace_existing=True,
    )
    
    # Payment retry: Daily 06:00 UTC
    scheduler.add_job(
        payment_retry_job,
        CronTrigger(hour=6, minute=0),
        id="payment_retry",
        replace_existing=True,
    )
    
    scheduler.start()
    print("Scheduler started with jobs:", [job.id for job in scheduler.get_jobs()])


def shutdown_scheduler() -> None:
    """Shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("Scheduler shutdown")
