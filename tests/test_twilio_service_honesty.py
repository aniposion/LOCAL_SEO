import pytest

from app.services.twilio_service import TwilioService, TwilioUnavailableError


@pytest.mark.asyncio
async def test_twilio_send_sms_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr("app.services.twilio_service.settings.twilio_account_sid", None, raising=False)
    monkeypatch.setattr("app.services.twilio_service.settings.twilio_auth_token", None, raising=False)
    monkeypatch.setattr("app.services.twilio_service.settings.twilio_phone_number", None, raising=False)

    service = TwilioService()

    with pytest.raises(TwilioUnavailableError) as exc_info:
        await service.send_sms("555-123-4567", "Hello")

    assert "twilio" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_twilio_send_sms_uses_injected_client_when_configured(monkeypatch):
    monkeypatch.setattr("app.services.twilio_service.settings.twilio_account_sid", "AC123", raising=False)
    monkeypatch.setattr("app.services.twilio_service.settings.twilio_auth_token", "token123", raising=False)
    monkeypatch.setattr("app.services.twilio_service.settings.twilio_phone_number", "+15555550100", raising=False)
    monkeypatch.setattr("app.services.twilio_service.settings.app_url", "https://app.example.com", raising=False)

    class FakeMessage:
        sid = "SM123"
        status = "queued"

    class FakeMessages:
        def create(self, **kwargs):
            self.kwargs = kwargs
            return FakeMessage()

    class FakeClient:
        def __init__(self):
            self.messages = FakeMessages()

    service = TwilioService()
    monkeypatch.setattr(service, "_create_client", lambda: FakeClient())

    result = await service.send_sms(
        "555-123-4567",
        "Hello from the system",
        status_callback="/webhooks/twilio/sms-status",
    )

    assert result["sid"] == "SM123"
    assert result["status"] == "queued"
    assert result["to"] == "+15551234567"
    assert result["from"] == "+15555550100"
