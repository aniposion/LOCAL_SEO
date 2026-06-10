import sys
from datetime import timedelta
from types import ModuleType

import pytest
from sqlalchemy import func

from app.core.time import utc_now_aware
from app.models.calls import CallLog, MessageDirection, SMSMessage, SMSThread, TwilioNumber
from app.models.credits import UsageRecord
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.review_booster import ReviewOptout
from app.services.call_text_back_service import get_call_text_back_service
from app.services.twilio_service import TwilioUnavailableError


def _create_number(db, location_id, twilio_number="+15550000001"):
    number = TwilioNumber(
        location_id=location_id,
        twilio_number=twilio_number,
        forward_to="+15551112222",
    )
    db.add(number)
    db.commit()
    db.refresh(number)
    return number


def _create_thread(db, location_id, twilio_number="+15550000004"):
    thread = SMSThread(
        location_id=location_id,
        customer_phone="+15556667777",
        twilio_number=twilio_number,
        unread_count=2,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def _mock_twilio_service(monkeypatch, sid="SM_TEST_1", status="sent"):
    captured = {"count": 0}

    class DummyTwilio:
        async def send_sms(self, to, body, from_number=None, status_callback=None):
            captured["count"] += 1
            captured["to"] = to
            captured["body"] = body
            captured["from_number"] = from_number
            captured["status_callback"] = status_callback
            return {"sid": sid, "status": status}

    monkeypatch.setattr("app.services.call_text_back_service.get_twilio_service", lambda: DummyTwilio())
    return captured


def _sms_usage_total(db, account_id) -> int:
    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == account_id,
            UsageRecord.usage_type == "sms",
        )
        .scalar()
    )
    return int(total or 0)


