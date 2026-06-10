from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.models.metrics import MetricSnapshot, SnapshotType
from app.models.post import Platform, Post, PostStatus
from app.models.revenue import RevenueProfile
from app.models.review_response import ResponseStatus, ReviewIntent, ReviewResponse
from app.models.subscription import PlanType, Subscription, SubscriptionStatus
from app.services.roi_service import ROIService


def test_generate_roi_report_uses_revenue_profile_and_subscription(db, test_user, test_location):
    now = datetime.now(UTC)

    db.add(
        RevenueProfile(
            location_id=test_location.id,
            average_order_value=Decimal('200.00'),
            gross_margin_percent=Decimal('40.00'),
            call_to_booking_rate=Decimal('50.00'),
            booking_to_visit_rate=Decimal('80.00'),
            visit_to_sale_rate=Decimal('50.00'),
            missed_call_recovery_rate=Decimal('20.00'),
            review_to_conversion_lift_percent=Decimal('10.00'),
            owner_hourly_value=Decimal('75.00'),
        )
    )
    db.add(
        Subscription(
            account_id=test_user.id,
            plan_type=PlanType.PRO,
            status=SubscriptionStatus.ACTIVE,
            access_state='active',
        )
    )
    db.add(
        MetricSnapshot(
            location_id=test_location.id,
            snapshot_date=now.date(),
            snapshot_type=SnapshotType.DAILY,
            calls=10,
            directions=4,
            website_clicks=6,
            new_reviews=2,
            total_reviews=10,
            call_value=Decimal('50.00'),
        )
    )
    db.add(
        Post(
            id=uuid4(),
            location_id=test_location.id,
            platform=Platform.GBP,
            status=PostStatus.POSTED,
            title='Posted post',
            created_at=now,
        )
    )
    db.add(
        ReviewResponse(
            location_id=test_location.id,
            review_id='review-1',
            review_author='Customer',
            review_rating=5,
            review_text='Great service',
            review_date=now,
            ai_draft='Thanks for visiting',
            intent=ReviewIntent.PRAISE,
            status=ResponseStatus.PUBLISHED,
            created_at=now,
        )
    )
    db.commit()

    report = ROIService(db).generate_roi_report(
        test_location.id,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=1),
    )

    assert report.subscription_cost == 149
    assert report.total_hours_saved == 0.4
    assert report.total_money_saved == 30.0
    assert report.revenue_projection['estimated_revenue_from_calls'] == 400.0
    assert report.revenue_projection['estimated_gross_profit_from_calls'] == 160.0
    assert report.revenue_projection['digital_intent']['estimated_digital_revenue'] == 800.0
    assert report.revenue_projection['review_uplift_revenue'] == 120.0
    assert report.roi_percentage == 59.7
    assert 'estimated $400.00 in call-driven revenue' in report.summary_message
    assert 'Review-driven conversion uplift added about $120.00' in report.summary_message
