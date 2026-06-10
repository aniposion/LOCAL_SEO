"""Seed demo data for ROI, review responder, and social proof flows."""

import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.account import Account
from app.models.calls import CallLog, TwilioNumber
from app.models.location import Location
from app.models.metrics import MetricSnapshot
from app.models.post import Platform, Post
from app.models.revenue import RevenueProfile
from app.models.review_response import ResponseStatus, ReviewIntent, ReviewResponse
from app.models.social_proof import SocialProofCard, SocialProofStatus
from app.models.subscription import PlanType, Subscription, SubscriptionStatus


def get_or_create_account(db) -> Account:
    account = db.query(Account).filter(Account.email == "test@example.com").first()
    if account:
        return account

    account = Account(
        email="test@example.com",
        password_hash=get_password_hash("password123"),
        full_name="Test Owner",
        company_name="Local SEO Demo",
        notification_channel="email",
        is_active=True,
        is_verified=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_or_create_subscription(db, account: Account) -> Subscription:
    subscription = (
        db.query(Subscription).filter(Subscription.account_id == account.id).first()
    )
    if subscription:
        return subscription

    subscription = Subscription(
        account_id=account.id,
        plan_type=PlanType.PRO,
        status=SubscriptionStatus.ACTIVE,
        access_state="active",
        current_period_start=datetime.now(timezone.utc) - timedelta(days=10),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=20),
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def get_or_create_location(db, account: Account) -> Location:
    location = db.query(Location).filter(Location.account_id == account.id).first()
    if location:
        return location

    location = Location(
        account_id=account.id,
        name="Downtown Coffee Shop",
        address="123 Main Street",
        city="Chicago",
        state="IL",
        postal_code="60601",
        country="US",
        phone="+1-312-555-0100",
        website_url="https://downtowncoffee.example.com",
        description="Neighborhood coffee shop with breakfast and lunch.",
        gbp_location_id="demo-gbp-location-1",
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def seed_revenue_profile(db, location: Location) -> None:
    profile = db.query(RevenueProfile).filter(RevenueProfile.location_id == location.id).first()
    if profile:
        return

    profile = RevenueProfile(
        location_id=location.id,
        business_type="coffee_shop",
        currency="USD",
        average_order_value=Decimal("28.00"),
        gross_margin_percent=Decimal("62.00"),
        call_to_booking_rate=Decimal("18.00"),
        booking_to_visit_rate=Decimal("85.00"),
        visit_to_sale_rate=Decimal("92.00"),
        missed_call_recovery_rate=Decimal("35.00"),
        review_to_conversion_lift_percent=Decimal("4.50"),
        owner_hourly_value=Decimal("45.00"),
    )
    db.add(profile)
    db.commit()


def seed_posts(db, location: Location) -> None:
    existing = db.query(Post).filter(Post.location_id == location.id).count()
    if existing >= 3:
        return

    posts = [
        Post(
            location_id=location.id,
            platform=Platform.GBP,
            status="POSTED",
            title="New breakfast combo",
            body="Try our breakfast sandwich and latte combo this week.",
            posted_at=datetime.now(timezone.utc) - timedelta(days=4),
        ),
        Post(
            location_id=location.id,
            platform=Platform.GBP,
            status="POSTED",
            title="Weekend pastry special",
            body="Fresh croissants and seasonal danishes are available all weekend.",
            posted_at=datetime.now(timezone.utc) - timedelta(days=8),
        ),
        Post(
            location_id=location.id,
            platform=Platform.INSTAGRAM,
            status="approved",
            title="Latte art feature",
            body="Our baristas are serving new spring latte art designs.",
        ),
    ]
    db.add_all(posts)
    db.commit()


def seed_metric_snapshots(db, location: Location) -> None:
    existing = db.query(MetricSnapshot).filter(MetricSnapshot.location_id == location.id).count()
    if existing >= 14:
        return

    today = date.today()
    snapshots = []
    for days_ago in range(14):
        snapshot_date = today - timedelta(days=days_ago)
        snapshots.append(
            MetricSnapshot(
                location_id=location.id,
                snapshot_date=snapshot_date,
                snapshot_type="daily",
                calls=8 + (days_ago % 4),
                directions=18 + (days_ago % 5),
                website_clicks=10 + (days_ago % 3),
                profile_views=90 + days_ago,
                photo_views=60 + days_ago,
                total_reviews=180 + days_ago,
                new_reviews=1 if days_ago in (2, 5, 9) else 0,
                avg_rating=Decimal("4.8"),
                calls_delta=2,
                directions_delta=3,
                website_clicks_delta=1,
                call_value=Decimal("28.00"),
                raw_data={"seeded": True},
            )
        )
    db.add_all(snapshots)
    db.commit()


def seed_call_data(db, location: Location) -> None:
    twilio_number = (
        db.query(TwilioNumber).filter(TwilioNumber.location_id == location.id).first()
    )
    if not twilio_number:
        twilio_number = TwilioNumber(
            location_id=location.id,
            twilio_number="+13125550199",
            forward_to=location.phone or "+13125550100",
            missed_call_sms_enabled=True,
            sms_template="Hi! Sorry we missed your call at Downtown Coffee Shop. Reply here and we will help.",
        )
        db.add(twilio_number)
        db.commit()
        db.refresh(twilio_number)

    existing = db.query(CallLog).filter(CallLog.location_id == location.id).count()
    if existing >= 10:
        return

    call_logs = []
    now = datetime.now(timezone.utc)
    for index in range(10):
        status = "completed" if index % 3 else "no-answer"
        call_logs.append(
            CallLog(
                location_id=location.id,
                twilio_number_id=twilio_number.id,
                twilio_call_sid=f"seed-call-{location.id}-{index}",
                caller_number=f"+13125550{100 + index:03d}",
                call_status=status,
                call_duration=120 if status == "completed" else 0,
                sms_sent=status != "completed",
                sms_sent_at=now - timedelta(days=index) if status != "completed" else None,
                tags=["seeded", "roi"],
                created_at=now - timedelta(days=index),
                updated_at=now - timedelta(days=index),
            )
        )
    db.add_all(call_logs)
    db.commit()


def seed_review_responses(db, account: Account, location: Location) -> None:
    existing = db.query(ReviewResponse).filter(ReviewResponse.location_id == location.id).count()
    if existing >= 4:
        return

    now = datetime.now(timezone.utc)
    responses = [
        ReviewResponse(
            location_id=location.id,
            review_id=f"seed-review-{uuid4()}",
            review_author="Sarah K",
            review_rating=5,
            review_text="Fantastic coffee and the staff remembered my order on the second visit.",
            review_date=now - timedelta(days=2),
            platform="google",
            sentiment_score=0.95,
            intent=ReviewIntent.PRAISE,
            detected_issues="[]",
            ai_draft="Thank you so much for the kind words. We are glad the team made you feel welcome and that you loved the coffee. We look forward to seeing you again soon.\n\nGenerated by AI - Subject to human review",
            tone="grateful",
            status=ResponseStatus.PENDING,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        ),
        ReviewResponse(
            location_id=location.id,
            review_id=f"seed-review-{uuid4()}",
            review_author="Michael T",
            review_rating=4,
            review_text="Great pastries and quick service, but parking is a bit tight in the morning.",
            review_date=now - timedelta(days=4),
            platform="google",
            sentiment_score=0.62,
            intent=ReviewIntent.SUGGESTION,
            detected_issues='["parking"]',
            ai_draft="Thank you for visiting and for the thoughtful feedback. We are happy you enjoyed the pastries and service, and we understand the parking challenge during busy hours. We hope to welcome you back again soon.\n\nGenerated by AI - Subject to human review",
            tone="warm",
            status=ResponseStatus.PUBLISHED,
            approved_by=account.id,
            approved_at=now - timedelta(days=4),
            published_at=now - timedelta(days=4),
            platform_response_id="seed-platform-response-1",
            created_at=now - timedelta(days=4),
            updated_at=now - timedelta(days=4),
        ),
        ReviewResponse(
            location_id=location.id,
            review_id=f"seed-review-{uuid4()}",
            review_author="Dana R",
            review_rating=5,
            review_text="Best neighborhood cafe for quick meetings. Reliable Wi-Fi and great espresso.",
            review_date=now - timedelta(days=7),
            platform="google",
            sentiment_score=0.88,
            intent=ReviewIntent.PRAISE,
            detected_issues="[]",
            ai_draft="We appreciate your review and are glad the cafe worked well for your meeting. Thank you for highlighting the Wi-Fi and espresso. We hope to see you back for your next coffee break.\n\nGenerated by AI - Subject to human review",
            tone="grateful",
            status=ResponseStatus.PUBLISHED,
            approved_by=account.id,
            approved_at=now - timedelta(days=7),
            published_at=now - timedelta(days=7),
            platform_response_id="seed-platform-response-2",
            created_at=now - timedelta(days=7),
            updated_at=now - timedelta(days=7),
        ),
    ]
    db.add_all(responses)
    db.commit()


def seed_social_cards(db, account: Account, location: Location) -> None:
    existing = db.query(SocialProofCard).filter(SocialProofCard.location_id == location.id).count()
    if existing >= 3:
        return

    now = datetime.now(timezone.utc)
    cards = [
        SocialProofCard(
            location_id=location.id,
            review_id=f"seed-social-review-{uuid4()}",
            review_author="Alicia P",
            review_rating=5,
            review_text="Loved the mocha and the cozy seating. Perfect place to work for an hour.",
            review_date=now - timedelta(days=1),
            card_title="Perfect Work Spot",
            card_text="Loved the mocha and the cozy seating. Perfect place to work for an hour.",
            layout_style="instagram_square",
            status=SocialProofStatus.PENDING,
            background_color="#2D221C",
            final_card_url="https://example.com/seed-social-card-1.png",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        ),
        SocialProofCard(
            location_id=location.id,
            review_id=f"seed-social-review-{uuid4()}",
            review_author="Brian J",
            review_rating=5,
            review_text="Fast service and great breakfast sandwich before work.",
            review_date=now - timedelta(days=6),
            card_title="Morning Favorite",
            card_text="Fast service and great breakfast sandwich before work.",
            layout_style="instagram_square",
            status=SocialProofStatus.APPROVED,
            approved_by=account.id,
            approved_at=now - timedelta(days=6),
            background_color="#1E3A34",
            final_card_url="https://example.com/seed-social-card-2.png",
            created_at=now - timedelta(days=6),
            updated_at=now - timedelta(days=6),
        ),
    ]
    db.add_all(cards)
    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        account = get_or_create_account(db)
        get_or_create_subscription(db, account)
        location = get_or_create_location(db, account)
        seed_revenue_profile(db, location)
        seed_posts(db, location)
        seed_metric_snapshots(db, location)
        seed_call_data(db, location)
        seed_review_responses(db, account, location)
        seed_social_cards(db, account, location)
        print(f"Seed complete for account={account.email} location={location.name}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
