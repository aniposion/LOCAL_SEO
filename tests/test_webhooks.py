from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.account import Account, AccountRole
from app.models.billing import (
    BillingAuditAction,
    BillingAuditLog,
    Dispute,
    DisputeStatus,
    Payment,
    PaymentStatus,
    Refund,
    RefundReason,
    RefundStatus,
)
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.subscription import (
    DunningStatus,
    PaymentHistory,
    PlanType,
    Subscription,
    SubscriptionStatus,
)


def _admin_account(db) -> Account:
    admin = Account(
        id=uuid4(),
        email="billing-admin@example.com",
        password_hash=get_password_hash("Adminpassword123!"),
        role=AccountRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.mark.asyncio
async def test_gbp_new_review_webhook_creates_notification(client, db, test_location, monkeypatch):
    test_location.gbp_location_id = "locations/456"
    db.commit()

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    response = client.post(
        "/webhooks/gbp-notifications",
        json={
            "type": "NEW_REVIEW",
            "review": {
                "name": "accounts/123/locations/456/reviews/789",
                "starRating": "FIVE",
                "comment": "Amazing service and very friendly staff.",
                "reviewer": {"displayName": "Jordan"},
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "received"}

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_location.account_id)
        .one()
    )
    assert event.type == "gbp_new_review"
    assert event.title == "New Google review (FIVE)"
    assert "Jordan left a new review" in event.body
    assert event.url == "/dashboard/reviews"

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_gbp_new_question_webhook_creates_notification(client, db, test_location, monkeypatch):
    test_location.gbp_location_id = "accounts/123/locations/456"
    db.commit()

    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    response = client.post(
        "/webhooks/gbp-notifications",
        json={
            "type": "NEW_QUESTION",
            "question": {
                "name": "accounts/123/locations/456/questions/1",
                "text": "Do you have weekend appointments?",
                "author": {"displayName": "Casey"},
            },
        },
    )

    assert response.status_code == 200

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_location.account_id)
        .one()
    )
    assert event.type == "gbp_new_question"
    assert event.title == "New GBP question"
    assert "Casey asked a new Google Business Profile question." in event.body
    assert "weekend appointments" in event.body
    assert event.url == "/dashboard/qa"


@pytest.mark.asyncio
async def test_gbp_webhook_without_matching_location_does_not_create_notification(client, db, monkeypatch):
    async def fake_send_email(self, **kwargs):
        return {"success": True, "provider": "fake-email"}

    monkeypatch.setattr("app.services.notification.NotificationService.send_email", fake_send_email)

    response = client.post(
        "/webhooks/gbp-notifications",
        json={
            "type": "NEW_REVIEW",
            "review": {
                "name": "accounts/123/locations/999/reviews/789",
                "comment": "No matching location",
            },
        },
    )

    assert response.status_code == 200
    assert db.query(NotificationEvent).count() == 0
    assert db.query(NotificationDeliveryLog).count() == 0


@pytest.mark.asyncio
async def test_stripe_invoice_payment_failed_uses_billing_workflow(db, test_user, monkeypatch):
    from app.routers.webhooks import process_stripe_event

    async def fake_send_dunning_email(self, subscription, attempt):
        return None

    monkeypatch.setattr(
        "app.services.dunning_service.DunningService._send_dunning_email",
        fake_send_dunning_email,
    )

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.ACTIVE,
        access_state="active",
        stripe_customer_id="cus_webhook_failed",
        stripe_subscription_id="sub_webhook_failed",
        current_period_start=datetime.now(UTC),
        current_period_end=datetime.now(UTC) + timedelta(days=30),
        locations_limit=1,
        posts_per_month=30,
        api_calls_per_day=500,
    )
    db.add(subscription)
    db.commit()

    invoice = SimpleNamespace(
        id="in_webhook_failed",
        customer="cus_webhook_failed",
        subscription="sub_webhook_failed",
        amount_due=9900,
        currency="usd",
        attempt_count=2,
        last_finalization_error=SimpleNamespace(message="card declined"),
    )
    event = SimpleNamespace(
        type="invoice.payment_failed",
        data=SimpleNamespace(object=invoice),
    )

    await process_stripe_event(event, db)

    db.refresh(subscription)

    payment = (
        db.query(PaymentHistory)
        .filter(PaymentHistory.stripe_invoice_id == "in_webhook_failed")
        .one()
    )
    assert payment.status == "failed"
    assert payment.amount == 99.0

    assert subscription.status == SubscriptionStatus.PAST_DUE
    assert subscription.access_state == "warning"
    assert subscription.dunning_status == DunningStatus.RETRYING
    assert subscription.payment_retry_count == 2
    assert subscription.last_payment_error == "card declined"

    audit = (
        db.query(BillingAuditLog)
        .filter(BillingAuditLog.action == BillingAuditAction.PAYMENT_FAILED)
        .one()
    )
    assert audit.entity_id == "in_webhook_failed"
    assert audit.new_value["attempt_count"] == 2
    assert audit.new_value["failure_message"] == "card declined"


