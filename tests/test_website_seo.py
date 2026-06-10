"""Tests for Website SEO draft persistence and publishing flow."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.credits import UsageRecord
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.website_seo import WebsiteSEOContentType, WebsiteSEODraft, WebsiteSEODraftStatus
from app.core.time import utc_now_aware


def _add_website_channel(db: Session, test_location) -> Channel:
    channel = Channel(
        id=uuid4(),
        location_id=test_location.id,
        type=ChannelType.WEBSITE,
        status=ChannelStatus.CONNECTED,
        is_active=True,
        access_token_expires_at=datetime.now(UTC) + timedelta(days=30),
        meta={},
    )
    channel.set_credentials(
        {
            "provider": "github",
            "access_token": "website-token",
            "repo": "owner/repo",
            "branch": "main",
            "content_path": "content/blog",
        }
    )
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


class TestWebsiteSEO:
    def test_generate_blog_post_persists_draft(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        async def fake_generate(self, prompt: str) -> str:
            return """---
title: Local Plumbing Tips
meta_description: Helpful plumbing tips for local homeowners.
---

## Intro
Helpful content for local customers.
"""

        monkeypatch.setattr("app.integrations.llm.LLMClient.generate", fake_generate)

        response = client.post(
            "/website-seo/blog-post",
            headers=auth_headers,
            json={"location_id": str(test_location.id), "topic": "Plumbing tips"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["draft_id"]

        draft = db.query(WebsiteSEODraft).filter(WebsiteSEODraft.location_id == test_location.id).first()
        assert draft is not None
        assert draft.title == "Local Plumbing Tips"
        assert draft.status.value == "draft"

        history_response = client.get(f"/website-seo/history/{test_location.id}", headers=auth_headers)
        assert history_response.status_code == 200
        assert history_response.json()["count"] == 1
        assert history_response.json()["total"] == 1
        assert history_response.json()["items"][0]["title"] == "Local Plumbing Tips"

        detail_response = client.get(f"/website-seo/drafts/{draft.id}", headers=auth_headers)
        assert detail_response.status_code == 200
        assert detail_response.json()["payload"]["title"] == "Local Plumbing Tips"
        assert _usage_total(db, test_location.account_id, "ai_content") == 1

    def test_generate_service_page_records_ai_content_usage(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        async def fake_generate(self, prompt: str) -> str:
            return "<h1>AC Repair</h1><p>Fast local service.</p>"

        monkeypatch.setattr("app.integrations.llm.LLMClient.generate", fake_generate)

        response = client.post(
            "/website-seo/service-page",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "service_name": "AC Repair",
                "service_description": "Emergency repairs and tune-ups",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["draft_id"]
        assert _usage_total(db, test_location.account_id, "ai_content") == 1

    def test_generate_service_page_empty_content_returns_503_and_does_not_consume_usage(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        async def fake_generate(self, prompt: str) -> str:
            return "   "

        monkeypatch.setattr("app.integrations.llm.LLMClient.generate", fake_generate)

        response = client.post(
            "/website-seo/service-page",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "service_name": "AC Repair",
                "service_description": "Emergency repairs and tune-ups",
            },
        )

        assert response.status_code == 503
        assert "returned no content" in response.json()["detail"]
        assert _usage_total(db, test_location.account_id, "ai_content") == 0

    def test_generate_blog_post_returns_429_when_ai_content_limit_is_reached(
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
                usage_type="ai_content",
                date=utc_now_aware(),
                daily_count=5,
                monthly_count=5,
                last_used_at=utc_now_aware() - timedelta(minutes=5),
            )
        )
        db.commit()

        called = {"llm": 0}

        async def fake_generate(self, prompt: str) -> str:
            called["llm"] += 1
            return "should not run"

        monkeypatch.setattr("app.integrations.llm.LLMClient.generate", fake_generate)

        response = client.post(
            "/website-seo/blog-post",
            headers=auth_headers,
            json={"location_id": str(test_location.id), "topic": "Plumbing tips"},
        )

        assert response.status_code == 429
        detail = response.json()["detail"]
        assert detail["usage_type"] == "ai_content"
        assert "Daily limit reached" in detail["message"]
        assert called["llm"] == 0
        assert db.query(WebsiteSEODraft).count() == 0
        assert _usage_total(db, test_location.account_id, "ai_content") == 5

    def test_generate_blog_post_empty_body_returns_503_and_does_not_consume_usage(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        async def fake_generate(self, prompt: str) -> str:
            return """---
