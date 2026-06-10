"""AI Smart Review Responder service."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from datetime import UTC

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.integrations.llm import LLMAdapter
from app.models.review_response import BulkRetryLog, ReviewIntent, ReviewResponse, ResponseStatus
from app.schemas.review_response import (
    BulkRetryItemResult,
    BulkRetryResponse,
    FailedResponseItem,
    GenerateResponseRequest,
    ReviewResponderSummaryResponse,
    ReviewResponseHistoryItem,
    ResponseDraft,
    ReviewResponseCreate,
    SentimentAnalysis,
)
from app.services.google_api_service import get_google_api_service
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


class PublishUnavailableError(RuntimeError):
    """Raised when GBP review publishing cannot be completed honestly."""

    pass


@dataclass
class GeneratedResponseDraftResult:
    """Internal review draft result with usage metadata."""

    draft: ResponseDraft
    used_ai_generation: bool


class ReviewResponderService:
    """Service for AI-powered review response generation."""

    def __init__(self, db: Session):
        """Initialize review responder service."""
        self.db = db
        self.llm = LLMAdapter()
        self.notification_service = NotificationService(db)

    async def analyze_sentiment(self, review_text: str, rating: int) -> SentimentAnalysis:
        """
        Analyze sentiment and intent of a review.

        Args:
            review_text: Review text
            rating: Review rating (1-5)

        Returns:
            Sentiment analysis result
        """
        prompt = f"""Analyze the following customer review and provide sentiment analysis.

Review Rating: {rating}/5
Review Text: "{review_text}"

Provide a JSON response with:
1. sentiment_score: Float from -1.0 (very negative) to 1.0 (very positive)
2. sentiment_label: "positive", "negative", or "neutral"
3. intent: One of "praise", "complaint", "suggestion", "question", "misunderstanding"
4. detected_issues: List of specific issues mentioned (if any)
5. key_phrases: List of important phrases or keywords

Format:
{{
  "sentiment_score": 0.8,
  "sentiment_label": "positive",
  "intent": "praise",
  "detected_issues": [],
  "key_phrases": ["great service", "delicious food"]
}}
"""

        try:
            response = await self.llm.generate(prompt)
            # Extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                return SentimentAnalysis(
                    score=data.get("sentiment_score", 0.0),
                    label=data.get("sentiment_label", "neutral"),
                    intent=data.get("intent", "praise"),
                    detected_issues=data.get("detected_issues", []),
                    key_phrases=data.get("key_phrases", []),
                )
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")

        # Fallback based on rating
        if rating >= 4:
            return SentimentAnalysis(
                score=0.7,
                label="positive",
                intent="praise",
                detected_issues=[],
                key_phrases=[],
            )
        elif rating <= 2:
            return SentimentAnalysis(
                score=-0.7,
                label="negative",
                intent="complaint",
                detected_issues=["service issue"],
                key_phrases=[],
            )
        else:
            return SentimentAnalysis(
                score=0.0,
                label="neutral",
                intent="suggestion",
                detected_issues=[],
                key_phrases=[],
            )

    async def generate_response_draft_with_meta(
        self, request: GenerateResponseRequest, business_name: Optional[str] = None
    ) -> GeneratedResponseDraftResult:
        """
        Generate AI response draft for a review.

        Args:
            request: Review information
            business_name: Business name for personalization

        Returns:
            Response draft with sentiment analysis
        """
        # Analyze sentiment first
        sentiment = await self.analyze_sentiment(request.review_text, request.review_rating)

        # Determine tone based on rating and sentiment
        if request.review_rating <= 2:
            tone = "apologetic"
        elif request.review_rating == 3:
            tone = "empathetic"
        elif request.review_rating == 4:
            tone = "warm"
        else:
            tone = "grateful"

        # Build prompt for response generation
        prompt = self._build_response_prompt(
            review_text=request.review_text,
            rating=request.review_rating,
            author=request.review_author or "valued customer",
            sentiment=sentiment,
            tone=tone,
            business_name=business_name or "our business",
        )

        # Generate response
        used_ai_generation = True

        try:
            response_text = await self.llm.generate(prompt)
            # Clean up response
            response_text = response_text.strip()

            # Remove any JSON formatting if present
            if response_text.startswith("{"):
                try:
                    data = json.loads(response_text)
                    response_text = data.get("response", response_text)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            used_ai_generation = False
            response_text = self._get_fallback_response(request.review_rating, tone)

        # Determine suggested actions
        suggested_actions = self._get_suggested_actions(sentiment, request.review_rating)

        return GeneratedResponseDraftResult(
            draft=ResponseDraft(
                draft_text=response_text,
                tone=tone,
                sentiment_analysis=sentiment,
                suggested_actions=suggested_actions,
            ),
            used_ai_generation=used_ai_generation,
        )

    async def generate_response_draft(
        self, request: GenerateResponseRequest, business_name: Optional[str] = None
    ) -> ResponseDraft:
        """Generate a response draft for API callers that only need the draft."""
        result = await self.generate_response_draft_with_meta(request, business_name)
        return result.draft

    def _build_response_prompt(
        self,
        review_text: str,
        rating: int,
        author: str,
        sentiment: SentimentAnalysis,
        tone: str,
        business_name: str,
    ) -> str:
        """Build prompt for response generation."""
        prompt = f"""You are writing a response to a customer review for {business_name}.

