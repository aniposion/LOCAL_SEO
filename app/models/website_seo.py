"""Models for Website SEO draft generation and publish history."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


class WebsiteSEOContentType(str, enum.Enum):
    """Supported Website SEO draft content types."""

    META_TAGS = "meta_tags"
    SERVICE_PAGE = "service_page"
    BLOG_POST = "blog_post"
    OPTIMIZATION = "optimization"


class WebsiteSEODraftStatus(str, enum.Enum):
    """Lifecycle for a generated SEO draft."""

    DRAFT = "draft"
    PUBLISHED = "published"
    FAILED = "failed"


class WebsiteSEOApprovalStatus(str, enum.Enum):
    """Review lifecycle for generated SEO drafts before publishing."""

    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WebsiteSEODraft(BaseModel):
    """Persisted Website SEO draft and publish history."""

    __tablename__ = "website_seo_drafts"

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content_type: Mapped[WebsiteSEOContentType] = mapped_column(
        Enum(WebsiteSEOContentType),
        nullable=False,
    )
    status: Mapped[WebsiteSEODraftStatus] = mapped_column(
        Enum(WebsiteSEODraftStatus),
        nullable=False,
        default=WebsiteSEODraftStatus.DRAFT,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_requested")
    approval_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    location: Mapped["Location"] = relationship("Location", back_populates="website_seo_drafts")
