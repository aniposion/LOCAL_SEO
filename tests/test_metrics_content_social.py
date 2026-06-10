"""Smoke tests for metrics, content, and social proof routes."""

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.credits import UsageRecord
from app.models.metrics import UTMLink
from app.models.social_proof import SocialProofCard, SocialProofStatus
from app.schemas.ai_content import ComplianceIssue
from app.services.ai_content_service import AIContentUnavailableError
from app.schemas.content import GBPContent, GeneratedContent, InstagramContent
from app.services.metrics_service import MetricsService


class TestMetricsRoutes:
    """Tests for metrics and report ownership boundaries."""

    def test_metrics_dashboard_returns_empty_summary_for_owned_location(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location,
    ) -> None:
        """Owned locations should return a dashboard payload even with no snapshots."""
        response = client.get(
            f"/metrics/dashboard?location_id={test_location.id}&period_days=7",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["location_id"] == str(test_location.id)
        assert data["metrics"]["calls"]["current"] == 0
        assert data["metrics"]["estimated_revenue"] == "0.00"

    def test_metrics_dashboard_hides_other_accounts_location(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        other_location,
    ) -> None:
        """Another account's metrics dashboard should not be visible."""
        response = client.get(
            f"/metrics/dashboard?location_id={other_location.id}&period_days=7",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_send_weekly_report_returns_503_without_email_delivery_and_does_not_mark_sent(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_user,
        test_location,
        monkeypatch,
    ) -> None:
        """Report send should fail honestly when email delivery is unavailable."""
        report = MetricsService(db).generate_weekly_report(
            test_location.id,
            test_user.id,
            date(2026, 4, 20),
        )

        async def fake_send_email(self, to_email: str, subject: str, html_body: str, text_body: str | None = None):
            return {"success": False, "error": "Email delivery is not configured"}

        monkeypatch.setattr("app.routers.metrics.NotificationService.send_email", fake_send_email)

        response = client.post(
            f"/reports/weekly/{report.id}/send",
            headers=auth_headers,
            json={"email_addresses": ["owner@example.com"]},
        )

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()

        db.refresh(report)
        assert report.sent_at is None
        assert report.sent_to is None

    def test_send_weekly_report_marks_sent_only_after_successful_delivery(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_user,
        test_location,
        monkeypatch,
    ) -> None:
        """Report send should persist sent metadata only after delivery succeeds."""
        report = MetricsService(db).generate_weekly_report(
            test_location.id,
            test_user.id,
            date(2026, 4, 20),
        )
        captured: dict[str, str] = {}

        async def fake_send_email(self, to_email: str, subject: str, html_body: str, text_body: str | None = None):
            captured["to_email"] = to_email
            captured["subject"] = subject
            return {"success": True, "provider": "sendgrid", "message_id": "sg-report-1"}

        monkeypatch.setattr("app.routers.metrics.NotificationService.send_email", fake_send_email)

        response = client.post(
            f"/reports/weekly/{report.id}/send",
            headers=auth_headers,
            json={"email_addresses": ["owner@example.com"]},
        )

        assert response.status_code == 200
        assert captured["to_email"] == "owner@example.com"
        assert "Weekly Performance Report" in captured["subject"]

        db.refresh(report)
        assert report.sent_at is not None
        assert report.sent_to == ["owner@example.com"]

    def test_generate_utm_link_persists_requested_source_and_medium(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location,
    ) -> None:
        """UTM generation should persist the source/medium selected in the UI."""
        response = client.post(
            f"/utm/generate?location_id={test_location.id}",
            headers=auth_headers,
            json={
                "original_url": "https://example.com/spring-offer",
                "campaign": "spring_offer_2026",
                "utm_source": "instagram",
                "utm_medium": "social",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["utm_source"] == "instagram"
        assert payload["utm_medium"] == "social"
        assert "utm_source=instagram" in payload["utm_url"]
        assert "utm_medium=social" in payload["utm_url"]

    def test_generate_utm_link_defaults_source_and_medium_when_omitted(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location,
    ) -> None:
        """UTM generation should keep legacy defaults when optional fields are omitted."""
        response = client.post(
            f"/utm/generate?location_id={test_location.id}",
            headers=auth_headers,
            json={
                "original_url": "https://example.com/default-offer",
                "campaign": "default_offer_2026",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["utm_source"] == "gbp"
        assert payload["utm_medium"] == "post"
        assert "utm_source=gbp" in payload["utm_url"]
        assert "utm_medium=post" in payload["utm_url"]

    def test_delete_utm_link_removes_owned_link(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
    ) -> None:
        """Owned UTM links should be deletable from the dashboard."""
        link = UTMLink(
            location_id=test_location.id,
            original_url="https://example.com/delete-me",
            utm_url="https://example.com/delete-me?utm_source=gbp&utm_medium=post",
            utm_source="gbp",
            utm_medium="post",
            utm_campaign="delete_me",
        )
        db.add(link)
        db.commit()
        db.refresh(link)

        response = client.delete(f"/utm/links/{link.id}", headers=auth_headers)

        assert response.status_code == 204
        assert db.query(UTMLink).filter(UTMLink.id == link.id).first() is None

    def test_delete_utm_link_blocks_other_accounts_location(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        other_location,
    ) -> None:
        """UTM links for another account should not be deletable."""
        link = UTMLink(
            location_id=other_location.id,
            original_url="https://example.com/not-yours",
            utm_url="https://example.com/not-yours?utm_source=gbp&utm_medium=post",
            utm_source="gbp",
            utm_medium="post",
            utm_campaign="not_yours",
        )
        db.add(link)
        db.commit()
        db.refresh(link)

        response = client.delete(f"/utm/links/{link.id}", headers=auth_headers)

        assert response.status_code == 404
        assert db.query(UTMLink).filter(UTMLink.id == link.id).first() is not None


class TestContentRoutes:
    """Tests for content suggestion and generation guardrails."""

    def test_content_suggestions_returns_items(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location,
    ) -> None:
        """Suggestions endpoint should return the requested number of options."""
        response = client.get(
            f"/content/suggestions?location_id={test_location.id}&limit=3",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 3
        assert "message" in data
        assert all("?" not in suggestion["title_ko"] for suggestion in data["suggestions"])
        assert all("?" not in suggestion["title_en"] for suggestion in data["suggestions"])

    def test_generate_from_suggestion_rejects_other_accounts_location(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        other_location,
    ) -> None:
        """Draft generation should be blocked for another account's location."""
        response = client.post(
            f"/content/generate-from-suggestion?suggestion_id=weekly-special&location_id={other_location.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_generate_from_suggestion_creates_draft_post(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Generating from a suggestion should persist a draft post."""
        monkeypatch.setattr(
            "app.routers.content.ContentSuggestionService.get_suggestion_by_id",
            lambda _self, _suggestion_id: {
                "id": "weekly-special",
                "title_en": "Weekly Special",
                "title_ko": "Weekly Special",
                "type": "promotion",
            },
        )

        async def fake_generate(self, **kwargs):
            return SimpleNamespace(
                gbp=SimpleNamespace(title="Weekly Special", body="Fresh menu this week", cta="Call now"),
                instagram=None,
                web=None,
                image_prompt="fresh menu photo",
            )

        monkeypatch.setattr("app.routers.content.ContentService.generate", fake_generate)

        response = client.post(
            f"/content/generate-from-suggestion?suggestion_id=weekly-special&location_id={test_location.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content"]["title"] == "Weekly Special"
        assert data["post_id"]
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 1

    def test_generate_from_suggestion_empty_result_returns_503_and_does_not_consume_usage(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Empty suggestion content should fail honestly without burning ai_content usage."""
        monkeypatch.setattr(
            "app.routers.content.ContentSuggestionService.get_suggestion_by_id",
            lambda _self, _suggestion_id: {
                "id": "weekly-special",
                "title_en": "Weekly Special",
                "title_ko": "Weekly Special",
                "type": "promotion",
            },
        )

        async def fake_generate(self, **kwargs):
            return GeneratedContent()

        monkeypatch.setattr("app.routers.content.ContentService.generate", fake_generate)

        response = client.post(
            f"/content/generate-from-suggestion?suggestion_id=weekly-special&location_id={test_location.id}",
            headers=auth_headers,
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "AI content provider is unavailable."
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 0

    def test_generate_content_creates_posts_for_targets(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Content generation should create draft posts for requested platforms."""
        async def fake_generate(self, **kwargs):
            return GeneratedContent(
                gbp=GBPContent(
                    title="GBP Title",
                    body="A" * 320,
                    cta="Visit us",
                    hashtags=["#one", "#two"],
                ),
                instagram=InstagramContent(
                    caption="B" * 720,
                    hashtags=[f"#tag{i}" for i in range(15)],
                ),
                web=None,
                image_prompt="storefront photo",
            )

        monkeypatch.setattr("app.routers.content.ContentService.generate", fake_generate)

        response = client.post(
            "/content/generate",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "theme": "Weekly update",
                "services": test_location.services,
                "tone": "friendly and professional",
                "language": "en",
                "platform_targets": ["GBP", "INSTAGRAM"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["location_id"] == str(test_location.id)
        assert data["posts_created"] == 2
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 1

    def test_generate_content_failure_does_not_consume_usage(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Failed content generation should not burn ai_content usage."""

        async def broken_generate(self, **kwargs):
            raise RuntimeError("LLM provider failed")

        monkeypatch.setattr("app.routers.content.ContentService.generate", broken_generate)

        with pytest.raises(RuntimeError, match="LLM provider failed"):
            client.post(
                "/content/generate",
                headers=auth_headers,
                json={
                    "location_id": str(test_location.id),
                    "theme": "Weekly update",
                    "services": test_location.services,
                    "tone": "friendly and professional",
                    "language": "en",
                    "platform_targets": ["GBP"],
                },
            )

        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 0

    def test_generate_content_empty_result_returns_503_and_does_not_consume_usage(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Empty generated content should not masquerade as a successful draft creation."""

        async def fake_generate(self, **kwargs):
            return GeneratedContent()

        monkeypatch.setattr("app.routers.content.ContentService.generate", fake_generate)

        response = client.post(
            "/content/generate",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "theme": "Weekly update",
                "services": test_location.services,
                "tone": "friendly and professional",
                "language": "en",
                "platform_targets": ["GBP", "INSTAGRAM"],
            },
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "AI content provider is unavailable."
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 0


class TestSocialProofRoutes:
    """Tests for social proof approval queues."""

    def test_social_proof_pending_hides_other_accounts_location(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        other_location,
    ) -> None:
        """Pending queue should return 404 for another account's location filter."""
        response = client.get(
            f"/social-proof/pending?location_id={other_location.id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_social_proof_pending_lists_owned_cards(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location,
        db: Session,
    ) -> None:
        """Owned pending cards should be returned from the approval queue."""
        card = SocialProofCard(
            location_id=test_location.id,
            review_id=f"review-{uuid4()}",
            review_author="Happy Customer",
            review_rating=5,
            review_text="Great service and fast response.",
            review_date=date.today(),
            status=SocialProofStatus.PENDING,
            generated_by_ai="imagen-3",
        )
        db.add(card)
        db.commit()

        response = client.get("/social-proof/pending", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["location_id"] == str(test_location.id)
        assert data[0]["status"] == "pending"


class TestAIContentRoutes:
    """Tests for honest unavailable states in AI content routes."""

    def test_generate_records_ai_content_usage_on_success(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Successful AI generation should record ai_content usage."""

        async def fake_call_llm(self, prompt: str) -> dict:
            return {"content": "Fresh weekly update for your customers.", "tokens": 42}

        monkeypatch.setattr("app.services.ai_content_service.AIContentService._call_llm", fake_call_llm)

        response = client.post(
            "/ai/generate",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "content_type": "post",
                "platforms": ["google"],
                "num_variations": 1,
            },
        )

        assert response.status_code == 200
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 1

    def test_generate_returns_503_when_provider_unavailable(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Missing AI provider should surface as service unavailable instead of sample content."""

        async def fake_call_llm(self, prompt: str) -> dict:
            raise AIContentUnavailableError("AI content provider is unavailable.")

        monkeypatch.setattr("app.services.ai_content_service.AIContentService._call_llm", fake_call_llm)

        response = client.post(
            "/ai/generate",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "content_type": "post",
                "platforms": ["google"],
                "num_variations": 1,
            },
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "AI content provider is unavailable."
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 0

    def test_quick_generate_rejects_other_accounts_location(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        other_location,
    ) -> None:
        """Quick generate should not allow another account's location context."""

        response = client.post(
            "/ai/generate/quick",
            headers=auth_headers,
            params={"location_id": str(other_location.id), "topic": "Spring promo", "platform": "google"},
        )

        assert response.status_code == 404

    def test_review_reply_records_ai_response_usage_on_success(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Successful review reply generation should record ai_response usage."""

        async def fake_call_llm(self, prompt: str) -> dict:
            return {"content": "Thanks for the kind words, Taylor. We hope to see you again soon!", "tokens": 21}

        monkeypatch.setattr("app.services.ai_content_service.AIContentService._call_llm", fake_call_llm)

        response = client.post(
            "/ai/review-reply",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "reviewer_name": "Taylor",
                "star_rating": 5,
                "review_text": "Great service.",
            },
        )

        assert response.status_code == 200
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_response")
            .scalar()
        )
        assert int(total or 0) == 1

    def test_review_reply_returns_503_when_provider_unavailable(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Review replies should not fabricate fallback text when AI is unavailable."""

        async def fake_call_llm(self, prompt: str) -> dict:
            raise AIContentUnavailableError("AI content provider is unavailable.")

        monkeypatch.setattr("app.services.ai_content_service.AIContentService._call_llm", fake_call_llm)

        response = client.post(
            "/ai/review-reply",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "reviewer_name": "Taylor",
                "star_rating": 4,
                "review_text": "Great service.",
            },
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "AI content provider is unavailable."

    def test_analyze_omits_suggested_revision_when_provider_unavailable(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Content analysis should still return honest analysis without a fabricated revision."""

        async def fake_call_llm(self, prompt: str) -> dict:
            raise AIContentUnavailableError("AI content provider is unavailable.")

        monkeypatch.setattr("app.services.ai_content_service.AIContentService._call_llm", fake_call_llm)

        response = client.post(
            "/ai/analyze",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "content": "We are the best guaranteed option in town.",
                "check_seo": True,
                "check_compliance": True,
                "check_tone": True,
                "check_readability": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["needs_review"] is True
        assert data["suggested_revision"] is None
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 0

    def test_analyze_records_ai_content_usage_when_revision_generated(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Analyze should record ai_content usage only when a revision is generated."""

        async def fake_call_llm(self, prompt: str) -> dict:
            return {"content": "We offer an excellent option in town.", "tokens": 12}

        monkeypatch.setattr("app.services.ai_content_service.AIContentService._call_llm", fake_call_llm)
        monkeypatch.setattr(
            "app.services.ai_content_service.AIContentService._analyze_compliance",
            lambda self, content, vault: [
                ComplianceIssue(
                    type="forbidden_phrase",
                    severity="high",
                    text="guaranteed",
                    suggestion="Remove guaranteed phrasing",
                )
            ],
        )

        response = client.post(
            "/ai/analyze",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "content": "We are the best guaranteed option in town.",
                "check_seo": True,
                "check_compliance": True,
                "check_tone": True,
                "check_readability": True,
            },
        )

        assert response.status_code == 200
        assert response.json()["suggested_revision"] == "We offer an excellent option in town."
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 1

    def test_analyze_does_not_record_usage_when_revision_is_not_needed(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Safe analyze flows should not trigger hidden ai_content usage."""

        async def fail_if_called(self, prompt: str) -> dict:
            raise AssertionError("Revision generation should not run for safe content.")

        monkeypatch.setattr("app.services.ai_content_service.AIContentService._call_llm", fail_if_called)

        response = client.post(
            "/ai/analyze",
            headers=auth_headers,
            json={
                "location_id": str(test_location.id),
                "content": "Friendly neighborhood updates and service tips for local customers.",
                "check_seo": True,
                "check_compliance": True,
                "check_tone": True,
                "check_readability": True,
            },
        )

        assert response.status_code == 200
        assert response.json()["suggested_revision"] is None
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 0

    def test_quick_analyze_records_ai_content_usage_when_revision_generated(
        self,
        client: TestClient,
        db: Session,
        auth_headers: dict[str, str],
        test_location,
        monkeypatch,
    ) -> None:
        """Quick analyze should follow the same revision-only ai_content charging rule."""

        async def fake_call_llm(self, prompt: str) -> dict:
            return {"content": "A clearer and safer version.", "tokens": 9}

        monkeypatch.setattr("app.services.ai_content_service.AIContentService._call_llm", fake_call_llm)
        monkeypatch.setattr(
            "app.services.ai_content_service.AIContentService._analyze_compliance",
            lambda self, content, vault: [
                ComplianceIssue(
                    type="forbidden_phrase",
                    severity="high",
                    text="guaranteed",
                    suggestion="Remove guaranteed phrasing",
                )
            ],
        )

        response = client.post(
            "/ai/analyze/quick",
            headers=auth_headers,
            params={
                "location_id": str(test_location.id),
                "content": "We are the best guaranteed option in town.",
            },
        )

        assert response.status_code == 200
        total = (
            db.query(func.coalesce(func.sum(UsageRecord.monthly_count), 0))
            .filter(UsageRecord.account_id == test_location.account_id, UsageRecord.usage_type == "ai_content")
            .scalar()
        )
        assert int(total or 0) == 1

    def test_quick_analyze_rejects_other_accounts_location(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        other_location,
    ) -> None:
        """Quick analyze should not allow another account's location context."""

        response = client.post(
            "/ai/analyze/quick",
            headers=auth_headers,
            params={"content": "Weekly update", "location_id": str(other_location.id)},
        )

        assert response.status_code == 404