**Review Details:**
- Author: {author}
- Rating: {rating}/5 stars
- Review: "{review_text}"

**Sentiment Analysis:**
- Intent: {sentiment.intent}
- Issues Detected: {', '.join(sentiment.detected_issues) if sentiment.detected_issues else 'None'}

**Response Guidelines:**
- Tone: {tone.title()}
- Style: Professional, warm, and authentic
- Length: 2-4 sentences
- Follow American business etiquette

**Specific Instructions Based on Rating:**
"""

        if rating <= 2:
            prompt += """
- Start with a sincere apology
- Acknowledge the specific issues mentioned
- Show commitment to improvement
- Offer to make it right (e.g., "Please contact us directly so we can resolve this")
- Do NOT make excuses or be defensive
"""
        elif rating == 3:
            prompt += """
- Thank them for honest feedback
- Acknowledge both positive and negative aspects
- Show you're taking their suggestions seriously
- Invite them to give you another chance
"""
        elif rating == 4:
            prompt += """
- Express genuine gratitude
- Highlight what they enjoyed
- Address any minor concerns if mentioned
- Encourage them to visit again
"""
        else:  # 5 stars
            prompt += """
- Express enthusiastic gratitude
- Personalize by mentioning specific details they mentioned
- Reinforce positive aspects
- Invite them to return and bring friends/family
"""

        prompt += """

**Important:**
- Use first person ("we", "our team")
- Be concise and authentic
- Add a personal touch
- End with a forward-looking statement
- Include "Generated by AI - Subject to human review" at the very end

