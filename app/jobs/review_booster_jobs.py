"""Review Booster background jobs."""

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.db.session import SessionLocal
from app.jobs.ops_alerts import notify_active_admins
from app.models.location import Location
from app.models.review_booster import BoosterRequest, RequestChannel, RequestStatus, ReviewCampaign
from app.services.credits import CreditsService
from app.services.email_service import get_email_service
from app.services.notification import NotificationService
from app.services.twilio_service import get_twilio_service

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3
RETRY_DELAYS_MINUTES = (5, 30, 180)


class NonRetryableDeliveryError(RuntimeError):
    """Delivery failure that should not be retried automatically."""


def _session() -> Session:
    return SessionLocal()


def _resolve_account_id_for_request(db: Session, request: BoosterRequest) -> UUID | None:
    return db.execute(
        select(Location.account_id).where(Location.id == request.location_id)
    ).scalar_one_or_none()


def _preview_sms_usage(db: Session, request: BoosterRequest) -> UUID:
    account_id = _resolve_account_id_for_request(db, request)
    if not account_id:
        raise ValueError("Unable to resolve account for review request")

    result = CreditsService(db).preview_usage(str(account_id), "sms", 1)
    if not result.get("allowed"):
        if int(result.get("cooldown_remaining_seconds", 0) or 0) > 0:
            raise RuntimeError(result.get("reason") or "SMS cooldown active")
        raise NonRetryableDeliveryError(result.get("reason") or "SMS usage limit reached")
    return account_id


def _record_sms_usage(db: Session, account_id: UUID, request: BoosterRequest) -> None:
    result = CreditsService(db).use_credits(str(account_id), "sms", 1)
    if result.get("allowed"):
        return

    logger.warning(
        "SMS usage record failed after review booster send for request %s: %s",
        request.id,
        result.get("reason"),
    )


def _mark_request_sent(
    db: Session,
    request: BoosterRequest,
    *,
    twilio_message_sid: str | None = None,
    sendgrid_message_id: str | None = None,
) -> None:
    """Persist a successful delivery attempt and update campaign counters once."""
    first_successful_send = request.sent_at is None

    request.status = RequestStatus.SENT
    request.sent_at = utc_now_aware()
    request.last_attempt_at = request.sent_at
    request.next_retry_at = None

    if twilio_message_sid is not None:
        request.twilio_message_sid = twilio_message_sid
    if sendgrid_message_id is not None:
        request.sendgrid_message_id = sendgrid_message_id

    if first_successful_send:
        campaign = db.execute(
            select(ReviewCampaign).where(ReviewCampaign.id == request.campaign_id)
        ).scalar_one_or_none()
        if campaign:
            campaign.total_sent = int(campaign.total_sent or 0) + 1

    db.commit()


async def process_pending_review_requests() -> None:
    """Process pending and retry-eligible review requests in small batches."""
    logger.info("Processing pending review requests")

    try:
        with _session() as db:
            now = utc_now_aware()
            requests = list(
                db.execute(
                    select(BoosterRequest)
                    .where(
                        or_(
                            BoosterRequest.status == RequestStatus.PENDING,
                            and_(
                                BoosterRequest.status == RequestStatus.FAILED,
                                BoosterRequest.retry_count < MAX_RETRY_ATTEMPTS,
                                BoosterRequest.next_retry_at.is_not(None),
                                BoosterRequest.next_retry_at <= now,
                            ),
                        ),
                    )
                    .order_by(BoosterRequest.created_at.asc())
                    .limit(100)
                )
                .scalars()
                .all()
            )

            logger.info("Found %s review requests ready to process", len(requests))
            for review_request in requests:
                try:
                    await send_review_request(db, review_request)
                except Exception as exc:
                    logger.error("Failed to send request %s: %s", review_request.id, exc)
                    await _record_delivery_failure(
                        db,
                        review_request,
                        str(exc),
                        non_retryable=isinstance(exc, NonRetryableDeliveryError),
                    )
    except Exception as exc:
        logger.error("Review booster worker failed: %s", exc)
        try:
            with _session() as alert_db:
                notify_active_admins(
                    alert_db,
                    title="Review booster worker failed",
                    message=(
                        "The scheduled review request processor could not complete its run."
                        f"\n\nReason: {exc}"
                    ),
                    notification_type="review_booster_job_failed",
                )
        except Exception as notify_exc:
            logger.warning("Failed to notify admins about review booster worker failure: %s", notify_exc)


async def send_review_request(db: Session, request: BoosterRequest) -> None:
    """Send one review request using the configured channel."""
    logger.info("Sending review request %s via %s", request.id, request.channel)

    request.last_attempt_at = utc_now_aware()
    request.last_error = None
    request.next_retry_at = None
    db.commit()

    if request.channel == RequestChannel.SMS:
        await send_sms_request(db, request)
    elif request.channel == RequestChannel.EMAIL:
        await send_email_request(db, request)


async def send_sms_request(db: Session, request: BoosterRequest) -> None:
    """Send one SMS review request."""
    if not request.customer_phone:
        raise ValueError("No phone number for SMS request")

    account_id = _preview_sms_usage(db, request)

    result = await get_twilio_service().send_sms(
        to=request.customer_phone,
        body=request.message_content,
        status_callback=f"/webhooks/twilio/sms-status?request_id={request.id}",
    )

    _mark_request_sent(db, request, twilio_message_sid=result.get("sid"))
    _record_sms_usage(db, account_id, request)
    logger.info("SMS sent for request %s", request.id)


