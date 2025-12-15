"""Missed Call Text Back service using Twilio API."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import UUID

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Dial
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class TwilioCallService:
    """
    Service for handling missed call text back functionality.
    
    핵심 기능: 부재중 전화 자동 문자 응답
    - 전화가 오면 실제 번호로 연결
    - 부재중(busy, no-answer, failed)이면 자동 SMS 발송
    """

    # Call statuses that trigger text back
    MISSED_CALL_STATUSES = ["busy", "no-answer", "failed", "canceled"]

    def __init__(self):
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.twilio_number = settings.twilio_phone_number
        self.client = None

        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)

    def generate_call_forward_twiml(
        self,
        real_phone_number: str,
        location_id: str,
        timeout: int = 20,
    ) -> str:
        """
        Generate TwiML for call forwarding with status callback.
        
        Args:
            real_phone_number: The actual business phone number to forward to
            location_id: Location ID for tracking
            timeout: Ring timeout in seconds before considering it missed
        
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()

        # Create dial with action callback
        dial = Dial(
            timeout=timeout,
            action=f"/api/v1/webhooks/voice-status?location_id={location_id}",
            method="POST",
        )
        dial.number(real_phone_number)

        response.append(dial)

        return str(response)

    async def send_missed_call_sms(
        self,
        to_number: str,
        from_number: str,
        message: str,
    ) -> dict[str, Any]:
        """
        Send SMS for missed call.
        
        Args:
            to_number: Caller's phone number
            from_number: Twilio phone number
            message: SMS message content
        
        Returns:
            Twilio message response
        """
        if not self.client:
            logger.error("Twilio client not initialized")
            return {"error": "Twilio not configured"}

        try:
            message_response = self.client.messages.create(
                body=message,
                from_=from_number,
                to=to_number,
            )

            logger.info(f"SMS sent to {to_number}: {message_response.sid}")

            return {
                "success": True,
                "message_sid": message_response.sid,
                "to": to_number,
                "status": message_response.status,
            }

        except Exception as e:
            logger.error(f"Failed to send SMS to {to_number}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def is_missed_call(self, call_status: str) -> bool:
        """Check if call status indicates a missed call."""
        return call_status.lower() in self.MISSED_CALL_STATUSES


class MissedCallTextBackService:
    """
    Service for managing missed call text back configurations and logs.
    """

    # Default message templates by business category
    DEFAULT_TEMPLATES = {
        "restaurant": (
            "Hi! Sorry we missed your call to {business_name}. "
            "We're currently busy but would love to help you. "
            "Reply to this text or call us back. "
            "View our menu: {website_url}"
        ),
        "spa": (
            "Hi! Thanks for calling {business_name}. "
            "We missed your call but want to help you book your appointment. "
            "Reply here or book online: {website_url}"
        ),
        "dentist": (
            "Thank you for calling {business_name}. "
            "We're sorry we couldn't answer. "
            "Please reply to schedule an appointment or call us back during business hours."
        ),
        "default": (
            "Hi! Thanks for calling {business_name}. "
            "We missed your call but we'd love to help. "
            "Please reply to this message or try calling again. "
            "We'll get back to you as soon as possible!"
        ),
    }

    def __init__(self, db: Session):
        self.db = db
        self.twilio_service = TwilioCallService()

    def get_message_template(
        self,
        location_id: UUID,
        category: str | None = None,
    ) -> str:
        """
        Get the missed call message template for a location.
        
        First checks for custom template, then falls back to category default.
        """
        from app.models.location import Location

        location = self.db.query(Location).filter(
            Location.id == location_id
        ).first()

        if not location:
            return self.DEFAULT_TEMPLATES["default"]

        # Check for custom template in location settings
        if location.settings and location.settings.get("missed_call_template"):
            return location.settings["missed_call_template"]

        # Use category-specific template
        loc_category = category or getattr(location, "category", None) or "default"
        template = self.DEFAULT_TEMPLATES.get(loc_category, self.DEFAULT_TEMPLATES["default"])

        # Fill in business details
        return template.format(
            business_name=location.name,
            website_url=location.website_url or "",
        )

    async def handle_missed_call(
        self,
        location_id: UUID,
        caller_number: str,
        call_status: str,
        call_sid: str | None = None,
    ) -> dict[str, Any]:
        """
        Handle a missed call event.
        
        1. Check if it's actually a missed call
        2. Check for duplicate (already sent SMS in last 24h)
        3. Get message template
        4. Send SMS
        5. Log the event
        """
        from app.models.location import Location

        # Verify it's a missed call
        if not self.twilio_service.is_missed_call(call_status):
            return {"action": "none", "reason": "not_missed_call"}

        # Get location
        location = self.db.query(Location).filter(
            Location.id == location_id
        ).first()

        if not location:
            return {"action": "none", "reason": "location_not_found"}

        # Check for duplicate (simple DB check - could use Redis for better performance)
        if await self._is_duplicate_sms(location_id, caller_number):
            return {"action": "skipped", "reason": "duplicate_within_24h"}

        # Get message template
        message = self.get_message_template(location_id, location.category)

        # Send SMS
        result = await self.twilio_service.send_missed_call_sms(
            to_number=caller_number,
            from_number=settings.twilio_phone_number,
            message=message,
        )

        # Log the event
        await self._log_missed_call_sms(
            location_id=location_id,
            caller_number=caller_number,
            call_status=call_status,
            call_sid=call_sid,
            sms_result=result,
        )

        return {
            "action": "sms_sent" if result.get("success") else "sms_failed",
            "result": result,
        }

    async def _is_duplicate_sms(
        self,
        location_id: UUID,
        caller_number: str,
        hours: int = 24,
    ) -> bool:
        """Check if SMS was already sent to this number within the time window."""
        from app.models.analytics import Analytics

        # Check recent SMS logs
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # This would query a missed_call_logs table
        # For now, simplified check using analytics or a dedicated table
        # TODO: Implement proper deduplication with Redis or dedicated table

        return False

    async def _log_missed_call_sms(
        self,
        location_id: UUID,
        caller_number: str,
        call_status: str,
        call_sid: str | None,
        sms_result: dict[str, Any],
    ) -> None:
        """Log the missed call SMS event."""
        # TODO: Create MissedCallLog model and save to database
        logger.info(
            f"Missed call SMS log: location={location_id}, "
            f"caller={caller_number}, status={call_status}, "
            f"result={sms_result.get('success')}"
        )


class CallAnalyticsService:
    """Service for tracking call analytics."""

    def __init__(self, db: Session):
        self.db = db

    async def record_incoming_call(
        self,
        location_id: UUID,
        caller_number: str,
        call_status: str,
        duration: int = 0,
    ) -> None:
        """Record an incoming call for analytics."""
        from app.models.analytics import Analytics

        # Update daily call count
        today = datetime.now(timezone.utc).date()

        analytics = self.db.query(Analytics).filter(
            Analytics.location_id == location_id,
            Analytics.date == today,
        ).first()

        if analytics:
            # Increment call count
            current_calls = analytics.metrics.get("calls", 0) if analytics.metrics else 0
            if not analytics.metrics:
                analytics.metrics = {}
            analytics.metrics["calls"] = current_calls + 1

            # Track missed vs answered
            if call_status in TwilioCallService.MISSED_CALL_STATUSES:
                missed = analytics.metrics.get("missed_calls", 0)
                analytics.metrics["missed_calls"] = missed + 1
            else:
                answered = analytics.metrics.get("answered_calls", 0)
                analytics.metrics["answered_calls"] = answered + 1

        self.db.commit()