@pytest.mark.asyncio
async def test_stripe_invoice_payment_succeeded_uses_billing_workflow(db, test_user, monkeypatch):
    from app.routers.webhooks import process_stripe_event

    sent_receipt: dict[str, object] = {}

    class FakeEmailService:
        async def send_payment_receipt(self, to, payment_data):
            sent_receipt["to"] = to
            sent_receipt["payment_data"] = payment_data

    async def fake_send_recovery_email(self, subscription, previous_state):
        return None

    def fake_process_payment(account_id, plan, payment_date=None):
        return {"credits_allocated": 250}

    monkeypatch.setattr(
        "app.services.dunning_service.DunningService._send_recovery_email",
        fake_send_recovery_email,
    )
    monkeypatch.setattr("app.services.billing.get_email_service", lambda: FakeEmailService())
    monkeypatch.setattr("app.services.billing.credits_service.process_payment", fake_process_payment)

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.PRO,
        status=SubscriptionStatus.PAST_DUE,
        access_state="warning",
        dunning_status=DunningStatus.RETRYING,
        dunning_started_at=datetime.now(UTC) - timedelta(days=2),
        payment_retry_count=2,
        last_payment_error="card declined",
        stripe_customer_id="cus_webhook_paid",
        stripe_subscription_id="sub_webhook_paid",
        stripe_price_id="price_pro_monthly",
        current_period_start=datetime.now(UTC) - timedelta(days=28),
        current_period_end=datetime.now(UTC) + timedelta(days=2),
        locations_limit=1,
        posts_per_month=60,
        api_calls_per_day=1000,
    )
    db.add(subscription)
    db.commit()

    invoice = SimpleNamespace(
        id="in_webhook_paid",
        customer="cus_webhook_paid",
        subscription="sub_webhook_paid",
        payment_intent="pi_webhook_paid",
        amount_paid=14900,
        currency="usd",
        hosted_invoice_url="https://stripe.example/invoices/in_webhook_paid",
        receipt_url="https://stripe.example/receipts/pi_webhook_paid",
    )
    event = SimpleNamespace(
        type="invoice.payment_succeeded",
        data=SimpleNamespace(object=invoice),
    )

    await process_stripe_event(event, db)

    db.refresh(subscription)

    payment = (
        db.query(PaymentHistory)
        .filter(PaymentHistory.stripe_invoice_id == "in_webhook_paid")
        .one()
    )
    assert payment.status == "succeeded"
    assert payment.amount == 149.0
    assert payment.stripe_payment_intent_id == "pi_webhook_paid"

    assert subscription.status == SubscriptionStatus.ACTIVE
    assert subscription.access_state == "active"
    assert subscription.dunning_status == DunningStatus.NONE
    assert subscription.payment_retry_count == 0
    assert subscription.last_payment_error is None

    audit = (
        db.query(BillingAuditLog)
        .filter(BillingAuditLog.action == BillingAuditAction.PAYMENT_SUCCEEDED)
        .one()
    )
    assert audit.entity_id == "in_webhook_paid"
    assert audit.new_value["payment_intent"] == "pi_webhook_paid"
    assert audit.new_value["amount"] == 149.0

    assert sent_receipt["to"] == test_user.email
    assert sent_receipt["payment_data"]["invoice_number"] == "in_webhook_paid"


