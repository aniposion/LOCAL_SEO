"""Webhook handlers for external services (Twilio, Stripe, etc.)."""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.call_service import MissedCallTextBackService, TwilioCallService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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
    """
    logger.info(
        f"Voice status webhook: location={location_id}, "
        f"status={CallStatus}, from={From}, duration={Duration}"
    )

    # Handle missed call text back
    service = MissedCallTextBackService(db)
    result = await service.handle_missed_call(
        location_id=location_id,
        caller_number=From,
        call_status=CallStatus,
        call_sid=CallSid,
    )

    logger.info(f"Missed call handling result: {result}")

    # Return empty TwiML (Twilio expects a response)
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


# ============ Twilio SMS Webhooks ============

@router.post("/sms-incoming")
async def handle_incoming_sms(
    request: Request,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    Handle incoming SMS messages.
    
    This can be used for:
    - Customer replies to missed call texts
    - Appointment confirmations
    - Review request responses
    """
    logger.info(f"Incoming SMS from {From}: {Body[:50]}...")

    # TODO: Implement SMS response handling
    # - Route to appropriate handler based on context
    # - Auto-respond if configured
    # - Notify business owner

    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


# ============ Stripe Webhooks ============

@router.post("/stripe")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    """
    Handle Stripe webhook events.
    
    Events handled:
    - checkout.session.completed
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed
    """
    import stripe
    from app.core.config import settings

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.stripe_webhook_secret,
        )
    except ValueError as e:
        logger.error(f"Invalid Stripe payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid Stripe signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, db)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data, db)
    elif event_type == "invoice.payment_succeeded":
        await _handle_payment_succeeded(data, db)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data, db)

    return {"status": "success"}


async def _handle_checkout_completed(data: dict, db: Session) -> None:
    """Handle successful checkout."""
    from app.models.subscription import Subscription, SubscriptionStatus

    customer_id = data.get("customer")
    subscription_id = data.get("subscription")

    # Find subscription by Stripe customer ID
    subscription = db.query(Subscription).filter(
        Subscription.stripe_customer_id == customer_id
    ).first()

    if subscription:
        subscription.stripe_subscription_id = subscription_id
        subscription.status = SubscriptionStatus.ACTIVE
        db.commit()
        logger.info(f"Subscription activated: {subscription.id}")


async def _handle_subscription_updated(data: dict, db: Session) -> None:
    """Handle subscription update."""
    from app.models.subscription import Subscription, SubscriptionStatus

    stripe_sub_id = data.get("id")
    status_map = {
        "active": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "trialing": SubscriptionStatus.TRIALING,
    }

    subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_sub_id
    ).first()

    if subscription:
        new_status = status_map.get(data.get("status"))
        if new_status:
            subscription.status = new_status
            db.commit()


async def _handle_subscription_deleted(data: dict, db: Session) -> None:
    """Handle subscription cancellation."""
    from app.models.subscription import Subscription, SubscriptionStatus

    stripe_sub_id = data.get("id")

    subscription = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_sub_id
    ).first()

    if subscription:
        subscription.status = SubscriptionStatus.CANCELED
        db.commit()
        logger.info(f"Subscription canceled: {subscription.id}")


async def _handle_payment_succeeded(data: dict, db: Session) -> None:
    """Handle successful payment."""
    from app.models.subscription import PaymentHistory

    customer_id = data.get("customer")
    amount = data.get("amount_paid", 0) / 100  # Convert cents to dollars

    # Log payment
    logger.info(f"Payment succeeded: customer={customer_id}, amount=${amount}")

    # TODO: Create PaymentHistory record


async def _handle_payment_failed(data: dict, db: Session) -> None:
    """Handle failed payment."""
    customer_id = data.get("customer")

    logger.warning(f"Payment failed for customer: {customer_id}")

    # TODO: Send notification to customer
    # TODO: Update subscription status


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


async def _handle_new_review(data: dict, db: Session) -> None:
    """Handle new review notification."""
    # TODO: Trigger review response workflow
    logger.info(f"New review received: {data}")


async def _handle_new_question(data: dict, db: Session) -> None:
    """Handle new Q&A question."""
    # TODO: Trigger Q&A response workflow
    logger.info(f"New question received: {data}")
