"""Usage limiter compatibility tests."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.credits import UsageRecord as DbUsageRecord
from app.models.subscription import PlanType, Subscription, SubscriptionStatus
from app.services.credits import CreditsService
from app.services.usage_limiter import UsageLimiterService, UsageType


def test_usage_limiter_reads_db_backed_limits_and_usage(
    db: Session,
    test_user,
) -> None:
    """check_usage should reflect persisted usage rows via CreditsService."""
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
        DbUsageRecord(
            account_id=test_user.id,
            usage_type="ai_content",
            date=now,
            daily_count=20,
            monthly_count=20,
            last_used_at=now - timedelta(minutes=5),
        )
    )
    db.commit()

    result = UsageLimiterService(CreditsService(db)).check_usage(str(test_user.id), UsageType.AI_CONTENT, 1)

    assert result.allowed is False
    assert result.remaining_daily == 0
    assert result.overage_available is True
    assert result.overage_cost_cents == 10


def test_usage_limiter_records_usage_to_db(
    db: Session,
    test_user,
) -> None:
    """record_usage should persist a DB usage row instead of mutating process memory only."""
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

    service = UsageLimiterService(CreditsService(db))
    preview = service.check_usage(str(test_user.id), UsageType.AI_RESPONSE, 1)
    assert preview.allowed is True

    record = service.record_usage(str(test_user.id), UsageType.AI_RESPONSE, 1)
    db.expire_all()

    persisted = (
        db.query(DbUsageRecord)
        .filter(
            DbUsageRecord.account_id == test_user.id,
            DbUsageRecord.usage_type == "ai_response",
        )
        .first()
    )

    assert record.daily_count == 1
    assert persisted is not None
    assert persisted.daily_count == 1
    assert persisted.monthly_count == 1
