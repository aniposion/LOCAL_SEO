"""Post schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.post import Platform, PostStatus


class PostBase(BaseModel):
    """Base post schema."""

    platform: Platform
    title: str | None = Field(None, max_length=255)
    body: str | None = None
    hashtags: list[str] | None = None
    image_url: str | None = None
    image_prompt: str | None = None


class PostCreate(PostBase):
    """Post creation schema."""

    location_id: UUID
    scheduled_at: datetime | None = None
    status: PostStatus = PostStatus.DRAFT


class PostUpdate(BaseModel):
    """Post update schema."""

    title: str | None = None
    body: str | None = None
    hashtags: list[str] | None = None
    image_url: str | None = None
    image_prompt: str | None = None
    scheduled_at: datetime | None = None
    status: PostStatus | None = None


class PostResponse(PostBase):
    """Post response schema."""

    id: UUID
    location_id: UUID
    status: PostStatus
    scheduled_at: datetime | None = None
    posted_at: datetime | None = None
    provider_post_id: str | None = None
    error_message: str | None = None
    generated_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PostPublishRequest(BaseModel):
    """Post publish request."""

    post_id: UUID


class PostBulkCreate(BaseModel):
    """Bulk post creation from content generation."""

    location_id: UUID
    posts: list[PostCreate]
