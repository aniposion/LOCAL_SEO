from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func

from app.core.time import utc_now_aware
from app.models.credits import UsageRecord
from app.models.post import Platform, Post, PostStatus
from app.services.approval import (
    ApprovalGenerationUnavailableError,
    ApprovalUsageLimitError,
    ApprovalWorkflowService,
)
from app.services.magic_link import (
    ApprovalWorkflowService as MagicLinkApprovalWorkflowService,
    MagicLinkService,
)
from app.services.notification import NotificationChannel, NotificationService


def _usage_total(db, account_id, usage_type: str) -> int:
    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(UsageRecord.account_id == account_id, UsageRecord.usage_type == usage_type)
        .scalar()
    )
    return int(total or 0)


@pytest.mark.asyncio
async def test_approve_post_updates_status_and_clears_token(db, test_user, test_location):
    post = Post(
        id=uuid4(),
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.PENDING_APPROVAL,
        title='Pending post',
        approval_token='approve-token',
        approval_requested_at=datetime.now(UTC),
    )
    db.add(post)
    db.commit()

    service = ApprovalWorkflowService(db)
    service.notification_service.send_approval_result = AsyncMock(return_value=True)

    approved_post = await service.approve_post(
        post_id=post.id,
        approval_token='approve-token',
        approver_id=test_user.id,
    )

    assert approved_post.status == PostStatus.APPROVED
    assert approved_post.approval_token is None
    assert approved_post.approved_by_id == test_user.id
    assert approved_post.approved_at is not None
    assert service.notification_service.send_approval_result.await_count in (0, 1)


@pytest.mark.asyncio
async def test_reject_post_updates_status_reason_and_clears_token(db, test_location):
    post = Post(
        id=uuid4(),
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.PENDING_APPROVAL,
        title='Pending post',
        approval_token='reject-token',
        approval_requested_at=datetime.now(UTC),
    )
    db.add(post)
    db.commit()

    service = ApprovalWorkflowService(db)
    service.notification_service.send_approval_result = AsyncMock(return_value=True)

    rejected_post = await service.reject_post(
        post_id=post.id,
        approval_token='reject-token',
        reason='Needs revision',
    )

    assert rejected_post.status == PostStatus.REJECTED
    assert rejected_post.approval_token is None
    assert rejected_post.rejection_reason == 'Needs revision'
    assert rejected_post.rejected_at is not None
    assert service.notification_service.send_approval_result.await_count in (0, 1)


@pytest.mark.asyncio
async def test_create_draft_with_approval_records_ai_content_and_image_usage(db, test_user, test_location):
    service = ApprovalWorkflowService(db)
    service.content_service.generate = AsyncMock(
        return_value=SimpleNamespace(
            gbp=SimpleNamespace(title="Fresh Spring Offer", body="Body copy", hashtags=["#spring"]),
            instagram=None,
            web=None,
            image_prompt="spring storefront photo",
        )
    )
    service.image_service.generate_and_upload = AsyncMock(return_value="https://cdn.example.com/generated.png")
    service.notification_service.send_approval_request = AsyncMock(return_value=True)

    result = await service.create_draft_with_approval(
        location_id=test_location.id,
        account_id=test_user.id,
        theme="Spring promotion",
        services=test_location.services,
        platform_targets=["GBP"],
        generate_image=True,
    )

    assert len(result["posts"]) == 1
    assert result["image_url"] == "https://cdn.example.com/generated.png"
    assert _usage_total(db, test_user.id, "ai_content") == 1
    assert _usage_total(db, test_user.id, "ai_image") == 1


@pytest.mark.asyncio
async def test_create_draft_with_approval_does_not_consume_usage_on_content_failure(
    db, test_user, test_location
):
    service = ApprovalWorkflowService(db)
    service.content_service.generate = AsyncMock(side_effect=RuntimeError("LLM provider failed"))
    service.image_service.generate_and_upload = AsyncMock(return_value="https://cdn.example.com/generated.png")
    service.notification_service.send_approval_request = AsyncMock(return_value=True)

    with pytest.raises(RuntimeError, match="LLM provider failed"):
        await service.create_draft_with_approval(
            location_id=test_location.id,
            account_id=test_user.id,
            theme="Spring promotion",
            services=test_location.services,
            platform_targets=["GBP"],
            generate_image=True,
        )

    assert _usage_total(db, test_user.id, "ai_content") == 0
    assert _usage_total(db, test_user.id, "ai_image") == 0


