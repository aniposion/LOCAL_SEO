from datetime import timedelta

import pytest

from app.core.time import utc_now_aware, utc_now_naive
from app.models.account import Account
from app.models.location import Location
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.post import Platform, Post, PostStatus
from app.models.publish_job import PlatformToken, PublishJob, PublishJobStatus
from app.models.subscription import DunningStatus, PlanType, Subscription, SubscriptionStatus
from app.services.dunning_service import DunningService
from app.services.email_service import EmailDeliveryError, EmailService, EmailUnavailableError
from app.services.notification import NotificationService
from app.services.reliable_publisher import ReliablePublisherService


@pytest.mark.asyncio
async def test_email_service_raises_when_sendgrid_is_unavailable(monkeypatch):
    monkeypatch.setattr("app.services.email_service.settings.sendgrid_api_key", None, raising=False)
    monkeypatch.setattr("app.services.email_service.settings.sendgrid_from_email", "noreply@example.com", raising=False)

    service = EmailService()

    with pytest.raises(EmailUnavailableError) as exc_info:
        await service.send_email(
            to="customer@example.com",
            subject="Hello",
            html_content="<p>Hello</p>",
            from_email="noreply@example.com",
        )

    assert "SendGrid" in str(exc_info.value)


@pytest.mark.asyncio
async def test_notification_service_uses_sendgrid_when_smtp_is_unconfigured(db, monkeypatch):
    monkeypatch.setattr("app.services.notification.settings.smtp_host", None, raising=False)
    monkeypatch.setattr("app.services.notification.settings.sendgrid_api_key", "sg-test", raising=False)
    monkeypatch.setattr("app.services.notification.settings.sendgrid_from_email", "billing@example.com", raising=False)

    captured: dict = {}

    async def fake_send_email(self, **kwargs):
        captured.update(kwargs)
        return {"message_id": "sg-msg-1", "status_code": 202}

    monkeypatch.setattr("app.services.notification.EmailService.send_email", fake_send_email)

    result = await NotificationService(db).send_email(
        to_email="customer@example.com",
        subject="Hello",
        html_body="<p>Hello</p>",
        text_body="Hello",
    )

    assert result["success"] is True
    assert result["provider"] == "sendgrid"
    assert captured["to"] == "customer@example.com"
    assert captured["from_email"] == "billing@example.com"


@pytest.mark.asyncio
async def test_notification_service_falls_back_to_sendgrid_after_smtp_failure(db, monkeypatch):
    monkeypatch.setattr("app.services.notification.settings.smtp_host", "smtp.example.com", raising=False)
    monkeypatch.setattr("app.services.notification.settings.sendgrid_api_key", "sg-test", raising=False)
    monkeypatch.setattr("app.services.notification.settings.sendgrid_from_email", "billing@example.com", raising=False)

    async def fake_smtp(self, **kwargs):
        raise EmailDeliveryError("smtp temporarily unavailable")

    async def fake_sendgrid(self, **kwargs):
        return {"message_id": "sg-msg-2", "status_code": 202}

    monkeypatch.setattr(NotificationService, "_send_email_via_smtp", fake_smtp)
    monkeypatch.setattr(NotificationService, "_send_email_via_sendgrid", fake_sendgrid)

    result = await NotificationService(db).send_email(
        to_email="customer@example.com",
        subject="Fallback",
        html_body="<p>Fallback</p>",
    )

    assert result["success"] is True
    assert result["message_id"] == "sg-msg-2"


@pytest.mark.asyncio
async def test_notification_service_persists_inbox_event_and_delivery_log(db, test_user, monkeypatch):
    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr(NotificationService, "send_email", fake_send_email)

    result = await NotificationService(db).send_notification(
        account_id=test_user.id,
        title="Reconnect Google integration",
        message="OAuth token needs reauthorization.",
        notification_type="oauth_reauth_required",
        data={"url": "/dashboard/integrations"},
    )

    assert result["success"] is True

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_user.id,
            NotificationEvent.type == "oauth_reauth_required",
        )
        .one()
    )
    assert event.title == "Reconnect Google integration"
    assert event.url == "/dashboard/integrations"

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.account_id == test_user.id
    assert delivery_log.channel == "email"
    assert delivery_log.delivery_status == "delivered"


def test_dunning_status_uses_real_fallback_url(db, test_user, monkeypatch):
    monkeypatch.setattr("app.services.dunning_service.settings.app_url", "https://app.example.com", raising=False)
    monkeypatch.setattr("app.services.dunning_service.settings.stripe_secret_key", None, raising=False)

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.ACTIVE,
        access_state="warning",
        dunning_status=DunningStatus.RETRYING,
        dunning_started_at=utc_now_naive(),
        payment_retry_count=1,
        stripe_customer_id="cus_test",
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    service = DunningService(db)
    status = service.get_dunning_status(subscription)

    assert status["portal_url"] == "https://app.example.com/dashboard/billing"
    assert status["portal_available"] is False
    assert status["portal_source"] == "billing_page"
    assert "not configured" in status["portal_error"].lower()


