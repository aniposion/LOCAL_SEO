"""P0 tests for Stripe webhook idempotency."""

from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.account import Account, AccountRole
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.stripe_event import StripeEvent


def _build_fake_event(event_id: str, event_type: str) -> SimpleNamespace:
    """Create a Stripe-like event object for webhook tests."""
    payload = {
        "id": event_id,
        "type": event_type,
        "data": {"object": {"id": "obj_test_123"}},
    }
    event = SimpleNamespace(
        id=event_id,
        type=event_type,
        data=SimpleNamespace(object=SimpleNamespace(id="obj_test_123")),
    )
    event.to_dict = lambda: payload
    return event


def _admin_account(db: Session) -> Account:
    admin = Account(
        id=uuid4(),
        email="stripe-webhook-admin@example.com",
        password_hash=get_password_hash("Adminpassword123!"),
        role=AccountRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def test_webhook_idempotency_duplicate_event(
    client: TestClient,
    db: Session,
    monkeypatch,
) -> None:
    """Duplicate webhook deliveries should create one DB record and one side effect."""
    fake_event = _build_fake_event("evt_test_12345", "invoice.payment_succeeded")
    processed: list[str] = []

    def fake_construct_event(payload, sig_header, secret):
        assert sig_header == "test_signature"
        return fake_event

    async def fake_process(event, db_session):
        processed.append(event.id)

    monkeypatch.setattr("stripe.Webhook.construct_event", fake_construct_event)
    monkeypatch.setattr("app.routers.webhooks.process_stripe_event", fake_process)

    response1 = client.post(
        "/webhooks/stripe",
        json={"id": fake_event.id},
        headers={"stripe-signature": "test_signature"},
    )
    assert response1.status_code == 200
    assert response1.json() == {"status": "success", "processed": True}

    response2 = client.post(
        "/webhooks/stripe",
        json={"id": fake_event.id},
        headers={"stripe-signature": "test_signature"},
    )
    assert response2.status_code == 200
    assert response2.json() == {"status": "duplicate", "processed": False}

    event_count = db.query(StripeEvent).filter_by(event_id=fake_event.id).count()
    assert event_count == 1
    assert processed == [fake_event.id]


def test_webhook_idempotency_five_duplicates(
    client: TestClient,
    db: Session,
    monkeypatch,
) -> None:
    """Five duplicate deliveries should still produce exactly one stored event."""
    fake_event = _build_fake_event("evt_test_99999", "customer.subscription.updated")
    processed: list[str] = []

    def fake_construct_event(payload, sig_header, secret):
        return fake_event

    async def fake_process(event, db_session):
        processed.append(event.id)

    monkeypatch.setattr("stripe.Webhook.construct_event", fake_construct_event)
    monkeypatch.setattr("app.routers.webhooks.process_stripe_event", fake_process)

    for _ in range(5):
        response = client.post(
            "/webhooks/stripe",
            json={"id": fake_event.id},
            headers={"stripe-signature": "test_signature"},
        )
        assert response.status_code == 200

    event_count = db.query(StripeEvent).filter_by(event_id=fake_event.id).count()
    assert event_count == 1
    assert processed == [fake_event.id]


def test_webhook_processing_error_is_recorded_once(
    client: TestClient,
    db: Session,
    monkeypatch,
) -> None:
    """Processing failures should still record the event and dedupe retries."""
    fake_event = _build_fake_event("evt_test_error", "invoice.payment_failed")
    attempts: list[str] = []

    def fake_construct_event(payload, sig_header, secret):
        return fake_event

    async def fake_process(event, db_session):
        attempts.append(event.id)
        raise RuntimeError("processing failed")

    monkeypatch.setattr("stripe.Webhook.construct_event", fake_construct_event)
    monkeypatch.setattr("app.routers.webhooks.process_stripe_event", fake_process)

    response1 = client.post(
        "/webhooks/stripe",
        json={"id": fake_event.id},
        headers={"stripe-signature": "test_signature"},
    )
    assert response1.status_code == 200
    assert response1.json()["status"] == "error"
    assert response1.json()["processed"] is False

    response2 = client.post(
        "/webhooks/stripe",
        json={"id": fake_event.id},
        headers={"stripe-signature": "test_signature"},
    )
    assert response2.status_code == 200
    assert response2.json() == {"status": "duplicate", "processed": False}

    event_count = db.query(StripeEvent).filter_by(event_id=fake_event.id).count()
    assert event_count == 1
    assert attempts == [fake_event.id]


def test_webhook_processing_error_notifies_active_admin_once(
    client: TestClient,
    db: Session,
    monkeypatch,
) -> None:
    """A signed webhook failure should create one admin inbox alert despite duplicate deliveries."""
    admin = _admin_account(db)
    fake_event = _build_fake_event("evt_test_error_notify", "invoice.payment_failed")

    def fake_construct_event(payload, sig_header, secret):
        assert sig_header == "test_signature"
        return fake_event

    async def fake_process(event, db_session):
        raise RuntimeError("billing projector crashed")

    monkeypatch.setattr("stripe.Webhook.construct_event", fake_construct_event)
    monkeypatch.setattr("app.routers.webhooks.process_stripe_event", fake_process)

    response1 = client.post(
        "/webhooks/stripe",
        json={"id": fake_event.id},
        headers={"stripe-signature": "test_signature"},
    )
    assert response1.status_code == 200
    assert response1.json()["status"] == "error"
    assert response1.json()["processed"] is False

    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == admin.id)
        .filter(NotificationEvent.type == "stripe_webhook_processing_failed")
        .one()
    )
    assert event.title == "Stripe webhook processing failed"
    assert event.url == "/admin"
    assert fake_event.id in event.body
    assert fake_event.type in event.body
    assert "billing projector crashed" in event.body

    delivery_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.notification_event_id == event.id)
        .one()
    )
    assert delivery_log.channel == "inbox"
    assert delivery_log.delivery_status == "delivered"

    response2 = client.post(
        "/webhooks/stripe",
        json={"id": fake_event.id},
        headers={"stripe-signature": "test_signature"},
    )
    assert response2.status_code == 200
    assert response2.json() == {"status": "duplicate", "processed": False}

    assert (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == admin.id)
        .filter(NotificationEvent.type == "stripe_webhook_processing_failed")
        .count()
        == 1
    )
