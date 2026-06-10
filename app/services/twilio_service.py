"""Twilio SMS and Voice service."""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class TwilioUnavailableError(RuntimeError):
    """Raised when Twilio cannot be used with the current configuration."""


class TwilioDeliveryError(RuntimeError):
    """Raised when Twilio rejects a delivery request."""


class TwilioService:
    """Service for Twilio SMS and Voice operations.

    Handles:
    - SMS sending for Review Booster
    - Missed call text-back
    - SMS conversations
    """

    def __init__(self):
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.default_from = settings.twilio_phone_number
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.default_from)

    def availability_reason(self) -> str:
        missing = []
        if not self.account_sid:
            missing.append("Twilio account SID")
        if not self.auth_token:
            missing.append("Twilio auth token")
        if not self.default_from:
            missing.append("Twilio phone number")
        return ", ".join(missing)

    def _create_client(self):
        if not self.account_sid or not self.auth_token:
            raise TwilioUnavailableError(
                f"Twilio is unavailable: {self.availability_reason() or 'credentials are missing'}"
            )

        try:
            from twilio.rest import Client
        except ImportError as exc:
            raise TwilioUnavailableError("Twilio SDK is not installed.") from exc

        return Client(self.account_sid, self.auth_token)

    @property
    def client(self):
        """Lazy load Twilio client."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    async def send_sms(
        self,
        to: str,
        body: str,
        from_number: Optional[str] = None,
        status_callback: Optional[str] = None,
    ) -> dict:
        """Send SMS message."""
        from_number = from_number or self.default_from

        if not from_number:
            raise TwilioUnavailableError("Twilio phone number is not configured.")

        to = self._format_phone(to)

        try:
            callback_url = None
            if status_callback and settings.app_url:
                callback_url = f"{settings.app_url}{status_callback}"

            message = self.client.messages.create(
                to=to,
                from_=from_number,
                body=body,
                status_callback=callback_url,
            )

            logger.info("SMS sent to %s, SID: %s", to[:4] + "****", message.sid)
            return {
                "sid": message.sid,
                "status": message.status,
                "to": to,
                "from": from_number,
            }
        except TwilioUnavailableError:
            raise
        except Exception as exc:
            logger.error("Failed to send SMS: %s", exc)
            raise TwilioDeliveryError(f"Failed to send SMS: {exc}") from exc

    async def send_mms(
        self,
        to: str,
        body: str,
        media_url: str,
        from_number: Optional[str] = None,
    ) -> dict:
        """Send MMS message with media."""
        from_number = from_number or self.default_from
        if not from_number:
            raise TwilioUnavailableError("Twilio phone number is not configured.")

        to = self._format_phone(to)

        try:
            message = self.client.messages.create(
                to=to,
                from_=from_number,
                body=body,
                media_url=[media_url],
            )
            return {
                "sid": message.sid,
                "status": message.status,
            }
        except TwilioUnavailableError:
            raise
        except Exception as exc:
            logger.error("Failed to send MMS: %s", exc)
            raise TwilioDeliveryError(f"Failed to send MMS: {exc}") from exc

    async def get_message_status(self, message_sid: str) -> dict:
        """Get message delivery status."""
        try:
            message = self.client.messages(message_sid).fetch()
            return {
                "sid": message.sid,
                "status": message.status,
                "error_code": message.error_code,
                "error_message": message.error_message,
            }
        except TwilioUnavailableError:
            raise
        except Exception as exc:
            logger.error("Failed to get message status: %s", exc)
            raise TwilioDeliveryError(f"Failed to get message status: {exc}") from exc

    def _format_phone(self, phone: str) -> str:
        """Format phone number to E.164."""
        digits = "".join(filter(str.isdigit, phone))

        if digits.startswith("010") or digits.startswith("011"):
            digits = "82" + digits[1:]
        elif len(digits) == 10:
            digits = "1" + digits
        elif digits.startswith("1") and len(digits) == 11:
            pass
        elif not digits.startswith("82") and not digits.startswith("1"):
            digits = "82" + digits

        return "+" + digits


_twilio_service: Optional[TwilioService] = None


def get_twilio_service() -> TwilioService:
    """Get Twilio service singleton."""
    global _twilio_service
    if _twilio_service is None:
        _twilio_service = TwilioService()
    return _twilio_service
