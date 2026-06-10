"""Tests for Q&A draft stabilization."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.credits import UsageRecord
from app.models.qa import QADraft, QADraftStatus, QAFeedbackRating
from app.core.time import utc_now_aware


def _add_gbp_channel(db: Session, test_location) -> Channel:
    channel = Channel(
        id=uuid4(),
        location_id=test_location.id,
        type=ChannelType.GBP,
        status=ChannelStatus.CONNECTED,
        is_active=True,
        access_token_expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    channel.set_credentials({"access_token": "gbp-token"})
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


class TestQARoutes:
    def test_list_questions_requires_connected_gbp(
        self,
        client: TestClient,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        response = client.get(f"/qa/{test_location.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["integration_status"] == "needs_gbp_connection"
        assert data["questions"] == []
        assert data["pending_count"] == 0

    def test_list_questions_uses_real_questions_and_upserts_drafts(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_gbp_channel(db, test_location)
        test_location.gbp_location_id = "locations/123"
        db.commit()

        async def fake_get_questions(self, location_id=None):
            assert location_id == "locations/123"
            return {
                "questions": [
                    {
                        "name": "locations/123/questions/1",
                        "text": "Do you accept walk-ins?",
                        "createTime": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        "author": {"displayName": "Alex"},
                    }
                ]
            }

        monkeypatch.setattr("app.integrations.gbp.GBPClient.get_questions", fake_get_questions)

        response = client.get(f"/qa/{test_location.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["integration_status"] == "ok"
        assert data["total"] == 1
        assert data["pending_count"] == 1
        assert data["questions"][0]["question_text"] == "Do you accept walk-ins?"
        assert data["questions"][0]["draft_status"] == "pending"

        draft = db.query(QADraft).filter(QADraft.location_id == test_location.id).one()
        assert draft.question_id == "locations/123/questions/1"
        assert draft.draft_status == QADraftStatus.PENDING

    def test_generate_answer_persists_draft(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        async def fake_generate(self, prompt: str) -> str:
            assert "Test Business" in prompt
            return "Yes, we accept walk-ins during business hours."

        monkeypatch.setattr("app.integrations.llm.LLMAdapter.generate", fake_generate)

        response = client.post(
            f"/qa/{test_location.id}/generate-answer",
            headers=auth_headers,
            json={
                "question_id": "locations/123/questions/2",
                "question_text": "Do you accept walk-ins?",
                "author_name": "Taylor",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["suggested_answer"] == "Yes, we accept walk-ins during business hours."
        assert data["draft_status"] == "draft"

        draft = db.query(QADraft).filter(QADraft.location_id == test_location.id).one()
        assert str(draft.id) == data["draft_id"]
        assert draft.draft_status == QADraftStatus.DRAFT
        assert draft.suggested_answer == "Yes, we accept walk-ins during business hours."
        assert _usage_total(db, test_location.account_id, "ai_response") == 1

    def test_generate_answer_returns_429_when_ai_response_limit_is_reached(
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

        async def fake_generate(self, prompt: str) -> str:
            llm_called["value"] = True
            return "Should not be returned"

        monkeypatch.setattr("app.integrations.llm.LLMAdapter.generate", fake_generate)

        response = client.post(
            f"/qa/{test_location.id}/generate-answer",
            headers=auth_headers,
            json={
                "question_id": "locations/123/questions/limit",
                "question_text": "Do you accept walk-ins?",
                "author_name": "Taylor",
            },
        )

        assert response.status_code == 429
        assert llm_called["value"] is False
        assert _usage_total(db, test_location.account_id, "ai_response") == 10

    def test_generate_answer_fallback_does_not_record_ai_response_usage(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        async def fake_generate(self, prompt: str) -> str:
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr("app.integrations.llm.LLMAdapter.generate", fake_generate)

        response = client.post(
            f"/qa/{test_location.id}/generate-answer",
            headers=auth_headers,
            json={
                "question_id": "locations/123/questions/fallback",
                "question_text": "What are your hours?",
                "author_name": "Jordan",
            },
        )

        assert response.status_code == 200
        assert "hours" in response.json()["suggested_answer"].lower()
        assert _usage_total(db, test_location.account_id, "ai_response") == 0

    def test_post_answer_updates_draft_to_posted(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_gbp_channel(db, test_location)
        test_location.gbp_location_id = "locations/123"
        draft = QADraft(
            id=uuid4(),
            location_id=test_location.id,
            question_id="locations/123/questions/3",
            question_text="Can I book online?",
            suggested_answer="Yes, online booking is available.",
            draft_status=QADraftStatus.DRAFT,
        )
        db.add(draft)
        db.commit()

        async def fake_answer_question(self, location_id, question_id, answer_text):
            assert location_id == "locations/123"
            assert question_id == "locations/123/questions/3"
            assert answer_text == "Yes, online booking is available."
            return {"success": True}

        monkeypatch.setattr("app.integrations.gbp.GBPClient.answer_question", fake_answer_question)

        response = client.post(
            f"/qa/{test_location.id}/answer",
            headers=auth_headers,
            json={
                "question_id": "locations/123/questions/3",
                "draft_id": str(draft.id),
                "answer_text": "Yes, online booking is available.",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["draft_status"] == "posted"

        db.refresh(draft)
        assert draft.draft_status == QADraftStatus.POSTED
        assert draft.posted_answer == "Yes, online booking is available."
        assert draft.answered_at is not None

    def test_draft_history_supports_status_and_search_filters(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        draft_ok = QADraft(
            id=uuid4(),
            location_id=test_location.id,
            question_id="q-ok",
            question_text="Do you take walk-ins?",
            suggested_answer="Yes, we do.",
            draft_status=QADraftStatus.DRAFT,
        )
        draft_failed = QADraft(
            id=uuid4(),
            location_id=test_location.id,
            question_id="q-failed",
            question_text="Can I bring my dog?",
            suggested_answer="Please call first.",
            last_error="GBP posting failed",
            draft_status=QADraftStatus.FAILED,
        )
        db.add_all([draft_ok, draft_failed])
        db.commit()

        response = client.get(
            f"/qa/{test_location.id}/drafts",
            headers=auth_headers,
            params={"status_filter": "failed", "search": "dog", "limit": 1, "offset": 0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["limit"] == 1
        assert data["offset"] == 0
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(draft_failed.id)
        assert data["items"][0]["draft_status"] == "failed"
        assert data["items"][0]["updated_at"] is not None

    def test_other_account_cannot_access_qa(
        self,
        client: TestClient,
        other_location,
        auth_headers: dict[str, str],
    ) -> None:
        response = client.get(f"/qa/{other_location.id}", headers=auth_headers)
        assert response.status_code == 404

    def test_gbp_channel_health_includes_qa_counts(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        _add_gbp_channel(db, test_location)
        db.add_all(
            [
                QADraft(
                    id=uuid4(),
                    location_id=test_location.id,
                    question_id="q1",
                    question_text="One",
                    draft_status=QADraftStatus.DRAFT,
                    feedback_rating=QAFeedbackRating.GOOD,
                ),
                QADraft(
                    id=uuid4(),
                    location_id=test_location.id,
                    question_id="q2",
                    question_text="Two",
                    draft_status=QADraftStatus.FAILED,
                    last_error="failed",
                    feedback_rating=QAFeedbackRating.WRONG,
                ),
                QADraft(
                    id=uuid4(),
                    location_id=test_location.id,
                    question_id="q3",
                    question_text="Three",
                    draft_status=QADraftStatus.POSTED,
                    answered_at=datetime.now(UTC),
                    feedback_rating=QAFeedbackRating.NEEDS_EDIT,
                ),
            ]
        )
        db.commit()

        response = client.get(f"/locations/{test_location.id}/channels", headers=auth_headers)
        assert response.status_code == 200
        channels = response.json()
        gbp_channel = next(channel for channel in channels if channel["type"] == "GBP")
        assert gbp_channel["qa_pending_count"] == 1
        assert gbp_channel["qa_failed_count"] == 1
        assert gbp_channel["qa_posted_count"] == 1
        assert gbp_channel["qa_feedback_good_count"] == 1
        assert gbp_channel["qa_feedback_needs_edit_count"] == 1
        assert gbp_channel["qa_feedback_wrong_count"] == 1

    def test_question_fetch_updates_sync_diagnostics(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        channel = _add_gbp_channel(db, test_location)
        test_location.gbp_location_id = "locations/123"
        db.commit()

        async def fake_get_questions(self, location_id=None):
            raise RuntimeError("GBP sync failed")

        monkeypatch.setattr("app.integrations.gbp.GBPClient.get_questions", fake_get_questions)

        response = client.get(f"/qa/{test_location.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["integration_status"] == "gbp_fetch_failed"
        assert data["last_sync_at"] is not None
        assert data["last_sync_error"] == "GBP sync failed"

        db.refresh(channel)
        assert channel.last_sync_at is not None
        assert channel.meta["qa_last_sync_error"] == "GBP sync failed"

    def test_manual_sync_returns_counts_and_updates_sync_timestamp(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        channel = _add_gbp_channel(db, test_location)
        test_location.gbp_location_id = "locations/123"
        db.commit()

        async def fake_get_questions(self, location_id=None):
            assert location_id == "locations/123"
            return {
                "questions": [
                    {
                        "name": "locations/123/questions/1",
                        "text": "Do you take walk-ins?",
                        "createTime": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        "author": {"displayName": "Alex"},
                    },
                    {
                        "name": "locations/123/questions/2",
                        "text": "Can I book online?",
                        "createTime": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        "author": {"displayName": "Jordan"},
                        "topAnswers": [{"text": "Yes, booking is available online."}],
                    },
                ]
            }

        monkeypatch.setattr("app.integrations.gbp.GBPClient.get_questions", fake_get_questions)

        response = client.post(f"/qa/{test_location.id}/sync", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["synced_questions"] == 2
        assert data["pending_count"] == 1
        assert data["last_sync_at"] is not None
        assert data["last_sync_error"] is None

        db.refresh(channel)
        assert channel.last_sync_at is not None
        assert channel.meta["qa_last_sync_error"] is None
        assert channel.meta["qa_last_sync_question_count"] == 2

    def test_manual_sync_failure_returns_error_and_persists_diagnostics(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        channel = _add_gbp_channel(db, test_location)
        test_location.gbp_location_id = "locations/123"
        db.commit()

        async def fake_get_questions(self, location_id=None):
            raise RuntimeError("GBP sync failed")

        monkeypatch.setattr("app.integrations.gbp.GBPClient.get_questions", fake_get_questions)

        response = client.post(f"/qa/{test_location.id}/sync", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["synced_questions"] == 0
        assert data["pending_count"] == 0
        assert data["message"].startswith("Google Business Profile Q&A sync is unavailable right now")
        assert data["last_sync_error"] == "GBP sync failed"

        db.refresh(channel)
        assert channel.last_sync_at is not None
        assert channel.meta["qa_last_sync_error"] == "GBP sync failed"
        assert channel.meta["qa_last_sync_question_count"] == 0

    def test_save_draft_feedback_persists_quality_rating_and_notes(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        draft = QADraft(
            id=uuid4(),
            location_id=test_location.id,
            question_id="q-feedback",
            question_text="Do you validate parking?",
            suggested_answer="Yes, parking validation is available.",
            draft_status=QADraftStatus.DRAFT,
        )
        db.add(draft)
        db.commit()

        response = client.post(
            f"/qa/{test_location.id}/drafts/{draft.id}/feedback",
            headers=auth_headers,
            json={"rating": "needs_edit", "notes": "Too generic for this location."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["feedback_rating"] == "needs_edit"
        assert data["feedback_notes"] == "Too generic for this location."
        assert data["feedback_at"] is not None

        db.refresh(draft)
        assert draft.feedback_rating == QAFeedbackRating.NEEDS_EDIT
        assert draft.feedback_notes == "Too generic for this location."
        assert draft.feedback_at is not None

        history_response = client.get(f"/qa/{test_location.id}/drafts", headers=auth_headers)
        assert history_response.status_code == 200
        history = history_response.json()
        assert history["feedback_good_count"] == 0
        assert history["feedback_needs_edit_count"] == 1
        assert history["feedback_wrong_count"] == 0
