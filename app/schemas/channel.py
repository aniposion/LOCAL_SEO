"""Channel schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.channel import ChannelType


class ChannelBase(BaseModel):
    """Base channel schema."""

    type: ChannelType
    is_active: bool = True
    meta: dict | None = None


class ChannelCreate(ChannelBase):
    """Channel creation schema."""

    credentials: dict | None = None


class ChannelUpdate(BaseModel):
    """Channel update schema."""

    credentials: dict | None = None
    is_active: bool | None = None
    meta: dict | None = None


class ChannelResponse(ChannelBase):
    """Channel response schema."""

    id: UUID
    location_id: UUID
    status: str
    platform_account_id: str | None = None
    platform_account_name: str | None = None
    access_token_expires_at: datetime | None = None
    refresh_token_expires_at: datetime | None = None
    is_token_expired: bool = False
    needs_refresh: bool = False
    reconnect_required: bool = False
    last_sync_at: datetime | None = None
    error_message: str | None = None
    error_count: int = 0
    last_publish_failed_at: datetime | None = None
    last_publish_failed_error: str | None = None
    last_publish_succeeded_at: datetime | None = None
    recent_publish_failures: int = 0
    recent_publish_successes: int = 0
    qa_pending_count: int = 0
    qa_failed_count: int = 0
    qa_posted_count: int = 0
    qa_last_failed_at: datetime | None = None
    qa_last_posted_at: datetime | None = None
    qa_last_sync_at: datetime | None = None
    qa_last_sync_error: str | None = None
    qa_last_sync_question_count: int = 0
    qa_feedback_good_count: int = 0
    qa_feedback_needs_edit_count: int = 0
    qa_feedback_wrong_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChannelCredentials(BaseModel):
    """Channel credentials for OAuth flow."""

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scope: str | None = None