@pytest.mark.asyncio
async def test_create_draft_with_approval_empty_generated_content_raises_and_does_not_consume_usage(
    db, test_user, test_location
):
    service = ApprovalWorkflowService(db)
    service.content_service.generate = AsyncMock(
        return_value=SimpleNamespace(
            gbp=None,
            instagram=None,
            web=None,
            image_prompt="unused prompt",
        )
    )
    service.image_service.generate_and_upload = AsyncMock(return_value="https://cdn.example.com/generated.png")
    service.notification_service.send_approval_request = AsyncMock(return_value=True)

    with pytest.raises(ApprovalGenerationUnavailableError, match="AI content provider is unavailable."):
        await service.create_draft_with_approval(
            location_id=test_location.id,
            account_id=test_user.id,
            theme="Spring promotion",
            services=test_location.services,
            platform_targets=["GBP"],
            generate_image=True,
        )

    assert service.image_service.generate_and_upload.await_count == 0
    assert db.query(Post).count() == 0
    assert _usage_total(db, test_user.id, "ai_content") == 0
    assert _usage_total(db, test_user.id, "ai_image") == 0


@pytest.mark.asyncio
async def test_create_draft_with_approval_skips_ai_image_usage_when_image_generation_fails(
    db, test_user, test_location
):
    service = ApprovalWorkflowService(db)
    service.content_service.generate = AsyncMock(
        return_value=SimpleNamespace(
            gbp=SimpleNamespace(title="Fresh Spring Offer", body="Body copy", hashtags=["#spring"]),
            instagram=None,
            web=None,
            image_prompt="spring storefront photo",
        )
    )
    service.image_service.generate_and_upload = AsyncMock(side_effect=RuntimeError("Image provider failed"))
    service.notification_service.send_approval_request = AsyncMock(return_value=True)

    result = await service.create_draft_with_approval(
        location_id=test_location.id,
        account_id=test_user.id,
        theme="Spring promotion",
        services=test_location.services,
        platform_targets=["GBP"],
        generate_image=True,
    )

    assert len(result["posts"]) == 1
    assert result["image_url"] is None
    assert _usage_total(db, test_user.id, "ai_content") == 1
    assert _usage_total(db, test_user.id, "ai_image") == 0


def test_create_draft_for_approval_returns_429_when_ai_image_limit_is_reached(
    client, db, auth_headers, test_user, test_location, monkeypatch
):
    db.add(
        UsageRecord(
            account_id=test_user.id,
            usage_type="ai_image",
            date=utc_now_aware(),
            daily_count=3,
            monthly_count=3,
            last_used_at=utc_now_aware() - timedelta(minutes=5),
        )
    )
    db.commit()

    called = {"content": 0}

    async def fake_generate(*args, **kwargs):
        called["content"] += 1
        return SimpleNamespace(
            gbp=SimpleNamespace(title="Should not generate", body="No body", hashtags=[]),
            instagram=None,
            web=None,
            image_prompt="unused",
        )

    monkeypatch.setattr("app.services.approval.ContentService.generate", fake_generate)

    response = client.post(
        "/approval/draft",
        headers=auth_headers,
        json={
            "location_id": str(test_location.id),
            "theme": "Spring promotion",
            "services": test_location.services,
            "platform_targets": ["GBP"],
            "generate_image": True,
        },
    )

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["usage_type"] == "ai_image"
    assert "Daily limit reached" in detail["message"]
    assert called["content"] == 0
    assert db.query(Post).count() == 0
    assert _usage_total(db, test_user.id, "ai_content") == 0
    assert _usage_total(db, test_user.id, "ai_image") == 3


