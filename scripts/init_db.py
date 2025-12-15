"""Initialize database and create test user with sample data."""

import sys
sys.path.insert(0, ".")

import uuid
from datetime import datetime, timedelta, timezone
from random import randint, choice

from app.db.session import engine, SessionLocal, Base
from app.models.account import Account
from app.models.location import Location
from app.models.subscription import Subscription, PlanType
from app.models.post import Post
from app.models.analytics import Analytics
from app.core.security import get_password_hash

def init_db():
    """Create all tables."""
    # Import all models to register them
    from app.models import account, location, subscription, credits, post, analytics
    
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")

def create_test_data():
    """Create test user with sample data."""
    db = SessionLocal()
    try:
        # Check if test user exists
        existing = db.query(Account).filter(Account.email == "test@example.com").first()
        if existing:
            print(f"Test user already exists: test@example.com")
            user = existing
        else:
            # Create test user
            user = Account(
                email="test@example.com",
                password_hash=get_password_hash("password123"),
                full_name="Test User",
                company_name="Test Business Inc.",
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print("Test user created!")
            print("  Email: test@example.com")
            print("  Password: password123")

        # Create subscription if not exists
        existing_sub = db.query(Subscription).filter(Subscription.account_id == user.id).first()
        if not existing_sub:
            subscription = Subscription(
                account_id=user.id,
                plan_type=PlanType.PRO,
                status="active",
                current_period_start=datetime.now(timezone.utc),
                current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
            )
            db.add(subscription)
            db.commit()
            print("Subscription created (Pro tier)")

        # Create locations if not exist
        existing_locations = db.query(Location).filter(Location.account_id == user.id).all()
        if not existing_locations:
            locations_data = [
                {
                    "name": "Downtown Coffee Shop",
                    "address": "123 Main Street",
                    "city": "New York",
                    "state": "NY",
                    "postal_code": "10001",
                    "phone": "+1 (555) 123-4567",
                    "website_url": "https://downtowncoffee.com",
                    "description": "Cozy coffee shop in downtown Manhattan",
                    "gbp_location_id": "ChIJ_demo_place_1",
                },
                {
                    "name": "Uptown Bakery",
                    "address": "456 Park Avenue",
                    "city": "New York",
                    "state": "NY",
                    "postal_code": "10022",
                    "phone": "+1 (555) 987-6543",
                    "website_url": "https://uptownbakery.com",
                    "description": "Fresh baked goods daily",
                    "gbp_location_id": "ChIJ_demo_place_2",
                },
            ]
            
            for loc_data in locations_data:
                location = Location(
                    account_id=user.id,
                    **loc_data
                )
                db.add(location)
            db.commit()
            print(f"Created {len(locations_data)} locations")

        # Get locations for analytics
        locations = db.query(Location).filter(Location.account_id == user.id).all()

        # Create sample analytics data
        for location in locations:
            existing_analytics = db.query(Analytics).filter(
                Analytics.location_id == location.id
            ).first()
            
            if not existing_analytics:
                # Create 30 days of analytics
                for i in range(30):
                    analytics_date = datetime.now(timezone.utc) - timedelta(days=i)
                    analytics_record = Analytics(
                        location_id=location.id,
                        platform="google",
                        date=analytics_date.date(),
                        impressions=randint(50, 200),
                        clicks=randint(30, 150),
                        calls=randint(5, 25),
                        direction_requests=randint(10, 40),
                    )
                    db.add(analytics_record)
                db.commit()
                print(f"Created 30 days of analytics for {location.name}")

        # Create sample posts
        from app.models.post import Platform, PostStatus
        for location in locations:
            existing_posts = db.query(Post).filter(Post.location_id == location.id).first()
            if not existing_posts:
                posts_data = [
                    {
                        "title": "Weekend Special!",
                        "body": "Join us this weekend for our special promotion! 20% off all items.",
                        "platform": Platform.GBP,
                        "status": PostStatus.POSTED,
                    },
                    {
                        "title": "New Menu Items",
                        "body": "We're excited to announce our new seasonal menu. Come try our latest creations!",
                        "platform": Platform.GBP,
                        "status": PostStatus.PENDING_APPROVAL,
                    },
                    {
                        "title": "Holiday Hours",
                        "body": "Please note our updated hours for the holiday season.",
                        "platform": Platform.GBP,
                        "status": PostStatus.DRAFT,
                    },
                ]
                for post_data in posts_data:
                    post = Post(
                        location_id=location.id,
                        **post_data
                    )
                    db.add(post)
                db.commit()
                print(f"Created sample posts for {location.name}")

        print("\n✅ Test data setup complete!")
        
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    create_test_data()
