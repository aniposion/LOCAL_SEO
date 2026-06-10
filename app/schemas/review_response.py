"""Review response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Review response schemas
class ReviewResponseBase(BaseModel):
    """Base review response schema."""

    review_id: str
    review_author: Optional[str] = None
    review_rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = None
    review_date: Optional[datetime] = None
    platform: str = "google"
    platform_review_url: Optional[str] = None


class ReviewResponseCreate(ReviewResponseBase):
    """Schema for creating a review response."""

    location_id: UUID
    sentiment_score: Optional[float] = None
    intent: str
    detected_issues: Optional[str] = None
    ai_draft: str
    tone: str
    generated_by_ai: str = "gemini-1.5-flash"


class ReviewResponseUpdate(BaseModel):
    """Schema for updating a review response."""

    ai_draft: Optional[str] = None
    status: Optional[str] = None
    rejection_reason: Optional[str] = None


class ReviewResponseResponse(ReviewResponseBase):
    """Schema for review response output."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_id: UUID
    sentiment_score: Optional[float] = None
    intent: str
    detected_issues: Optional[str] = None
    ai_draft: str
    tone: str
    generated_by_ai: str
    status: str
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    published_at: Optional[datetime] = None
    platform_response_id: Optional[str] = None
    publish_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReviewResponseHistoryItem(ReviewResponseResponse):
    """Review response history item with operator-facing priority metadata."""

    high_priority: bool = False
    priority_level: str = "normal"
    priority_reason: str = ""
    age_minutes: Optional[int] = None


class ReviewResponseHistoryResponse(BaseModel):
    """Paginated review response history payload."""

    items: list[ReviewResponseHistoryItem]
    total: int
    limit: int
    offset: int


class FailedResponseItem(ReviewResponseHistoryItem):
    """Failed response enriched with error categorization for operator triage."""

    error_category: str = "unknown"
    """One of: no_oauth_token | token_missing | api_error | unknown"""


class FailedResponsesResponse(BaseModel):
    """Paginated failed responses with error category counts for triage."""

    items: list[FailedResponseItem]
    total: int
    limit: int
    offset: int
    error_category_counts: dict[str, int] = Field(default_factory=dict)


class BulkRetryRequest(BaseModel):
    """Request to bulk-retry a set of failed response publishes."""

    response_ids: list[int] = Field(..., min_length=1, max_length=50)


class BulkRetryItemResult(BaseModel):
    """Per-item outcome from a bulk retry operation."""

    response_id: int
    success: bool
    status: str
    publish_error: Optional[str] = None


class BulkRetryResponse(BaseModel):
    """Aggregate result of a bulk retry operation."""

    results: list[BulkRetryItemResult]
    total: int
    succeeded: int
    still_failed: int
    skipped: int
    """Items not found, not owned, or not in failed status."""


class ReviewResponderSummaryResponse(BaseModel):
    """Operational summary for the review responder queue."""

    total_count: int = 0
    pending_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    published_count: int = 0
    failed_count: int = 0
    high_priority_pending_count: int = 0
    high_priority_total_count: int = 0
    average_rating: Optional[float] = None
    last_activity_at: Optional[datetime] = None
    last_failed_at: Optional[datetime] = None
    last_published_at: Optional[datetime] = None
    # Bulk retry activity (populated when account_id is available)
    last_bulk_retry_at: Optional[datetime] = None
    last_bulk_retry_succeeded: Optional[int] = None
    last_bulk_retry_still_failed: Optional[int] = None
    last_bulk_retry_total: Optional[int] = None


# Request schemas
class GenerateResponseRequest(BaseModel):
    """Request to generate AI response for a review."""

    location_id: UUID
    review_id: str
    review_author: Optional[str] = None
    review_rating: int = Field(..., ge=1, le=5)
    review_text: str
    review_date: Optional[datetime] = None
    platform: str = "google"
    platform_review_url: Optional[str] = None


class ApproveResponseRequest(BaseModel):
    """Request to approve a review response."""

    response_id: int
    edited_draft: Optional[str] = Field(
        None, description="Optional edited version of the draft"
    )


class RejectResponseRequest(BaseModel):
    """Request to reject a review response."""

    response_id: int
    reason: str = Field(..., description="Reason for rejection")


class PendingResponsesFilter(BaseModel):
    """Filter for pending responses."""

    location_id: Optional[UUID] = None
    platform: Optional[str] = None
    min_rating: Optional[int] = Field(None, ge=1, le=5)
    max_rating: Optional[int] = Field(None, ge=1, le=5)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# Sentiment analysis result
class SentimentAnalysis(BaseModel):
    """Sentiment analysis result."""

    score: float = Field(..., ge=-1.0, le=1.0, description="Sentiment score")
    label: str = Field(..., description="Sentiment label: positive, negative, neutral")
    intent: str = Field(..., description="Review intent")
    detected_issues: list[str] = Field(default_factory=list)
    key_phrases: list[str] = Field(default_factory=list)


# Response draft
class ResponseDraft(BaseModel):
    """AI-generated response draft."""

    draft_text: str
    tone: str
    sentiment_analysis: SentimentAnalysis
    suggested_actions: list[str] = Field(
        default_factory=list, description="Suggested follow-up actions"
    )


# Webhook schemas
class ReviewWebhookPayload(BaseModel):
    """Webhook payload for new review."""

    location_id: UUID
    platform: str
    event_type: str
    review_id: str
    review_data: dict
