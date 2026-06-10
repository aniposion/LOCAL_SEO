import importlib
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.time import utc_now_naive
from app.core.security import get_password_hash
from app.models.account import Account, AccountRole
from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.post import Platform, Post, PostStatus
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.schedule import Schedule
from app.models.subscription import DunningStatus, PlanType, Subscription, SubscriptionStatus
from app.services.approval import ApprovalWorkflowService
from app.services.analytics import AnalyticsService
from app.services.dunning_service import DunningService
from app.services.notification import NotificationChannel, NotificationService
from app.services.reporting import ReportingService
from app.services.seo import SEOService


worker_scheduler = importlib.import_module("app.workers.scheduler")


def _admin_account(db) -> Account:
    admin = Account(
        id=uuid4(),
        email="worker-admin@example.com",
        password_hash=get_password_hash("Adminpassword123!"),
        role=AccountRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.mark.asyncio
async def test_content_generate_job_uses_account_notification_channel(
    db, test_user, test_location, monkeypatch
):
    test_user.notification_channel = "sms"
    db.commit()
    db.refresh(test_user)
    schedule = Schedule(
        id=uuid4(),
        location_id=test_location.id,
        platform="GBP",
        topic_prefs={"theme": "spring launch"},
        tone="friendly",
        language="en",
        is_active=True,
    )
    db.add(schedule)
    db.commit()

    captured: dict[str, NotificationChannel] = {}

    async def fake_create_draft(self, **kwargs):
        captured["notification_channel"] = kwargs["notification_channel"]
        return {"notifications": []}

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(ApprovalWorkflowService, "create_draft_with_approval", fake_create_draft)

    await worker_scheduler.content_generate_job()

    assert captured["notification_channel"] == NotificationChannel.SMS


@pytest.mark.asyncio
async def test_content_generate_job_notifies_when_scheduled_generation_fails(
    db, test_user, test_location, monkeypatch
):
    schedule = Schedule(
        id=uuid4(),
        location_id=test_location.id,
        platform="GBP",
        topic_prefs={"theme": "spring launch"},
        tone="friendly",
        language="en",
        is_active=True,
    )
    db.add(schedule)
    db.commit()

    async def fake_create_draft(self, **kwargs):
        raise RuntimeError("LLM unavailable")

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(ApprovalWorkflowService, "create_draft_with_approval", fake_create_draft)
    monkeypatch.setattr(NotificationService, "send_email", fake_send_email)

    await worker_scheduler.content_generate_job()

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.type == "scheduled_content_generation_failed")
        .one()
    )
    assert event.account_id == test_user.id
    assert event.url == f"/dashboard/content/new?locationId={test_location.id}"
    assert "spring launch" in event.body
    assert "LLM unavailable" in event.body

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_content_generate_job_notifies_admin_on_top_level_failure(
    db, test_user, test_location, monkeypatch
):
    admin = _admin_account(db)
    schedule = Schedule(
        id=uuid4(),
        location_id=test_location.id,
        platform="GBP",
        topic_prefs={"theme": "spring launch"},
        tone="friendly",
        language="en",
        is_active=True,
    )
    db.add(schedule)
    db.commit()

    class ExplodingApprovalWorkflowService:
        def __init__(self, _db):
            raise RuntimeError("approval workflow bootstrap failed")

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr("app.services.approval.ApprovalWorkflowService", ExplodingApprovalWorkflowService)

    await worker_scheduler.content_generate_job()

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == admin.id)
        .filter(NotificationEvent.type == "content_generation_job_failed")
        .one()
    )
    assert event.url == "/admin"
    assert "approval workflow bootstrap failed" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_weekly_report_job_notifies_when_generation_fails(
    db, test_user, test_location, monkeypatch
):
    async def fake_generate_weekly_report(self, **kwargs):
        raise RuntimeError("report storage unavailable")

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(ReportingService, "generate_weekly_report", fake_generate_weekly_report)
    monkeypatch.setattr(NotificationService, "send_email", fake_send_email)

    await worker_scheduler.weekly_report_job()

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.type == "weekly_report_failed")
        .one()
    )
    assert event.account_id == test_user.id
    assert event.url == f"/dashboard/reports?locationId={test_location.id}"
    assert "report storage unavailable" in event.body

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_weekly_report_job_notifies_admin_on_top_level_failure(
    db, monkeypatch
):
    admin = _admin_account(db)

    class ExplodingReportingService:
        def __init__(self, _db):
            raise RuntimeError("reporting service bootstrap failed")

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(worker_scheduler, "ReportingService", ExplodingReportingService)

    await worker_scheduler.weekly_report_job()

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == admin.id)
        .filter(NotificationEvent.type == "weekly_report_job_failed")
        .one()
    )
    assert event.url == "/admin"
    assert "reporting service bootstrap failed" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_publisher_job_persists_failure_and_notifies_account(
    db, test_user, test_location, monkeypatch
):
    post = Post(
        id=uuid4(),
        location_id=test_location.id,
        platform=Platform.INSTAGRAM,
        status=PostStatus.APPROVED,
        title="Publish this later",
        body="Caption without image",
    )
    channel = Channel(
        id=uuid4(),
        location_id=test_location.id,
        type=ChannelType.INSTAGRAM,
        status=ChannelStatus.CONNECTED,
        is_active=True,
    )
    channel.set_credentials({"access_token": "ig-token", "ig_user_id": "ig-user-123"})

    db.add_all([post, channel])
    db.commit()

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(NotificationService, "send_email", fake_send_email)

    await worker_scheduler.publisher_job()

    db.refresh(post)
    db.refresh(channel)
    publish_job = db.query(PublishJob).filter(PublishJob.post_id == post.id).one()

    assert post.status == PostStatus.FAILED
    assert post.error_message == "Instagram publishing requires an image"
    assert channel.status == ChannelStatus.ERROR
    assert channel.error_message == "Instagram publishing requires an image"
    assert publish_job.status == PublishJobStatus.FAILED
    assert publish_job.last_error == "Instagram publishing requires an image"

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id)
        .filter(NotificationEvent.type == "publish_job_failed")
        .one()
    )
    assert event.url == f"/dashboard/content/{post.id}"
    assert "Instagram publishing requires an image" in event.body

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "email"
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_publisher_job_notifies_admin_on_top_level_failure(
    db, monkeypatch
):
    admin = _admin_account(db)

    async def fake_publish_queued_posts(self):
        raise RuntimeError("publisher queue unavailable")

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr("app.services.publisher.PublisherService.publish_queued_posts", fake_publish_queued_posts)

    await worker_scheduler.publisher_job()

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == admin.id)
        .filter(NotificationEvent.type == "publish_worker_failed")
        .one()
    )
    assert event.url == "/admin"
    assert "publisher queue unavailable" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_payment_retry_job_recovers_subscription_and_notifies(
    db, test_user, monkeypatch
):
    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.PAST_DUE,
        access_state="warning",
        dunning_status=DunningStatus.RETRYING,
        dunning_started_at=utc_now_naive() - timedelta(days=2),
        payment_retry_count=2,
        next_payment_retry_at=utc_now_naive() - timedelta(minutes=5),
        stripe_customer_id="cus_retry_success",
        stripe_subscription_id="sub_retry_success",
    )
    db.add(subscription)
    db.commit()

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    invoice = SimpleNamespace(id="in_retry_success")

    class FakeInvoiceApi:
        @staticmethod
        def list(**kwargs):
            return SimpleNamespace(data=[invoice])

        @staticmethod
        def pay(invoice_id):
            assert invoice_id == "in_retry_success"
            return invoice

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)
    monkeypatch.setattr(DunningService, "_get_customer_portal_url", lambda self, subscription: "/dashboard/billing")
    monkeypatch.setattr("stripe.Invoice", FakeInvoiceApi)

    await worker_scheduler.payment_retry_job()

    db.refresh(subscription)
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.access_state == "active"
    assert subscription.dunning_status == DunningStatus.NONE
    assert subscription.payment_retry_count == 0

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id, NotificationEvent.type == "billing_payment_recovered")
        .one()
    )
    assert event.url == "/dashboard/billing"