Write ONLY the response text, no additional commentary.
"""
        return prompt

    def _get_fallback_response(self, rating: int, tone: str) -> str:
        """Get fallback response if LLM fails."""
        if rating <= 2:
            return (
                "We sincerely apologize for your experience. Your feedback is important to us, "
                "and we'd like to make this right. Please contact us directly so we can address "
                "your concerns. Thank you for giving us the opportunity to improve.\n\n"
                "Generated by AI - Subject to human review"
            )
        elif rating == 3:
            return (
                "Thank you for your honest feedback. We appreciate you taking the time to share "
                "your experience. We're always working to improve, and your input helps us do that. "
                "We hope to serve you better next time!\n\n"
                "Generated by AI - Subject to human review"
            )
        else:
            return (
                "Thank you so much for your wonderful review! We're thrilled you had a great "
                "experience with us. We look forward to welcoming you back soon!\n\n"
                "Generated by AI - Subject to human review"
            )

    def _get_suggested_actions(
        self, sentiment: SentimentAnalysis, rating: int
    ) -> list[str]:
        """Get suggested follow-up actions."""
        actions = []

        if rating <= 2:
            actions.extend(
                [
                    "Contact customer directly to resolve issues",
                    "Review internal processes related to mentioned issues",
                    "Train staff on identified problem areas",
                ]
            )
        elif rating == 3:
            actions.extend(
                [
                    "Follow up with customer for more details",
                    "Implement suggested improvements",
                ]
            )
        else:
            actions.extend(
                [
                    "Share positive feedback with team",
                    "Consider featuring this review in marketing",
                ]
            )

        return actions

    def _priority_level(self, review_response: ReviewResponse) -> str:
        """Classify a response by operator priority."""
        if review_response.status == ResponseStatus.FAILED:
            return "high"
        if review_response.review_rating <= 2:
            return "high"
        if review_response.intent in {ReviewIntent.COMPLAINT, ReviewIntent.MISUNDERSTANDING}:
            return "high"
        if review_response.review_rating == 3 or review_response.intent in {
            ReviewIntent.QUESTION,
            ReviewIntent.SUGGESTION,
        }:
            return "medium"
        return "normal"

    def _priority_reason(self, review_response: ReviewResponse) -> str:
        """Explain why a response is prioritized."""
        if review_response.status == ResponseStatus.FAILED:
            return "Previous publish attempt failed"
        if review_response.review_rating <= 2:
            return "Low rating needs a fast owner reply"
        if review_response.intent == ReviewIntent.COMPLAINT:
            return "Complaint requires attention"
        if review_response.intent == ReviewIntent.MISUNDERSTANDING:
            return "Customer may be confused and waiting for clarification"
        if review_response.review_rating == 3:
            return "Neutral review may benefit from a careful reply"
        if review_response.intent == ReviewIntent.QUESTION:
            return "Question can convert better with a quick answer"
        if review_response.intent == ReviewIntent.SUGGESTION:
            return "Suggestion is useful feedback to acknowledge"
        return "Standard review response queue item"

    def _age_minutes(self, timestamp) -> Optional[int]:
        if not timestamp:
            return None
        now = utc_now_naive()
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(UTC).replace(tzinfo=None)
        delta = now - timestamp
        return max(int(delta.total_seconds() // 60), 0)

    def _matches_search(self, review_response: ReviewResponse, search: Optional[str]) -> bool:
        if not search:
            return True
        needle = search.strip().lower()
        if not needle:
            return True

        values = [
            review_response.review_id,
            review_response.review_author,
            review_response.review_text,
            review_response.ai_draft,
            review_response.platform,
            review_response.platform_review_url,
            review_response.rejection_reason,
            review_response.platform_response_id,
            review_response.intent.value if hasattr(review_response.intent, "value") else review_response.intent,
            review_response.status.value if hasattr(review_response.status, "value") else review_response.status,
        ]
        haystack = " ".join(str(value or "") for value in values).lower()
        return needle in haystack

    def _filter_responses(
        self,
        *,
        location_ids: Optional[list[UUID]] = None,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        search: Optional[str] = None,
        high_priority_only: bool = False,
    ) -> list[ReviewResponse]:
        query = self.db.query(ReviewResponse)

        if location_ids:
            query = query.filter(ReviewResponse.location_id.in_(location_ids))

        if platform:
            query = query.filter(ReviewResponse.platform == platform)

        if status and status.lower() != "all":
            try:
                status_enum = ResponseStatus(status.lower())
                query = query.filter(ReviewResponse.status == status_enum)
            except ValueError:
                pass

        responses = query.order_by(desc(ReviewResponse.created_at)).all()

        if search:
            responses = [response for response in responses if self._matches_search(response, search)]

        if high_priority_only:
            responses = [response for response in responses if self._priority_level(response) == "high"]

        return responses

    def _error_category(self, publish_error: Optional[str]) -> str:
        """Classify a publish_error string into a triage category."""
        if not publish_error:
            return "unknown"
        lower = publish_error.lower()
        if "no google oauth token" in lower or "no google oauth" in lower:
            return "no_oauth_token"
        if "access token is missing" in lower:
            return "token_missing"
        if "gbp review publishing failed" in lower or "api" in lower:
            return "api_error"
        return "unknown"

    def _failed_item(self, review_response: ReviewResponse) -> FailedResponseItem:
        base = self._history_item(review_response)
        return FailedResponseItem(
            **base.model_dump(),
            error_category=self._error_category(review_response.publish_error),
        )

    def _history_item(self, review_response: ReviewResponse) -> ReviewResponseHistoryItem:
        base = ReviewResponseHistoryItem.model_validate(review_response).model_dump(
            exclude={
                "high_priority",
                "priority_level",
                "priority_reason",
                "age_minutes",
            }
        )
        return ReviewResponseHistoryItem(
            **base,
            high_priority=self._priority_level(review_response) == "high",
            priority_level=self._priority_level(review_response),
            priority_reason=self._priority_reason(review_response),
            age_minutes=self._age_minutes(review_response.created_at),
        )

    async def create_review_response(
        self, request: GenerateResponseRequest, account_id: UUID
    ) -> tuple[ReviewResponse, bool]:
        """
        Create a review response with AI draft.

        Args:
            request: Review information
            account_id: Account ID for notifications

        Returns:
            Created review response
        """
        # Check if response already exists
        existing = (
            self.db.query(ReviewResponse)
            .filter(ReviewResponse.review_id == request.review_id)
            .first()
        )
        if existing:
            logger.info(f"Response already exists for review {request.review_id}")
            return existing, False

        # Get business name from location
        from app.models.location import Location

        location = self.db.query(Location).filter(Location.id == request.location_id).first()
        business_name = location.business_name if location else None

        # Generate response draft
        draft_result = await self.generate_response_draft_with_meta(request, business_name)
        draft = draft_result.draft

        # Create review response record
        response_data = ReviewResponseCreate(
            location_id=request.location_id,
            review_id=request.review_id,
            review_author=request.review_author,
            review_rating=request.review_rating,
            review_text=request.review_text,
            review_date=request.review_date,
            platform=request.platform,
            platform_review_url=request.platform_review_url,
            sentiment_score=draft.sentiment_analysis.score,
            intent=draft.sentiment_analysis.intent,
            detected_issues=json.dumps(draft.sentiment_analysis.detected_issues),
            ai_draft=draft.draft_text,
            tone=draft.tone,
        )

        review_response = ReviewResponse(**response_data.model_dump())
        self.db.add(review_response)
        self.db.commit()
        self.db.refresh(review_response)

        # Send notification to owner
        try:
            await self._send_approval_notification(review_response, account_id)
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

        return review_response, draft_result.used_ai_generation

    async def _send_approval_notification(
        self, review_response: ReviewResponse, account_id: UUID
    ) -> None:
        """Send notification for pending approval."""
        from app.models.account import Account

        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return

        rating_stars = "*" * max(1, min(review_response.review_rating, 5))
        review_preview = (review_response.review_text or "").strip()
        if len(review_preview) > 100:
            review_preview = review_preview[:100].rstrip() + "..."

        message = (
            "New review response is ready for approval.\n\n"
            f"{rating_stars} review from {review_response.review_author or 'Customer'}\n"
            f"Review: \"{review_preview}\"\n\n"
            "AI-generated draft:\n"
            f"{review_response.ai_draft}\n\n"
            "Open the dashboard to approve, edit, or reject this response."
        )

        await self.notification_service.send_notification(
            account_id=account_id,
            title="New Review Response Pending",
            message=message,
            notification_type="review_response",
            data={"review_response_id": review_response.id},
        )

    async def _notify_publish_failure(
        self,
        review_response: ReviewResponse,
        error_message: str,
    ) -> None:
        """Persist an operator-facing alert when GBP reply publish fails."""
        from app.models.location import Location

        location = (
            self.db.query(Location)
            .filter(Location.id == review_response.location_id)
            .first()
        )
        if not location:
            return

        rating_stars = "*" * max(1, min(review_response.review_rating, 5))
        review_preview = (review_response.review_text or "").strip()
        if len(review_preview) > 100:
            review_preview = review_preview[:100].rstrip() + "..."

        await self.notification_service.send_notification(
            account_id=location.account_id,
            title="Review response publish failed",
            message=(
                "A review response could not be published to Google Business Profile.\n\n"
                f"{rating_stars} review from {review_response.review_author or 'Customer'}"
                f" for {location.name}\n"
                f"Review: \"{review_preview}\"\n\n"
                f"Reason: {error_message}\n\n"
                "Open the dashboard to reconnect GBP or retry the failed response."
            ),
            notification_type="review_response_publish_failed",
            data={
                "url": "/dashboard/review-responder",
                "review_response_id": review_response.id,
                "location_id": str(review_response.location_id),
                "review_id": review_response.review_id,
                "error_message": error_message,
            },
        )

    async def approve_response(
        self, response_id: int, account_id: UUID, edited_draft: Optional[str] = None
    ) -> ReviewResponse:
        """
        Approve a review response.

        Args:
            response_id: Review response ID
            account_id: Approving account ID
            edited_draft: Optional edited version of the draft

        Returns:
            Updated review response
        """
        review_response = (
            self.db.query(ReviewResponse).filter(ReviewResponse.id == response_id).first()
        )
        if not review_response:
            raise ValueError(f"Review response {response_id} not found")

        if review_response.status != ResponseStatus.PENDING:
            raise ValueError(f"Review response is not pending (status: {review_response.status})")

        # Update response
        review_response.status = ResponseStatus.APPROVED
        review_response.approved_by = account_id
        review_response.approved_at = utc_now_naive()

        if edited_draft:
            review_response.ai_draft = edited_draft

        self.db.commit()
        self.db.refresh(review_response)

        # Publish to platform
        try:
            await self._publish_response(review_response)
            review_response.publish_error = None
        except Exception as e:
            logger.error(f"Error publishing response: {e}")
            review_response.status = ResponseStatus.FAILED
            review_response.publish_error = str(e)
            review_response.platform_response_id = None
            review_response.published_at = None
            self.db.commit()
            try:
                await self._notify_publish_failure(review_response, str(e))
            except Exception as notify_exc:
                logger.warning(
                    "Failed to notify account about review publish failure for response %s: %s",
                    review_response.id,
                    notify_exc,
                )

        return review_response

    async def reject_response(
        self, response_id: int, account_id: UUID, reason: str
    ) -> ReviewResponse:
        """
        Reject a review response.

        Args:
            response_id: Review response ID
            account_id: Rejecting account ID
            reason: Rejection reason

        Returns:
            Updated review response
        """
        review_response = (
            self.db.query(ReviewResponse).filter(ReviewResponse.id == response_id).first()
        )
        if not review_response:
            raise ValueError(f"Review response {response_id} not found")

        review_response.status = ResponseStatus.REJECTED
        review_response.approved_by = account_id
        review_response.approved_at = utc_now_naive()
        review_response.rejection_reason = reason

        self.db.commit()
        self.db.refresh(review_response)

        return review_response

    async def _publish_response(self, review_response: ReviewResponse) -> None:
        """
        Publish response to platform (Google Business Profile).

        Args:
            review_response: Review response to publish
        """
        from app.models.oauth import OAuthToken

        # Get OAuth token for location
        oauth_token = (
            self.db.query(OAuthToken)
            .filter(
                and_(
                    OAuthToken.location_id == review_response.location_id,
                    OAuthToken.provider == "google",
                )
            )
            .first()
        )

        if not oauth_token:
            raise PublishUnavailableError(
                "GBP review publishing is unavailable because no Google OAuth token is connected. "
                "Reconnect Google in Integrations and try again."
            )

        access_token = oauth_token.access_token_ref
        if not access_token:
            raise PublishUnavailableError(
                "GBP review publishing is unavailable because the Google access token is missing. "
                "Reconnect Google in Integrations and try again."
            )

        try:
            gbp = get_google_api_service()
            result = await gbp.reply_to_review(
                access_token=access_token,
                review_name=review_response.review_id,
                comment=review_response.ai_draft,
            )
        except Exception as exc:
            raise PublishUnavailableError(
                f"GBP review publishing failed and needs operator attention: {exc}"
            ) from exc

        review_response.status = ResponseStatus.PUBLISHED
        review_response.published_at = utc_now_naive()
        review_response.platform_response_id = (
            result.get("name")
            or result.get("reply", {}).get("name")
            or result.get("replyName")
        )
        review_response.publish_error = None
        self.db.commit()

        logger.info(f"Published response for review {review_response.review_id}")

    def get_pending_responses(
        self,
        location_ids: Optional[list[UUID]] = None,
        platform: Optional[str] = None,
        search: Optional[str] = None,
        high_priority_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReviewResponseHistoryItem]:
        """
        Get pending review responses.

        Args:
            location_id: Filter by location
            platform: Filter by platform
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of pending review responses
        """
        responses = self._filter_responses(
            location_ids=location_ids,
            status=ResponseStatus.PENDING.value,
            platform=platform,
            search=search,
            high_priority_only=high_priority_only,
        )
        return [self._history_item(response) for response in responses[offset : offset + limit]]

    def get_review_history(
        self,
        location_ids: Optional[list[UUID]] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        high_priority_only: bool = False,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[ReviewResponseHistoryItem], int]:
        """Return a paginated history of review responses."""
        responses = self._filter_responses(
            location_ids=location_ids,
            status=status,
            platform=platform,
            search=search,
            high_priority_only=high_priority_only,
        )
        total = len(responses)
        items = [self._history_item(response) for response in responses[offset : offset + limit]]
        return items, total

    def get_summary(self, location_ids: Optional[list[UUID]] = None, account_id: Optional[UUID] = None) -> ReviewResponderSummaryResponse:
        """Compute an operator summary for review responses."""
        responses = self._filter_responses(location_ids=location_ids)

        total_count = len(responses)
        pending_count = sum(1 for response in responses if response.status == ResponseStatus.PENDING)
        approved_count = sum(1 for response in responses if response.status == ResponseStatus.APPROVED)
        rejected_count = sum(1 for response in responses if response.status == ResponseStatus.REJECTED)
        published_count = sum(1 for response in responses if response.status == ResponseStatus.PUBLISHED)
        failed_count = sum(1 for response in responses if response.status == ResponseStatus.FAILED)
        high_priority_pending_count = sum(
            1
            for response in responses
            if response.status == ResponseStatus.PENDING and self._priority_level(response) == "high"
        )
        high_priority_total_count = sum(
            1 for response in responses if self._priority_level(response) == "high"
        )
        ratings = [response.review_rating for response in responses if response.review_rating is not None]
        average_rating = round(sum(ratings) / len(ratings), 1) if ratings else None
        last_activity_at = max(
            [response.updated_at for response in responses if response.updated_at],
            default=None,
        )
        last_failed_at = max(
            [
                response.updated_at
                for response in responses
                if response.status == ResponseStatus.FAILED and response.updated_at
            ],
            default=None,
        )
        last_published_at = max(
            [response.published_at for response in responses if response.published_at],
            default=None,
        )

        # Bulk retry stats (requires account_id to query logs)
        last_bulk_retry_at = None
        last_bulk_retry_succeeded = None
        last_bulk_retry_still_failed = None
        last_bulk_retry_total = None
        if account_id is not None:
            last_log = (
                self.db.query(BulkRetryLog)
                .filter(BulkRetryLog.account_id == account_id)
                .order_by(desc(BulkRetryLog.created_at))
                .first()
            )
            if last_log is not None:
                last_bulk_retry_at = last_log.created_at
                last_bulk_retry_succeeded = last_log.succeeded
                last_bulk_retry_still_failed = last_log.still_failed
                last_bulk_retry_total = last_log.total

        return ReviewResponderSummaryResponse(
            total_count=total_count,
            pending_count=pending_count,
            approved_count=approved_count,
            rejected_count=rejected_count,
            published_count=published_count,
            failed_count=failed_count,
            high_priority_pending_count=high_priority_pending_count,
            high_priority_total_count=high_priority_total_count,
            average_rating=average_rating,
            last_activity_at=last_activity_at,
            last_failed_at=last_failed_at,
            last_published_at=last_published_at,
            last_bulk_retry_at=last_bulk_retry_at,
            last_bulk_retry_succeeded=last_bulk_retry_succeeded,
            last_bulk_retry_still_failed=last_bulk_retry_still_failed,
            last_bulk_retry_total=last_bulk_retry_total,
        )

    def get_failed_responses(
        self,
        location_ids: Optional[list[UUID]] = None,
        platform: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[FailedResponseItem], int, dict[str, int]]:
        """
        Dedicated operational query for failed publish responses.

        Sorted most-recently-failed first (updated_at desc). Returns items,
        total count, and error_category_counts across all matching failures.
        """
        responses = self._filter_responses(
            location_ids=location_ids,
            status=ResponseStatus.FAILED.value,
            platform=platform,
            search=search,
        )
        # Sort by updated_at desc — most recently failed first
        responses.sort(
            key=lambda r: r.updated_at or r.created_at,
            reverse=True,
        )

        total = len(responses)

        # Category counts across all failures (not just this page)
        counts: dict[str, int] = {}
        for r in responses:
            cat = self._error_category(r.publish_error)
            counts[cat] = counts.get(cat, 0) + 1

        page = responses[offset : offset + limit]
        items = [self._failed_item(r) for r in page]
        return items, total, counts

    async def bulk_retry(
        self,
        response_ids: list[int],
        allowed_location_ids: list[UUID],
        account_id: Optional[UUID] = None,
    ) -> BulkRetryResponse:
        """
        Bulk-retry failed review response publishes.

        Only retries items that are found, owned, and currently in FAILED
        status. Everything else is counted as skipped with no error raised.
        """
        results: list[BulkRetryItemResult] = []
        succeeded = 0
        still_failed = 0
        skipped = 0

        for response_id in response_ids:
            review_response = (
                self.db.query(ReviewResponse).filter(ReviewResponse.id == response_id).first()
            )
            if not review_response or review_response.location_id not in allowed_location_ids:
                skipped += 1
                continue
            if review_response.status != ResponseStatus.FAILED:
                skipped += 1
                continue

            try:
                updated = await self.retry_publish(response_id=response_id)
                if updated.status == ResponseStatus.PUBLISHED:
                    succeeded += 1
                    results.append(
                        BulkRetryItemResult(
                            response_id=response_id,
                            success=True,
                            status="published",
                            publish_error=None,
                        )
                    )
                else:
                    still_failed += 1
                    results.append(
                        BulkRetryItemResult(
                            response_id=response_id,
                            success=False,
                            status="failed",
                            publish_error=updated.publish_error,
                        )
                    )
            except Exception as exc:
                logger.error(f"Bulk retry failed for response {response_id}: {exc}")
                still_failed += 1
                results.append(
                    BulkRetryItemResult(
                        response_id=response_id,
                        success=False,
                        status="failed",
                        publish_error=str(exc),
                    )
                )

        outcome = BulkRetryResponse(
            results=results,
            total=len(response_ids),
            succeeded=succeeded,
            still_failed=still_failed,
            skipped=skipped,
        )

        if account_id is not None:
            try:
                log = BulkRetryLog(
                    account_id=account_id,
                    total=outcome.total,
                    succeeded=outcome.succeeded,
                    still_failed=outcome.still_failed,
                    skipped=outcome.skipped,
                )
                self.db.add(log)
                self.db.commit()
            except Exception as exc:
                logger.error(f"Failed to persist BulkRetryLog: {exc}")
                self.db.rollback()

        return outcome

    async def retry_publish(self, response_id: int, account_id: Optional[UUID] = None) -> ReviewResponse:
        """
        Retry publishing a failed review response.

        Only allowed when status is FAILED. Re-uses the existing approved draft
        and attempts a fresh publish to GBP. Updates publish_error on the record
        regardless of outcome so the caller always gets honest state back.
        """
        review_response = (
            self.db.query(ReviewResponse).filter(ReviewResponse.id == response_id).first()
        )
        if not review_response:
            raise ValueError(f"Review response {response_id} not found")

        if review_response.status != ResponseStatus.FAILED:
            raise ValueError(
                f"Retry is only allowed for failed responses (current status: {review_response.status})"
            )

        # Reset to approved so _publish_response can proceed
        review_response.status = ResponseStatus.APPROVED
        review_response.publish_error = None
        review_response.published_at = None
        review_response.platform_response_id = None
        self.db.commit()

        try:
            await self._publish_response(review_response)
            review_response.publish_error = None
        except Exception as exc:
            logger.error(f"Retry publish failed for response {response_id}: {exc}")
            review_response.status = ResponseStatus.FAILED
            review_response.publish_error = str(exc)
            review_response.published_at = None
            review_response.platform_response_id = None
            self.db.commit()

        return review_response

    def export_review_history_csv(
        self,
        location_ids: Optional[list[UUID]] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        high_priority_only: bool = False,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Return review history rows and headers for CSV export."""
        responses = self._filter_responses(
            location_ids=location_ids,
            status=status,
            platform=platform,
            search=search,
            high_priority_only=high_priority_only,
        )

        rows: list[dict[str, Any]] = []
        for response in responses:
            priority_level = self._priority_level(response)
            rows.append(
                {
                    "id": response.id,
                    "location_id": response.location_id,
                    "review_id": response.review_id,
                    "review_author": response.review_author or "",
                    "review_rating": response.review_rating,
                    "platform": response.platform,
                    "status": response.status.value if hasattr(response.status, "value") else str(response.status),
                    "intent": response.intent.value if hasattr(response.intent, "value") else str(response.intent),
                    "high_priority": priority_level == "high",
                    "priority_level": priority_level,
                    "priority_reason": self._priority_reason(response),
                    "review_text": response.review_text or "",
                    "ai_draft": response.ai_draft or "",
                    "rejection_reason": response.rejection_reason or "",
                    "approved_at": response.approved_at.isoformat() if response.approved_at else "",
                    "published_at": response.published_at.isoformat() if response.published_at else "",
                    "platform_response_id": response.platform_response_id or "",
                    "publish_error": response.publish_error or "",
                    "created_at": response.created_at.isoformat() if response.created_at else "",
                    "updated_at": response.updated_at.isoformat() if response.updated_at else "",
                }
            )

        headers = list(rows[0].keys()) if rows else [
            "id",
            "location_id",
            "review_id",
            "review_author",
            "review_rating",
            "platform",
            "status",
            "intent",
            "high_priority",
            "priority_level",
            "priority_reason",
            "review_text",
            "ai_draft",
            "rejection_reason",
            "approved_at",
            "published_at",
            "platform_response_id",
            "publish_error",
            "created_at",
            "updated_at",
        ]
        return rows, headers
