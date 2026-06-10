"""Tests for persistent AI feature rate limiting."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.rate_limiter import RateLimiter
from app.models.credits import UsageRecord
from app.models.competitor import Competitor, CompetitorAnalysis, CompetitorReview, CompetitorStatus
from app.models.social_proof import SocialProofCard, SocialProofStatus
from app.models.subscription import PlanType, Subscription, SubscriptionStatus


def _starter_subscription(test_user) -> Subscription:
    return Subscription(
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


def _make_competitor_analysis_fixture(db: Session, test_location) -> Competitor:
    now = datetime.now(UTC).replace(tzinfo=None)
    competitor = Competitor(
        location_id=test_location.id,
        place_id=f"place-{uuid4()}",
        name="Nearby Rival",
        address="123 Market St",
        business_type="restaurant",
        rating=4.5,
        review_count=42,
        distance_miles=1.1,
        status=CompetitorStatus.ACTIVE,
        raw_data={"source": "test"},
        last_synced_at=now - timedelta(days=1),
        last_review_synced_at=now - timedelta(days=1),
    )
    db.add(competitor)
    db.commit()
    db.refresh(competitor)

    db.add(
        CompetitorReview(
            competitor_id=competitor.id,
            review_id=f"review-{uuid4()}",
            author_name="Customer",
            rating=5,
            text="Great service and friendly team.",
            publish_time=now - timedelta(days=2),
        )
    )
    db.commit()
    return competitor


def _make_social_proof_card(test_location, *, card_id: int, final_card_url: str | None) -> SocialProofCard:
    now = datetime.now(UTC).replace(tzinfo=None)
    card = SocialProofCard(
        id=card_id,
        location_id=test_location.id,
        review_id=f"review-{uuid4()}",
        review_author="Customer",
        review_rating=5,
        review_text="Amazing service and fast response.",
        review_date=now - timedelta(days=1),
        card_title="Customer Favorite",
        card_text="Amazing service and fast response.",
        image_prompt="Warm branded social proof card",
        background_image_url="https://cdn.example.com/bg.png",
        final_card_url=final_card_url,
        layout_style="instagram_square",
        text_color="#FFFFFF",
        background_color="#000000",
        font_family="Arial",
        status=SocialProofStatus.PENDING if final_card_url else SocialProofStatus.DRAFT,
        generated_by_ai="imagen-3",
        created_at=now,
        updated_at=now,
    )
    return card


def test_rate_limiter_persists_usage_and_blocks_after_limit(
    db: Session,
    test_user,
) -> None:
    """Rate limiter should use persistent usage rows and stop after the plan limit."""
    db.add(_starter_subscription(test_user))
    db.commit()

    limiter = RateLimiter(db)

    for _ in range(4):
        allowed, message = limiter.check_limit(test_user.id, "competitor_analysis", increment=True)
        assert allowed is True
        assert "Remaining" in (message or "")

    blocked, message = limiter.check_limit(test_user.id, "competitor_analysis", increment=True)
    assert blocked is False
    assert "Monthly limit exceeded" in (message or "")

    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "competitor_analysis",
        )
        .scalar()
    )
    assert int(total or 0) == 4


def test_rate_limiter_preview_does_not_persist_until_recorded(
    db: Session,
    test_user,
) -> None:
    """Preview checks should not consume usage before the downstream action succeeds."""
    db.add(_starter_subscription(test_user))
    db.commit()

    limiter = RateLimiter(db)

    allowed, message = limiter.check_limit(test_user.id, "competitor_analysis", increment=False)
    assert allowed is True
    assert "Remaining" in (message or "")

    preview_total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "competitor_analysis",
        )
        .scalar()
    )
    assert int(preview_total or 0) == 0

    limiter.record_usage(test_user.id, "competitor_analysis")

    recorded_total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "competitor_analysis",
        )
        .scalar()
    )
    assert int(recorded_total or 0) == 1


def test_competitor_route_uses_persistent_rate_limiter(
    client: TestClient,
    db: Session,
    test_user,
    test_location,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    """Competitor route should return 429 after the starter plan limit is exhausted."""
    db.add(_starter_subscription(test_user))
    db.commit()

    async def fake_discover(self, location_id, radius_miles, business_type, max_results):
        return []

    monkeypatch.setattr(
        "app.services.competitor_service.CompetitorService.discover_competitors",
        fake_discover,
    )

    payload = {
        "location_id": str(test_location.id),
        "radius_miles": 3.0,
        "business_type": "restaurant",
        "max_results": 3,
    }

    for _ in range(4):
        response = client.post("/competitor/discover", headers=auth_headers, json=payload)
        assert response.status_code == 200, response.text
        assert response.json() == []

    blocked = client.post("/competitor/discover", headers=auth_headers, json=payload)
    assert blocked.status_code == 429
    assert "Monthly limit exceeded" in blocked.json()["detail"]

    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "competitor_analysis",
        )
        .scalar()
    )
    assert int(total or 0) == 4


def test_competitor_route_failure_does_not_consume_usage(
    client: TestClient,
    db: Session,
    test_user,
    test_location,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    """Failed downstream work should not burn the feature limit anymore."""
    db.add(_starter_subscription(test_user))
    db.commit()

    async def broken_discover(self, location_id, radius_miles, business_type, max_results):
        raise RuntimeError("upstream provider failed")

    monkeypatch.setattr(
        "app.services.competitor_service.CompetitorService.discover_competitors",
        broken_discover,
    )

    payload = {
        "location_id": str(test_location.id),
        "radius_miles": 3.0,
        "business_type": "restaurant",
        "max_results": 3,
    }

    response = client.post("/competitor/discover", headers=auth_headers, json=payload)
    assert response.status_code == 500

    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "competitor_analysis",
        )
        .scalar()
    )
    assert int(total or 0) == 0


def test_competitor_analyze_cached_result_does_not_consume_usage(
    client: TestClient,
    db: Session,
    test_user,
    test_location,
    auth_headers: dict[str, str],
) -> None:
    """Returning a cached competitor analysis should not burn usage again."""
    db.add(_starter_subscription(test_user))
    competitor = _make_competitor_analysis_fixture(db, test_location)
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        CompetitorAnalysis(
            location_id=test_location.id,
            competitor_id=competitor.id,
            week_start=now - timedelta(days=7),
            week_end=now,
            trending_keywords=["service", "friendly"],
            threat_level="medium",
            rating_trend="stable",
            recommended_actions=[
                {
                    "title": "Watch reviews",
                    "description": "Monitor weekly review themes.",
                    "priority": "medium",
                    "effort": "low",
                }
            ],
            summary_text="Cached competitor analysis snapshot.",
            metrics_snapshot={"competitors": [{"id": competitor.id}]},
            created_at=now - timedelta(hours=2),
        )
    )
    db.commit()

    response = client.post(
        "/competitor/analyze",
        headers=auth_headers,
        json={"location_id": str(test_location.id), "force_refresh": False},
    )

    assert response.status_code == 200, response.text
    assert response.json()["summary_text"] == "Cached competitor analysis snapshot."

    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "competitor_analysis",
        )
        .scalar()
    )
    assert int(total or 0) == 0


def test_competitor_analyze_fallback_result_does_not_consume_usage(
    client: TestClient,
    db: Session,
    test_user,
    test_location,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    """Parsed fallback analysis should stay honest and not consume usage."""
    db.add(_starter_subscription(test_user))
    _make_competitor_analysis_fixture(db, test_location)

    async def fake_generate(_self, _prompt: str) -> str:
        return "not valid json"

    monkeypatch.setattr("app.integrations.llm.LLMAdapter.generate", fake_generate)

    response = client.post(
        "/competitor/analyze",
        headers=auth_headers,
        json={"location_id": str(test_location.id), "force_refresh": True},
    )

    assert response.status_code == 200, response.text
    assert response.json()["summary_text"] == "Competitor analysis completed. Continue monitoring trends."

    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "competitor_analysis",
        )
        .scalar()
    )
    assert int(total or 0) == 0


def test_competitor_analyze_real_ai_result_consumes_usage(
    client: TestClient,
    db: Session,
    test_user,
    test_location,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    """A real AI-generated competitor analysis should still consume usage once."""
    db.add(_starter_subscription(test_user))
    _make_competitor_analysis_fixture(db, test_location)

    async def fake_generate(_self, _prompt: str) -> str:
        return """
        {
          "trending_keywords": ["service", "speed", "value"],
          "threat_level": "high",
          "rating_trend": "improving",
          "recommended_actions": [
            {"title": "Speed up service", "description": "Reduce wait times.", "priority": "high", "effort": "medium"}
          ],
          "summary_text": "Competitors are improving their service speed."
        }
        """

    monkeypatch.setattr("app.integrations.llm.LLMAdapter.generate", fake_generate)

    response = client.post(
        "/competitor/analyze",
        headers=auth_headers,
        json={"location_id": str(test_location.id), "force_refresh": True},
    )

    assert response.status_code == 200, response.text
    assert response.json()["summary_text"] == "Competitors are improving their service speed."

    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "competitor_analysis",
        )
        .scalar()
    )
    assert int(total or 0) == 1


def test_social_proof_generate_card_without_final_asset_does_not_consume_usage(
    client: TestClient,
    db: Session,
    test_user,
    test_location,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    """An incomplete social proof card should not consume usage yet."""
    db.add(_starter_subscription(test_user))
    db.commit()

    async def fake_generate_card(self, request):
        return _make_social_proof_card(test_location, card_id=1, final_card_url=None)

    monkeypatch.setattr(
        "app.services.social_proof_service.SocialProofService.generate_card",
        fake_generate_card,
    )

    response = client.post(
        "/social-proof/generate-card",
        headers=auth_headers,
        json={
            "location_id": str(test_location.id),
            "review_id": "review-sp-1",
            "review_author": "Customer",
            "review_rating": 5,
            "review_text": "Amazing service and fast response.",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["final_card_url"] is None

    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "social_proof_cards",
        )
        .scalar()
    )
    assert int(total or 0) == 0


def test_social_proof_generate_card_with_final_asset_consumes_usage(
    client: TestClient,
    db: Session,
    test_user,
    test_location,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    """A completed social proof card should still consume one usage."""
    db.add(_starter_subscription(test_user))
    db.commit()

    async def fake_generate_card(self, request):
        return _make_social_proof_card(
            test_location,
            card_id=2,
            final_card_url="https://cdn.example.com/card-final.png",
        )

    monkeypatch.setattr(
        "app.services.social_proof_service.SocialProofService.generate_card",
        fake_generate_card,
    )

    response = client.post(
        "/social-proof/generate-card",
        headers=auth_headers,
        json={
            "location_id": str(test_location.id),
            "review_id": "review-sp-2",
            "review_author": "Customer",
            "review_rating": 5,
            "review_text": "Amazing service and fast response.",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["final_card_url"] == "https://cdn.example.com/card-final.png"

    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "social_proof_cards",
        )
        .scalar()
    )
    assert int(total or 0) == 1


def test_social_proof_auto_generate_consumes_only_completed_cards(
    client: TestClient,
    db: Session,
    test_user,
    test_location,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    """Auto-generate should charge only for cards with a final asset."""
    db.add(_starter_subscription(test_user))
    db.commit()

    async def fake_auto_generate_cards(self, request):
        return [
            _make_social_proof_card(
                test_location,
                card_id=3,
                final_card_url="https://cdn.example.com/card-1.png",
            ),
            _make_social_proof_card(test_location, card_id=4, final_card_url=None),
        ]

    monkeypatch.setattr(
        "app.services.social_proof_service.SocialProofService.auto_generate_cards",
        fake_auto_generate_cards,
    )

    response = client.post(
        "/social-proof/auto-generate",
        headers=auth_headers,
        json={
            "location_id": str(test_location.id),
            "max_cards": 2,
            "min_rating": 5,
            "min_text_length": 10,
            "days_back": 7,
        },
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2

    total = (
        db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
        .filter(
            UsageRecord.account_id == test_user.id,
            UsageRecord.usage_type == "social_proof_cards",
        )
        .scalar()
    )
    assert int(total or 0) == 1
