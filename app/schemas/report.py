"""Report schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class ReportBase(BaseModel):
    """Base report schema."""

    period_start: date
    period_end: date


class ReportCreate(ReportBase):
    """Report creation schema."""

    location_id: UUID


class ReportResponse(ReportBase):
    """Report response schema."""

    id: UUID
    location_id: UUID
    file_url: str | None = None
    summary: dict | None = None
    email_sent: bool = False
    email_sent_at: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportGenerateRequest(BaseModel):
    """Report generation request."""

    location_id: UUID
    send_email: bool = True


class ReportSummary(BaseModel):
    """Report summary data."""

    kpi_cards: dict
    top_posts: list[dict]
    review_summary: dict | None = None
    next_actions: list[str]
