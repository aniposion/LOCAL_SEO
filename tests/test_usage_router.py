"""Usage router tests for plan alignment."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.credits import UsageRecord
from app.models.subscription import PlanType, Subscription, SubscriptionStatus


def test_usage_summary_uses_subscription_plan(
    client: TestClient,
    db: Session,
    test_user,
    auth_headers: dict[str, str],
) -> None:
    """Usage summary should report the active subscription plan, not the in-memory default."""
    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.PREMIUM,
        status=SubscriptionStatus.ACTIVE,
        access_state="active",
        current_period_start=datetime.now(UTC),
        current_period_end=datetime.now(UTC) + timedelta(days=30),
        locations_limit=1,
        posts_per_month=120,
        api_calls_per_day=5000,
    )
    db.add(subscription)
    db.commit()

    response = client.get("/usage/summary", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["plan"] == "premium"
    assert data["usage"]["ai_content"]["daily_limit"] == 50
    assert data["usage"]["api_calls"]["daily_limit"] == 20000


def test_usage_summary_reads_db_usage_records(
    client: TestClient,
    db: Session,
    test_user,
    auth_headers: dict[str, str],
) -> None:
    """Usage summary should reflect persisted usage rows instead of in-memory counters."""
    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.ACTIVE,
        access_state="active",
        current_period_start=datetime.now(UTC),
        current_period_end=datetime.now(UTC) + timedelta(days=30),
        locations_limit=1,
        posts_per_month=30,
        api_calls_per_day=5000,
    )
    db.add(subscription)
    db.flush()

    now = datetime.now(UTC)
    db.add_all(
        [
            UsageRecord(
                account_id=test_user.id,
                usage_type="ai_content",
                date=now,
                daily_count=7,
                monthly_count=42,
                last_used_at=now,
            ),
            UsageRecord(
                account_id=test_user.id,
                usage_type="api_calls",
                date=now,
                daily_count=321,
                monthly_count=4321,
                last_used_at=now,
            ),
        ]
    )
    db.commit()

    response = client.get("/usage/summary", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["usage"]["ai_content"]["daily_used"] == 7
    assert data["usage"]["ai_content"]["monthly_used"] == 42
    assert data["usage"]["api_calls"]["daily_used"] == 321
    assert data["usage"]["api_calls"]["monthly_used"] == 4321


def test_usage_check_uses_db_backed_limits(
    client: TestClient,
    db: Session,
    test_user,
    auth_headers: dict[str, str],
) -> None:
    """Usage preview endpoint should use persisted counts and subscription limits."""
    subscription = Subscription(
        account_id=test_user.id,
        plan_type=PlanType.STARTER,
        status=SubscriptionStatus.ACTIVE,
        access_state="active",
        current_period_start=datetime.now(UTC),
        current_period_end=datetime.now(UTC) + timedelta(days=30),
        locations_limit=1,
        posts_per_month=30,
        api_calls_per_day=5000,
    )
    db.add(subscription)
    db.flush()

    now = datetime.now(UTC)
    db.add(
        UsageRecord(
            account_id=test_user.id,
            usage_type="ai_content",
            date=now,
            daily_count=20,
            monthly_count=20,
            last_used_at=now - timedelta(minutes=5),
        )
    )
    db.commit()

    response = client.post("/usage/check/ai_content?count=1", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["allowed"] is False
    assert data["overage_available"] is True
    assert data["overage_cost_cents"] == 10
