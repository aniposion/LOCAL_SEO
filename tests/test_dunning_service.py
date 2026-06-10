from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.core.time import utc_now_naive
from app.models.account import Account, AccountRole
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.subscription import DunningStatus, PlanType, Subscription, SubscriptionStatus
from app.services.dunning_service import DUNNING_CONFIG, DunningService


def _stub_track_event(*_args, **_kwargs):
    return None


def _admin_account(db) -> Account:
    admin = Account(
        id=uuid4(),
        email="dunning-admin@example.com",
        password_hash=get_password_hash("Adminpassword123!"),
        role=AccountRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.mark.asyncio
async def test_handle_payment_failure_sets_retry_state(db, test_user, monkeypatch):
    monkeypatch.setattr("app.services.analytics_service.track_event", _stub_track_event)

    async def fake_send_dunning_email(self, subscription, attempt):
        return None

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr(DunningService, "_send_dunning_email", fake_send_dunning_email)
    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.ACTIVE,
        access_state="active",
        dunning_status=DunningStatus.NONE,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    service = DunningService(db)
    await service.handle_payment_failure(
        subscription,
        failure_message="card_declined",
        attempt_count=1,
    )

    assert subscription.access_state == "warning"
    assert subscription.status == SubscriptionStatus.PAST_DUE
    assert subscription.dunning_status == DunningStatus.RETRYING
    assert subscription.payment_retry_count == 1
    assert subscription.last_payment_error == "card_declined"
    assert subscription.dunning_started_at is not None
    assert subscription.next_payment_retry_at == (
        subscription.dunning_started_at + timedelta(days=DUNNING_CONFIG["retry_schedule_days"][0])
    )
    assert subscription.grace_period_ends_at is None

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id, NotificationEvent.type == "billing_payment_failed")
        .one()
    )
    assert event.url == "/dashboard/billing"
    assert "retry attempt 1" in event.body.lower()

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_handle_payment_failure_enters_grace_period_after_retries(db, test_user, monkeypatch):
    monkeypatch.setattr("app.services.analytics_service.track_event", _stub_track_event)

    async def fake_send_grace_period_email(self, subscription):
        return None

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr(DunningService, "_send_grace_period_email", fake_send_grace_period_email)
    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.PAST_DUE,
        access_state="warning",
        dunning_status=DunningStatus.RETRYING,
        dunning_started_at=utc_now_naive(),
        payment_retry_count=3,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    service = DunningService(db)
    await service.handle_payment_failure(
        subscription,
        failure_message="hard_decline",
        attempt_count=len(DUNNING_CONFIG["retry_schedule_days"]) + 1,
    )

    assert subscription.access_state == "warning"
    assert subscription.dunning_status == DunningStatus.GRACE_PERIOD
    assert subscription.next_payment_retry_at is None
    assert subscription.grace_period_ends_at is not None
    assert subscription.grace_period_ends_at.date() == (
        subscription.dunning_started_at + timedelta(days=DUNNING_CONFIG["grace_period_days"])
    ).date()

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_user.id,
            NotificationEvent.type == "billing_grace_period_started",
        )
        .one()
    )
    assert event.url == "/dashboard/billing"
    assert "grace period" in event.title.lower()


