"""Lightweight Twilio voice helpers used by webhook routing."""

from twilio.twiml.voice_response import Dial, VoiceResponse


class TwilioCallService:
    """Generate TwiML for forwarding inbound calls to the real business line.

    Missed-call text-back delivery now lives in ``app.services.call_text_back_service``.
    This module intentionally stays narrow so legacy dead code does not drift away
    from the active production path.
    """

    def generate_call_forward_twiml(
        self,
        real_phone_number: str,
        location_id: str,
        timeout: int = 20,
    ) -> str:
        """Return TwiML that dials the real business number with a status callback."""
        response = VoiceResponse()
        dial = Dial(
            timeout=timeout,
            action=f"/webhooks/voice-status?location_id={location_id}",
            method="POST",
        )
        dial.number(real_phone_number)
        response.append(dial)
        return str(response)