@pytest.mark.asyncio
async def test_stripe_invoice_payment_succeeded_notifies_admin_when_receipt_email_fails(
    db, test_user, monkeypatch
):
    from app.routers.webhooks import process_stripe_event

    admin = _admin_account(db)

    class FailingEmailService:
        async def send_payment_receipt(self, to, payment_data):
            raise RuntimeError("receipt smtp offline")

    async def fake_send_recovery_email(self, subscription, previous_state):
        return None

    def fake_process_payment(account_id, plan, payment_date=None):
        return {"credits_allocated": 250}

    monkeypatch.setattr(
        "app.services.dunning_service.DunningService._send_recovery_email",
        fake_send_recovery_email,
    )
    monkeypatch.setattr("app.services.billing.get_email_service", lambda: FailingEmailService())
    monkeypatch.setattr("app.services.billing.credits_service.process_payment", fake_process_payment)

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.PRO,
        status=SubscriptionStatus.PAST_DUE,
        access_state="warning",
        dunning_status=DunningStatus.RETRYING,
        dunning_started_at=datetime.now(UTC) - timedelta(days=2),
        payment_retry_count=2,
        last_payment_error="card declined",
        stripe_customer_id="cus_webhook_paid_email_fail",
        stripe_subscription_id="sub_webhook_paid_email_fail",
        stripe_price_id="price_pro_monthly",
        current_period_start=datetime.now(UTC) - timedelta(days=28),
        current_period_end=datetime.now(UTC) + timedelta(days=2),
        locations_limit=1,
        posts_per_month=60,
        api_calls_per_day=1000,
    )
    db.add(subscription)
    db.commit()

    invoice = SimpleNamespace(
        id="in_webhook_paid_email_fail",
        customer="cus_webhook_paid_email_fail",
        subscription="sub_webhook_paid_email_fail",
        payment_intent="pi_webhook_paid_email_fail",
        amount_paid=14900,
        currency="usd",
        hosted_invoice_url="https://stripe.example/invoices/in_webhook_paid_email_fail",
        receipt_url="https://stripe.example/receipts/pi_webhook_paid_email_fail",
    )
    event = SimpleNamespace(
        type="invoice.payment_succeeded",
        data=SimpleNamespace(object=invoice),
    )

    await process_stripe_event(event, db)

    admin_event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == admin.id,
            NotificationEvent.type == "billing_receipt_email_failed",
        )
        .one()
    )
    assert admin_event.url == "/admin"
    assert "billing receipt email failed" in admin_event.title.lower()
    assert "receipt smtp offline" in admin_event.body.lower()
    assert test_user.email in admin_event.body

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == admin_event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_stripe_dispute_created_uses_billing_workflow(db, test_user):
    from app.routers.webhooks import process_stripe_event

    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.PRO,
        status=SubscriptionStatus.ACTIVE,
        access_state="active",
        stripe_customer_id="cus_webhook_dispute_created",
        stripe_subscription_id="sub_webhook_dispute_created",
        stripe_price_id="price_pro_monthly",
        current_period_start=datetime.now(UTC) - timedelta(days=10),
        current_period_end=datetime.now(UTC) + timedelta(days=20),
        locations_limit=1,
        posts_per_month=60,
        api_calls_per_day=1000,
    )
    db.add(subscription)
    db.flush()

    payment = Payment(
        account_id=test_user.id,
        stripe_payment_intent_id="pi_webhook_dispute_created",
        stripe_charge_id="ch_webhook_dispute_created",
        amount=14900,
        currency="usd",
        status=PaymentStatus.SUCCEEDED,
        description="Monthly PRO subscription",
    )
    db.add(payment)
    db.commit()

    dispute_due_by = datetime.now(UTC) + timedelta(days=7)
    event = SimpleNamespace(
        type="charge.dispute.created",
        data=SimpleNamespace(
            object=SimpleNamespace(
                id="dp_webhook_created",
                charge="ch_webhook_dispute_created",
                payment_intent="pi_webhook_dispute_created",
                amount=14900,
                currency="usd",
                status="needs_response",
                reason="subscription_canceled",
                evidence_details=SimpleNamespace(due_by=int(dispute_due_by.timestamp())),
            )
        ),
    )

    await process_stripe_event(event, db)

    dispute_record = (
        db.query(Dispute)
        .filter(Dispute.stripe_dispute_id == "dp_webhook_created")
        .one()
    )
    assert dispute_record.account_id == test_user.id
    assert dispute_record.payment_id == payment.id
    assert dispute_record.status == DisputeStatus.NEEDS_RESPONSE
    assert dispute_record.evidence_snapshot["customer_email"] == test_user.email
    assert dispute_record.evidence_snapshot["plan_at_dispute"] == "pro"

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.action == BillingAuditAction.DISPUTE_CREATED,
            BillingAuditLog.entity_id == "dp_webhook_created",
        )
        .one()
    )
    assert audit.account_id == test_user.id
    assert audit.new_value["amount"] == 14900
    assert audit.new_value["reason"] == "subscription_canceled"


