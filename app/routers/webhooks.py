"""Webhook handlers for external services (Twilio, Stripe, etc.)."""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, Response as FastAPIResponse, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.db.session import get_db
from app.services.call_service import TwilioCallService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _notify_admin_webhook_failure(
    db: Session,
    *,
    title: str,
    message: str,
    notification_type: str,
    url: str = "/admin",
) -> None:
    """Persist an inbox-only alert for active admins when a webhook fails after verification."""
    from app.models.account import Account, AccountRole
    from app.services.notification import NotificationService

    admins = (
        db.query(Account)
        .filter(
            Account.role == AccountRole.ADMIN,
            Account.is_active == True,  # noqa: E712
        )
        .all()
    )
    if not admins:
        logger.warning("No active admin accounts available for webhook alert %s", notification_type)
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


# ============ Twilio Voice Webhooks ============

@router.post("/voice-incoming")
async def handle_incoming_call(
    request: Request,
    location_id: UUID = Query(...),
    db: Session = Depends(get_db),
):
    """
    Handle incoming voice call from Twilio.
    
    This endpoint returns TwiML to forward the call to the real business number.
    """
    from app.models.location import Location

    # Get location
    location = db.query(Location).filter(Location.id == location_id).first()

    if not location:
        logger.error(f"Location not found: {location_id}")
        # Return simple TwiML that says we're unavailable
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?>'
                    '<Response><Say>Sorry, this number is not available.</Say></Response>',
            media_type="application/xml",
        )

    # Get the real phone number from location
    real_phone = location.phone
    if not real_phone:
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?>'
                    '<Response><Say>Sorry, this business is currently unavailable.</Say></Response>',
            media_type="application/xml",
        )

    # Generate call forwarding TwiML
    twilio_service = TwilioCallService()
    twiml = twilio_service.generate_call_forward_twiml(
        real_phone_number=real_phone,
        location_id=str(location_id),
        timeout=20,
    )

    return Response(content=twiml, media_type="application/xml")


@router.post("/voice-status")
async def handle_voice_status(
    request: Request,
    location_id: UUID = Query(...),
    CallSid: str = Form(None),
    CallStatus: str = Form(...),
    From: str = Form(None),
    To: str = Form(None),
    Duration: int = Form(0),
    db: Session = Depends(get_db),
):
    """
    Handle call status callback from Twilio.
    
    This is called after a call ends. If the call was missed (busy, no-answer, failed),
    we automatically send an SMS to the caller.
    
    P3: Missed Call Text Back Feature
    """
    logger.info(
        f"Voice status webhook: location={location_id}, "
        f"status={CallStatus}, from={From}, duration={Duration}"
    )

    missed_statuses = ["no-answer", "busy", "failed", "canceled"]

    if CallStatus.lower() in missed_statuses and From:
        from app.models.calls import TwilioNumber
        from app.services.call_text_back_service import get_call_text_back_service

        twilio_number = None
        if To:
            twilio_number = (
                db.query(TwilioNumber)
                .filter(
                    TwilioNumber.location_id == location_id,
                    TwilioNumber.twilio_number == To,
                )
                .first()
            )
        if not twilio_number:
            twilio_number = (
                db.query(TwilioNumber)
                .filter(TwilioNumber.location_id == location_id)
                .first()
            )

        if twilio_number:
            service = get_call_text_back_service(db)
            await service.handle_missed_call(
                location_id=location_id,
                caller_phone=From,
                twilio_call_sid=CallSid or "unknown-call-sid",
                twilio_number_id=twilio_number.id,
            )
            logger.info(f"Missed call text back scheduled for {From[:4]}****")
        else:
            logger.warning(f"No Twilio number configured for location {location_id}")
    else:
        logger.info(f"Call {CallSid} completed with status {CallStatus}")

    # Return empty TwiML (Twilio expects a response)
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


# ============ Stripe Webhooks ============

@router.post("/stripe-legacy", include_in_schema=False)
async def handle_stripe_webhook(
    request: Request,
    response: FastAPIResponse,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    """Deprecated Stripe webhook endpoint."""
    logger.warning("Legacy Stripe webhook endpoint used: /webhooks/stripe-legacy")
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-06-30"
    response.headers["Link"] = '</webhooks/stripe>; rel="successor-version"'
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Legacy endpoint removed. Use /webhooks/stripe.",
    )

