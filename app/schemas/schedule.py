"""Schedule schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ScheduleBase(BaseModel):
    """Base schedule schema."""

    platform: str
    cron_expr: str | None = None
    rrule: str | None = None
    topic_prefs: dict | None = None
    tone: str | None = None
    language: str = "en"
    is_active: bool = True


class ScheduleCreate(ScheduleBase):
    """Schedule creation schema."""

    location_id: UUID


class ScheduleUpdate(BaseModel):
    """Schedule update schema."""

    cron_expr: str | None = None
    rrule: str | None = None
    topic_prefs: dict | None = None
    tone: str | None = None
    language: str | None = None
    is_active: bool | None = None


class ScheduleResponse(ScheduleBase):
    """Schedule response schema."""

    id: UUID
    location_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
