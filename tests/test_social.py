"""Tests for social response logging and billing plan wording."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.credits import UsageRecord
from app.models.social_response import SocialResponseLog, SocialResponseMode
from app.core.time import utc_now_aware
from app.services.social_responder import AutoResponse, SocialMessage, ResponseType


def _add_instagram_channel(db: Session, test_location) -> Channel:
    channel = Channel(
        id=uuid4(),
        location_id=test_location.id,
        type=ChannelType.INSTAGRAM,
        status=ChannelStatus.CONNECTED,
        is_active=True,
        access_token_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    channel.set_credentials({"access_token": "ig-token"})
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def _usage_total(db: Session, account_id, usage_type: str) -> int:
    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(UsageRecord.account_id == account_id, UsageRecord.usage_type == usage_type)
        .scalar()
    )
    return int(total or 0)


def _same_utc_day_usage_timestamp() -> datetime:
    """Return a stable in-day UTC timestamp so limit tests do not flap around midnight."""
    return utc_now_aware().replace(hour=12, minute=0, second=0, microsecond=0)


class TestSocialLogging:
    def test_manual_response_creates_audit_log(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_instagram_channel(db, test_location)

        async def fake_send_response(self, message, response_text):
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=datetime.now(UTC),
                success=True,
            )

        monkeypatch.setattr(
            "app.services.social_responder.SocialResponderService.send_response",
            fake_send_response,
        )

        response = client.post(
            f"/social/{test_location.id}/respond",
            headers=auth_headers,
            json={
                "message_id": "msg-1",
                "response_text": "Thanks for reaching out.",
                "sender_id": "user-1",
                "sender_name": "customer",
                "message_text": "Do you take walk-ins?",
                "message_type": "dm",
                "platform": "instagram",
                "message_created_at": datetime.now(UTC).isoformat(),
            },
        )

        assert response.status_code == 200
        logs = db.query(SocialResponseLog).filter(SocialResponseLog.location_id == test_location.id).all()
        assert len(logs) == 1
        assert logs[0].response_mode.value == "manual"
        assert logs[0].success is True
        assert logs[0].source_message == "Do you take walk-ins?"
        assert logs[0].sentiment == "neutral"

    def test_manual_response_uses_heuristic_sentiment_without_hidden_ai_usage(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_instagram_channel(db, test_location)

        async def fake_send_response(self, message, response_text):
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=datetime.now(UTC),
                success=True,
            )

        async def should_not_classify_with_ai(self, message):
            raise AssertionError("manual social respond should not call classify_sentiment_model")

        monkeypatch.setattr(
            "app.services.social_responder.SocialResponderService.send_response",
            fake_send_response,
        )
        monkeypatch.setattr(
            "app.services.social_responder.SocialResponderService.classify_sentiment_model",
            should_not_classify_with_ai,
        )

        response = client.post(
            f"/social/{test_location.id}/respond",
            headers=auth_headers,
            json={
                "message_id": "msg-heuristic",
                "response_text": "We're sorry to hear that.",
                "sender_id": "user-2",
                "sender_name": "customer",
                "message_text": "I have a problem with my order",
                "message_type": "dm",
                "platform": "instagram",
                "message_created_at": datetime.now(UTC).isoformat(),
            },
        )

        assert response.status_code == 200
        logs = db.query(SocialResponseLog).filter(SocialResponseLog.location_id == test_location.id).all()
        assert len(logs) == 1
        assert logs[0].sentiment == "negative"
        assert _usage_total(db, test_location.account_id, "ai_response") == 0

    def test_auto_respond_logs_and_stats_use_db_data(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_instagram_channel(db, test_location)
        created_at = datetime.now(UTC) - timedelta(minutes=10)

        async def fake_get_pending_messages(self, location_id, platform="instagram", limit=20):
            return [
                SocialMessage(
                    id="msg-2",
                    platform="instagram",
                    type=ResponseType.DM,
                    sender_id="user-2",
                    sender_name="lead",
                    message="Can I book for tomorrow?",
                    created_at=created_at,
                )
            ]

        async def fake_generate_response(self, message, business_name, business_info):
            return "Yes, we can help with that."

        async def fake_send_response(self, message, response_text):
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=created_at + timedelta(minutes=4),
                success=True,
            )

        monkeypatch.setattr("app.services.social_responder.SocialResponderService.get_pending_messages", fake_get_pending_messages)
        monkeypatch.setattr("app.services.social_responder.SocialResponderService.generate_response", fake_generate_response)
        monkeypatch.setattr("app.services.social_responder.SocialResponderService.send_response", fake_send_response)

        auto_response = client.post(f"/social/{test_location.id}/auto-respond", headers=auth_headers)
        assert auto_response.status_code == 200
        assert auto_response.json()["success_count"] == 1
        assert _usage_total(db, test_location.account_id, "ai_response") == 1

        history = client.get(f"/social/{test_location.id}/history", headers=auth_headers)
        assert history.status_code == 200
        assert history.json()["total"] == 1
        assert history.json()["items"][0]["response_mode"] == "auto"

        stats = client.get(f"/social/{test_location.id}/stats", headers=auth_headers)
        assert stats.status_code == 200
        data = stats.json()
        assert data["total_messages"] == 1
        assert data["auto_responded"] == 1
        assert data["manual_responses"] == 0
        assert data["avg_response_time_minutes"] == 4.0
        assert data["response_rate"] == 100.0
        assert data["sentiment_neutral"] == 1

        filtered_history = client.get(
            f"/social/{test_location.id}/history",
            headers=auth_headers,
            params={"mode": "auto", "sentiment": "neutral", "search": "book"},
        )
        assert filtered_history.status_code == 200
        assert filtered_history.json()["total"] == 1
        assert filtered_history.json()["limit"] == 50
        assert filtered_history.json()["offset"] == 0

    def test_generate_response_records_ai_response_usage_on_success(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        async def fake_generate_response(self, message, business_name, business_info):
            return "Thanks for reaching out. We can help with that."

        monkeypatch.setattr("app.services.social_responder.SocialResponderService.generate_response", fake_generate_response)

        response = client.post(
            f"/social/{test_location.id}/generate-response",
            headers=auth_headers,
            json={"message_text": "Do you offer weekend appointments?", "message_type": "dm"},
        )

        assert response.status_code == 200
        assert response.json()["suggested_response"] == "Thanks for reaching out. We can help with that."
        assert _usage_total(db, test_location.account_id, "ai_response") == 1

    def test_generate_response_returns_429_when_ai_response_limit_is_reached(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        db.add(
            UsageRecord(
                account_id=test_location.account_id,
                usage_type="ai_response",
                date=_same_utc_day_usage_timestamp(),
                daily_count=10,
                monthly_count=10,
            )
        )
        db.commit()

        llm_called = {"value": False}

        async def fake_generate_response(self, message, business_name, business_info):
            llm_called["value"] = True
            return "Should not be returned"

        monkeypatch.setattr("app.services.social_responder.SocialResponderService.generate_response", fake_generate_response)

        response = client.post(
            f"/social/{test_location.id}/generate-response",
            headers=auth_headers,
            json={"message_text": "Can I book today?", "message_type": "dm"},
        )

        assert response.status_code == 429
        assert llm_called["value"] is False
        assert _usage_total(db, test_location.account_id, "ai_response") == 10

    def test_generate_response_fallback_does_not_record_ai_response_usage(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        async def fail_generate(_self, _prompt: str):
            raise RuntimeError("provider unavailable")

        monkeypatch.setattr("app.integrations.llm.LLMAdapter.generate", fail_generate)

        response = client.post(
            f"/social/{test_location.id}/generate-response",
            headers=auth_headers,
            json={"message_text": "How do I book an appointment?", "message_type": "dm"},
        )

        assert response.status_code == 200
        assert "call" in response.json()["suggested_response"].lower()
        assert _usage_total(db, test_location.account_id, "ai_response") == 0

    def test_social_stats_include_failure_and_health_signals(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        _add_instagram_channel(db, test_location)
        client.put(
            f"/social/{test_location.id}/settings",
            headers=auth_headers,
            json={
                "auto_respond_enabled": True,
                "auto_respond_dms": True,
                "auto_respond_comments": False,
                "response_delay_seconds": 0,
                "excluded_keywords": [],
            },
        )

        now = datetime.now(UTC)
        db.add(
            SocialResponseLog(
                location_id=test_location.id,
                platform="instagram",
                message_type="dm",
                response_mode=SocialResponseMode.MANUAL,
                message_id="success-1",
                response_text="Thanks for reaching out.",
                success=True,
                responded_at=now - timedelta(minutes=3),
            )
        )
        db.add(
            SocialResponseLog(
                location_id=test_location.id,
                platform="instagram",
                message_type="comment",
                response_mode=SocialResponseMode.AUTO,
                message_id="failed-1",
                response_text="Draft response",
                success=False,
                error_message="rate limit",
                responded_at=now - timedelta(minutes=1),
            )
        )
        db.commit()

        stats = client.get(f"/social/{test_location.id}/stats", headers=auth_headers)
        assert stats.status_code == 200
        payload = stats.json()
        assert payload["failed_responses"] == 1
        assert payload["automation_health"] == "ready"
        assert payload["last_successful_response_at"] is not None
        assert payload["last_failed_response_at"] is not None

    def test_settings_are_persisted(
        self,
        client: TestClient,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        update_response = client.put(
            f"/social/{test_location.id}/settings",
            headers=auth_headers,
            json={
                "auto_respond_enabled": True,
                "auto_respond_dms": False,
                "auto_respond_comments": True,
                "response_delay_seconds": 120,
                "excluded_keywords": ["refund", "angry"],
                "high_priority_alerts_enabled": True,
                "high_priority_alert_channel": "email",
            },
        )
        assert update_response.status_code == 200

        get_response = client.get(f"/social/{test_location.id}/settings", headers=auth_headers)
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["auto_respond_dms"] is False
        assert data["auto_respond_comments"] is True
        assert data["response_delay_seconds"] == 120
        assert data["excluded_keywords"] == ["refund", "angry"]
        assert data["high_priority_alerts_enabled"] is True
        assert data["high_priority_alert_channel"] == "email"

    def test_auto_respond_respects_delay_and_excluded_keywords(
        self,
        client: TestClient,
        test_location,
        auth_headers: dict[str, str],
        db: Session,
        monkeypatch,
    ) -> None:
        _add_instagram_channel(db, test_location)
        client.put(
            f"/social/{test_location.id}/settings",
            headers=auth_headers,
            json={
                "auto_respond_enabled": True,
                "auto_respond_dms": True,
                "auto_respond_comments": False,
                "response_delay_seconds": 300,
                "excluded_keywords": ["refund"],
            },
        )

        async def fake_get_pending_messages(self, location_id, platform="instagram", limit=20):
            now = datetime.now(UTC)
            return [
                SocialMessage(
                    id="recent-msg",
                    platform="instagram",
                    type=ResponseType.DM,
                    sender_id="u1",
                    sender_name="recent",
                    message="hello there",
                    created_at=now - timedelta(seconds=30),
                ),
                SocialMessage(
                    id="refund-msg",
                    platform="instagram",
                    type=ResponseType.DM,
                    sender_id="u2",
                    sender_name="refund",
                    message="I want a refund",
                    created_at=now - timedelta(minutes=10),
                ),
                SocialMessage(
                    id="ok-msg",
                    platform="instagram",
                    type=ResponseType.DM,
                    sender_id="u3",
                    sender_name="ok",
                    message="Can I book today?",
                    created_at=now - timedelta(minutes=10),
                ),
            ]

        async def fake_generate_response(self, message, business_name, business_info):
            return "Handled"

        async def fake_send_response(self, message, response_text):
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=datetime.now(UTC),
                success=True,
            )

        async def fake_sentiment(self, message):
            return "neutral"

        monkeypatch.setattr("app.services.social_responder.SocialResponderService.get_pending_messages", fake_get_pending_messages)
        monkeypatch.setattr("app.services.social_responder.SocialResponderService.generate_response", fake_generate_response)
        monkeypatch.setattr("app.services.social_responder.SocialResponderService.send_response", fake_send_response)
        monkeypatch.setattr("app.services.social_responder.SocialResponderService.classify_sentiment_model", fake_sentiment)

        response = client.post(f"/social/{test_location.id}/auto-respond", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total_processed"] == 3
        assert data["success_count"] == 1
        assert data["skipped_count"] == 2
        assert data["skipped_excluded_keywords"] == 1
        assert data["skipped_too_recent"] == 1

    def test_pending_messages_are_triaged_and_history_paginates(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_instagram_channel(db, test_location)

        async def fake_get_pending_messages(self, location_id, platform="instagram", limit=20):
            now = datetime.now(UTC)
            return [
                SocialMessage(
                    id="low-msg",
                    platform="instagram",
                    type=ResponseType.DM,
                    sender_id="u1",
                    sender_name="keyword",
                    message="refund please",
                    created_at=now - timedelta(minutes=5),
                ),
                SocialMessage(
                    id="high-msg",
                    platform="instagram",
                    type=ResponseType.COMMENT,
                    sender_id="u2",
                    sender_name="angry",
                    message="This is terrible",
                    created_at=now - timedelta(minutes=10),
                ),
                SocialMessage(
                    id="medium-msg",
                    platform="instagram",
                    type=ResponseType.DM,
                    sender_id="u3",
                    sender_name="buyer",
                    message="Can I book today?",
                    created_at=now - timedelta(minutes=1),
                ),
            ]

        monkeypatch.setattr("app.services.social_responder.SocialResponderService.get_pending_messages", fake_get_pending_messages)

        client.put(
            f"/social/{test_location.id}/settings",
            headers=auth_headers,
            json={"excluded_keywords": ["refund"]},
        )

        response = client.get(f"/social/{test_location.id}/messages", headers=auth_headers)
        assert response.status_code == 200
        messages = response.json()["messages"]
        assert messages[0]["triage_priority"] == "high"
        assert messages[1]["triage_priority"] == "medium"
        assert messages[2]["triage_priority"] == "low"
        assert all(message.get("suggested_response") is None for message in messages)

        # Seed two logs for paging
        db.add(
            SocialResponseLog(
                location_id=test_location.id,
                platform="instagram",
                message_type="dm",
                response_mode=SocialResponseMode.MANUAL,
                message_id="h1",
                response_text="one",
                success=True,
                responded_at=datetime.now(UTC),
            )
        )
        db.add(
            SocialResponseLog(
                location_id=test_location.id,
                platform="instagram",
                message_type="dm",
                response_mode=SocialResponseMode.MANUAL,
                message_id="h2",
                response_text="two",
                success=True,
                responded_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        db.commit()

        history_page = client.get(
            f"/social/{test_location.id}/history",
            headers=auth_headers,
            params={"limit": 1, "offset": 1},
        )
        assert history_page.status_code == 200
        payload = history_page.json()
        assert payload["total"] >= 2
        assert payload["limit"] == 1
        assert payload["offset"] == 1
        assert len(payload["items"]) == 1

    def test_pending_messages_do_not_generate_ai_suggestions_implicitly(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_instagram_channel(db, test_location)

        async def fake_get_pending_messages(self, location_id, platform="instagram", limit=20):
            return [
                SocialMessage(
                    id="msg-no-ai",
                    platform="instagram",
                    type=ResponseType.DM,
                    sender_id="u1",
                    sender_name="lead",
                    message="Can you tell me your pricing?",
                    created_at=datetime.now(UTC) - timedelta(minutes=5),
                )
            ]

        async def should_not_generate(self, message, business_name, business_info):
            raise AssertionError("get_messages should not call generate_response")

        monkeypatch.setattr("app.services.social_responder.SocialResponderService.get_pending_messages", fake_get_pending_messages)
        monkeypatch.setattr("app.services.social_responder.SocialResponderService.generate_response", should_not_generate)

        response = client.get(f"/social/{test_location.id}/messages", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["messages"][0]["suggested_response"] is None

    def test_social_routes_require_connected_instagram_for_send(
        self,
        client: TestClient,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        response = client.post(
            f"/social/{test_location.id}/respond",
            headers=auth_headers,
            json={"message_id": "msg-3", "response_text": "Hello"},
        )
        assert response.status_code == 409

    async def test_social_responder_without_instagram_client_fails_honestly(self) -> None:
        from app.services.social_responder import SocialResponderService

        service = SocialResponderService()
        result = await service.send_response(
            SocialMessage(
                id="msg-no-client",
                platform="instagram",
                type=ResponseType.DM,
                sender_id="sender-1",
                sender_name="customer",
                message="hello",
            ),
            "Hi there.",
        )

        assert result.success is False
        assert result.error_message == "Instagram is not connected"

    def test_manual_response_logs_gateway_failure_detail(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_instagram_channel(db, test_location)

        async def fake_send_response(self, message, response_text):
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=datetime.now(UTC),
                success=False,
                error_message="Instagram rate limit exceeded",
            )

        monkeypatch.setattr(
            "app.services.social_responder.SocialResponderService.send_response",
            fake_send_response,
        )

        response = client.post(
            f"/social/{test_location.id}/respond",
            headers=auth_headers,
            json={
                "message_id": "msg-failure-detail",
                "response_text": "Thanks for reaching out.",
                "sender_id": "user-1",
                "sender_name": "customer",
                "message_text": "hello",
                "message_type": "dm",
                "platform": "instagram",
                "message_created_at": datetime.now(UTC).isoformat(),
            },
        )

        assert response.status_code == 200
        assert response.json()["success"] is False
        assert response.json()["message"] == "Instagram rate limit exceeded"
        log = db.query(SocialResponseLog).filter(
            SocialResponseLog.message_id == "msg-failure-detail"
        ).one()
        assert log.success is False
        assert log.error_message == "Instagram rate limit exceeded"

    def test_history_export_returns_csv(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        db.add(
            SocialResponseLog(
                location_id=test_location.id,
                platform="instagram",
                message_type="dm",
                response_mode=SocialResponseMode.MANUAL,
                message_id="csv-1",
                sender_name="Casey",
                source_message="Need help",
                response_text="We can help.",
                success=True,
                sentiment="neutral",
                responded_at=datetime.now(UTC),
            )
        )
        db.commit()

        response = client.get(f"/social/{test_location.id}/history/export", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment; filename=" in response.headers["content-disposition"]
        body = response.text
        assert "sender_name" in body
        assert "Casey" in body
        assert "We can help." in body

    def test_auto_respond_sends_high_priority_alert(
        self,
        client: TestClient,
        test_location,
        auth_headers: dict[str, str],
        db: Session,
        monkeypatch,
    ) -> None:
        _add_instagram_channel(db, test_location)
        client.put(
            f"/social/{test_location.id}/settings",
            headers=auth_headers,
            json={
                "auto_respond_enabled": True,
                "auto_respond_dms": True,
                "auto_respond_comments": True,
                "response_delay_seconds": 0,
                "excluded_keywords": [],
                "high_priority_alerts_enabled": True,
                "high_priority_alert_channel": "email",
            },
        )

        async def fake_get_pending_messages(self, location_id, platform="instagram", limit=20):
            now = datetime.now(UTC)
            return [
                SocialMessage(
                    id="angry-comment",
                    platform="instagram",
                    type=ResponseType.COMMENT,
                    sender_id="u1",
                    sender_name="angry_customer",
                    message="This is terrible and I want a refund",
                    created_at=now - timedelta(minutes=15),
                )
            ]

        async def fake_generate_response(self, message, business_name, business_info):
            return "We are sorry to hear that. Please send us a DM so we can help."

        async def fake_send_response(self, message, response_text):
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=datetime.now(UTC),
                success=True,
            )

        captured = {}

        async def fake_send_notification(self, account_id, title, message, notification_type, data=None, channel_override=None):
            captured["title"] = title
            captured["message"] = message
            captured["type"] = notification_type
            captured["channel_override"] = channel_override
            captured["data"] = data or {}
            return {"success": True}

        monkeypatch.setattr("app.services.social_responder.SocialResponderService.get_pending_messages", fake_get_pending_messages)
        monkeypatch.setattr("app.services.social_responder.SocialResponderService.generate_response", fake_generate_response)
        monkeypatch.setattr("app.services.social_responder.SocialResponderService.send_response", fake_send_response)
        monkeypatch.setattr("app.services.notification.NotificationService.send_notification", fake_send_notification)

        response = client.post(f"/social/{test_location.id}/auto-respond", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["high_priority_count"] == 1
        assert data["alerted_high_priority_count"] == 1
        assert captured["type"] == "social_high_priority_alert"
        assert captured["channel_override"] == "email"
        assert captured["data"]["count"] == 1

    def test_auto_respond_stops_when_ai_response_limit_is_reached_mid_run(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_instagram_channel(db, test_location)
        db.add(
            UsageRecord(
                account_id=test_location.account_id,
                usage_type="ai_response",
                date=_same_utc_day_usage_timestamp(),
                daily_count=9,
                monthly_count=9,
            )
        )
        db.commit()

        async def fake_get_pending_messages(self, location_id, platform="instagram", limit=20):
            now = datetime.now(UTC)
            return [
                SocialMessage(
                    id="msg-1",
                    platform="instagram",
                    type=ResponseType.DM,
                    sender_id="user-1",
                    sender_name="first",
                    message="Can I book an appointment?",
                    created_at=now - timedelta(minutes=10),
                ),
                SocialMessage(
                    id="msg-2",
                    platform="instagram",
                    type=ResponseType.DM,
                    sender_id="user-2",
                    sender_name="second",
                    message="Do you have pricing info?",
                    created_at=now - timedelta(minutes=9),
                ),
            ]

        generated_messages: list[str] = []

        async def fake_generate_response(self, message, business_name, business_info):
            generated_messages.append(message.id)
            return f"Reply for {message.id}"

        async def fake_send_response(self, message, response_text):
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=datetime.now(UTC),
                success=True,
            )

        monkeypatch.setattr("app.services.social_responder.SocialResponderService.get_pending_messages", fake_get_pending_messages)
        monkeypatch.setattr("app.services.social_responder.SocialResponderService.generate_response", fake_generate_response)
        monkeypatch.setattr("app.services.social_responder.SocialResponderService.send_response", fake_send_response)

        response = client.post(f"/social/{test_location.id}/auto-respond", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["success_count"] == 1
        assert payload["failed_count"] == 0
        assert payload["rate_limited_count"] == 1
        assert payload["rate_limit_detail"]["error"] == "Rate limit exceeded"
        assert generated_messages == ["msg-1"]
        assert _usage_total(db, test_location.account_id, "ai_response") == 10

    def test_auto_respond_fallback_template_does_not_record_ai_response_usage(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_instagram_channel(db, test_location)
        created_at = datetime.now(UTC) - timedelta(minutes=10)

        async def fake_get_pending_messages(self, location_id, platform="instagram", limit=20):
            return [
                SocialMessage(
                    id="msg-fallback",
                    platform="instagram",
                    type=ResponseType.DM,
                    sender_id="user-1",
                    sender_name="lead",
                    message="Can I book for tomorrow?",
                    created_at=created_at,
                )
            ]

        async def fail_generate(_self, _prompt: str):
            raise RuntimeError("provider unavailable")

        async def fake_send_response(self, message, response_text):
            return AutoResponse(
                message_id=message.id,
                response_text=response_text,
                sent_at=datetime.now(UTC),
                success=True,
            )

        monkeypatch.setattr(
            "app.services.social_responder.SocialResponderService.get_pending_messages",
            fake_get_pending_messages,
        )
        monkeypatch.setattr("app.integrations.llm.LLMAdapter.generate", fail_generate)
        monkeypatch.setattr(
            "app.services.social_responder.SocialResponderService.send_response",
            fake_send_response,
        )

        response = client.post(f"/social/{test_location.id}/auto-respond", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["success_count"] == 1
        assert payload["failed_count"] == 0
        assert _usage_total(db, test_location.account_id, "ai_response") == 0


class TestBillingPlanWording:
    def test_get_plans_uses_safe_beta_wording(self, client: TestClient) -> None:
        response = client.get("/billing/plans?catalog=legacy")
        assert response.status_code == 200

        data = response.json()
        pro = next(plan for plan in data if plan["id"] == "pro")
        premium = next(plan for plan in data if plan["id"] == "premium")

        assert "Instagram Publishing Tools (Beta)" in pro["features"]
        assert "Q&A Response Drafts (Beta)" in pro["features"]
        assert "Website SEO Tools (Beta)" in pro["features"]
        assert "Advanced Response Automation (Beta)" in premium["features"]