title: Local Plumbing Tips
meta_description: Helpful plumbing tips for local homeowners.
---
"""

        monkeypatch.setattr("app.integrations.llm.LLMClient.generate", fake_generate)

        response = client.post(
            "/website-seo/blog-post",
            headers=auth_headers,
            json={"location_id": str(test_location.id), "topic": "Plumbing tips"},
        )

        assert response.status_code == 503
        assert "returned no content" in response.json()["detail"]
        assert db.query(WebsiteSEODraft).count() == 0
        assert _usage_total(db, test_location.account_id, "ai_content") == 0

    def test_keywords_require_location_ownership(
        self,
        client: TestClient,
        other_location,
        auth_headers: dict[str, str],
    ) -> None:
        response = client.get(f"/website-seo/keywords/{other_location.id}", headers=auth_headers)
        assert response.status_code == 404

    def test_optimize_existing_page_persists_draft(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        response = client.post(
            "/website-seo/optimize",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "page_url": "https://example.com/plumbing",
                "current_content": "This is current content for the plumbing page. " * 4,
            },
        )

        assert response.status_code == 200
        draft_id = response.json()["draft_id"]

        draft = db.query(WebsiteSEODraft).filter(WebsiteSEODraft.id == UUID(draft_id)).first()
        assert draft is not None
        assert draft.content_type.value == "optimization"

        detail_response = client.get(f"/website-seo/drafts/{draft_id}", headers=auth_headers)
        assert detail_response.status_code == 200
        assert detail_response.json()["payload"]["page_url"] == "https://example.com/plumbing"

    def test_publish_updates_draft_and_channel_meta(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_website_channel(db, test_location)

        async def fake_generate(self, prompt: str) -> str:
            return """---
title: Local HVAC Tips
meta_description: Helpful HVAC tips.
---

## Intro
Useful seasonal advice.
"""

        async def fake_publish_markdown(self, title: str | None, content: str, slug: str | None = None) -> str:
            return "https://example.com/blog/local-hvac-tips"

        monkeypatch.setattr("app.integrations.llm.LLMClient.generate", fake_generate)
        monkeypatch.setattr("app.integrations.website.WebsiteClient.publish_markdown", fake_publish_markdown)

        create_response = client.post(
            "/website-seo/blog-post",
            headers=auth_headers,
            json={"location_id": str(test_location.id), "topic": "HVAC tips"},
        )
        assert create_response.status_code == 200
        draft_id = create_response.json()["draft_id"]

        request_approval = client.post(
            f"/website-seo/drafts/{draft_id}/request-approval",
            headers=auth_headers,
        )
        assert request_approval.status_code == 200

        approve_response = client.post(
            f"/website-seo/drafts/{draft_id}/approve",
            headers=auth_headers,
        )
        assert approve_response.status_code == 200

        publish_response = client.post(
            "/website-seo/publish",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "content_type": "blog",
                "content": create_response.json(),
                "draft_id": draft_id,
            },
        )
        assert publish_response.status_code == 200

        draft = db.query(WebsiteSEODraft).filter(WebsiteSEODraft.id == UUID(draft_id)).first()
        assert draft is not None
        assert draft.status.value == "published"
        assert draft.published_url == "https://example.com/blog/local-hvac-tips"

        channel = db.query(Channel).filter(Channel.location_id == test_location.id, Channel.type == ChannelType.WEBSITE).first()
        assert channel is not None
        assert channel.meta["last_publish_succeeded_at"]

    def test_publish_requires_approved_draft(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_website_channel(db, test_location)

        async def fake_generate(self, prompt: str) -> str:
            return """---
title: Local Roofing Tips
meta_description: Helpful roofing tips.
---

