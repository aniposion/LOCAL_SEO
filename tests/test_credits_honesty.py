"""Honesty checks for credits, usage, and purchase flows."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.credits import (
    CreditBalance,
    CreditPurchaseOrder,
    CreditPurchaseStatus,
    CreditTransaction,
    UsageRecord,
)
from app.services.credits import CreditsService, PlanTier


class TestBillingCredits:
    """Billing credits endpoints should not fabricate purchase success."""

    def test_get_credit_status_is_empty_and_honest(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        response = client.get("/billing/credits", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["storage_mode"] == "database_persistent"
        # Purchase is now productized via Stripe Checkout
        assert data["purchase_available"] is True
        assert data["credits"]["balance"] == 0
        assert data["credits"]["bonus_balance"] == 0
        assert data["stats"]["total_received"] == 0
        assert data["stats"]["total_used"] == 0
        assert data["stats"]["total_purchased"] == 0

    def test_get_credit_transactions_is_empty_when_unpersisted(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        response = client.get("/billing/credits/transactions", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_purchase_credits_requires_stripe_config(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Without Stripe configured the endpoint returns 503, not a fake success."""
        from unittest.mock import patch

        with patch("app.core.config.settings.stripe_secret_key", None):
            response = client.post(
                "/billing/credits/purchase",
                params={
                    "package_id": "credits_100",
                    "success_url": "http://localhost/ok",
                    "cancel_url": "http://localhost/cancel",
                },
                headers=auth_headers,
            )
        assert response.status_code == 503
        assert "Stripe is not configured" in response.json()["detail"]


class TestUsageCredits:
    """Usage credits endpoints should reflect real state only."""

    def test_usage_credit_balance_is_empty_by_default(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        response = client.get("/usage/credits", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["total_credits"] == 0
        assert data["used_credits"] == 0
        assert data["remaining_credits"] == 0
        assert data["bonus_credits"] == 0
        assert data["expires_at"] is None

    def test_usage_credit_history_is_empty_by_default(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        response = client.get("/usage/credits/history", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert data["transactions"] == []

    def test_usage_credit_orders_is_empty_by_default(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /usage/credits/orders returns empty list when no orders exist."""
        response = client.get("/usage/credits/orders", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["orders"] == []

    def test_usage_credit_orders_reflects_real_purchase_statuses(
        self,
        client: TestClient,
        db: Session,
        test_user,
        auth_headers: dict[str, str],
    ) -> None:
        """Order history shows all lifecycle statuses honestly."""
        now = datetime.now(UTC)
        statuses_to_create = [
            ("cs_ord_pending",   CreditPurchaseStatus.PENDING),
            ("cs_ord_completed", CreditPurchaseStatus.COMPLETED),
            ("cs_ord_refunded",  CreditPurchaseStatus.REFUNDED),
            ("cs_ord_canceled",  CreditPurchaseStatus.CANCELED),
        ]
        for session_id, s in statuses_to_create:
            db.add(
                CreditPurchaseOrder(
                    account_id=test_user.id,
                    stripe_session_id=session_id,
                    package_id="credits_50",
                    credits_amount=50,
                    price_cents=499,
                    status=s,
                )
            )
        db.commit()

        response = client.get("/usage/credits/orders", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4

        returned_statuses = {o["status"] for o in data["orders"]}
        assert returned_statuses == {"pending", "completed", "refunded", "canceled"}

    def test_usage_credit_orders_status_filter(
        self,
        client: TestClient,
        db: Session,
        test_user,
        auth_headers: dict[str, str],
    ) -> None:
        """status_filter limits results to the requested status."""
        now = datetime.now(UTC)
        for session_id, s in [
            ("cs_sf_completed", CreditPurchaseStatus.COMPLETED),
            ("cs_sf_refunded",  CreditPurchaseStatus.REFUNDED),
        ]:
            db.add(
                CreditPurchaseOrder(
                    account_id=test_user.id,
                    stripe_session_id=session_id,
                    package_id="credits_50",
                    credits_amount=50,
                    price_cents=499,
                    status=s,
                )
            )
        db.commit()

        r = client.get("/usage/credits/orders?status_filter=refunded", headers=auth_headers)
        assert r.status_code == 200
        orders = r.json()["orders"]
        assert len(orders) == 1
        assert orders[0]["status"] == "refunded"

        bad = client.get("/usage/credits/orders?status_filter=bogus", headers=auth_headers)
        assert bad.status_code == 400

    def test_usage_purchase_requires_stripe_config(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Without Stripe configured the endpoint returns 503, not a fake success."""
        from unittest.mock import patch

        with patch("app.core.config.settings.stripe_secret_key", None):
            response = client.post(
                "/usage/credits/purchase",
                json={
                    "package_id": "credits_100",
                    "success_url": "http://localhost/ok",
                    "cancel_url": "http://localhost/cancel",
                },
                headers=auth_headers,
            )
        assert response.status_code == 503

    def test_credit_state_persists_through_db_backed_service(
        self,
        client: TestClient,
        db: Session,
        test_user,
        auth_headers: dict[str, str],
    ) -> None:
        service = CreditsService(db)

        payment_result = service.process_payment(
            str(test_user.id),
            PlanTier.STARTER,
            payment_date=datetime.now(UTC),
        )
        assert payment_result["success"] is True
        assert payment_result["credits_allocated"] == 100

        bonus_result = service.grant_bonus(str(test_user.id), 50, reason="Launch bonus")
        assert bonus_result["success"] is True
        assert bonus_result["new_total"] == 150

        usage_result = service.use_credits(str(test_user.id), "ai_response", count=60)
        assert usage_result["allowed"] is True
        assert usage_result["credits_used"] == 120

        db_balance = db.query(CreditBalance).filter(CreditBalance.account_id == test_user.id).first()
        assert db_balance is not None
        assert db_balance.balance == 30
        assert db_balance.bonus_balance == 0
        assert db_balance.total_credits_received == 150
        assert db_balance.total_credits_used == 120

        usage_row = (
            db.query(UsageRecord)
            .filter(
                UsageRecord.account_id == test_user.id,
                UsageRecord.usage_type == "ai_response",
            )
            .first()
        )
        assert usage_row is not None
        assert usage_row.daily_count == 60
        assert usage_row.monthly_count == 60

        transactions = service.get_transactions(str(test_user.id), limit=10)
        assert [transaction["type"] for transaction in transactions] == [
            "ai_response_usage",
            "bonus",
            "monthly_allocation",
        ]

        response = client.get("/billing/credits", headers=auth_headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["storage_mode"] == "database_persistent"
        assert payload["credits"]["balance"] == 30
        assert payload["credits"]["bonus_balance"] == 0
        assert payload["stats"]["total_received"] == 150
        assert payload["stats"]["total_used"] == 120

        history = client.get("/billing/credits/transactions", headers=auth_headers)
        assert history.status_code == 200
        history_payload = history.json()
        assert len(history_payload) == 3
        assert history_payload[0]["type"] == "ai_response_usage"