@pytest.mark.asyncio
async def test_stripe_dispute_updated_uses_billing_workflow(db, test_user):
    from app.routers.webhooks import process_stripe_event

    payment = Payment(
        account_id=test_user.id,
        stripe_payment_intent_id="pi_webhook_dispute_updated",
        stripe_charge_id="ch_webhook_dispute_updated",
        amount=14900,
        currency="usd",
        status=PaymentStatus.SUCCEEDED,
        description="Monthly PRO subscription",
    )
    db.add(payment)
    db.flush()

    dispute_record = Dispute(
        account_id=test_user.id,
        payment_id=payment.id,
        stripe_dispute_id="dp_webhook_updated",
        stripe_charge_id="ch_webhook_dispute_updated",
        stripe_payment_intent_id="pi_webhook_dispute_updated",
        amount=14900,
        currency="usd",
        status=DisputeStatus.NEEDS_RESPONSE,
    )
    db.add(dispute_record)
    db.commit()

    event = SimpleNamespace(
        type="charge.dispute.updated",
        data=SimpleNamespace(
            object=SimpleNamespace(
                id="dp_webhook_updated",
                status="under_review",
            )
        ),
    )

    await process_stripe_event(event, db)

    db.refresh(dispute_record)
    assert dispute_record.status == DisputeStatus.UNDER_REVIEW

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.action == BillingAuditAction.DISPUTE_UPDATED,
            BillingAuditLog.entity_id == "dp_webhook_updated",
        )
        .one()
    )
    assert audit.account_id == test_user.id
    assert audit.old_value["status"] == "needs_response"
    assert audit.new_value["status"] == "under_review"


@pytest.mark.asyncio
async def test_stripe_charge_refunded_uses_billing_workflow(db, test_user):
    from app.routers.webhooks import process_stripe_event

    payment = Payment(
        account_id=test_user.id,
        stripe_payment_intent_id="pi_webhook_refund",
        stripe_charge_id="ch_webhook_refund",
        amount=14900,
        currency="usd",
        status=PaymentStatus.SUCCEEDED,
        description="Monthly PRO subscription",
    )
    db.add(payment)
    db.commit()

    event = SimpleNamespace(
        type="charge.refunded",
        data=SimpleNamespace(
            object=SimpleNamespace(
                id="ch_webhook_refund",
                payment_intent="pi_webhook_refund",
                refunds=SimpleNamespace(
                    data=[
                        SimpleNamespace(
                            id="re_webhook_refund",
                            amount=14900,
                            currency="usd",
                            status="succeeded",
                            reason="requested_by_customer",
                        )
                    ]
                ),
            )
        ),
    )

    await process_stripe_event(event, db)

    refund_record = (
        db.query(Refund)
        .filter(Refund.stripe_refund_id == "re_webhook_refund")
        .one()
    )
    assert refund_record.account_id == test_user.id
    assert refund_record.payment_id == payment.id
    assert refund_record.status == RefundStatus.SUCCEEDED
    assert refund_record.reason == RefundReason.REQUESTED_BY_CUSTOMER
    assert refund_record.amount == 14900

    db.refresh(payment)
    assert payment.status == PaymentStatus.REFUNDED
    assert payment.amount_refunded == 14900

    audit = (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.action == BillingAuditAction.REFUND_CREATED,
            BillingAuditLog.entity_id == "re_webhook_refund",
        )
        .one()
    )
    assert audit.account_id == test_user.id
    assert audit.new_value["amount"] == 14900
    assert audit.new_value["reason"] == "requested_by_customer"