def test_call_stats_success(client, db, auth_headers, test_location):
    number = _create_number(db, test_location.id)

    db.add_all(
        [
            CallLog(
                location_id=test_location.id,
                twilio_number_id=number.id,
                twilio_call_sid="CA_TEST_1",
                caller_number="+15551230001",
                call_status="no-answer",
                call_duration=0,
                sms_sent=True,
            ),
            CallLog(
                location_id=test_location.id,
                twilio_number_id=number.id,
                twilio_call_sid="CA_TEST_2",
                caller_number="+15551230002",
                call_status="completed",
                call_duration=45,
                sms_sent=False,
            ),
        ]
    )
    db.commit()

    response = client.get(f"/calls/{test_location.id}/stats", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_calls"] == 2
    assert data["missed_calls"] == 1
    assert data["answered_calls"] == 1
    assert data["text_backs_sent"] == 1
    assert data["text_back_rate"] == 100.0


def test_call_stats_blocks_other_location(client, auth_headers, other_location):
    response = client.get(f"/calls/{other_location.id}/stats", headers=auth_headers)
    assert response.status_code == 404


def test_call_settings_success(client, db, auth_headers, test_location):
    db.add(
        TwilioNumber(
            location_id=test_location.id,
            twilio_number="+15550000003",
            forward_to="+15553334444",
            missed_call_sms_enabled=True,
            sms_template="Hi from {business_name}",
        )
    )
    db.commit()

    response = client.get(f"/calls/{test_location.id}/settings", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["twilio_number"] == "+15550000003"
    assert data["forward_to"] == "+15553334444"


def test_voice_incoming_returns_forwarding_twiml(client, db, test_location):
    response = client.post(f"/webhooks/voice-incoming?location_id={test_location.id}")

    assert response.status_code == 200
    assert "<Dial" in response.text
    assert test_location.phone in response.text
    assert f"/webhooks/voice-status?location_id={test_location.id}" in response.text


def test_send_and_fetch_thread_messages_flow(client, db, auth_headers, test_location, monkeypatch):
    thread = _create_thread(db, test_location.id)
    db.add(
        SMSMessage(
            thread_id=thread.id,
            direction=MessageDirection.INBOUND,
            body="Need a callback",
            status="received",
        )
    )
    db.commit()
    captured = _mock_twilio_service(monkeypatch, sid="SM_THREAD_1", status="queued")

    send_response = client.post(
        f"/calls/{test_location.id}/threads/{thread.id}/send?body=We%20can%20help%20today",
        headers=auth_headers,
    )
    assert send_response.status_code == 200
    assert send_response.json()["success"] is True
    assert send_response.json()["status"] == "queued"
    assert captured["count"] == 1
    assert captured["to"] == thread.customer_phone

    messages_response = client.get(
        f"/calls/{test_location.id}/threads/{thread.id}",
        headers=auth_headers,
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["direction"] == "inbound"
    assert messages[1]["direction"] == "outbound"
    assert messages[1]["body"] == "We can help today"
    assert messages[1]["status"] == "queued"

    outbound = (
        db.query(SMSMessage)
        .filter(SMSMessage.thread_id == thread.id, SMSMessage.direction == MessageDirection.OUTBOUND)
        .one()
    )
    assert outbound.twilio_message_sid == "SM_THREAD_1"
    assert _sms_usage_total(db, test_location.account_id) == 1


def test_send_message_accepts_json_body(client, db, auth_headers, test_location, monkeypatch):
    thread = _create_thread(db, test_location.id)
    captured = _mock_twilio_service(monkeypatch, sid="SM_JSON_1", status="sent")

    response = client.post(
        f"/calls/{test_location.id}/threads/{thread.id}/send",
        headers=auth_headers,
        json={"body": "We can help this afternoon"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["status"] == "sent"
    assert captured["count"] == 1

    messages_response = client.get(
        f"/calls/{test_location.id}/threads/{thread.id}",
        headers=auth_headers,
    )
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    assert messages[-1]["direction"] == "outbound"
    assert messages[-1]["body"] == "We can help this afternoon"
    assert messages[-1]["status"] == "sent"

    outbound = (
        db.query(SMSMessage)
        .filter(SMSMessage.thread_id == thread.id, SMSMessage.direction == MessageDirection.OUTBOUND)
        .one()
    )
    assert outbound.twilio_message_sid == "SM_JSON_1"


def test_send_message_returns_429_when_sms_limit_is_reached(
    client, db, auth_headers, test_location, monkeypatch
):
    thread = _create_thread(db, test_location.id)
    captured = _mock_twilio_service(monkeypatch, sid="SM_SHOULD_NOT_SEND", status="sent")

    db.add(
        UsageRecord(
            account_id=test_location.account_id,
            usage_type="sms",
            date=utc_now_aware(),
            daily_count=10,
            monthly_count=10,
            last_used_at=utc_now_aware() - timedelta(minutes=5),
        )
    )
    db.commit()

    response = client.post(
        f"/calls/{test_location.id}/threads/{thread.id}/send",
        headers=auth_headers,
        json={"body": "Checking in after your missed call"},
    )

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert "Daily limit reached" in detail["message"]
    assert captured["count"] == 0
    assert db.query(SMSMessage).filter(SMSMessage.thread_id == thread.id).count() == 0
    assert _sms_usage_total(db, test_location.account_id) == 10


def test_list_threads_with_unread_only_filter(client, db, auth_headers, test_location):
    unread_thread = _create_thread(db, test_location.id, twilio_number="+15550000005")
    read_thread = SMSThread(
        location_id=test_location.id,
        customer_phone="+15550009999",
        twilio_number="+15550000006",
        unread_count=0,
    )
    db.add(read_thread)
    db.commit()

    response = client.get(
        f"/calls/{test_location.id}/threads?unread_only=true",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(unread_thread.id)


def test_mark_thread_read_success(client, db, auth_headers, test_location):
    thread = _create_thread(db, test_location.id)
    db.add(
        SMSMessage(
            thread_id=thread.id,
            direction=MessageDirection.INBOUND,
            body="Need a callback",
            status="received",
        )
    )
    db.commit()

    response = client.post(
        f"/calls/{test_location.id}/threads/{thread.id}/read",
        headers=auth_headers,
    )

    assert response.status_code == 200
    db.refresh(thread)
    assert thread.unread_count == 0


def test_update_settings_accepts_json_body(client, db, auth_headers, test_location):
    number = TwilioNumber(
        location_id=test_location.id,
        twilio_number="+15550000007",
        forward_to="+15553335555",
        missed_call_sms_enabled=True,
        sms_template="Original template",
    )
    db.add(number)
    db.commit()

    response = client.put(
        f"/calls/{test_location.id}/settings",
        headers=auth_headers,
        json={"enabled": False, "sms_template": "Updated template"},
    )

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["sms_template"] == "Updated template"

    db.refresh(number)
    assert number.missed_call_sms_enabled is False
    assert number.sms_template == "Updated template"



def test_voice_status_missed_call_triggers_text_back(client, db, test_location, monkeypatch):
    number = _create_number(db, test_location.id, twilio_number="+15559990000")
    captured = {}

    async def fake_handle_missed_call(self, location_id, caller_phone, twilio_call_sid, twilio_number_id):
        captured["location_id"] = str(location_id)
        captured["caller_phone"] = caller_phone
        captured["twilio_call_sid"] = twilio_call_sid
        captured["twilio_number_id"] = str(twilio_number_id)
        return None

    monkeypatch.setattr(
        "app.services.call_text_back_service.MissedCallTextBackService.handle_missed_call",
        fake_handle_missed_call,
    )

    response = client.post(
        f"/webhooks/voice-status?location_id={test_location.id}",
        data={
            "CallSid": "CA_MISSED_1",
            "CallStatus": "no-answer",
            "From": "+15554443333",
            "To": number.twilio_number,
            "Duration": 0,
        },
    )

    assert response.status_code == 200
    assert "<Response>" in response.text
    assert captured == {
        "location_id": str(test_location.id),
        "caller_phone": "+15554443333",
        "twilio_call_sid": "CA_MISSED_1",
        "twilio_number_id": str(number.id),
    }


def test_voice_status_answered_call_does_not_trigger_text_back(client, db, test_location, monkeypatch):
    number = _create_number(db, test_location.id, twilio_number="+15559990001")
    called = {"value": False}

    async def fake_handle_missed_call(self, location_id, caller_phone, twilio_call_sid, twilio_number_id):
        called["value"] = True
        return None

    monkeypatch.setattr(
        "app.services.call_text_back_service.MissedCallTextBackService.handle_missed_call",
        fake_handle_missed_call,
    )

    response = client.post(
        f"/webhooks/voice-status?location_id={test_location.id}",
        data={
            "CallSid": "CA_DONE_1",
            "CallStatus": "completed",
            "From": "+15554443334",
            "To": number.twilio_number,
            "Duration": 42,
        },
    )

    assert response.status_code == 200
    assert called["value"] is False


@pytest.mark.asyncio
async def test_handle_missed_call_sends_twilio_sms_and_records_usage(db, test_location, monkeypatch):
    number = _create_number(db, test_location.id, twilio_number="+15559990002")
    captured = _mock_twilio_service(monkeypatch, sid="SM_MISSED_1", status="sent")

    call_log = await get_call_text_back_service(db).handle_missed_call(
        test_location.id,
        "+15554443335",
        "CA_MISSED_REAL_1",
        number.id,
    )

    assert call_log is not None
    db.refresh(call_log)
    db.refresh(number)

    thread = db.query(SMSThread).filter(SMSThread.id == call_log.thread_id).one()
    outbound = (
        db.query(SMSMessage)
        .filter(SMSMessage.thread_id == thread.id, SMSMessage.direction == MessageDirection.OUTBOUND)
        .one()
    )

    assert captured["count"] == 1
    assert captured["to"] == "+15554443335"
    assert captured["from_number"] == number.twilio_number
    assert call_log.sms_sent is True
    assert call_log.sms_message_sid == "SM_MISSED_1"
    assert call_log.thread_id == thread.id
    assert number.sms_sent == 1
    assert thread.last_message_at is not None
    assert outbound.status == "sent"
    assert outbound.twilio_message_sid == "SM_MISSED_1"
    assert _sms_usage_total(db, test_location.account_id) == 1


@pytest.mark.asyncio
async def test_handle_missed_call_notifies_when_sms_limit_blocks_text_back(db, test_location, monkeypatch):
    number = _create_number(db, test_location.id, twilio_number="+15559990012")

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    db.add(
        UsageRecord(
            account_id=test_location.account_id,
            usage_type="sms",
            date=utc_now_aware(),
            daily_count=10,
            monthly_count=10,
            last_used_at=utc_now_aware() - timedelta(minutes=5),
        )
    )
    db.commit()

    call_log = await get_call_text_back_service(db).handle_missed_call(
        test_location.id,
        "+15554443336",
        "CA_MISSED_LIMIT_1",
        number.id,
    )

    assert call_log is not None
    db.refresh(call_log)
    assert call_log.sms_sent is False
    assert call_log.sms_message_sid is None
    assert _sms_usage_total(db, test_location.account_id) == 10

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_location.account_id,
            NotificationEvent.type == "missed_call_text_back_skipped",
        )
        .one()
    )
    assert "Missed call text-back skipped" in event.title
    assert "Daily limit reached" in event.body
    assert event.url == "/dashboard/calls"

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_handle_missed_call_notifies_when_twilio_send_fails(db, test_location, monkeypatch):
    number = _create_number(db, test_location.id, twilio_number="+15559990013")

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    class FailingTwilio:
        async def send_sms(self, to, body, from_number=None, status_callback=None):
            raise TwilioUnavailableError("Twilio credentials are missing")

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)
    monkeypatch.setattr("app.services.call_text_back_service.get_twilio_service", lambda: FailingTwilio())

    call_log = await get_call_text_back_service(db).handle_missed_call(
        test_location.id,
        "+15554443337",
        "CA_MISSED_FAIL_1",
        number.id,
    )

    assert call_log is not None
    db.refresh(call_log)
    assert call_log.sms_sent is False
    assert call_log.sms_message_sid is None
    assert _sms_usage_total(db, test_location.account_id) == 0

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_location.account_id,
            NotificationEvent.type == "missed_call_text_back_failed",
        )
        .one()
    )
    assert "Missed call text-back failed" in event.title
    assert "Twilio credentials are missing" in event.body
    assert event.url == "/dashboard/calls"

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"

def test_twilio_sms_incoming_stores_inbound_message(client, db, test_location):
    number = _create_number(db, test_location.id, twilio_number="+15558889999")

    response = client.post(
        "/webhooks/twilio/sms-incoming",
        data={
            "From": "+15557776666",
            "To": number.twilio_number,
            "Body": "Can you call me back?",
            "MessageSid": "SM_INBOUND_1",
        },
    )

    assert response.status_code == 200
    assert "<Response>" in response.text

    thread = db.query(SMSThread).filter(SMSThread.location_id == test_location.id).first()
    assert thread is not None
    assert thread.customer_phone == "+15557776666"
    assert thread.unread_count == 1

    message = db.query(SMSMessage).filter(SMSMessage.thread_id == thread.id).first()
    assert message is not None
    assert message.direction.value == "inbound"
    assert message.body == "Can you call me back?"
    assert message.twilio_message_sid == "SM_INBOUND_1"


def test_twilio_sms_incoming_optout_returns_confirmation(client, db, test_location, monkeypatch):
    _create_number(db, test_location.id, twilio_number="+15558889999")

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    response = client.post(
        "/webhooks/twilio/sms-incoming",
        data={
            "From": "+15557776666",
            "To": "+15558889999",
            "Body": "STOP",
            "MessageSid": "SM_STOP_1",
        },
    )

    assert response.status_code == 200
    assert "<Message>" in response.text
    assert "</Message>" in response.text

    optout = db.query(ReviewOptout).filter(ReviewOptout.location_id == test_location.id).one()
    assert optout.phone == "+15557776666"
    assert optout.reason == "sms_stop_webhook"

    notification = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_location.account_id)
        .one()
    )
    assert notification.type == "sms_optout_received"
    assert notification.url == "/dashboard/reviews"
    assert "replied STOP" in notification.body


def test_twilio_sms_status_callback_invokes_job_handler(client, monkeypatch):
    captured = {}

    async def fake_handle_sms_status_callback(request_id, message_sid, status):
        captured["request_id"] = str(request_id)
        captured["message_sid"] = message_sid
        captured["status"] = status

    fake_module = ModuleType("app.jobs.review_booster_jobs")
    fake_module.handle_sms_status_callback = fake_handle_sms_status_callback
    monkeypatch.setitem(sys.modules, "app.jobs.review_booster_jobs", fake_module)

    request_id = "11111111-1111-1111-1111-111111111111"
    response = client.post(
        f"/webhooks/twilio/sms-status?request_id={request_id}",
        data={
            "MessageSid": "SM_STATUS_1",
            "MessageStatus": "delivered",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "received"}
    assert captured == {
        "request_id": request_id,
        "message_sid": "SM_STATUS_1",
        "status": "delivered",
    }
