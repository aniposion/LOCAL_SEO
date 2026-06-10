"""P2: Review Booster schemas - Compliance-Safe."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewCampaignCreate(BaseModel):
    """Create a review campaign."""

    name: str = Field(..., min_length=1, max_length=200)
    sms_template: Optional[str] = Field(
        default="Hi {customer_name}, thanks for choosing {business_name}. If you have a minute, please leave a Google review here: {google_link}",
        description="SMS template with placeholders",
    )
    email_template: Optional[str] = Field(default=None, description="Email HTML template")
    email_subject: Optional[str] = Field(
        default="Thanks for visiting - please leave a review",
        max_length=200,
    )
    delay_hours: int = Field(default=24, ge=0, le=168)
    channels: list[str] = Field(default=["sms"])
    google_review_url: str = Field(..., description="Google review URL - REQUIRED")
    private_feedback_url: Optional[str] = Field(
        default=None,
        description="Optional parallel feedback form (not conditional gating)",
    )

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, value: list[str]) -> list[str]:
        valid = {"sms", "email"}
        for channel in value:
            if channel not in valid:
                raise ValueError(f"Invalid channel: {channel}. Must be one of {valid}")
        return value

    @field_validator("google_review_url")
    @classmethod
    def validate_google_url(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Google review URL is required for compliance")
        normalized = value.strip()
        if "google" not in normalized.lower() and "g.page" not in normalized.lower():
            raise ValueError("Must be a valid Google review URL")
        return normalized


class ReviewCampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    sms_template: Optional[str] = None
    email_template: Optional[str] = None
    email_subject: Optional[str] = None
    delay_hours: Optional[int] = Field(None, ge=0, le=168)
    channels: Optional[list[str]] = None
    status: Optional[Literal["active", "paused", "completed"]] = None
    private_feedback_url: Optional[str] = None
    google_review_url: Optional[str] = None


class ReviewCampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    name: str
    status: str
    sms_template: Optional[str]
    email_template: Optional[str]
    email_subject: Optional[str]
    delay_hours: int
    channels: list[str]
    google_review_url: str
    private_feedback_url: Optional[str]
    total_sent: int
    total_clicked: int
    total_reviews_estimated: int
    created_at: datetime
    updated_at: datetime


class ReviewCampaignList(BaseModel):
    items: list[ReviewCampaignResponse]
    total: int


class ReviewRequestCreate(BaseModel):
    campaign_id: UUID
    customer_name: str = Field(..., min_length=1, max_length=200)
    customer_phone: Optional[str] = Field(None, max_length=20)
    customer_email: Optional[str] = Field(None, max_length=200)
    channel: Literal["sms", "email"]
    consent_given: bool = Field(..., description="Customer consent REQUIRED")
    consent_method: str = Field(..., description="How consent was obtained")

    @field_validator("consent_given")
    @classmethod
    def validate_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Customer consent is required before sending review requests")
        return value


class ReviewRequestBulk(BaseModel):
    campaign_id: UUID
    requests: list[ReviewRequestCreate]


class ReviewRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    location_id: UUID
    customer_name: Optional[str]
    customer_email: Optional[str]
    customer_phone: Optional[str]
    channel: str
    status: str
    consent_given: bool
    consent_method: Optional[str]
    google_link_included: bool
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    last_attempt_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    retry_count: int
    last_error: Optional[str]
    google_link_clicked_at: Optional[datetime]
    created_at: datetime


class ReviewRequestList(BaseModel):
    items: list[ReviewRequestResponse]
    total: int


class OptoutCreate(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=200)


class OptoutResponse(BaseModel):
    is_opted_out: bool
    opted_out_at: Optional[datetime] = None


class PrivateFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    rating: Optional[int]
    feedback_text: Optional[str]
    customer_name: Optional[str]
    status: str
    assigned_to: Optional[UUID]
    notes: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime


class FeedbackUpdateStatus(BaseModel):
    status: Literal["new", "in_progress", "resolved", "closed"]
    notes: Optional[str] = None
    assigned_to: Optional[UUID] = None


class FeedbackList(BaseModel):
    items: list[PrivateFeedbackResponse]
    total: int


class CampaignStats(BaseModel):
    campaign_id: UUID
    total_sent: int
    total_delivered: int
    total_failed: int
    total_opted_out: int
    google_link_clicks: int
    feedback_link_clicks: int
    estimated_reviews: int
    conversion_rate: float


class ReviewBoosterAnalyticsResponse(BaseModel):
    location_id: UUID
    period_days: int
    total_campaigns: int
    active_campaigns: int
    paused_campaigns: int
    completed_campaigns: int
    total_requests: int
    pending_requests: int
    delivered_requests: int
    failed_requests: int
    pending_retries: int
    opted_out_requests: int
    attention_requests: int
    total_sent: int
