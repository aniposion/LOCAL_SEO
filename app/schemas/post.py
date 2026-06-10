"""Post schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.post import Platform, PostStatus
from app.models.publish_job import PublishJobStatus


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


class PublishJobSummary(BaseModel):
    """Latest publish job summary for operational visibility."""

    id: UUID
    platform: str
    status: PublishJobStatus
    tries: int
    max_tries: int
    last_error: str | None = None
    error_code: str | None = None
    next_run_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    platform_post_id: str | None = None

    model_config = {"from_attributes": True}


class PublishJobResponse(PublishJobSummary):
    """Detailed publish job response for history views."""

    created_at: datetime
    updated_at: datetime
    request_payload: dict | None = None
    response_payload: dict | None = None


class PublishJobListResponse(BaseModel):
    """Paginated publish job history response."""

    items: list[PublishJobResponse]
    total: int
    limit: int
    offset: int


class PublishIssueItem(BaseModel):
    """Account-level actionable publish issue for operator visibility."""

    job_id: UUID
    post_id: UUID
    location_id: UUID
    location_name: str
    title: str | None = None
    platform: str
    job_status: PublishJobStatus
    post_status: PostStatus
    tries: int
    max_tries: int
    can_retry: bool
    last_error: str | None = None
    error_code: str | None = None
    created_at: datetime
    next_run_at: datetime | None = None
    completed_at: datetime | None = None


class PublishIssueSummaryResponse(BaseModel):
    """Account-level summary of latest actionable publish issues."""

    items: list[PublishIssueItem]
    total: int
    failed: int
    retrying: int
    limit: int


class PostResponse(PostBase):
    """Post response schema."""

    id: UUID
    location_id: UUID
    status: PostStatus
    scheduled_at: datetime | None = None
    posted_at: datetime | None = None
    approval_requested_at: datetime | None = None
    provider_post_id: str | None = None
    error_message: str | None = None
    generated_by: str | None = None
    approval_token: str | None = None
    notification_sent: bool
    notification_channel: str | None = None
    notification_sent_at: datetime | None = None
    ai_image_url: str | None = None
    latest_publish_job: "PublishJobSummary | None" = None
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