@pytest.mark.asyncio
async def test_payment_retry_job_notifies_when_billing_service_errors(
    db, test_user, monkeypatch
):
    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.PAST_DUE,
        access_state="warning",
        dunning_status=DunningStatus.RETRYING,
        dunning_started_at=utc_now_naive() - timedelta(days=1),
        payment_retry_count=1,
        next_payment_retry_at=utc_now_naive() - timedelta(minutes=5),
        stripe_customer_id="cus_retry_error",
        stripe_subscription_id="sub_retry_error",
    )
    db.add(subscription)
    db.commit()

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    class FakeInvoiceApi:
        @staticmethod
        def list(**kwargs):
            raise RuntimeError("Stripe API unavailable")

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)
    monkeypatch.setattr(DunningService, "_get_customer_portal_url", lambda self, subscription: "/dashboard/billing")
    monkeypatch.setattr("stripe.Invoice", FakeInvoiceApi)

    await worker_scheduler.payment_retry_job()

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_user.id,
            NotificationEvent.type == "billing_payment_retry_job_failed",
        )
        .one()
    )
    assert event.url == "/dashboard/billing"
    assert "stripe api unavailable" in event.body.lower()


@pytest.mark.asyncio
async def test_analytics_collect_job_notifies_on_collection_failures(
    db, test_user, test_location, monkeypatch
):
    async def fake_collect_all(self):
        return {
            "success": 0,
            "failed": 1,
            "errors": [
                {
                    "location_id": str(test_location.id),
                    "error": "GBP token expired",
                }
            ],
        }

    async def fake_calculate_score(self, **kwargs):
        return None

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(AnalyticsService, "collect_all", fake_collect_all)
    monkeypatch.setattr(SEOService, "calculate_score", fake_calculate_score)

    await worker_scheduler.analytics_collect_job()

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id)
        .filter(NotificationEvent.type == "analytics_collection_failed")
        .one()
    )
    assert event.url == f"/dashboard/analytics?locationId={test_location.id}"
    assert "GBP token expired" in event.body
    assert test_location.name in event.body

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_analytics_collect_job_notifies_on_seo_score_failure(
    db, test_user, test_location, monkeypatch
):
    async def fake_collect_all(self):
        return {"success": 1, "failed": 0, "errors": []}

    async def fake_calculate_score(self, **kwargs):
        raise RuntimeError("seo scoring unavailable")

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(AnalyticsService, "collect_all", fake_collect_all)
    monkeypatch.setattr(SEOService, "calculate_score", fake_calculate_score)

    await worker_scheduler.analytics_collect_job()

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id)
        .filter(NotificationEvent.type == "seo_score_calculation_failed")
        .one()
    )
    assert event.url == f"/dashboard/seo?locationId={test_location.id}"
    assert "seo scoring unavailable" in event.body.lower()
    assert "covering" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_dunning_check_job_notifies_admin_on_top_level_failure(
    db, monkeypatch
):
    admin = _admin_account(db)

    async def fake_check_grace_period_expiry(self):
        raise RuntimeError("billing table locked")

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(DunningService, "check_grace_period_expiry", fake_check_grace_period_expiry)

    await worker_scheduler.dunning_check_job()

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == admin.id)
        .filter(NotificationEvent.type == "billing_dunning_job_failed")
        .one()
    )
    assert event.url == "/admin"
    assert "billing table locked" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_payment_retry_job_notifies_admin_on_top_level_failure(
    db, monkeypatch
):
    admin = _admin_account(db)

    class ExplodingDunningService:
        def __init__(self, _db):
            raise RuntimeError("dunning service bootstrap failed")

    monkeypatch.setattr(worker_scheduler, "get_db", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr("app.services.dunning_service.DunningService", ExplodingDunningService)

    await worker_scheduler.payment_retry_job()

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == admin.id)
        .filter(NotificationEvent.type == "billing_payment_retry_worker_failed")
        .one()
    )
    assert event.url == "/admin"
    assert "dunning service bootstrap failed" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"
