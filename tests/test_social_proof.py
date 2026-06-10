"""Tests for social proof operational history and metrics."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.social_proof import SocialProofCard, SocialProofStatus


def _make_card(
    db: Session,
    location,
    *,
    title: str,
    status: SocialProofStatus,
    review_id: str,
    created_at: datetime,
    updated_at: datetime | None = None,
    published_at: datetime | None = None,
    rejection_reason: str | None = None,
) -> SocialProofCard:
    card = SocialProofCard(
        location_id=location.id,
        review_id=review_id,
        review_author="Customer",
        review_rating=5,
        review_text="Great service and fast response.",
        review_date=created_at,
        card_title=title,
        card_text="Great service and fast response.",
        image_prompt="Warm, branded social proof card",
        layout_style="instagram_square",
        text_color="#FFFFFF",
        background_color="#000000",
        font_family="Arial",
        status=status,
        approved_at=published_at or updated_at or created_at,
        rejection_reason=rejection_reason,
        published_to="instagram" if status == SocialProofStatus.PUBLISHED else None,
        published_at=published_at,
        platform_post_id=f"post_{uuid4().hex[:8]}" if status == SocialProofStatus.PUBLISHED else None,
        generated_by_ai="imagen-3",
        created_at=created_at,
        updated_at=updated_at or created_at,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


class TestSocialProofHistory:
    """Tests for social proof history and operational metrics."""

    def test_history_returns_metrics_and_filters(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location,
        db: Session,
    ) -> None:
        """History should return saved cards, metrics, and status filters."""
        now = datetime.now(UTC).replace(tzinfo=None)
        _make_card(
            db,
            test_location,
            title="Old Draft",
            status=SocialProofStatus.DRAFT,
            review_id="review-draft-1",
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=3),
        )
        _make_card(
            db,
            test_location,
            title="Old Pending",
            status=SocialProofStatus.PENDING,
            review_id="review-pending-1",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        )
        _make_card(
            db,
            test_location,
            title="Approved Card",
            status=SocialProofStatus.APPROVED,
            review_id="review-approved-1",
            created_at=now - timedelta(hours=8),
            updated_at=now - timedelta(hours=8),
        )
        _make_card(
            db,
            test_location,
            title="Published Card",
            status=SocialProofStatus.PUBLISHED,
            review_id="review-published-1",
            created_at=now - timedelta(hours=6),
            updated_at=now - timedelta(hours=6),
            published_at=now - timedelta(hours=5),
        )
        _make_card(
            db,
            test_location,
            title="Rejected Card",
            status=SocialProofStatus.REJECTED,
            review_id="review-rejected-1",
            created_at=now - timedelta(hours=4),
            updated_at=now - timedelta(hours=4),
            rejection_reason="Too much text",
        )
        response = client.get(
            f"/social-proof/history/{test_location.id}?status_filter=all&limit=20&offset=0",
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total"] == 5
        assert payload["metrics"]["total_cards"] == 5
        assert payload["metrics"]["draft_count"] == 1
        assert payload["metrics"]["pending_count"] == 1
        assert payload["metrics"]["approved_count"] == 1
        assert payload["metrics"]["published_count"] == 1
        assert payload["metrics"]["rejected_count"] == 1
        assert payload["metrics"]["attention_required_count"] == 2
        assert payload["metrics"]["last_published_at"] is not None

        published_response = client.get(
            f"/social-proof/history/{test_location.id}?status_filter=published&limit=20&offset=0",
            headers=auth_headers,
        )
        assert published_response.status_code == 200
        published_payload = published_response.json()
        assert published_payload["total"] == 1
        assert published_payload["items"][0]["status"] == "published"
        assert published_payload["items"][0]["platform_post_id"] is not None

        search_response = client.get(
            f"/social-proof/history/{test_location.id}?status_filter=all&search=Rejected&limit=20&offset=0",
            headers=auth_headers,
        )
        assert search_response.status_code == 200
        search_payload = search_response.json()
        assert search_payload["total"] == 1
        assert search_payload["items"][0]["status"] == "rejected"
        assert search_payload["items"][0]["rejection_reason"] == "Too much text"

        attention_response = client.get(
            f"/social-proof/history/{test_location.id}?status_filter=attention&limit=20&offset=0",
            headers=auth_headers,
        )
        assert attention_response.status_code == 200
        attention_payload = attention_response.json()
        assert attention_payload["total"] == 2
        assert all(item["status"] in {"draft", "pending"} for item in attention_payload["items"])

    def test_history_rejects_other_accounts_location(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        other_location,
    ) -> None:
        """Another account's social proof history should be hidden."""
        response = client.get(
            f"/social-proof/history/{other_location.id}?status_filter=all&limit=20&offset=0",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestSocialProofApproval:
    """Tests for social proof approval honesty."""

    def test_approve_card_marks_card_approved_without_fake_publish(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location,
        db: Session,
    ) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        card = _make_card(
            db,
            test_location,
            title="Pending Card",
            status=SocialProofStatus.PENDING,
            review_id="review-pending-approve-1",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )

        response = client.post(
            f"/social-proof/{card.id}/approve",
            headers=auth_headers,
            json={"card_id": card.id},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "approved"
        assert payload["published_at"] is None
        assert payload["published_to"] is None
        assert payload["platform_post_id"] is None

    def test_approve_card_rejects_fake_publish_immediately_flag(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location,
        db: Session,
    ) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        card = _make_card(
            db,
            test_location,
            title="Pending Card",
            status=SocialProofStatus.PENDING,
            review_id="review-pending-publish-1",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )

        response = client.post(
            f"/social-proof/{card.id}/approve",
            headers=auth_headers,
            json={"card_id": card.id, "publish_immediately": True},
        )

        assert response.status_code == 400, response.text
        assert "not wired yet" in response.json()["detail"].lower()

        db.refresh(card)
        assert card.status == SocialProofStatus.PENDING
        assert card.published_at is None
        assert card.published_to is None
