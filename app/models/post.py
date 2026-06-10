"""Post model for content management."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.analytics import Analytics
    from app.models.feedback import PostFeedback
    from app.models.location import Location
    from app.models.publish_job import PublishJob
    from app.models.vault import ApprovalAnalysis


class Platform(str, enum.Enum):
    """Target platforms."""

    GBP = "GBP"
    INSTAGRAM = "INSTAGRAM"
    WEBSITE = "WEBSITE"


class PostStatus(str, enum.Enum):
    """Post lifecycle status."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    QUEUED = "queued"
    POSTED = "posted"
    FAILED = "failed"


class Post(BaseModel):
    """Content post model."""

    __tablename__ = "posts"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), index=True
    )

    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    status: Mapped[PostStatus] = mapped_column(
        Enum(
            PostStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=PostStatus.DRAFT,
        nullable=False,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    provider_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    generated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    approval_token: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    approval_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    ai_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_image_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    location: Mapped["Location"] = relationship("Location", back_populates="posts")
    analytics: Mapped[list["Analytics"]] = relationship(
        "Analytics", back_populates="post", cascade="all, delete-orphan"
    )
    feedbacks: Mapped[list["PostFeedback"]] = relationship(
        "PostFeedback", back_populates="post", cascade="all, delete-orphan"
    )
    publish_jobs: Mapped[list["PublishJob"]] = relationship(
        "PublishJob", back_populates="post", cascade="all, delete-orphan"
    )
    approval_analysis: Mapped["ApprovalAnalysis | None"] = relationship(
        "ApprovalAnalysis", back_populates="post", uselist=False, cascade="all, delete-orphan"
    )
    approved_by: Mapped["Account | None"] = relationship("Account", foreign_keys=[approved_by_id])

    def __repr__(self) -> str:
        return f"<Post {self.platform.value} - {self.status.value}>"
