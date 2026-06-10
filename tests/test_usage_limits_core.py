"""Tests for legacy usage-limit warning audits."""

import pytest
from fastapi import HTTPException

from app.core.usage_limits import FeatureName, UsageLimitChecker
from app.models.location import Location
from app.models.notification import NotificationDeliveryLog, NotificationEvent
from app.models.post import Platform, Post, PostStatus
from app.models.review_response import ResponseStatus, ReviewIntent, ReviewResponse


def test_usage_limit_warning_persists_inbox_event_once_per_threshold(
    db,
    test_user,
    monkeypatch,
) -> None:
    """80% warnings should create one inbox event and not spam duplicates."""
    monkeypatch.setattr(
        UsageLimitChecker,
        "get_current_usage",
        lambda self, *args, **kwargs: 40,
    )
    monkeypatch.setattr(
        UsageLimitChecker,
        "get_usage_limit",
        lambda self, *args, **kwargs: 50,
    )

    checker = UsageLimitChecker(db)
    first = checker.check_usage_limit(
        test_user.id,
        FeatureName.REVIEW_RESPONSE,
        raise_exception=False,
    )
    second = checker.check_usage_limit(
        test_user.id,
        FeatureName.REVIEW_RESPONSE,
        raise_exception=False,
    )

    assert first["usage_percentage"] == 80.0
    assert second["usage_percentage"] == 80.0

    events = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id)
        .order_by(NotificationEvent.created_at.asc())
        .all()
    )
    assert len(events) == 1
    assert events[0].type == "usage_warning_review_response_80"
    assert events[0].url == "/dashboard/usage"

    logs = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.account_id == test_user.id)
        .all()
    )
    assert len(logs) == 1
    assert logs[0].channel == "inbox"
    assert logs[0].delivery_status == "delivered"
    assert logs[0].notification_event_id == events[0].id


def test_usage_limit_warning_escalates_to_next_threshold(
    db,
    test_user,
    monkeypatch,
) -> None:
    """Crossing from 80% to 90% should record a second, distinct warning."""
    usage_state = {"current": 40}
    monkeypatch.setattr(
        UsageLimitChecker,
        "get_current_usage",
        lambda self, *args, **kwargs: usage_state["current"],
    )
    monkeypatch.setattr(
        UsageLimitChecker,
        "get_usage_limit",
        lambda self, *args, **kwargs: 50,
    )

    checker = UsageLimitChecker(db)
    checker.check_usage_limit(
        test_user.id,
        FeatureName.REVIEW_RESPONSE,
        raise_exception=False,
    )

    usage_state["current"] = 45
    checker.check_usage_limit(
        test_user.id,
        FeatureName.REVIEW_RESPONSE,
        raise_exception=False,
    )

    event_types = [
        item.type
        for item in db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id)
        .order_by(NotificationEvent.created_at.asc())
        .all()
    ]
    assert event_types == [
        "usage_warning_review_response_80",
        "usage_warning_review_response_90",
    ]


def test_usage_limit_warning_respects_disabled_performance_alerts(
    db,
    test_user,
    monkeypatch,
) -> None:
    """No warning should be recorded when performance alerts are disabled."""
    test_user.settings = {
        "notification_preferences": {
            "performance_alerts": False,
        }
    }
    db.add(test_user)
    db.commit()

    monkeypatch.setattr(
        UsageLimitChecker,
        "get_current_usage",
        lambda self, *args, **kwargs: 40,
    )
    monkeypatch.setattr(
        UsageLimitChecker,
        "get_usage_limit",
        lambda self, *args, **kwargs: 50,
    )

    checker = UsageLimitChecker(db)
    checker.check_usage_limit(
        test_user.id,
        FeatureName.REVIEW_RESPONSE,
        raise_exception=False,
    )

    assert (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id)
        .count()
        == 0
    )
    assert (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.account_id == test_user.id)
        .count()
        == 0
    )