# ============ Google Business Profile Webhooks ============

@router.post("/gbp-notifications")
async def handle_gbp_notification(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Handle Google Business Profile notifications.
    
    Events:
    - New review
    - New Q&A question
    - Profile update
    """
    data = await request.json()
    logger.info(f"GBP notification: {data}")

    notification_type = data.get("type")

    if notification_type == "NEW_REVIEW":
        await _handle_new_review(data, db)
    elif notification_type == "NEW_QUESTION":
        await _handle_new_question(data, db)

    return {"status": "received"}


def _candidate_gbp_location_resources(payload: dict[str, Any]) -> list[str]:
    """Extract likely GBP location resource identifiers from a webhook payload."""
    candidates: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                visit(nested)
            return
        if isinstance(value, list):
            for nested in value:
                visit(nested)
            return
        if isinstance(value, str) and "locations/" in value:
            cleaned = value.strip()
            candidates.append(cleaned)
            for marker in ("/reviews/", "/questions/", "/localPosts/", "/media/"):
                if marker in cleaned:
                    candidates.append(cleaned.split(marker, 1)[0])
            location_index = cleaned.find("locations/")
            if location_index >= 0:
                location_tail = cleaned[location_index:]
                candidates.append(location_tail)
                parts = location_tail.split("/")
                if len(parts) >= 2:
                    candidates.append("/".join(parts[:2]))

    visit(payload)

    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    return ordered


def _resolve_gbp_location(db: Session, payload: dict[str, Any]):
    """Resolve the owning location for a GBP webhook payload."""
    from app.models.location import Location

    for candidate in _candidate_gbp_location_resources(payload):
        location = db.query(Location).filter(Location.gbp_location_id == candidate).first()
        if location:
            return location
    return None


def _extract_review_summary(payload: dict[str, Any]) -> tuple[str, str]:
    """Build a user-facing title/body for a new review webhook."""
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    reviewer = review.get("reviewer", {}) if isinstance(review.get("reviewer"), dict) else {}
    reviewer_name = (
        reviewer.get("displayName")
        or review.get("reviewer_name")
        or payload.get("reviewer_name")
        or "A customer"
    )
    rating = review.get("starRating") or review.get("rating") or payload.get("rating")
    review_text = review.get("comment") or review.get("text") or payload.get("comment") or payload.get("text") or ""
    compact_text = " ".join(str(review_text).split())
    snippet = compact_text[:140] + ("..." if len(compact_text) > 140 else "")

    title = "New Google review"
    if rating:
        title = f"New Google review ({rating})"

    message = f"{reviewer_name} left a new review on Google Business Profile."
    if snippet:
        message += f"\n\n{snippet}"
    return title, message


def _extract_question_summary(payload: dict[str, Any]) -> tuple[str, str]:
    """Build a user-facing title/body for a new GBP question webhook."""
    question = payload.get("question") if isinstance(payload.get("question"), dict) else {}
    author = question.get("author", {}) if isinstance(question.get("author"), dict) else {}
    author_name = author.get("displayName") or payload.get("author_name") or "A customer"
    question_text = question.get("text") or payload.get("text") or ""
    compact_text = " ".join(str(question_text).split())
    snippet = compact_text[:180] + ("..." if len(compact_text) > 180 else "")

    message = f"{author_name} asked a new Google Business Profile question."
    if snippet:
        message += f"\n\n{snippet}"
    return "New GBP question", message


async def _handle_new_review(data: dict, db: Session) -> None:
    """Handle new review notification."""
    logger.info(f"New review received: {data}")
    from app.services.notification import NotificationService

    location = _resolve_gbp_location(db, data)
    if not location:
        logger.warning("GBP review webhook could not be matched to a location: %s", data)
        return

    title, message = _extract_review_summary(data)
    await NotificationService(db).send_notification(
        account_id=location.account_id,
        title=title,
        message=message,
        notification_type="gbp_new_review",
        data={
            "url": "/dashboard/reviews",
            "location_id": str(location.id),
            "gbp_location_id": location.gbp_location_id,
            "payload_type": data.get("type"),
        },
    )


async def _handle_new_question(data: dict, db: Session) -> None:
    """Handle new Q&A question."""
    logger.info(f"New question received: {data}")
    from app.services.notification import NotificationService

    location = _resolve_gbp_location(db, data)
    if not location:
        logger.warning("GBP question webhook could not be matched to a location: %s", data)
        return

    title, message = _extract_question_summary(data)
    await NotificationService(db).send_notification(
        account_id=location.account_id,
        title=title,
        message=message,
        notification_type="gbp_new_question",
        data={
            "url": "/dashboard/qa",
            "location_id": str(location.id),
            "gbp_location_id": location.gbp_location_id,
            "payload_type": data.get("type"),
        },
    )


# ============ Twilio SMS Status Webhooks ============

@router.post("/twilio/sms-status")
async def handle_sms_status(
    request_id: UUID = Query(...),
    MessageSid: str = Form(...),
    MessageStatus: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Handle Twilio SMS delivery status callback.
    
    Called when SMS status changes (queued, sent, delivered, failed, etc.)
    """
    from app.jobs.review_booster_jobs import handle_sms_status_callback
    
    logger.info(f"SMS status callback: {request_id} -> {MessageStatus}")
    
    await handle_sms_status_callback(
        request_id=request_id,
        message_sid=MessageSid,
        status=MessageStatus,
    )
    
    return {"status": "received"}


@router.post("/twilio/sms-incoming")
async def handle_twilio_incoming_sms(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Handle incoming SMS messages.

    Used for:
    - Customer replies to review requests
    - SMS conversation threads (P3)
    - Opt-out keywords (STOP)
    """
    from app.models.calls import MessageDirection, SMSMessage, TwilioNumber
    from app.models.location import Location
    from app.services.call_text_back_service import get_call_text_back_service
    from app.services.notification import NotificationService
    from app.services.review_booster_service import get_review_booster_service
    from app.schemas.review_booster import OptoutCreate

    logger.info(f"Incoming SMS from {From[:4]}**** to {To}: {Body[:50]}")

    twilio_number = (
        db.query(TwilioNumber)
        .filter(TwilioNumber.twilio_number == To)
        .first()
    )

    opt_out_keywords = ["stop", "unsubscribe"]
    if Body.strip().lower() in opt_out_keywords:
        logger.info(f"Opt-out request from {From}")
        if twilio_number:
            location = db.get(Location, twilio_number.location_id)
            review_booster_service = get_review_booster_service(db)
            if not review_booster_service.is_opted_out(twilio_number.location_id, From, None):
                review_booster_service.add_optout(
                    twilio_number.location_id,
                    OptoutCreate(phone=From, reason="sms_stop_webhook"),
                )
                if location:
                    await NotificationService(db).send_notification(
                        account_id=location.account_id,
                        title="Customer opted out of SMS",
                        message=f"{From} replied STOP and has been added to the review/SMS opt-out list.",
                        notification_type="sms_optout_received",
                        data={
                            "url": "/dashboard/reviews",
                            "location_id": str(twilio_number.location_id),
                            "phone": From,
                            "twilio_number": To,
                        },
                    )
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Message>You have been unsubscribed. Reply START to opt back in.</Message></Response>',
            media_type="application/xml",
        )

    if twilio_number:
        service = get_call_text_back_service(db)
        thread = service._get_or_create_thread(
            twilio_number.location_id,
            From,
            twilio_number.twilio_number,
        )
        db.add(
            SMSMessage(
                thread_id=thread.id,
                direction=MessageDirection.INBOUND,
                body=Body,
                status="received",
                twilio_message_sid=MessageSid,
            )
        )
        thread.last_message_at = utc_now_naive()
        thread.unread_count += 1
        db.commit()
        logger.info(f"Stored inbound SMS for thread {thread.id}")

    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


# ============ Stripe Webhooks (P0: Idempotency) ============

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Stripe webhook handler with idempotency guarantee.
    
    P0 CRITICAL: Uses INSERT with IntegrityError catch to prevent duplicate processing.
    Race condition safe: Multiple simultaneous deliveries will result in
    exactly one successful INSERT, others fail with IntegrityError.
    """
    import stripe
    from sqlalchemy.exc import IntegrityError
    from app.core.config import settings
    from app.models.stripe_event import StripeEvent
    
    stripe.api_key = settings.stripe_secret_key
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    # Verify signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        raise HTTPException(400, "Invalid signature")
    
    # IDEMPOTENCY: Try to insert event, fail if duplicate
    try:
        stripe_event = StripeEvent(
            event_id=event.id,
            event_type=event.type,
            payload=event.to_dict()
        )
        db.add(stripe_event)
        db.commit()  # Persist event log first so retries are deduped even if processing fails
        
        logger.info(f"Processing new webhook event: {event.id} type={event.type}")
        
    except IntegrityError:
        # Duplicate event_id - already processed
        db.rollback()
        logger.warning(f"Duplicate webhook event ignored: {event.id}")
        return {"status": "duplicate", "processed": False}
    
    # Process event (side effects happen exactly once)
    try:
        await process_stripe_event(event, db)
        db.commit()
        logger.info(f"Successfully processed webhook: {event.id}")
        return {"status": "success", "processed": True}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing webhook {event.id}: {str(e)}", exc_info=True)
        _notify_admin_webhook_failure(
            db,
            title="Stripe webhook processing failed",
            message=(
                f"Stripe webhook {event.type} ({event.id}) was recorded but could not be fully applied."
                f"\n\nReason: {e}"
                "\n\nThis delivery will not be retried automatically because the event has already been deduplicated."
            ),
            notification_type="stripe_webhook_processing_failed",
        )
        # Return 200 to prevent Stripe retries (event is recorded, can replay manually)
        return {"status": "error", "message": str(e), "processed": False}


async def process_stripe_event(event: Any, db: Session):
    """Process different Stripe event types."""
    from app.services.billing import BillingService

    billing_service = BillingService(db)

    if event.type == "checkout.session.completed":
        await handle_checkout_session_completed(event, db)

    elif event.type == "checkout.session.expired":
        await handle_checkout_session_expired(event, db)

    elif event.type == "checkout.session.async_payment_failed":
        await handle_checkout_session_async_payment_failed(event, db)

    elif event.type == "charge.refunded":
        credit_refund_result = await handle_charge_refunded(event, db)
        await billing_service.handle_verified_event_object(
            event_type=event.type,
            event_object=event.data.object,
        )
        _notify_unmatched_refund_if_needed(
            db,
            charge=event.data.object,
            credit_refund_result=credit_refund_result,
        )

    elif event.type == "charge.dispute.created":
        await billing_service.handle_verified_event_object(
            event_type=event.type,
            event_object=event.data.object,
        )

    elif event.type == "charge.dispute.updated":
        await billing_service.handle_verified_event_object(
            event_type=event.type,
            event_object=event.data.object,
        )

    elif event.type == "customer.subscription.created":
        await billing_service.handle_verified_event_object(
            event_type=event.type,
            event_object=event.data.object,
        )

    elif event.type == "invoice.payment_failed":
        await billing_service.handle_verified_event_object(
            event_type=event.type,
            event_object=event.data.object,
        )

    elif event.type in {"invoice.payment_succeeded", "invoice.paid"}:
        await billing_service.handle_verified_event_object(
            event_type=event.type,
            event_object=event.data.object,
        )

    elif event.type == "customer.subscription.updated":
        await billing_service.handle_verified_event_object(
            event_type=event.type,
            event_object=event.data.object,
        )

    elif event.type == "customer.subscription.deleted":
        await billing_service.handle_verified_event_object(
            event_type=event.type,
            event_object=event.data.object,
        )

    elif event.type == "customer.subscription.trial_will_end":
        await billing_service.handle_verified_event_object(
            event_type=event.type,
            event_object=event.data.object,
        )

    else:
        logger.info(f"Unhandled event type: {event.type}")


async def handle_checkout_session_completed(event: Any, db: Session):
    """Handle checkout.session.completed for credit purchases (and subscriptions).

    Subscription checkouts activate the subscription via stripe_subscription_id.
    Credit purchases apply the purchased credits to the account balance.
    """
    session = event.data.object
    metadata = session.get("metadata") or {}
    purchase_type = metadata.get("purchase_type")

    if purchase_type == "credits":
        from app.services.credits import CreditsService

        stripe_session_id = session.get("id")
        stripe_payment_intent_id = session.get("payment_intent")

        result = CreditsService(db).apply_purchase_from_webhook(
            stripe_session_id=stripe_session_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
        )

        if result.get("applied"):
            logger.info(
                "Credits applied from purchase: account=%s credits=%s order=%s",
                result.get("account_id"),
                result.get("credits_amount"),
                result.get("order_id"),
            )
        elif result.get("already_applied"):
            logger.info(
                "Credit purchase already applied (duplicate webhook): order=%s",
                result.get("order_id"),
            )
        else:
            logger.error(
                "Credit purchase apply failed: reason=%s session=%s",
                result.get("reason"),
                stripe_session_id,
            )
            _notify_admin_webhook_failure(
                db,
                title="Stripe credit purchase apply failed",
                message=(
                    "A Stripe checkout.session.completed event for a credit purchase "
                    "could not be applied to the local credit balance.\n\n"
                    f"Session ID: {stripe_session_id or 'Not recorded'}\n"
                    f"Payment intent ID: {stripe_payment_intent_id or 'Not recorded'}\n"
                    f"Account ID: {metadata.get('account_id') or 'Not recorded'}\n"
                    f"Package ID: {metadata.get('package_id') or 'Not recorded'}\n"
                    f"Credits amount: {metadata.get('credits_amount') or 'Not recorded'}\n"
                    f"Reason: {result.get('reason') or 'unknown'}"
                ),
                notification_type="stripe_credit_purchase_apply_failed",
            )
    else:
        from app.services.billing import BillingService

        await BillingService(db).handle_verified_event_object(
            event_type=event.type,
            event_object=session,
        )


async def handle_checkout_session_expired(event: Any, db: Session):
    """Mark a pending credit purchase order as EXPIRED when the session times out."""
    from app.models.credits import CreditPurchaseStatus
    from app.services.credits import CreditsService

    session = event.data.object
    metadata = session.get("metadata") or {}
    if metadata.get("purchase_type") != "credits":
        return

    stripe_session_id = session.get("id")
    result = CreditsService(db).cancel_purchase_order(
        stripe_session_id=stripe_session_id,
        target_status=CreditPurchaseStatus.EXPIRED,
    )
    if result.get("canceled"):
        logger.info(
            "Credit purchase order expired: order=%s session=%s",
            result.get("order_id"),
            stripe_session_id,
        )
    elif result.get("already_canceled"):
        logger.info(
            "Credit purchase order already canceled/expired (duplicate webhook): order=%s",
            result.get("order_id"),
        )
    else:
        logger.warning(
            "Could not expire credit purchase order: reason=%s session=%s",
            result.get("reason"),
            stripe_session_id,
        )
        _notify_credit_purchase_close_failed(
            db,
            action="expire",
            session=session,
            result=result,
            target_status=CreditPurchaseStatus.EXPIRED.value,
        )


async def handle_checkout_session_async_payment_failed(event: Any, db: Session):
    """Mark a pending credit purchase order as CANCELED on async payment failure."""
    from app.models.credits import CreditPurchaseStatus
    from app.services.credits import CreditsService

    session = event.data.object
    metadata = session.get("metadata") or {}
    if metadata.get("purchase_type") != "credits":
        return

    stripe_session_id = session.get("id")
    result = CreditsService(db).cancel_purchase_order(
        stripe_session_id=stripe_session_id,
        target_status=CreditPurchaseStatus.CANCELED,
    )
    if result.get("canceled"):
        logger.info(
            "Credit purchase order canceled (async payment failed): order=%s session=%s",
            result.get("order_id"),
            stripe_session_id,
        )
    elif result.get("already_canceled"):
        logger.info(
            "Credit purchase order already canceled/expired (duplicate async failure): order=%s",
            result.get("order_id"),
        )
    else:
        logger.warning(
            "Could not cancel credit purchase order: reason=%s session=%s",
            result.get("reason"),
            stripe_session_id,
        )
        _notify_credit_purchase_close_failed(
            db,
            action="cancel",
            session=session,
            result=result,
            target_status=CreditPurchaseStatus.CANCELED.value,
        )


def _stripe_object_value(obj: Any, key: str, default: Any = None) -> Any:
    if hasattr(obj, "get"):
        try:
            return obj.get(key, default)
        except Exception:
            pass
    return getattr(obj, key, default)


def _notify_credit_purchase_close_failed(
    db: Session,
    *,
    action: str,
    session: Any,
    result: dict[str, Any],
    target_status: str,
) -> None:
    metadata = _stripe_object_value(session, "metadata", {}) or {}
    stripe_session_id = _stripe_object_value(session, "id", "Not recorded")
    _notify_admin_webhook_failure(
        db,
        title="Stripe credit purchase close failed",
        message=(
            f"A Stripe checkout session could not {action} the local credit purchase order.\n\n"
            f"Session ID: {stripe_session_id}\n"
            f"Target status: {target_status}\n"
            f"Account ID: {metadata.get('account_id') or 'Not recorded'}\n"
            f"Package ID: {metadata.get('package_id') or 'Not recorded'}\n"
            f"Credits amount: {metadata.get('credits_amount') or 'Not recorded'}\n"
            f"Order ID: {result.get('order_id') or 'Not recorded'}\n"
            f"Current status: {result.get('status') or 'Not recorded'}\n"
            f"Reason: {result.get('reason') or 'unknown'}"
        ),
        notification_type="stripe_credit_purchase_close_failed",
    )


def _refund_ids_from_charge(charge: Any) -> list[str]:
    refunds = _stripe_object_value(charge, "refunds")
    refund_items = _stripe_object_value(refunds, "data", []) if refunds is not None else []
    try:
        iterable = list(refund_items)
    except TypeError:
        return []

    refund_ids: list[str] = []
    for refund in iterable:
        refund_id = _stripe_object_value(refund, "id")
        if refund_id:
            refund_ids.append(str(refund_id))
    return refund_ids


def _notify_unmatched_refund_if_needed(
    db: Session,
    *,
    charge: Any,
    credit_refund_result: dict[str, Any] | None,
) -> None:
    """Alert admins when a Stripe refund matches neither credits nor billing records."""
    from app.models.billing import Refund

    credit_refund_result = credit_refund_result or {}
    credit_order_matched = bool(
        credit_refund_result.get("refunded")
        or credit_refund_result.get("already_refunded")
        or credit_refund_result.get("order_id")
    )
    if credit_order_matched:
        return

    refund_ids = _refund_ids_from_charge(charge)
    recorded_refund_count = 0
    if refund_ids:
        recorded_refund_count = (
            db.query(Refund)
            .filter(Refund.stripe_refund_id.in_(refund_ids))
            .count()
        )
    if recorded_refund_count > 0:
        return

    charge_id = _stripe_object_value(charge, "id", "unknown")
    payment_intent_id = _stripe_object_value(charge, "payment_intent", "unknown")
    _notify_admin_webhook_failure(
        db,
        title="Stripe refund unmatched",
        message=(
            "A Stripe charge.refunded event did not match a local credit purchase "
            "or billing payment record.\n\n"
            f"Charge ID: {charge_id}\n"
            f"Payment intent ID: {payment_intent_id}\n"
            f"Refund IDs: {', '.join(refund_ids) if refund_ids else 'Not recorded'}\n"
            f"Credit refund reason: {credit_refund_result.get('reason') or 'Not recorded'}"
        ),
        notification_type="stripe_refund_unmatched",
    )


async def handle_charge_refunded(event: Any, db: Session) -> dict[str, Any]:
    """Claw back credits when Stripe issues a refund for a credit purchase."""
    from app.services.credits import CreditsService

    charge = event.data.object
    payment_intent_id = _stripe_object_value(charge, "payment_intent")

    if not payment_intent_id:
        logger.warning("charge.refunded event missing payment_intent; skipping")
        return {"refunded": False, "reason": "missing_payment_intent"}

    result = CreditsService(db).refund_purchase(
        stripe_payment_intent_id=str(payment_intent_id),
    )

    if result.get("refunded"):
        logger.info(
            "Credits clawed back on refund: account=%s credits=%s order=%s",
            result.get("account_id"),
            result.get("credits_deducted"),
            result.get("order_id"),
        )
    elif result.get("already_refunded"):
        logger.info(
            "Credit refund already processed (duplicate webhook): order=%s",
            result.get("order_id"),
        )
    else:
        logger.info(
            "charge.refunded: no credit purchase order found or not applicable "
            "(reason=%s, pi=%s) – no credit changes made",
            result.get("reason"),
            payment_intent_id,
        )
    return result