@pytest.mark.asyncio
async def test_dunning_checks_promote_restricted_then_suspended(db, test_user, monkeypatch):
    monkeypatch.setattr("app.services.analytics_service.track_event", _stub_track_event)

    async def fake_send_restriction_email(self, subscription):
        return None

    async def fake_send_suspension_email(self, subscription):
        return None

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr(DunningService, "_send_restriction_email", fake_send_restriction_email)
    monkeypatch.setattr(DunningService, "_send_suspension_email", fake_send_suspension_email)
    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.PRO,
        status=SubscriptionStatus.PAST_DUE,
        access_state="warning",
        dunning_status=DunningStatus.GRACE_PERIOD,
        dunning_started_at=utc_now_naive() - timedelta(days=15),
        grace_period_ends_at=utc_now_naive() - timedelta(days=1),
        payment_retry_count=4,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    service = DunningService(db)
    restricted_ids = await service.check_grace_period_expiry()

    assert restricted_ids == [subscription.id]
    assert subscription.dunning_status == DunningStatus.RESTRICTED
    assert subscription.access_state == "warning"

    suspended_ids = await service.check_suspension()

    assert suspended_ids == [subscription.id]
    assert subscription.dunning_status == DunningStatus.SUSPENDED
    assert subscription.access_state == "suspended"
    assert subscription.status == SubscriptionStatus.CANCELED
    assert subscription.ended_at is not None

    event_types = {
        event.type
        for event in db.query(NotificationEvent).filter(NotificationEvent.account_id == test_user.id).all()
    }
    assert "billing_access_restricted" in event_types
    assert "billing_subscription_suspended" in event_types


@pytest.mark.asyncio
async def test_handle_payment_success_skips_recovery_email_for_healthy_subscription(
    db,
    test_user,
    monkeypatch,
):
    monkeypatch.setattr("app.services.analytics_service.track_event", _stub_track_event)
    recovery_calls: list[str] = []

    async def fake_send_recovery_email(self, subscription, previous_state):
        recovery_calls.append(previous_state)
        return None

    monkeypatch.setattr(DunningService, "_send_recovery_email", fake_send_recovery_email)

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.ACTIVE,
        access_state="active",
        dunning_status=DunningStatus.NONE,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    service = DunningService(db)
    await service.handle_payment_success(subscription)

    assert recovery_calls == []
    assert subscription.access_state == "active"
    assert subscription.dunning_status == DunningStatus.NONE
    assert subscription.payment_retry_count == 0


@pytest.mark.asyncio
async def test_handle_payment_success_notifies_when_recovered(db, test_user, monkeypatch):
    monkeypatch.setattr("app.services.analytics_service.track_event", _stub_track_event)

    async def fake_send_recovery_email(self, subscription, previous_state):
        return None

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr(DunningService, "_send_recovery_email", fake_send_recovery_email)
    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.PAST_DUE,
        access_state="warning",
        dunning_status=DunningStatus.RETRYING,
        dunning_started_at=utc_now_naive() - timedelta(days=2),
        payment_retry_count=2,
        last_payment_error="card declined",
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    service = DunningService(db)
    await service.handle_payment_success(subscription)

    assert subscription.access_state == "active"
    assert subscription.dunning_status == DunningStatus.NONE
    assert subscription.payment_retry_count == 0

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == test_user.id,
            NotificationEvent.type == "billing_payment_recovered",
        )
        .one()
    )
    assert event.url == "/dashboard/billing"
    assert "account restored" in event.title.lower()


@pytest.mark.asyncio
async def test_handle_payment_success_notifies_admin_when_recovery_email_fails(
    db, test_user, monkeypatch
):
    admin = _admin_account(db)
    monkeypatch.setattr("app.services.analytics_service.track_event", _stub_track_event)

    async def fake_notification_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    async def failing_recovery_email(self, **kwargs):
        raise RuntimeError("smtp offline")

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_notification_email)
    monkeypatch.setattr("app.services.email_service.EmailService.send_email", failing_recovery_email)

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.PAST_DUE,
        access_state="warning",
        dunning_status=DunningStatus.RETRYING,
        dunning_started_at=utc_now_naive() - timedelta(days=2),
        payment_retry_count=2,
        last_payment_error="card declined",
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    service = DunningService(db)
    await service.handle_payment_success(subscription)

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == admin.id,
            NotificationEvent.type == "billing_lifecycle_email_failed",
        )
        .one()
    )
    assert event.url == "/admin"
    assert "billing recovery email failed" in event.title.lower()
    assert "smtp offline" in event.body.lower()
    assert test_user.email in event.body

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"