@pytest.mark.asyncio
async def test_reliable_publisher_marks_platform_unavailable(db, test_user, test_location, monkeypatch):
    monkeypatch.setattr("app.services.reliable_publisher.settings.gbp_client_id", None, raising=False)
    monkeypatch.setattr("app.services.reliable_publisher.settings.gbp_client_secret", None, raising=False)

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr(NotificationService, "send_email", fake_send_email)

    post = Post(
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.APPROVED,
        title="Weekend update",
        body="New hours and services",
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    token = PlatformToken(
        location_id=test_location.id,
        platform="gbp",
        access_token="access-token",
        refresh_token="refresh-token",
        expires_at=utc_now_aware() + timedelta(days=7),
        status="active",
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    job = PublishJob(
        post_id=post.id,
        platform="gbp",
        status=PublishJobStatus.PENDING,
        tries=0,
        max_tries=3,
        next_run_at=utc_now_aware(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    service = ReliablePublisherService(db)
    processed = await service.process_job(job)

    assert processed.status == PublishJobStatus.FAILED
    assert processed.error_code == "UNAVAILABLE"
    assert processed.platform_post_id is None
    assert processed.platform_url is None
    assert processed.response_payload["available"] is False
    assert "unavailable" in processed.last_error.lower()

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_user.id,
            NotificationEvent.type == "publish_job_failed",
        )
        .one()
    )
    assert "publish failed" in event.title.lower()
    assert event.url == f"/dashboard/content/{post.id}"

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_reliable_publisher_persists_failure_when_notification_fails(
    db, test_location, monkeypatch
):
    """Publish job failure state must survive even if the alert channel is broken."""
    monkeypatch.setattr("app.services.reliable_publisher.settings.gbp_client_id", None, raising=False)
    monkeypatch.setattr("app.services.reliable_publisher.settings.gbp_client_secret", None, raising=False)

    async def exploding_notification(*args, **kwargs):
        raise RuntimeError("notification channel offline")

    monkeypatch.setattr(NotificationService, "send_notification", exploding_notification)

    post = Post(
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.APPROVED,
        title="Persist failure even if alerts fail",
        body="New hours and services",
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    token = PlatformToken(
        location_id=test_location.id,
        platform="gbp",
        access_token="access-token",
        refresh_token="refresh-token",
        expires_at=utc_now_aware() + timedelta(days=7),
        status="active",
    )
    job = PublishJob(
        post_id=post.id,
        platform="gbp",
        status=PublishJobStatus.PENDING,
        tries=0,
        max_tries=3,
        next_run_at=utc_now_aware(),
    )
    db.add_all([token, job])
    db.commit()
    db.refresh(job)

    processed = await ReliablePublisherService(db).process_job(job)

    assert processed.status == PublishJobStatus.FAILED
    assert processed.error_code == "UNAVAILABLE"
    assert "unavailable" in (processed.last_error or "").lower()

    persisted = db.get(PublishJob, job.id)
    assert persisted is not None
    assert persisted.status == PublishJobStatus.FAILED
    assert persisted.error_code == "UNAVAILABLE"
    assert persisted.response_payload["success"] is False


@pytest.mark.asyncio
async def test_reliable_publisher_notifies_when_token_needs_reauth(db, test_user, test_location, monkeypatch):
    monkeypatch.setattr("app.services.reliable_publisher.settings.gbp_client_id", "gbp-client", raising=False)
    monkeypatch.setattr("app.services.reliable_publisher.settings.gbp_client_secret", "gbp-secret", raising=False)

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr(NotificationService, "send_email", fake_send_email)

    post = Post(
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.APPROVED,
        title="Reconnect test",
        body="Needs a live token",
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    token = PlatformToken(
        location_id=test_location.id,
        platform="gbp",
        access_token="expired-access-token",
        refresh_token=None,
        expires_at=utc_now_aware() - timedelta(minutes=5),
        status="active",
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    job = PublishJob(
        post_id=post.id,
        platform="gbp",
        status=PublishJobStatus.PENDING,
        tries=0,
        max_tries=3,
        next_run_at=utc_now_aware(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    service = ReliablePublisherService(db)
    processed = await service.process_job(job)

    db.refresh(token)
    assert processed.status == PublishJobStatus.FAILED
    assert processed.error_code == "TOKEN_EXPIRED"
    assert token.status == "reauth_required"

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_user.id,
            NotificationEvent.type == "publish_reauth_required",
        )
        .one()
    )
    assert "reconnect" in event.title.lower()
    assert event.url == "/dashboard/integrations"

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_reliable_publisher_job_stats_are_location_scoped(db, test_location, other_location):
    service = ReliablePublisherService(db)

    own_failed_post = Post(
        location_id=test_location.id,
        platform=Platform.GBP,
        status=PostStatus.FAILED,
        title="Own failed post",
    )
    own_completed_post = Post(
        location_id=test_location.id,
        platform=Platform.INSTAGRAM,
        status=PostStatus.POSTED,
        title="Own completed post",
    )
    other_failed_post = Post(
        location_id=other_location.id,
        platform=Platform.GBP,
        status=PostStatus.FAILED,
        title="Other failed post",
    )
    db.add_all([own_failed_post, own_completed_post, other_failed_post])
    db.commit()

    db.add_all(
        [
            PublishJob(
                post_id=own_failed_post.id,
                platform="gbp",
                status=PublishJobStatus.FAILED,
                next_run_at=utc_now_aware(),
            ),
            PublishJob(
                post_id=own_completed_post.id,
                platform="instagram",
                status=PublishJobStatus.COMPLETED,
                next_run_at=utc_now_aware(),
            ),
            PublishJob(
                post_id=other_failed_post.id,
                platform="gbp",
                status=PublishJobStatus.FAILED,
                next_run_at=utc_now_aware(),
            ),
        ]
    )
    db.commit()

    stats = await service.get_job_stats(test_location.id)

    assert stats == {
        "pending": 0,
        "processing": 0,
        "completed": 1,
        "failed": 1,
    }
