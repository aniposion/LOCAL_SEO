"""Tests for competitor freshness and trust signals."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.competitor import Competitor, CompetitorAnalysis, CompetitorReview, CompetitorStatus


def _make_competitor(db: Session, test_location, name: str, synced_at: datetime, review_synced_at: datetime) -> Competitor:
    competitor = Competitor(
        location_id=test_location.id,
        place_id=f"place-{uuid4()}",
        name=name,
        address="123 Market St",
        business_type="restaurant",
        rating=4.4,
        review_count=120,
        distance_miles=1.2,
        status=CompetitorStatus.ACTIVE,
        raw_data={"source": "test"},
        last_synced_at=synced_at,
        last_review_synced_at=review_synced_at,
    )
    db.add(competitor)
    db.commit()
    db.refresh(competitor)
    return competitor


def test_competitor_report_surfaces_freshness_signals(
    client: TestClient,
    db: Session,
    test_location,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    competitor_one = _make_competitor(
        db,
        test_location,
        "Nearby One",
        synced_at=now - timedelta(days=11),
        review_synced_at=now - timedelta(days=9),
    )
    competitor_two = _make_competitor(
        db,
        test_location,
        "Nearby Two",
        synced_at=now - timedelta(days=4),
        review_synced_at=now - timedelta(days=4),
    )

    db.add_all(
        [
            CompetitorReview(
                competitor_id=competitor_one.id,
                review_id="review-1",
                author_name="A",
                rating=5,
                text="Great service and fast response.",
                publish_time=now - timedelta(days=2),
            ),
            CompetitorReview(
                competitor_id=competitor_one.id,
                review_id="review-2",
                author_name="B",
                rating=4,
                text="Solid food, good value.",
                publish_time=now - timedelta(days=5),
            ),
            CompetitorReview(
                competitor_id=competitor_two.id,
                review_id="review-3",
                author_name="C",
                rating=5,
                text="Friendly team and clean space.",
                publish_time=now - timedelta(days=3),
            ),
        ]
    )
    db.add(
        CompetitorAnalysis(
            location_id=test_location.id,
            week_start=now - timedelta(days=14),
            week_end=now - timedelta(days=7),
            trending_keywords=["service", "value", "clean"],
            threat_level="medium",
            rating_trend="stable",
            recommended_actions=[
                {
                    "title": "Track review themes",
                    "description": "Watch what competitors are getting praised for.",
                    "priority": "medium",
                    "effort": "low",
                }
            ],
            summary_text="Saved snapshot for nearby competitors.",
            metrics_snapshot={"competitors": 2},
            generated_by_ai="gemini-1.5-flash",
            created_at=now - timedelta(days=8),
        )
    )
    db.commit()

    async def fake_analyze(self, location_id, force_refresh=False):
        return db.query(CompetitorAnalysis).filter(CompetitorAnalysis.location_id == location_id).first()

    monkeypatch.setattr("app.services.competitor_service.CompetitorService.analyze_competitors", fake_analyze)

    response = client.get(f"/competitor/report/{test_location.id}", headers=auth_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    freshness = payload["freshness"]

    assert freshness["freshness_status"] == "stale"
    assert freshness["review_sample_size"] == 3
    assert freshness["analysis_age_minutes"] is not None
    assert freshness["cache_age_minutes"] is not None
    assert freshness["last_review_sync_at"] is not None
    assert any("older than 7 days" in note for note in freshness["freshness_notes"])
    assert payload["competitors"][0]["last_review_synced_at"] is not None