## Intro
Useful advice.
"""

        monkeypatch.setattr("app.integrations.llm.LLMClient.generate", fake_generate)

        create_response = client.post(
            "/website-seo/blog-post",
            headers=auth_headers,
            json={"location_id": str(test_location.id), "topic": "Roofing tips"},
        )
        assert create_response.status_code == 200

        publish_response = client.post(
            "/website-seo/publish",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "content_type": "blog",
                "content": create_response.json(),
                "draft_id": create_response.json()["draft_id"],
            },
        )
        assert publish_response.status_code == 400
        assert publish_response.json()["detail"] == "Draft must be approved before publishing"

    def test_publish_failure_creates_operator_notification(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        _add_website_channel(db, test_location)

        async def fake_send_email(self, **kwargs):
            return {"success": True, "provider": "fake-email"}

        async def fake_generate(self, prompt: str) -> str:
            return """---
title: Local HVAC Tips
meta_description: Helpful HVAC tips.
---

## Intro
Useful seasonal advice.
"""

        async def fake_publish_markdown(self, title: str | None, content: str, slug: str | None = None) -> str:
            raise RuntimeError("cms repository unavailable")

        monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)
        monkeypatch.setattr("app.integrations.llm.LLMClient.generate", fake_generate)
        monkeypatch.setattr("app.integrations.website.WebsiteClient.publish_markdown", fake_publish_markdown)

        create_response = client.post(
            "/website-seo/blog-post",
            headers=auth_headers,
            json={"location_id": str(test_location.id), "topic": "HVAC tips"},
        )
        assert create_response.status_code == 200
        draft_id = create_response.json()["draft_id"]

        request_approval = client.post(
            f"/website-seo/drafts/{draft_id}/request-approval",
            headers=auth_headers,
        )
        assert request_approval.status_code == 200

        approve_response = client.post(
            f"/website-seo/drafts/{draft_id}/approve",
            headers=auth_headers,
        )
        assert approve_response.status_code == 200

        publish_response = client.post(
            "/website-seo/publish",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "content_type": "blog",
                "content": create_response.json(),
                "draft_id": draft_id,
            },
        )
        assert publish_response.status_code == 400
        assert "Website publishing failed" in publish_response.json()["detail"]

        draft = db.query(WebsiteSEODraft).filter(WebsiteSEODraft.id == UUID(draft_id)).first()
        assert draft is not None
        assert draft.status.value == "failed"
        assert draft.last_error == "cms repository unavailable"

        event = (
            db.query(NotificationEvent)
            .filter(
                NotificationEvent.account_id == test_location.account_id,
                NotificationEvent.type == "website_publish_failed",
            )
            .one()
        )
        assert "Website publish failed" in event.title
        assert "cms repository unavailable" in event.body
        assert event.url == "/dashboard/seo"

        delivery_log = (
            db.query(NotificationDeliveryLog)
            .filter(NotificationDeliveryLog.notification_event_id == event.id)
            .one()
        )
        assert delivery_log.delivery_status == "delivered"

    def test_request_approve_reject_workflow(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        draft = WebsiteSEODraft(
            id=uuid4(),
            location_id=test_location.id,
            content_type=WebsiteSEOContentType.SERVICE_PAGE,
            status=WebsiteSEODraftStatus.DRAFT,
            title="AC Repair",
            payload={},
        )
        db.add(draft)
        db.commit()

        request_response = client.post(
            f"/website-seo/drafts/{draft.id}/request-approval",
            headers=auth_headers,
        )
        assert request_response.status_code == 200
        assert request_response.json()["approval_status"] == "pending"

        approve_response = client.post(
            f"/website-seo/drafts/{draft.id}/approve",
            headers=auth_headers,
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["approval_status"] == "approved"

        reject_response = client.post(
            f"/website-seo/drafts/{draft.id}/reject",
            headers=auth_headers,
            json={"reason": "Needs stronger local detail"},
        )
        assert reject_response.status_code == 200
        assert reject_response.json()["approval_status"] == "rejected"
        assert reject_response.json()["rejection_reason"] == "Needs stronger local detail"

    def test_history_supports_failed_only_search_and_pagination(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        db.add_all(
            [
                WebsiteSEODraft(
                    id=uuid4(),
                    location_id=test_location.id,
                    content_type=WebsiteSEOContentType.BLOG_POST,
                    status=WebsiteSEODraftStatus.FAILED,
                    title="Broken HVAC Post",
                    slug="broken-hvac-post",
                    source_topic="hvac",
                    last_error="publish failed",
                    payload={},
                ),
                WebsiteSEODraft(
                    id=uuid4(),
                    location_id=test_location.id,
                    content_type=WebsiteSEOContentType.SERVICE_PAGE,
                    status=WebsiteSEODraftStatus.DRAFT,
                    title="Water Heater Service",
                    slug="water-heater-service",
                    source_topic="water heater",
                    payload={},
                ),
            ]
        )
        db.commit()

        response = client.get(
            f"/website-seo/history/{test_location.id}",
            headers=auth_headers,
            params={"status": "failed", "search": "HVAC", "limit": 1, "offset": 0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["total"] == 1
        assert data["limit"] == 1
        assert data["offset"] == 0
        assert data["items"][0]["title"] == "Broken HVAC Post"

    def test_history_supports_approval_status_filter(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        pending_draft = WebsiteSEODraft(
            id=uuid4(),
            location_id=test_location.id,
            content_type=WebsiteSEOContentType.BLOG_POST,
            status=WebsiteSEODraftStatus.DRAFT,
            title="Pending SEO Draft",
            approval_status="pending",
            payload={},
        )
        approved_draft = WebsiteSEODraft(
            id=uuid4(),
            location_id=test_location.id,
            content_type=WebsiteSEOContentType.SERVICE_PAGE,
            status=WebsiteSEODraftStatus.DRAFT,
            title="Approved SEO Draft",
            approval_status="approved",
            payload={},
        )
        db.add_all([pending_draft, approved_draft])
        db.commit()

        response = client.get(
            f"/website-seo/history/{test_location.id}",
            headers=auth_headers,
            params={"approval_status": "pending"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Pending SEO Draft"

    def test_bulk_archive_moves_drafts_out_of_active_history(
        self,
        client: TestClient,
        db: Session,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        draft_one = WebsiteSEODraft(
            id=uuid4(),
            location_id=test_location.id,
            content_type=WebsiteSEOContentType.BLOG_POST,
            status=WebsiteSEODraftStatus.DRAFT,
            title="Archive Me",
            payload={},
        )
        draft_two = WebsiteSEODraft(
            id=uuid4(),
            location_id=test_location.id,
            content_type=WebsiteSEOContentType.SERVICE_PAGE,
            status=WebsiteSEODraftStatus.FAILED,
            title="Keep Me",
            payload={},
        )
        db.add_all([draft_one, draft_two])
        db.commit()

        archive_response = client.post(
            f"/website-seo/history/{test_location.id}/archive",
            headers=auth_headers,
            json={"draft_ids": [str(draft_one.id)], "reason": "Cleanup stale draft"},
        )
        assert archive_response.status_code == 200
        assert archive_response.json()["archived_count"] == 1
        assert archive_response.json()["archived_ids"] == [str(draft_one.id)]

        active_history = client.get(
            f"/website-seo/history/{test_location.id}",
            headers=auth_headers,
        )
        assert active_history.status_code == 200
        active_data = active_history.json()
        assert active_data["total"] == 1
        assert active_data["items"][0]["title"] == "Keep Me"

        archived_history = client.get(
            f"/website-seo/history/{test_location.id}",
            headers=auth_headers,
            params={"status": "archived"},
        )
        assert archived_history.status_code == 200
        archived_data = archived_history.json()
        assert archived_data["total"] == 1
        assert archived_data["items"][0]["status"] == "archived"
        assert archived_data["items"][0]["archived_reason"] == "Cleanup stale draft"

        archived_detail = client.get(f"/website-seo/drafts/{draft_one.id}", headers=auth_headers)
        assert archived_detail.status_code == 200
        assert archived_detail.json()["status"] == "archived"
