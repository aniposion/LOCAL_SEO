"""Tests for the Stripe-backed credit purchase flow.

Coverage:
- create_purchase_checkout(): creates CreditPurchaseOrder in PENDING state
- apply_purchase_from_webhook(): applies credits after payment confirmation
- Idempotency: double-application is a safe no-op
- Unknown package returns ValueError
- Missing Stripe key returns RuntimeError
- /billing/credits/purchase endpoint delegates to the service
- /usage/credits/purchase endpoint delegates to the service
- /webhooks/stripe handles checkout.session.completed for credits
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.account import Account, AccountRole
from app.models.credits import (
    CREDIT_PACKAGES,
    CreditBalance,
    CreditPurchaseOrder,
    CreditPurchaseStatus,
    CreditTransaction,
    CreditTransactionType,
)
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.services.credits import CreditsService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stripe_session(
    session_id: str = "cs_test_abc123",
    payment_intent: str = "pi_test_xyz",
    purchase_type: str = "credits",
    package_id: str = "credits_100",
    credits_amount: str = "100",
    account_id: str | None = None,
) -> MagicMock:
    """Build a minimal mock of a Stripe checkout.Session object."""
    session = MagicMock()
    session.id = session_id
    session.url = f"https://checkout.stripe.com/pay/{session_id}"
    session.payment_intent = payment_intent
    session.get = lambda key, default=None: {
        "id": session_id,
        "payment_intent": payment_intent,
        "metadata": {
            "purchase_type": purchase_type,
            "package_id": package_id,
            "credits_amount": credits_amount,
            "account_id": account_id or "",
        },
    }.get(key, default)
    return session


def _admin_account(db: Session) -> Account:
    admin = Account(
        id=uuid.uuid4(),
        email="credits-admin@example.com",
        password_hash=get_password_hash("Adminpassword123!"),
        role=AccountRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


# ---------------------------------------------------------------------------
# Unit: CreditsService
# ---------------------------------------------------------------------------


class TestCreatePurchaseCheckout:
    """CreditsService.create_purchase_checkout unit tests."""

    def test_raises_for_unknown_package(self, db: Session, test_user) -> None:
        service = CreditsService(db)
        with pytest.raises(ValueError, match="Unknown credit package"):
            service.create_purchase_checkout(
                account_id=str(test_user.id),
                package_id="credits_9999",
                success_url="http://localhost/success",
                cancel_url="http://localhost/cancel",
            )

    def test_raises_when_stripe_not_configured(self, db: Session, test_user) -> None:
        service = CreditsService(db)
        with patch("app.core.config.settings.stripe_secret_key", None):
            with pytest.raises(RuntimeError, match="Stripe is not configured"):
                service.create_purchase_checkout(
                    account_id=str(test_user.id),
                    package_id="credits_100",
                    success_url="http://localhost/success",
                    cancel_url="http://localhost/cancel",
                )

    def test_creates_pending_order_and_returns_checkout_url(
        self, db: Session, test_user
    ) -> None:
        mock_session = _make_stripe_session(account_id=str(test_user.id))

        with (
            patch("app.core.config.settings.stripe_secret_key", "sk_test_fake"),
            patch("stripe.checkout.Session.create", return_value=mock_session),
        ):
            service = CreditsService(db)
            result = service.create_purchase_checkout(
                account_id=str(test_user.id),
                package_id="credits_100",
                success_url="http://localhost/success",
                cancel_url="http://localhost/cancel",
            )

        assert result["checkout_url"] == mock_session.url
        assert result["session_id"] == mock_session.id
        assert result["credits_amount"] == 100
        assert result["price_cents"] == 899
        assert "order_id" in result

        # DB row created in PENDING state
        order = (
            db.query(CreditPurchaseOrder)
            .filter(CreditPurchaseOrder.account_id == test_user.id)
            .first()
        )
        assert order is not None
        assert order.status == CreditPurchaseStatus.PENDING
        assert order.stripe_session_id == mock_session.id
        assert order.credits_amount == 100
        assert order.price_cents == 899
        assert order.completed_at is None

        # No credits added yet
        balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
        assert balance is None  # balance row not yet created

    @pytest.mark.parametrize("package_id", list(CREDIT_PACKAGES.keys()))
    def test_all_packages_produce_correct_amounts(
        self, db: Session, test_user, package_id: str
    ) -> None:
        expected_credits, expected_cents, _ = CREDIT_PACKAGES[package_id]
        mock_session = _make_stripe_session(
            package_id=package_id,
            credits_amount=str(expected_credits),
            account_id=str(test_user.id),
        )

        with (
            patch("app.core.config.settings.stripe_secret_key", "sk_test_fake"),
            patch("stripe.checkout.Session.create", return_value=mock_session),
        ):
            service = CreditsService(db)
            result = service.create_purchase_checkout(
                account_id=str(test_user.id),
                package_id=package_id,
                success_url="http://localhost/success",
                cancel_url="http://localhost/cancel",
            )

        assert result["credits_amount"] == expected_credits
        assert result["price_cents"] == expected_cents


class TestApplyPurchaseFromWebhook:
    """CreditsService.apply_purchase_from_webhook unit tests."""

    def _create_pending_order(
        self,
        db: Session,
        account_id: uuid.UUID,
        session_id: str = "cs_test_abc123",
        package_id: str = "credits_100",
        status: CreditPurchaseStatus = CreditPurchaseStatus.PENDING,
    ) -> CreditPurchaseOrder:
        credits, cents, _ = CREDIT_PACKAGES[package_id]
        order = CreditPurchaseOrder(
            account_id=account_id,
            stripe_session_id=session_id,
            package_id=package_id,
            credits_amount=credits,
            price_cents=cents,
            status=status,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    def test_applies_credits_to_balance(self, db: Session, test_user) -> None:
        self._create_pending_order(db, test_user.id)
        service = CreditsService(db)

        result = service.apply_purchase_from_webhook(
            stripe_session_id="cs_test_abc123",
            stripe_payment_intent_id="pi_test_xyz",
        )

        assert result["applied"] is True
        assert result["credits_amount"] == 100

        balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
        assert balance is not None
        assert balance.balance == 100
        assert balance.total_credits_purchased == 100
        assert balance.total_credits_received == 100

    def test_creates_purchase_transaction(self, db: Session, test_user) -> None:
        self._create_pending_order(db, test_user.id)
        CreditsService(db).apply_purchase_from_webhook("cs_test_abc123")

        tx = (
            db.query(CreditTransaction)
            .filter(
                CreditTransaction.account_id == test_user.id,
                CreditTransaction.type == CreditTransactionType.PURCHASE,
            )
            .first()
        )
        assert tx is not None
        assert tx.amount == 100
        assert tx.reference_type == "credit_purchase"

    def test_marks_order_completed(self, db: Session, test_user) -> None:
        order = self._create_pending_order(db, test_user.id)
        CreditsService(db).apply_purchase_from_webhook(
            "cs_test_abc123", stripe_payment_intent_id="pi_test_xyz"
        )

        db.refresh(order)
        assert order.status == CreditPurchaseStatus.COMPLETED
        assert order.stripe_payment_intent_id == "pi_test_xyz"
        assert order.completed_at is not None

    def test_idempotent_double_application(self, db: Session, test_user) -> None:
        self._create_pending_order(db, test_user.id)
        service = CreditsService(db)

        service.apply_purchase_from_webhook("cs_test_abc123")
        second = service.apply_purchase_from_webhook("cs_test_abc123")

        assert second["applied"] is False
        assert second["already_applied"] is True

        # Balance still 100, not 200
        balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
        assert balance.balance == 100

    def test_unknown_session_returns_not_found(self, db: Session, test_user) -> None:
        service = CreditsService(db)
        result = service.apply_purchase_from_webhook("cs_nonexistent")
        assert result["applied"] is False
        assert result["reason"] == "order_not_found"

    @pytest.mark.parametrize(
        "status",
        [CreditPurchaseStatus.CANCELED, CreditPurchaseStatus.EXPIRED, CreditPurchaseStatus.REFUNDED],
    )
    def test_terminal_order_is_not_applied(self, db: Session, test_user, status) -> None:
        order = self._create_pending_order(db, test_user.id, status=status)
        result = CreditsService(db).apply_purchase_from_webhook(
            "cs_test_abc123",
            stripe_payment_intent_id="pi_terminal_order",
        )

        assert result["applied"] is False
        assert result["reason"] == "order_not_pending"
        assert result["status"] == status.value

        db.refresh(order)
        assert order.status == status
        assert order.stripe_payment_intent_id is None
        assert order.completed_at is None
        assert db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first() is None
        assert (
            db.query(CreditTransaction)
            .filter(CreditTransaction.reference_id == str(order.id))
            .count()
            == 0
        )

    def test_purchased_credits_stack_with_monthly_allocation(
        self, db: Session, test_user
    ) -> None:
        """Purchased credits add on top of monthly allocation."""
        service = CreditsService(db)
        service.process_payment(str(test_user.id), __import__("app.services.credits", fromlist=["PlanTier"]).PlanTier.STARTER)

        self._create_pending_order(db, test_user.id)
        service.apply_purchase_from_webhook("cs_test_abc123")

        balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
        assert balance.balance == 200  # 100 monthly + 100 purchased


class TestLegacyPurchaseCreditsWrapper:
    """CreditsService.purchase_credits compatibility wrapper tests."""

    def test_maps_exact_credit_amount_to_checkout_package(self, db: Session, test_user) -> None:
        service = CreditsService(db)

        with (
            patch("app.core.config.settings.app_url", "https://app.example.com"),
            patch.object(
                CreditsService,
                "create_purchase_checkout",
                return_value={
                    "checkout_url": "https://checkout.stripe.test/session",
                    "session_id": "cs_legacy_wrapper",
                    "order_id": "order_123",
                    "credits_amount": 100,
                    "price_cents": 899,
                },
            ) as mock_checkout,
        ):
            result = service.purchase_credits(
                account_id=str(test_user.id),
                amount=100,
                payment_id="legacy_456",
            )

        mock_checkout.assert_called_once_with(
            account_id=str(test_user.id),
            package_id="credits_100",
            success_url="https://app.example.com/dashboard/usage?creditsPurchase=success&payment_id=legacy_456",
            cancel_url="https://app.example.com/dashboard/usage?creditsPurchase=canceled&payment_id=legacy_456",
        )
        assert result["package_id"] == "credits_100"
        assert result["legacy_amount"] == 100

    def test_rejects_non_package_credit_amount(self, db: Session, test_user) -> None:
        service = CreditsService(db)

        with pytest.raises(ValueError, match="Supported amounts"):
            service.purchase_credits(
                account_id=str(test_user.id),
                amount=75,
            )


# ---------------------------------------------------------------------------
# Integration: API endpoints
# ---------------------------------------------------------------------------


class TestBillingCreditsPurchaseEndpoint:
    """POST /billing/credits/purchase integration tests."""

    def test_returns_checkout_url_on_valid_package(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        mock_session = _make_stripe_session(session_id="cs_test_billing_100")

        with (
            patch("app.core.config.settings.stripe_secret_key", "sk_test_fake"),
            patch("stripe.checkout.Session.create", return_value=mock_session),
        ):
            resp = client.post(
                "/billing/credits/purchase",
                params={
                    "package_id": "credits_100",
                    "success_url": "http://localhost/success",
                    "cancel_url": "http://localhost/cancel",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["checkout_url"] == mock_session.url
        assert data["session_id"] == "cs_test_billing_100"
        assert data["credits_amount"] == 100
        assert data["price_cents"] == 899
        assert "order_id" in data

    def test_returns_400_on_unknown_package(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch("app.core.config.settings.stripe_secret_key", "sk_test_fake"):
            resp = client.post(
                "/billing/credits/purchase",
                params={
                    "package_id": "credits_9999",
                    "success_url": "http://localhost/success",
                    "cancel_url": "http://localhost/cancel",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert "Unknown credit package" in resp.json()["detail"]

    def test_returns_503_when_stripe_not_configured(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch("app.core.config.settings.stripe_secret_key", None):
            resp = client.post(
                "/billing/credits/purchase",
                params={
                    "package_id": "credits_100",
                    "success_url": "http://localhost/success",
                    "cancel_url": "http://localhost/cancel",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 503
        assert "Stripe is not configured" in resp.json()["detail"]

    def test_get_credits_shows_purchase_available_and_packages(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/billing/credits", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["purchase_available"] is True
        assert len(data["credit_packages"]) == len(CREDIT_PACKAGES)
        pkg_ids = {p["package_id"] for p in data["credit_packages"]}
        assert pkg_ids == set(CREDIT_PACKAGES.keys())


class TestUsageCreditsPurchaseEndpoint:
    """POST /usage/credits/purchase integration tests."""

    def test_returns_checkout_url_on_valid_package(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        mock_session = _make_stripe_session(session_id="cs_test_usage_50")

        with (
            patch("app.core.config.settings.stripe_secret_key", "sk_test_fake"),
            patch("stripe.checkout.Session.create", return_value=mock_session),
        ):
            resp = client.post(
                "/usage/credits/purchase",
                json={
                    "package_id": "credits_50",
                    "success_url": "http://localhost/success",
                    "cancel_url": "http://localhost/cancel",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["checkout_url"] == mock_session.url
        assert data["credits_amount"] == 50

    def test_returns_503_when_stripe_not_configured(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch("app.core.config.settings.stripe_secret_key", None):
            resp = client.post(
                "/usage/credits/purchase",
                json={
                    "package_id": "credits_100",
                    "success_url": "http://localhost/success",
                    "cancel_url": "http://localhost/cancel",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 503


class TestWebhookCreditPurchase:
    """checkout.session.completed webhook handler for credit purchases.

    Tests call ``process_stripe_event`` directly (bypassing the HTTP layer and
    the Stripe idempotency wrapper) so the test DB does not need stripe_events.
    """

    def _make_checkout_event(
        self,
        session_id: str = "cs_wh_test_100",
        payment_intent: str = "pi_test_abc",
        purchase_type: str = "credits",
        package_id: str = "credits_100",
        credits_amount: str = "100",
        account_id: str = "",
    ) -> MagicMock:
        mock_event = MagicMock()
        mock_event.type = "checkout.session.completed"

        session_obj = MagicMock()
        session_obj.get = lambda key, default=None: {
            "id": session_id,
            "payment_intent": payment_intent,
            "metadata": {
                "purchase_type": purchase_type,
                "package_id": package_id,
                "credits_amount": credits_amount,
                "account_id": account_id,
            },
        }.get(key, default)
        mock_event.data.object = session_obj
        return mock_event

    @pytest.mark.asyncio
    async def test_applies_credits_on_checkout_completed(
        self,
        db: Session,
        test_user,
    ) -> None:
        from app.routers.webhooks import process_stripe_event

        # Create pending order
        credits, cents, _ = CREDIT_PACKAGES["credits_100"]
        order = CreditPurchaseOrder(
            account_id=test_user.id,
            stripe_session_id="cs_wh_test_100",
            package_id="credits_100",
            credits_amount=credits,
            price_cents=cents,
            status=CreditPurchaseStatus.PENDING,
        )
        db.add(order)
        db.commit()

        mock_event = self._make_checkout_event(account_id=str(test_user.id))
        await process_stripe_event(mock_event, db)

        db.refresh(order)
        assert order.status == CreditPurchaseStatus.COMPLETED
        assert order.stripe_payment_intent_id == "pi_test_abc"

        balance = (
            db.query(CreditBalance)
            .filter(CreditBalance.account_id == test_user.id)
            .first()
        )
        assert balance is not None
        assert balance.balance == 100

    @pytest.mark.asyncio
    async def test_idempotent_double_webhook(
        self,
        db: Session,
        test_user,
    ) -> None:
        """Calling the handler twice does not double-apply credits."""
        from app.routers.webhooks import process_stripe_event

        credits, cents, _ = CREDIT_PACKAGES["credits_100"]
        order = CreditPurchaseOrder(
            account_id=test_user.id,
            stripe_session_id="cs_wh_idem_100",
            package_id="credits_100",
            credits_amount=credits,
            price_cents=cents,
            status=CreditPurchaseStatus.PENDING,
        )
        db.add(order)
        db.commit()

        mock_event = self._make_checkout_event(
            session_id="cs_wh_idem_100",
            account_id=str(test_user.id),
        )
        await process_stripe_event(mock_event, db)
        await process_stripe_event(mock_event, db)  # duplicate

        balance = (
            db.query(CreditBalance)
            .filter(CreditBalance.account_id == test_user.id)
            .first()
        )
        assert balance.balance == 100  # not 200

    @pytest.mark.asyncio
    async def test_unknown_credit_checkout_notifies_admin(
        self,
        db: Session,
        test_user,
    ) -> None:
        from app.routers.webhooks import process_stripe_event

        admin = _admin_account(db)

        mock_event = self._make_checkout_event(
            session_id="cs_missing_credit_order",
            payment_intent="pi_missing_credit_order",
            account_id=str(test_user.id),
        )

        await process_stripe_event(mock_event, db)

        admin_event = (
            db.query(NotificationEvent)
            .filter(
                NotificationEvent.account_id == admin.id,
                NotificationEvent.type == "stripe_credit_purchase_apply_failed",
            )
            .one()
        )
        assert admin_event.url == "/admin"
        assert "stripe credit purchase apply failed" in admin_event.title.lower()
        assert "cs_missing_credit_order" in admin_event.body
        assert "pi_missing_credit_order" in admin_event.body
        assert "order_not_found" in admin_event.body
        assert str(test_user.id) in admin_event.body

        delivery_log = (
            db.query(NotificationDeliveryLog)
            .filter(NotificationDeliveryLog.notification_event_id == admin_event.id)
            .one()
        )
        assert delivery_log.channel == "inbox"
        assert delivery_log.delivery_status == "delivered"

    @pytest.mark.asyncio
    async def test_terminal_credit_checkout_does_not_apply_and_notifies_admin(
        self,
        db: Session,
        test_user,
    ) -> None:
        from app.routers.webhooks import process_stripe_event

        admin = _admin_account(db)
        credits, cents, _ = CREDIT_PACKAGES["credits_100"]
        order = CreditPurchaseOrder(
            account_id=test_user.id,
            stripe_session_id="cs_terminal_credit_order",
            package_id="credits_100",
            credits_amount=credits,
            price_cents=cents,
            status=CreditPurchaseStatus.EXPIRED,
        )
        db.add(order)
        db.commit()

        mock_event = self._make_checkout_event(
            session_id="cs_terminal_credit_order",
            payment_intent="pi_terminal_credit_order",
            account_id=str(test_user.id),
        )

        await process_stripe_event(mock_event, db)

        db.refresh(order)
        assert order.status == CreditPurchaseStatus.EXPIRED
        assert order.stripe_payment_intent_id is None
        assert db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first() is None

        admin_event = (
            db.query(NotificationEvent)
            .filter(
                NotificationEvent.account_id == admin.id,
                NotificationEvent.type == "stripe_credit_purchase_apply_failed",
            )
            .one()
        )
        assert "cs_terminal_credit_order" in admin_event.body
        assert "pi_terminal_credit_order" in admin_event.body
        assert "order_not_pending" in admin_event.body

    @pytest.mark.asyncio
    async def test_subscription_checkout_delegates_to_subscription_handler(
        self,
        db: Session,
        test_user,
    ) -> None:
        """checkout.session.completed without purchase_type=credits goes to _handle_checkout_completed."""
        from app.routers.webhooks import process_stripe_event

        mock_event = self._make_checkout_event(
            session_id="cs_sub_test",
            purchase_type="",  # not a credit purchase
        )

        # Should not raise even though there's no matching subscription
        await process_stripe_event(mock_event, db)


# ---------------------------------------------------------------------------
# Unit: cancel_purchase_order
# ---------------------------------------------------------------------------


class TestCancelPurchaseOrder:
    """CreditsService.cancel_purchase_order unit tests."""

    def _make_order(
        self,
        db: Session,
        account_id: uuid.UUID,
        session_id: str,
        status: CreditPurchaseStatus = CreditPurchaseStatus.PENDING,
    ) -> CreditPurchaseOrder:
        credits, cents, _ = CREDIT_PACKAGES["credits_100"]
        order = CreditPurchaseOrder(
            account_id=account_id,
            stripe_session_id=session_id,
            package_id="credits_100",
            credits_amount=credits,
            price_cents=cents,
            status=status,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    def test_cancels_pending_order(self, db: Session, test_user) -> None:
        order = self._make_order(db, test_user.id, "cs_cancel_test")
        result = CreditsService(db).cancel_purchase_order("cs_cancel_test")
        assert result["canceled"] is True
        assert result["new_status"] == "canceled"
        db.refresh(order)
        assert order.status == CreditPurchaseStatus.CANCELED

    def test_expires_pending_order(self, db: Session, test_user) -> None:
        order = self._make_order(db, test_user.id, "cs_expire_test")
        result = CreditsService(db).cancel_purchase_order(
            "cs_expire_test", CreditPurchaseStatus.EXPIRED
        )
        assert result["canceled"] is True
        assert result["new_status"] == "expired"
        db.refresh(order)
        assert order.status == CreditPurchaseStatus.EXPIRED

    def test_idempotent_cancel(self, db: Session, test_user) -> None:
        self._make_order(db, test_user.id, "cs_idem_cancel")
        svc = CreditsService(db)
        svc.cancel_purchase_order("cs_idem_cancel")
        second = svc.cancel_purchase_order("cs_idem_cancel")
        assert second["canceled"] is False
        assert second["already_canceled"] is True

    def test_cannot_cancel_completed_order(self, db: Session, test_user) -> None:
        self._make_order(
            db, test_user.id, "cs_completed_order", CreditPurchaseStatus.COMPLETED
        )
        result = CreditsService(db).cancel_purchase_order("cs_completed_order")
        assert result["canceled"] is False
        assert result["reason"] == "order_already_completed"

    def test_unknown_session_returns_not_found(self, db: Session, test_user) -> None:
        result = CreditsService(db).cancel_purchase_order("cs_nonexistent_xyz")
        assert result["canceled"] is False
        assert result["reason"] == "order_not_found"

    def test_no_balance_changes_on_cancel(self, db: Session, test_user) -> None:
        """Canceling a pending order must not touch the credit balance."""
        self._make_order(db, test_user.id, "cs_no_balance_cancel")
        CreditsService(db).cancel_purchase_order("cs_no_balance_cancel")
        balance = (
            db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
        )
        assert balance is None  # never created


# ---------------------------------------------------------------------------
# Unit: refund_purchase
# ---------------------------------------------------------------------------


class TestRefundPurchase:
    """CreditsService.refund_purchase unit tests."""

    def _seed_completed_order(
        self,
        db: Session,
        account_id: uuid.UUID,
        session_id: str = "cs_refund_test",
        pi_id: str = "pi_refund_test",
        package_id: str = "credits_100",
    ) -> CreditPurchaseOrder:
        credits, cents, _ = CREDIT_PACKAGES[package_id]
        order = CreditPurchaseOrder(
            account_id=account_id,
            stripe_session_id=session_id,
            package_id=package_id,
            credits_amount=credits,
            price_cents=cents,
            status=CreditPurchaseStatus.COMPLETED,
            stripe_payment_intent_id=pi_id,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    def _seed_balance(
        self, db: Session, account_id: uuid.UUID, balance: int, bonus: int = 0
    ) -> CreditBalance:
        cb = CreditBalance(
            account_id=account_id,
            balance=balance,
            bonus_balance=bonus,
            total_credits_received=balance + bonus,
            total_credits_purchased=balance,
        )
        db.add(cb)
        db.commit()
        db.refresh(cb)
        return cb

    def test_deducts_purchased_credits_from_balance(
        self, db: Session, test_user
    ) -> None:
        self._seed_completed_order(db, test_user.id)
        self._seed_balance(db, test_user.id, 100)

        result = CreditsService(db).refund_purchase("pi_refund_test")

        assert result["refunded"] is True
        assert result["credits_deducted"] == 100
        balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
        assert balance.balance == 0
        assert balance.bonus_balance == 0

    def test_deducts_from_bonus_first(self, db: Session, test_user) -> None:
        """Refund deducts bonus credits before regular credits."""
        self._seed_completed_order(db, test_user.id, package_id="credits_100")
        # 40 bonus + 100 regular = 140 total; refund 100 → takes all 40 bonus + 60 regular
        self._seed_balance(db, test_user.id, balance=100, bonus=40)

        CreditsService(db).refund_purchase("pi_refund_test")

        balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
        assert balance.bonus_balance == 0
        assert balance.balance == 40  # 100 - 60 remaining

    def test_clamps_deduction_at_zero_when_balance_insufficient(
        self, db: Session, test_user
    ) -> None:
        """If the user spent credits, refund only deducts what remains (no negative)."""
        self._seed_completed_order(db, test_user.id)
        self._seed_balance(db, test_user.id, 30)  # user spent 70 of 100

        result = CreditsService(db).refund_purchase("pi_refund_test")

        assert result["refunded"] is True
        assert result["credits_deducted"] == 30  # only what was available
        balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
        assert balance.balance == 0
        assert balance.bonus_balance == 0

    def test_records_refund_transaction(self, db: Session, test_user) -> None:
        self._seed_completed_order(db, test_user.id)
        self._seed_balance(db, test_user.id, 100)

        CreditsService(db).refund_purchase("pi_refund_test")

        tx = (
            db.query(CreditTransaction)
            .filter(
                CreditTransaction.account_id == test_user.id,
                CreditTransaction.type == CreditTransactionType.REFUND,
            )
            .first()
        )
        assert tx is not None
        assert tx.amount == -100
        assert tx.reference_type == "credit_purchase"

    def test_marks_order_refunded(self, db: Session, test_user) -> None:
        order = self._seed_completed_order(db, test_user.id)
        self._seed_balance(db, test_user.id, 100)

        CreditsService(db).refund_purchase("pi_refund_test")

        db.refresh(order)
        assert order.status == CreditPurchaseStatus.REFUNDED
        assert order.refunded_at is not None

    def test_idempotent_double_refund(self, db: Session, test_user) -> None:
        self._seed_completed_order(db, test_user.id)
        self._seed_balance(db, test_user.id, 100)
        svc = CreditsService(db)

        svc.refund_purchase("pi_refund_test")
        second = svc.refund_purchase("pi_refund_test")

        assert second["refunded"] is False
        assert second["already_refunded"] is True
        # Balance still 0, not -100
        balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
        assert balance.balance == 0

    def test_unknown_payment_intent_returns_not_found(self, db: Session, test_user) -> None:
        result = CreditsService(db).refund_purchase("pi_nonexistent")
        assert result["refunded"] is False
        assert result["reason"] == "order_not_found"

    def test_refund_on_pending_order_returns_not_completed(
        self, db: Session, test_user
    ) -> None:
        credits, cents, _ = CREDIT_PACKAGES["credits_100"]
        order = CreditPurchaseOrder(
            account_id=test_user.id,
            stripe_session_id="cs_pending_refund",
            package_id="credits_100",
            credits_amount=credits,
            price_cents=cents,
            status=CreditPurchaseStatus.PENDING,
            stripe_payment_intent_id="pi_pending_refund",
        )
        db.add(order)
        db.commit()

        result = CreditsService(db).refund_purchase("pi_pending_refund")
        assert result["refunded"] is False
        assert result["reason"] == "order_not_completed"

    def test_refund_without_balance_row_is_safe(self, db: Session, test_user) -> None:
        """Refund should succeed even if there is no balance row (rare edge case)."""
        self._seed_completed_order(db, test_user.id, pi_id="pi_no_balance")
        # No balance row created

        result = CreditsService(db).refund_purchase("pi_no_balance")
        assert result["refunded"] is True
        assert result["credits_deducted"] == 0


# ---------------------------------------------------------------------------
# Integration: webhook handlers for expired/canceled checkout and refund
# ---------------------------------------------------------------------------


def _make_session_event(
    event_type: str,
    session_id: str = "cs_evt_test",
    purchase_type: str = "credits",
    account_id: str = "",
    package_id: str = "credits_100",
    credits_amount: str = "100",
) -> MagicMock:
    mock_event = MagicMock()
    mock_event.type = event_type
    session_obj = MagicMock()
    session_obj.get = lambda key, default=None: {
        "id": session_id,
        "metadata": {
            "purchase_type": purchase_type,
            "account_id": account_id,
            "package_id": package_id,
            "credits_amount": credits_amount,
        },
    }.get(key, default)
    mock_event.data.object = session_obj
    return mock_event


def _make_charge_refunded_event(payment_intent_id: str) -> MagicMock:
    mock_event = MagicMock()
    mock_event.type = "charge.refunded"
    charge_obj = MagicMock()
    charge_obj.get = lambda key, default=None: {
        "payment_intent": payment_intent_id,
    }.get(key, default)
    mock_event.data.object = charge_obj
    return mock_event


class TestWebhookCheckoutExpired:
    """checkout.session.expired webhook marks orders EXPIRED."""

    @pytest.mark.asyncio
    async def test_marks_pending_order_expired(
        self, db: Session, test_user
    ) -> None:
        from app.routers.webhooks import process_stripe_event

        credits, cents, _ = CREDIT_PACKAGES["credits_100"]
        order = CreditPurchaseOrder(
            account_id=test_user.id,
            stripe_session_id="cs_expire_wh",
            package_id="credits_100",
            credits_amount=credits,
            price_cents=cents,
            status=CreditPurchaseStatus.PENDING,
        )
        db.add(order)
        db.commit()

        await process_stripe_event(
            _make_session_event("checkout.session.expired", "cs_expire_wh"), db
        )

        db.refresh(order)
        assert order.status == CreditPurchaseStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_idempotent_duplicate_expired_event(
        self, db: Session, test_user
    ) -> None:
        from app.routers.webhooks import process_stripe_event

        credits, cents, _ = CREDIT_PACKAGES["credits_100"]
        order = CreditPurchaseOrder(
            account_id=test_user.id,
            stripe_session_id="cs_idem_expire",
            package_id="credits_100",
            credits_amount=credits,
            price_cents=cents,
            status=CreditPurchaseStatus.PENDING,
        )
        db.add(order)
        db.commit()

        evt = _make_session_event("checkout.session.expired", "cs_idem_expire")
        await process_stripe_event(evt, db)
        await process_stripe_event(evt, db)  # duplicate – should not raise

        db.refresh(order)
        assert order.status == CreditPurchaseStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_non_credit_session_is_ignored(
        self, db: Session, test_user
    ) -> None:
        from app.routers.webhooks import process_stripe_event

        # Should not raise even though there's no purchase order
        await process_stripe_event(
            _make_session_event(
                "checkout.session.expired", "cs_sub_expire", purchase_type=""
            ),
            db,
        )

    @pytest.mark.asyncio
    async def test_unknown_expired_credit_checkout_notifies_admin(
        self, db: Session, test_user
    ) -> None:
        from app.routers.webhooks import process_stripe_event

        admin = _admin_account(db)

        await process_stripe_event(
            _make_session_event(
                "checkout.session.expired",
                "cs_missing_expired_order",
                account_id=str(test_user.id),
            ),
            db,
        )

        admin_event = (
            db.query(NotificationEvent)
            .filter(
                NotificationEvent.account_id == admin.id,
                NotificationEvent.type == "stripe_credit_purchase_close_failed",
            )
            .one()
        )
        assert admin_event.url == "/admin"
        assert "stripe credit purchase close failed" in admin_event.title.lower()
        assert "cs_missing_expired_order" in admin_event.body
        assert "expired" in admin_event.body
        assert "order_not_found" in admin_event.body
        assert str(test_user.id) in admin_event.body

        delivery_log = (
            db.query(NotificationDeliveryLog)
            .filter(NotificationDeliveryLog.notification_event_id == admin_event.id)
            .one()
        )
        assert delivery_log.channel == "inbox"
        assert delivery_log.delivery_status == "delivered"


class TestWebhookCheckoutAsyncPaymentFailed:
    """checkout.session.async_payment_failed webhook closes pending credit orders."""

    @pytest.mark.asyncio
    async def test_unknown_async_failed_credit_checkout_notifies_admin(
        self, db: Session, test_user
    ) -> None:
        from app.routers.webhooks import process_stripe_event

        admin = _admin_account(db)

        await process_stripe_event(
            _make_session_event(
                "checkout.session.async_payment_failed",
                "cs_missing_async_failed_order",
                account_id=str(test_user.id),
            ),
            db,
        )

        admin_event = (
            db.query(NotificationEvent)
            .filter(
                NotificationEvent.account_id == admin.id,
                NotificationEvent.type == "stripe_credit_purchase_close_failed",
            )
            .one()
        )
        assert admin_event.url == "/admin"
        assert "cs_missing_async_failed_order" in admin_event.body
        assert "canceled" in admin_event.body
        assert "order_not_found" in admin_event.body


class TestWebhookChargeRefunded:
    """charge.refunded webhook claws back credits."""

    @pytest.mark.asyncio
    async def test_claws_back_credits(self, db: Session, test_user) -> None:
        from app.routers.webhooks import process_stripe_event

        credits, cents, _ = CREDIT_PACKAGES["credits_100"]
        order = CreditPurchaseOrder(
            account_id=test_user.id,
            stripe_session_id="cs_chref_100",
            package_id="credits_100",
            credits_amount=credits,
            price_cents=cents,
            status=CreditPurchaseStatus.COMPLETED,
            stripe_payment_intent_id="pi_chref_100",
        )
        db.add(order)
        balance = CreditBalance(
            account_id=test_user.id,
            balance=100,
            bonus_balance=0,
            total_credits_received=100,
            total_credits_purchased=100,
        )
        db.add(balance)
        db.commit()

        await process_stripe_event(
            _make_charge_refunded_event("pi_chref_100"), db
        )

        db.refresh(order)
        db.refresh(balance)
        assert order.status == CreditPurchaseStatus.REFUNDED
        assert order.refunded_at is not None
        assert balance.balance == 0

    @pytest.mark.asyncio
    async def test_idempotent_double_refund_webhook(
        self, db: Session, test_user
    ) -> None:
        from app.routers.webhooks import process_stripe_event

        credits, cents, _ = CREDIT_PACKAGES["credits_100"]
        order = CreditPurchaseOrder(
            account_id=test_user.id,
            stripe_session_id="cs_idem_chref",
            package_id="credits_100",
            credits_amount=credits,
            price_cents=cents,
            status=CreditPurchaseStatus.COMPLETED,
            stripe_payment_intent_id="pi_idem_chref",
        )
        db.add(order)
        balance = CreditBalance(
            account_id=test_user.id,
            balance=100,
            bonus_balance=0,
            total_credits_received=100,
            total_credits_purchased=100,
        )
        db.add(balance)
        db.commit()

        evt = _make_charge_refunded_event("pi_idem_chref")
        await process_stripe_event(evt, db)
        await process_stripe_event(evt, db)  # duplicate – balance must not go to -100

        db.refresh(balance)
        assert balance.balance == 0  # not -100

    @pytest.mark.asyncio
    async def test_unknown_payment_intent_does_not_raise(
        self, db: Session, test_user
    ) -> None:
        from app.routers.webhooks import process_stripe_event

        # charge.refunded for a non-credit payment intent should be a no-op
        await process_stripe_event(
            _make_charge_refunded_event("pi_unknown_xyz"), db
        )
