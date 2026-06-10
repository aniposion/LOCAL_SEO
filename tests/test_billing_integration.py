"""Billing endpoint smoke tests aligned to current routes."""

import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.billing import BillingAuditAction, BillingAuditLog
from app.models.credits import UsageRecord
from app.models.stripe_event import StripeEvent
from app.models.subscription import DunningStatus, PlanType, Subscription, SubscriptionStatus


class TestBillingPlans:
    """Smoke tests for billing plan metadata."""

    def test_get_plans(self, client: TestClient) -> None:
        """Public plans endpoint should return current plan IDs and pricing."""
        response = client.get("/billing/plans")
        assert response.status_code == 200

        data = response.json()
        plan_ids = [plan["id"] for plan in data]
        assert plan_ids == ["free", "maps_starter", "calls_growth", "competitive_market"]

        maps_starter = next(plan for plan in data if plan["id"] == "maps_starter")
        calls_growth = next(plan for plan in data if plan["id"] == "calls_growth")
        competitive = next(plan for plan in data if plan["id"] == "competitive_market")
        assert maps_starter["price_monthly"] == 699
        assert maps_starter["setup_fee"] == 499
        assert maps_starter["managed_service"] is True
        assert calls_growth["price_monthly"] == 999
        assert competitive["price_monthly"] == 1499
        assert competitive["limits"]["api_calls_per_day"] == 100000

    def test_get_legacy_plans_catalog(self, client: TestClient) -> None:
        """Legacy SaaS plan metadata should remain available for existing customers."""
        response = client.get("/billing/plans?catalog=legacy")
        assert response.status_code == 200

        data = response.json()
        plan_ids = [plan["id"] for plan in data]
        assert plan_ids == ["starter", "pro", "premium", "agency"]

        starter = next(plan for plan in data if plan["id"] == "starter")
        assert starter["price_monthly"] == 99
        assert starter["price_yearly"] == 990
        assert starter["publicly_listed"] is False

    def test_get_pricing_data_uses_clean_customer_copy(self, client: TestClient) -> None:
        """Public pricing metadata should not expose legacy mojibake copy."""
        response = client.get("/billing/pricing")
        assert response.status_code == 200

        data = response.json()
        serialized = json.dumps(data, ensure_ascii=False)

        assert "Managed Google Maps foundation work" in serialized
        assert "Competitive Market" in serialized
        assert "Review Booster is included from Calls Growth" in serialized
        for broken_token in ("?", "\uf9de", "\u6e72", "\u6028", "\u5a9b", "\u8e30"):
            assert broken_token not in serialized