async def send_email_request(db: Session, request: BoosterRequest) -> None:
    """Send one email review request."""
    if not request.customer_email:
        raise ValueError("No email for email request")

    campaign = db.execute(
        select(ReviewCampaign).where(ReviewCampaign.id == request.campaign_id)
    ).scalar_one_or_none()
    if not campaign:
        raise ValueError("Campaign not found")

    email_body = build_review_email_html(
        customer_name=request.customer_name or "Customer",
        business_name="Your Business",
        google_link=campaign.google_review_url,
        feedback_link=campaign.private_feedback_url,
    )

    result = await get_email_service().send_email(
        to=request.customer_email,
        subject=campaign.email_subject or "Please share your review",
        html_content=email_body,
    )

    _mark_request_sent(db, request, sendgrid_message_id=result.get("message_id"))
    logger.info("Email sent for request %s", request.id)


def _retry_delay_for_attempt(retry_count: int) -> timedelta:
    index = min(max(retry_count - 1, 0), len(RETRY_DELAYS_MINUTES) - 1)
    return timedelta(minutes=RETRY_DELAYS_MINUTES[index])


async def _record_delivery_failure(
    db: Session,
    request: BoosterRequest,
    error: str,
    *,
    non_retryable: bool = False,
) -> None:
    """Persist delivery failure state and notify the owner on terminal failure."""
    now = utc_now_aware()
    request.status = RequestStatus.FAILED
    request.retry_count = (request.retry_count or 0) + 1
    request.last_attempt_at = now
    request.last_error = error

    if non_retryable:
        request.retry_count = max(request.retry_count, MAX_RETRY_ATTEMPTS)
        request.next_retry_at = None
        db.commit()
        await _notify_terminal_failure(db, request)
        return

    if request.retry_count < MAX_RETRY_ATTEMPTS:
        request.next_retry_at = now + _retry_delay_for_attempt(request.retry_count)
        db.commit()
        return

    request.next_retry_at = None
    db.commit()
    await _notify_terminal_failure(db, request)


async def _notify_terminal_failure(db: Session, request: BoosterRequest) -> None:
    """Notify the owning account when retries are exhausted."""
    account_id = db.execute(
        select(Location.account_id).where(Location.id == request.location_id)
    ).scalar_one_or_none()
    if not account_id:
        logger.warning("Unable to resolve owner for failed request %s", request.id)
        return

    campaign = db.execute(
        select(ReviewCampaign).where(ReviewCampaign.id == request.campaign_id)
    ).scalar_one_or_none()
    campaign_name = campaign.name if campaign else "Unknown campaign"
    destination = request.customer_phone or request.customer_email or "unknown recipient"

    await NotificationService(db).send_notification(
        account_id=account_id,
        title="Review request delivery failed",
        message=(
            f"Campaign: {campaign_name}\n"
            f"Request ID: {request.id}\n"
            f"Destination: {destination}\n"
            f"Retries exhausted after {request.retry_count} attempts.\n"
            f"Last error: {request.last_error or 'unknown'}"
        ),
        notification_type="review_booster_delivery_failed",
        data={
            "request_id": str(request.id),
            "campaign_id": str(request.campaign_id),
            "location_id": str(request.location_id),
            "retry_count": request.retry_count,
        },
    )


def build_review_email_html(
    customer_name: str,
    business_name: str,
    google_link: str,
    feedback_link: str | None = None,
) -> str:
    """Build review request email HTML."""
    feedback_section = ""
    if feedback_link:
        feedback_section = f'''
        <p style="margin-top: 16px; font-size: 14px; color: #666;">
            If you prefer to share feedback directly with us, use this link:<br>
            <a href="{feedback_link}" style="color: #6366f1;">Share private feedback</a>
        </p>
        '''

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">Please leave a review</h1>
        </div>
        <div style="background: white; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
            <p style="font-size: 16px;">Hello <strong>{customer_name}</strong>,</p>
            <p style="font-size: 16px;">Thank you for visiting <strong>{business_name}</strong>.</p>
            <p style="font-size: 16px;">If you have a moment, please share your experience using the review link below.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{google_link}" style="display: inline-block; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">Leave a Google review</a>
            </div>
            <p style="font-size: 14px; color: #666; text-align: center;">
                If the button does not work, copy and paste this link:<br>
                <a href="{google_link}" style="color: #6366f1; word-break: break-all;">{google_link}</a>
            </p>
            {feedback_section}
        </div>
    </body>
    </html>
    '''


async def handle_sms_status_callback(request_id: UUID, message_sid: str, status: str) -> None:
    """Handle Twilio SMS delivery callbacks."""
    logger.info("SMS status update: %s -> %s", request_id, status)

    with _session() as db:
        request = db.execute(
            select(BoosterRequest).where(BoosterRequest.id == request_id)
        ).scalar_one_or_none()
        if not request:
            logger.warning("Request %s not found for status update", request_id)
            return

        status_map = {
            "queued": RequestStatus.PENDING,
            "sent": RequestStatus.SENT,
            "delivered": RequestStatus.DELIVERED,
            "failed": RequestStatus.FAILED,
            "undelivered": RequestStatus.FAILED,
        }
        new_status = status_map.get(status.lower())
        if not new_status:
            return

        request.status = new_status
        if new_status == RequestStatus.DELIVERED:
            request.delivered_at = utc_now_aware()
        request.twilio_message_sid = message_sid or request.twilio_message_sid
        db.commit()
        logger.info("Updated request %s status to %s", request_id, new_status)