def test_usage_limit_reached_persists_blocking_warning(
    db,
    test_user,
    monkeypatch,
) -> None:
    """A hard block should also leave an inbox/audit event for operators and users."""
    monkeypatch.setattr(
        UsageLimitChecker,
        "get_current_usage",
        lambda self, *args, **kwargs: 50,
    )
    monkeypatch.setattr(
        UsageLimitChecker,
        "get_usage_limit",
        lambda self, *args, **kwargs: 50,
    )

    checker = UsageLimitChecker(db)

    with pytest.raises(HTTPException) as exc_info:
        checker.check_usage_limit(
            test_user.id,
            FeatureName.REVIEW_RESPONSE,
            raise_exception=True,
        )

    assert exc_info.value.status_code == 402
    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id)
        .one()
    )
    assert event.type == "usage_warning_review_response_100"
    assert event.url == "/dashboard/usage"

    checker.check_usage_limit(
        test_user.id,
        FeatureName.REVIEW_RESPONSE,
        raise_exception=False,
    )

    assert (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id)
        .count()
        == 1
    )


def test_usage_limit_reached_with_zero_included_still_records_warning(
    db,
    test_user,
    monkeypatch,
) -> None:
    """Plans with zero included usage should still leave an inbox/audit warning."""
    monkeypatch.setattr(
        UsageLimitChecker,
        "get_current_usage",
        lambda self, *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        UsageLimitChecker,
        "get_usage_limit",
        lambda self, *args, **kwargs: 0,
    )

    checker = UsageLimitChecker(db)

    with pytest.raises(HTTPException) as exc_info:
        checker.check_usage_limit(
            test_user.id,
            FeatureName.REVIEW_RESPONSE,
            raise_exception=True,
        )

    assert exc_info.value.status_code == 402
    event = (
        db.query(NotificationEvent)
        .filter(NotificationEvent.account_id == test_user.id)
        .one()
    )
    assert event.type == "usage_warning_review_response_100"
    assert "does not include review response generations" in event.body.lower()


def test_usage_counts_are_scoped_to_the_account(
    db,
    test_user,
    other_user,
) -> None:
    """Legacy usage-limit counters should not count another account's records."""
    own_location = Location(
        account_id=test_user.id,
        name="Own Location",
        address="100 Main St",
    )
    other_location = Location(
        account_id=other_user.id,
        name="Other Location",
        address="200 Main St",
    )
    db.add_all([own_location, other_location])
    db.commit()
    db.refresh(own_location)
    db.refresh(other_location)

    own_response = ReviewResponse(
        location_id=own_location.id,
        review_id="own-review-1",
        review_rating=5,
        review_text="Great service",
        ai_draft="Thanks for the review!",
        intent=ReviewIntent.PRAISE,
        status=ResponseStatus.PENDING,
    )
    other_response = ReviewResponse(
        location_id=other_location.id,
        review_id="other-review-1",
        review_rating=5,
        review_text="Great service",
        ai_draft="Thanks for the review!",
        intent=ReviewIntent.PRAISE,
        status=ResponseStatus.PENDING,
    )
    db.add_all([own_response, other_response])
    db.commit()

    checker = UsageLimitChecker(db)
    own_count = checker.get_current_usage(test_user.id, FeatureName.REVIEW_RESPONSE)
    other_count = checker.get_current_usage(other_user.id, FeatureName.REVIEW_RESPONSE)

    assert own_count == 1
    assert other_count == 1


def test_ai_content_usage_counts_generated_posts_for_the_account(
    db,
    test_user,
    other_user,
) -> None:
    """AI content usage should count only generated posts for the target account."""
    own_location = Location(
        account_id=test_user.id,
        name="Own Content Location",
        address="100 Main St",
    )
    other_location = Location(
        account_id=other_user.id,
        name="Other Content Location",
        address="200 Main St",
    )
    db.add_all([own_location, other_location])
    db.commit()
    db.refresh(own_location)
    db.refresh(other_location)

    own_generated_post = Post(
        location_id=own_location.id,
        platform=Platform.GBP,
        status=PostStatus.DRAFT,
        title="Generated post",
        body="Generated body",
        generated_by="gpt-5",
    )
    own_manual_post = Post(
        location_id=own_location.id,
        platform=Platform.GBP,
        status=PostStatus.DRAFT,
        title="Manual post",
        body="Manual body",
        generated_by=None,
    )
    other_generated_post = Post(
        location_id=other_location.id,
        platform=Platform.GBP,
        status=PostStatus.DRAFT,
        title="Other generated post",
        body="Generated body",
        generated_by="gpt-5",
    )
    db.add_all([own_generated_post, own_manual_post, other_generated_post])
    db.commit()

    checker = UsageLimitChecker(db)

    assert checker.get_current_usage(test_user.id, FeatureName.AI_CONTENT) == 1
    assert checker.get_current_usage(other_user.id, FeatureName.AI_CONTENT) == 1
