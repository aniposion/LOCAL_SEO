"""Social proof schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Social proof card schemas
class SocialProofCardBase(BaseModel):
    """Base social proof card schema."""

    review_id: str
    review_author: Optional[str] = None
    review_rating: int = Field(..., ge=1, le=5)
    review_text: str
    review_date: Optional[datetime] = None


class SocialProofCardCreate(SocialProofCardBase):
    """Schema for creating a social proof card."""

    location_id: UUID
    card_title: Optional[str] = None
    card_text: Optional[str] = None
    image_prompt: Optional[str] = None
    layout_style: str = "instagram_square"
    text_color: str = "#FFFFFF"
    background_color: str = "#000000"
    font_family: str = "Arial"


class SocialProofCardUpdate(BaseModel):
    """Schema for updating a social proof card."""

    card_title: Optional[str] = None
    card_text: Optional[str] = None
    status: Optional[str] = None
    rejection_reason: Optional[str] = None


class SocialProofCardResponse(SocialProofCardBase):
    """Schema for social proof card response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_id: UUID
    card_title: Optional[str] = None
    card_text: Optional[str] = None
    image_prompt: Optional[str] = None
    image_url: Optional[str] = None
    background_image_url: Optional[str] = None
    final_card_url: Optional[str] = None
    layout_style: str
    text_color: str
    background_color: str
    font_family: str
    status: str
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    published_to: Optional[str] = None
    published_at: Optional[datetime] = None
    platform_post_id: Optional[str] = None
    generated_by_ai: str
    created_at: datetime
    updated_at: datetime


class SocialProofMetrics(BaseModel):
    """Operational metrics for social proof cards."""

    total_cards: int = 0
    draft_count: int = 0
    pending_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    published_count: int = 0
    attention_required_count: int = 0
    approval_rate: float = 0.0
    publish_rate: float = 0.0
    last_published_at: Optional[datetime] = None
    last_rejected_at: Optional[datetime] = None
    last_pending_at: Optional[datetime] = None


class SocialProofHistoryResponse(BaseModel):
    """Paginated social proof history response."""

    items: list[SocialProofCardResponse]
    total: int
    limit: int
    offset: int
    status_filter: str = "all"
    search: Optional[str] = None
    metrics: SocialProofMetrics


# Request schemas
class GenerateCardRequest(BaseModel):
    """Request to generate a social proof card."""

    location_id: UUID
    review_id: str
    review_author: Optional[str] = None
    review_rating: int = Field(..., ge=1, le=5)
    review_text: str
    review_date: Optional[datetime] = None
    layout_style: str = Field(default="instagram_square")
    custom_prompt: Optional[str] = Field(
        None, description="Custom prompt for image generation"
    )


class AutoGenerateCardsRequest(BaseModel):
    """Request to auto-generate cards from best reviews."""

    location_id: UUID
    max_cards: int = Field(default=1, ge=1, le=5)
    min_rating: int = Field(default=5, ge=1, le=5)
    min_text_length: int = Field(default=50, ge=10)
    days_back: int = Field(default=7, ge=1, le=90)


class ApproveCardRequest(BaseModel):
    """Request to approve a social proof card."""

    card_id: int
    publish_immediately: bool = Field(
        default=False, description="Deprecated legacy flag. Direct social proof publishing is not wired."
    )
    platforms: list[str] = Field(
        default_factory=lambda: ["instagram"], description="Platforms to publish to"
    )


class RejectCardRequest(BaseModel):
    """Request to reject a social proof card."""

    card_id: int
    reason: str = Field(..., description="Reason for rejection")


# Schedule schemas
class SocialProofScheduleBase(BaseModel):
    """Base schedule schema."""

    enabled: bool = True
    frequency: str = Field(default="weekly", description="daily, weekly, biweekly, monthly")
    day_of_week: int = Field(default=0, ge=0, le=6, description="0=Sunday, 6=Saturday")
    time_of_day: str = Field(default="18:00", description="HH:MM format")
    min_rating: int = Field(default=5, ge=1, le=5)
    min_text_length: int = Field(default=50, ge=10)
    max_cards_per_run: int = Field(default=1, ge=1, le=5)
    auto_approve: bool = False
    auto_publish: bool = False


class SocialProofScheduleCreate(SocialProofScheduleBase):
    """Schema for creating a schedule."""

    location_id: UUID


class SocialProofScheduleUpdate(BaseModel):
    """Schema for updating a schedule."""

    enabled: Optional[bool] = None
    frequency: Optional[str] = None
    day_of_week: Optional[int] = None
    time_of_day: Optional[str] = None
    min_rating: Optional[int] = None
    min_text_length: Optional[int] = None
    max_cards_per_run: Optional[int] = None
    auto_approve: Optional[bool] = None
    auto_publish: Optional[bool] = None


class SocialProofScheduleResponse(SocialProofScheduleBase):
    """Schema for schedule response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_id: UUID
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# Card design options
class CardDesignOptions(BaseModel):
    """Design options for card generation."""

    layout_style: str = Field(
        default="instagram_square",
        description="Layout style: instagram_square, instagram_story, facebook_post",
    )
    text_color: str = Field(default="#FFFFFF", description="Hex color for text")
    background_color: str = Field(default="#000000", description="Hex color for background")
    font_family: str = Field(default="Arial", description="Font family name")
    include_business_logo: bool = Field(default=True, description="Include business logo")
    include_google_icon: bool = Field(default=True, description="Include Google review icon")
    include_stars: bool = Field(default=True, description="Include star rating")