@pytest.mark.asyncio
async def test_stripe_charge_refunded_skips_unknown_billing_payment_and_notifies_admin(db):
    from app.routers.webhooks import process_stripe_event

    admin = _admin_account(db)

    event = SimpleNamespace(
        type="charge.refunded",
        data=SimpleNamespace(
            object=SimpleNamespace(
                id="ch_webhook_unknown_refund",
                payment_intent="pi_webhook_unknown_refund",
                refunds=SimpleNamespace(
                    data=[
                        SimpleNamespace(
                            id="re_webhook_unknown_refund",
                            amount=9900,
                            currency="usd",
                            status="succeeded",
                            reason="requested_by_customer",
                        )
                    ]
                ),
            )
        ),
    )

    await process_stripe_event(event, db)

    assert (
        db.query(Refund)
        .filter(Refund.stripe_refund_id == "re_webhook_unknown_refund")
        .count()
        == 0
    )
    assert (
        db.query(BillingAuditLog)
        .filter(
            BillingAuditLog.action == BillingAuditAction.REFUND_CREATED,
            BillingAuditLog.entity_id == "re_webhook_unknown_refund",
        )
        .count()
        == 0
    )
    admin_event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == admin.id,
            NotificationEvent.type == "stripe_refund_unmatched",
        )
        .one()
    )
    assert admin_event.url == "/admin"
    assert "stripe refund unmatched" in admin_event.title.lower()
    assert "pi_webhook_unknown_refund" in admin_event.body
    assert "re_webhook_unknown_refund" in admin_event.body

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == admin_event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"


@pytest.mark.asyncio
async def test_stripe_trial_will_end_notifies_admin_when_trial_ending_email_fails(
    db, test_user, monkeypatch
):
    from app.routers.webhooks import process_stripe_event

    admin = _admin_account(db)

    class FailingEmailService:
        async def send_email(self, **_kwargs):
            raise RuntimeError("trial smtp offline")

    monkeypatch.setattr("app.services.billing.get_email_service", lambda: FailingEmailService())
    monkeypatch.setattr(
        "app.services.billing.stripe.PaymentMethod.list",
        lambda **_kwargs: SimpleNamespace(data=[]),
    )

    trial_end = datetime.now(UTC) + timedelta(days=3)
    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.PRO,
        status=SubscriptionStatus.TRIALING,
        access_state="active",
        stripe_customer_id="cus_trial_ending_email_fail",
        stripe_subscription_id="sub_trial_ending_email_fail",
        stripe_price_id="price_pro_monthly",
        trial_end=trial_end,
        current_period_start=datetime.now(UTC) - timedelta(days=27),
        current_period_end=trial_end,
        locations_limit=1,
        posts_per_month=60,
        api_calls_per_day=1000,
    )
    db.add(subscription)
    db.commit()

    event = SimpleNamespace(
        type="customer.subscription.trial_will_end",
        data=SimpleNamespace(
            object=SimpleNamespace(
                id="sub_trial_ending_email_fail",
                trial_end=int(trial_end.timestamp()),
            )
        ),
    )

    await process_stripe_event(event, db)

    admin_event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == admin.id,
            NotificationEvent.type == "billing_trial_ending_email_failed",
        )
        .one()
    )
    assert admin_event.url == "/admin"
    assert "billing trial ending email failed" in admin_event.title.lower()
    assert "trial smtp offline" in admin_event.body.lower()
    assert test_user.email in admin_event.body
    assert "sub_trial_ending_email_fail" in admin_event.body

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == admin_event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"