class TestBillingSubscription:
    """Authenticated subscription and usage tests."""

    def test_get_subscription_not_found_without_subscription(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Users without a subscription should receive 404."""
        response = client.get("/billing/subscription", headers=auth_headers)
        assert response.status_code == 404

    def test_get_subscription_success(
        self,
        client: TestClient,
        db: Session,
        test_user,
        auth_headers: dict[str, str],
    ) -> None:
        """Users with a subscription should receive current plan info."""
        subscription = Subscription(
            account_id=test_user.id,
            plan_type=PlanType.STARTER,
            status=SubscriptionStatus.ACTIVE,
            access_state="active",
            stripe_price_id="price_starter_yearly",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            locations_limit=1,
            posts_per_month=30,
            api_calls_per_day=500,
            active_addons=["review_booster"],
        )
        db.add(subscription)
        db.commit()

        response = client.get("/billing/subscription", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["plan_type"] == "starter"
        assert data["status"] == "active"
        assert data["billing_cycle"] == "yearly"
        assert data["current_price"] == 990
        assert data["active_addons"] == ["review_booster"]

    def test_get_usage_success(
        self,
        client: TestClient,
        db: Session,
        test_user,
        test_location,
        auth_headers: dict[str, str],
    ) -> None:
        """Usage endpoint should use subscription limits and current location counts."""
        subscription = Subscription(
            account_id=test_user.id,
            plan_type=PlanType.PRO,
            status=SubscriptionStatus.ACTIVE,
            access_state="active",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            locations_limit=3,
            posts_per_month=60,
            api_calls_per_day=2000,
        )
        db.add(subscription)
        db.commit()

        response = client.get("/billing/usage", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["plan"] == "pro"
        assert data["locations_used"] == 1
        assert data["locations_limit"] == 3
        assert data["posts_limit"] == 60
        assert data["api_calls_limit"] == 20000

    def test_get_usage_reads_db_backed_api_call_usage(
        self,
        client: TestClient,
        db: Session,
        test_user,
        auth_headers: dict[str, str],
    ) -> None:
        """Usage endpoint should expose persisted API call usage instead of a placeholder zero."""
        subscription = Subscription(
            account_id=test_user.id,
            plan_type=PlanType.STARTER,
            status=SubscriptionStatus.ACTIVE,
            access_state="active",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            locations_limit=1,
            posts_per_month=30,
            api_calls_per_day=500,
        )
        now = datetime.now(UTC)
        db.add(subscription)
        db.flush()
        db.add(
            UsageRecord(
                account_id=test_user.id,
                usage_type="api_calls",
                date=now,
                daily_count=123,
                monthly_count=456,
                last_used_at=now,
            )
        )
        db.commit()

        response = client.get("/billing/usage", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["api_calls_today"] == 123
        assert data["api_calls_limit"] == 5000

    def test_get_plan_limits_uses_shared_api_call_limit_source(
        self,
        client: TestClient,
        db: Session,
        test_user,
        auth_headers: dict[str, str],
    ) -> None:
        """Plan limits endpoint should derive API call limits from the shared plan config."""
        subscription = Subscription(
            account_id=test_user.id,
            plan_type=PlanType.STARTER,
            status=SubscriptionStatus.ACTIVE,
            access_state="active",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            locations_limit=1,
            posts_per_month=30,
            api_calls_per_day=500,
        )
        db.add(subscription)
        db.commit()

        response = client.get("/billing/limits", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["plan_type"] == "starter"
        assert data["api_calls_per_day"] == 5000

    def test_get_dunning_status_success(
        self,
        client: TestClient,
        db: Session,
        test_user,
        auth_headers: dict[str, str],
        monkeypatch,
    ) -> None:
        """Billing dunning status endpoint should return actionable portal info."""
        monkeypatch.setattr("app.services.dunning_service.settings.app_url", "https://app.example.com", raising=False)
        monkeypatch.setattr("app.services.dunning_service.settings.stripe_secret_key", None, raising=False)

        subscription = Subscription(
            account_id=test_user.id,
            plan_type=PlanType.STARTER,
            status=SubscriptionStatus.ACTIVE,
            access_state="warning",
            dunning_status=DunningStatus.RETRYING,
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            dunning_started_at=utc_now_naive(),
            locations_limit=1,
            posts_per_month=30,
            api_calls_per_day=500,
            stripe_customer_id="cus_test",
        )
        db.add(subscription)
        db.commit()

        response = client.get("/billing/dunning-status", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert data["in_dunning"] is True
        assert data["state"] == "warning"
        assert data["portal_url"] == "https://app.example.com/dashboard/billing"

    def test_start_trial_creates_three_day_free_preview(
        self,
        client: TestClient,
        db: Session,
        test_user,
        auth_headers: dict[str, str],
    ) -> None:
        """No-card preview should stay on the Free plan and avoid paid feature access."""
        response = client.post("/billing/trial/start", headers=auth_headers, json={"plan_type": "free"})
        assert response.status_code == 200, response.text

        data = response.json()
        assert data["plan_type"] == "free"
        assert "3-day free preview" in data["message"]

        subscription = db.query(Subscription).filter(Subscription.account_id == test_user.id).one()
        assert subscription.plan_type == PlanType.FREE
        assert subscription.status == SubscriptionStatus.TRIALING
        assert subscription.posts_per_month == 0
        assert subscription.trial_start is not None
        assert subscription.trial_end is not None
        assert 2.9 <= (subscription.trial_end - subscription.trial_start).total_seconds() / 86400 <= 3.1

        features = client.get("/billing/features", headers=auth_headers)
        assert features.status_code == 200
        feature_payload = features.json()
        assert feature_payload["plan"] == "free"
        assert feature_payload["is_trial"] is True
        assert feature_payload["features"]["basic_dashboard"] is True
        assert feature_payload["features"]["google_posts"] is False
        assert feature_payload["features"]["missed_call_text_back"] is False

    def test_start_trial_rejects_paid_plan_preview(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Paid plan functionality should not be opened by the no-card preview endpoint."""
        response = client.post("/billing/trial/start", headers=auth_headers, json={"plan_type": "starter"})
        assert response.status_code == 400
        assert "no-card preview only includes the Free plan" in response.json()["detail"]


class TestBillingAuditTrail:
    """Billing and Stripe audit visibility tests."""

    def test_get_billing_audit_is_account_scoped_and_filterable(
        self,
        client: TestClient,
        db: Session,
        test_user,
        other_user,
        auth_headers: dict[str, str],
    ) -> None:
        """Billing audit endpoint should return only current-account events."""
        now = datetime.now(UTC)
        db.add_all(
            [
                BillingAuditLog(
                    account_id=test_user.id,
                    action=BillingAuditAction.PAYMENT_FAILED,
                    entity_type="invoice",
                    entity_id="in_failed_001",
                    description="Primary card failed",
                    new_value={
                        "attempt_count": 2,
                        "failure_message": "card_declined",
                    },
                    created_at=now,
                ),
                BillingAuditLog(
                    account_id=test_user.id,
                    action=BillingAuditAction.PLAN_CHANGED,
                    entity_type="subscription",
                    entity_id="sub_live_001",
                    old_value={"plan_type": "starter"},
                    new_value={"plan_type": "pro", "is_upgrade": True},
                    created_at=now - timedelta(minutes=5),
                ),
                BillingAuditLog(
                    account_id=other_user.id,
                    action=BillingAuditAction.REFUND_CREATED,
                    entity_type="refund",
                    entity_id="re_other_001",
                    created_at=now - timedelta(minutes=1),
                ),
            ]
        )
        db.commit()

        response = client.get("/billing/audit?limit=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 2
        assert [item["entity_id"] for item in data["items"]] == [
            "in_failed_001",
            "sub_live_001",
        ]

        filtered = client.get(
            "/billing/audit?action=payment_failed",
            headers=auth_headers,
        )
        assert filtered.status_code == 200
        filtered_data = filtered.json()
        assert filtered_data["total"] == 1
        assert filtered_data["items"][0]["action"] == "payment_failed"

        searched = client.get(
            "/billing/audit?search=card_declined",
            headers=auth_headers,
        )
        assert searched.status_code == 200
        searched_data = searched.json()
        assert searched_data["total"] == 1
        assert searched_data["items"][0]["entity_id"] == "in_failed_001"

    def test_get_billing_webhook_events_matches_account_refs(
        self,
        client: TestClient,
        db: Session,
        test_user,
        auth_headers: dict[str, str],
    ) -> None:
        """Stripe event listing should match account metadata, customer, and subscription refs."""
        subscription = Subscription(
            account_id=test_user.id,
            plan_type=PlanType.STARTER,
            status=SubscriptionStatus.ACTIVE,
            access_state="active",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
            locations_limit=1,
            posts_per_month=30,
            api_calls_per_day=500,
            stripe_customer_id="cus_test_user",
            stripe_subscription_id="sub_test_user",
        )
        db.add(subscription)
        db.flush()

        now = datetime.now(UTC)
        db.add_all(
            [
                StripeEvent(
                    event_id="evt_customer_match",
                    event_type="invoice.payment_failed",
                    payload={
                        "data": {
                            "object": {
                                "id": "in_001",
                                "customer": "cus_test_user",
                            }
                        }
                    },
                    created_at=now,
                    processed_at=now,
                ),
                StripeEvent(
                    event_id="evt_metadata_match",
                    event_type="checkout.session.completed",
                    payload={
                        "data": {
                            "object": {
                                "id": "cs_001",
                                "metadata": {"account_id": str(test_user.id)},
                            }
                        }
                    },
                    created_at=now - timedelta(minutes=1),
                    processed_at=now - timedelta(minutes=1),
                ),
                StripeEvent(
                    event_id="evt_subscription_match",
                    event_type="customer.subscription.updated",
                    payload={
                        "data": {
                            "object": {
                                "id": "sub_test_user",
                            }
                        }
                    },
                    created_at=now - timedelta(minutes=2),
                    processed_at=now - timedelta(minutes=2),
                ),
                StripeEvent(
                    event_id="evt_other_account",
                    event_type="invoice.payment_failed",
                    payload={
                        "data": {
                            "object": {
                                "id": "in_other",
                                "customer": "cus_other_account",
                                "metadata": {"account_id": "someone-else"},
                            }
                        }
                    },
                    created_at=now - timedelta(minutes=3),
                    processed_at=now - timedelta(minutes=3),
                ),
            ]
        )
        db.commit()

        response = client.get("/billing/webhook-events?limit=10", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert [item["event_id"] for item in data["items"]] == [
            "evt_customer_match",
            "evt_metadata_match",
            "evt_subscription_match",
        ]
        assert {item["account_match_source"] for item in data["items"]} == {
            "customer",
            "metadata.account_id",
            "object.id",
        }

        filtered = client.get(
            "/billing/webhook-events?event_type=invoice.payment_failed",
            headers=auth_headers,
        )
        assert filtered.status_code == 200
        filtered_data = filtered.json()
        assert filtered_data["total"] == 1
        assert filtered_data["items"][0]["event_id"] == "evt_customer_match"

        searched = client.get(
            "/billing/webhook-events?search=evt_metadata_match",
            headers=auth_headers,
        )
        assert searched.status_code == 200
        searched_data = searched.json()
        assert searched_data["total"] == 1
        assert searched_data["items"][0]["account_match_source"] == "metadata.account_id"


class TestBillingWebhook:
    """Stripe webhook guardrail tests."""

    def test_webhook_requires_signature(self, client: TestClient) -> None:
        """Billing webhook should reject requests without Stripe signature."""
        response = client.post("/billing/webhook", json={"type": "test"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Missing Stripe signature"
