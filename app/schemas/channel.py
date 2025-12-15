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
    last_sync_at: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChannelCredentials(BaseModel):
    """Channel credentials for OAuth flow."""

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scope: str | None = None