def test_create_draft_for_approval_returns_503_when_no_platform_content_is_generated(
    client, db, auth_headers, test_user, test_location, monkeypatch
):
    async def fake_generate(*args, **kwargs):
        return SimpleNamespace(
            gbp=None,
            instagram=None,
            web=None,
            image_prompt="unused prompt",
        )

    monkeypatch.setattr("app.services.approval.ContentService.generate", fake_generate)

    response = client.post(
        "/approval/draft",
        headers=auth_headers,
        json={
            "location_id": str(test_location.id),
            "theme": "Spring promotion",
            "services": test_location.services,
            "platform_targets": ["GBP"],
            "generate_image": True,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "AI content provider is unavailable."
    assert db.query(Post).count() == 0
    assert _usage_total(db, test_user.id, "ai_content") == 0
    assert _usage_total(db, test_user.id, "ai_image") == 0


@pytest.mark.asyncio
async def test_notification_service_send_sms_records_usage_on_success(db, test_user, monkeypatch):
    test_user.phone = "+15556667777"
    db.commit()

    class DummyTwilio:
        async def send_sms(self, to, body, from_number=None, status_callback=None):
            return {"sid": "SM_NOTIFY_1", "status": "queued"}

    monkeypatch.setattr("app.services.notification.get_twilio_service", lambda: DummyTwilio())

    service = NotificationService(db)
    result = await service.send_sms(test_user.phone, "Approval reminder", account_id=test_user.id)

    assert result["success"] is True
    assert result["message_sid"] == "SM_NOTIFY_1"
    assert result["status"] == "queued"
    assert _usage_total(db, test_user.id, "sms") == 1


@pytest.mark.asyncio
async def test_notification_service_send_sms_blocks_when_sms_limit_reached(db, test_user, monkeypatch):
    test_user.phone = "+15556667777"
    db.add(
        UsageRecord(
            account_id=test_user.id,
            usage_type="sms",
            date=utc_now_aware(),
            daily_count=10,
            monthly_count=10,
            last_used_at=utc_now_aware() - timedelta(minutes=5),
        )
    )
    db.commit()

    captured = {"count": 0}

    class DummyTwilio:
        async def send_sms(self, to, body, from_number=None, status_callback=None):
            captured["count"] += 1
            return {"sid": "SM_SHOULD_NOT_SEND", "status": "queued"}

    monkeypatch.setattr("app.services.notification.get_twilio_service", lambda: DummyTwilio())

    service = NotificationService(db)
    result = await service.send_sms(test_user.phone, "Approval reminder", account_id=test_user.id)

    assert result["success"] is False
    assert result["error_code"] == "rate_limit_exceeded"
    assert "Daily limit reached" in result["message"]
    assert captured["count"] == 0
    assert _usage_total(db, test_user.id, "sms") == 10


@pytest.mark.asyncio
async def test_send_approval_request_sms_records_usage_and_marks_post(
    db, test_user, test_location, monkeypatch
):
    def fake_magic_link_init(self, db_session=None):
        self.db = db_session
        self.secret_key = "test-secret-key-for-magic-links-1234567890"

    monkeypatch.setattr("app.services.magic_link.MagicLinkService.__init__", fake_magic_link_init)
    test_user.phone = "+15556667777"
    post = Post(
        id=uuid4(),
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.PENDING_APPROVAL,
        title="SMS approval request",
        approval_token="sms-approve-token",
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    class DummyTwilio:
        async def send_sms(self, to, body, from_number=None, status_callback=None):
            return {"sid": "SM_APPROVAL_1", "status": "sent"}

    monkeypatch.setattr("app.services.notification.get_twilio_service", lambda: DummyTwilio())

    service = NotificationService(db)
    success = await service.send_approval_request(post, test_user, NotificationChannel.SMS)

    assert success is True
    db.refresh(post)
    assert post.notification_sent is True
    assert post.notification_channel == "sms"
    assert post.notification_sent_at is not None
    assert _usage_total(db, test_user.id, "sms") == 1


@pytest.mark.asyncio
async def test_magic_link_sms_notification_records_usage_on_success(
    db, test_user, test_location, monkeypatch
):
    def fake_magic_link_init(self, db_session=None):
        self.db = db_session
        self.secret_key = "test-secret-key-for-magic-links-1234567890"

    monkeypatch.setattr("app.services.magic_link.MagicLinkService.__init__", fake_magic_link_init)
    test_user.phone = "+15556667777"
    post = Post(
        id=uuid4(),
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.PENDING_APPROVAL,
        title="Magic link SMS",
        approval_token="magic-link-token",
    )
    db.add(post)
    db.commit()

    class DummyTwilio:
        async def send_sms(self, to, body, from_number=None, status_callback=None):
            return {"sid": "SM_MAGIC_1", "status": "sent"}

    monkeypatch.setattr("app.services.notification.get_twilio_service", lambda: DummyTwilio())

    service = MagicLinkApprovalWorkflowService(db)
    result = await service.send_approval_notification(post.id, channel="sms")

    assert result["success"] is True
    assert result["channel"] == "sms"
    assert result["sms_sent"] is True
    assert _usage_total(db, test_user.id, "sms") == 1


def test_magic_link_generate_approval_links_prefers_live_review_page_with_approval_token(db):
    service = MagicLinkService(db)
    post_id = uuid4()
    account_id = uuid4()

    links = service.generate_approval_links(
        post_id=post_id,
        account_id=account_id,
        base_url="https://app.example.com",
        approval_token="approval-token-123",
    )

    assert links["approve_url"] == f"https://app.example.com/approve/{post_id}?token=approval-token-123&action=approve"
    assert links["reject_url"] == f"https://app.example.com/approve/{post_id}?token=approval-token-123&action=reject"
    assert links["review_url"] == f"https://app.example.com/approve/{post_id}?token=approval-token-123"
    assert links["edit_url"] == links["review_url"]


def test_magic_link_email_content_uses_review_first_copy(db):
    service = MagicLinkService(db)
    links = {
        "approve_url": "https://app.example.com/approve/post-1?token=approval-token-123&action=approve",
        "reject_url": "https://app.example.com/approve/post-1?token=approval-token-123&action=reject",
        "review_url": "https://app.example.com/approve/post-1?token=approval-token-123",
        "edit_url": "https://app.example.com/approve/post-1?token=approval-token-123",
    }

    content = service.generate_approval_email_content(
        post=SimpleNamespace(title="Fresh Spring Offer", body="Body copy goes here"),
        location=SimpleNamespace(name="Test Business"),
        links=links,
    )

    assert "Approve & Publish" not in content["html"]
    assert "Review First" in content["html"]
    assert links["review_url"] in content["html"]
    assert "Review or respond (no login required):" in content["text"]
    assert "Review First:" in content["text"]
    assert "??" not in content["html"]
    assert "??" not in content["text"]
    assert "Approve & Publish" not in content["text"]


def test_magic_link_sms_content_uses_clean_approval_copy(db):
    service = MagicLinkApprovalWorkflowService(db)
    links = {
        "approve_url": "https://app.example.com/approve/post-1?token=approval-token-123&action=approve",
        "reject_url": "https://app.example.com/approve/post-1?token=approval-token-123&action=reject",
    }

    message = service._generate_approval_sms_content(
        post=SimpleNamespace(title="Fresh Spring Offer"),
        location=SimpleNamespace(name="Test Business"),
        links=links,
    )

    assert "Content approval requested" in message
    assert "Approve:" in message
    assert "Reject:" in message
    assert "??" not in message


def test_public_preview_post_for_approval_includes_location_and_schedule(
    client, db, test_location
):
    scheduled_at = datetime.now(UTC) + timedelta(days=1)
    post = Post(
        id=uuid4(),
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.PENDING_APPROVAL,
        title="Pending preview",
        body="Preview body",
        approval_token="preview-token",
        approval_requested_at=datetime.now(UTC),
        scheduled_at=scheduled_at,
    )
    db.add(post)
    db.commit()

    response = client.get(f"/approval/posts/{post.id}/preview", params={"token": "preview-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["location"]["name"] == test_location.name
    assert payload["location"]["address"] == test_location.address
    assert payload["location"]["city"] == test_location.city
    assert payload["scheduled_at"] == scheduled_at.isoformat()
    assert payload["created_at"] is not None
