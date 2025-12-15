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
    from app.models.location import Location


class Platform(str, enum.Enum):
    """Target platforms."""

    GBP = "GBP"
    INSTAGRAM = "INSTAGRAM"
    WEBSITE = "WEBSITE"


class PostStatus(str, enum.Enum):
    """Post lifecycle status."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"  # AI ì´ˆì•ˆ ?ì„± ?„ë£Œ, ?¹ì¸ ?€ê¸?
    APPROVED = "approved"  # ?¹ì¸?? ?…ë¡œ???€ê¸?
    REJECTED = "rejected"  # ê±°ì ˆ??
    QUEUED = "queued"  # ?ˆì•½??
    POSTED = "posted"  # ê²Œì‹œ ?„ë£Œ
    FAILED = "failed"  # ê²Œì‹œ ?¤íŒ¨


class Post(BaseModel):
    """Content post model."""

    __tablename__ = "posts"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), index=True
    )

    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus), default=PostStatus.DRAFT, nullable=False, index=True
    )

    # Content
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scheduling
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Provider tracking
    provider_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Generation metadata
    generated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Approval workflow
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

    # Notification tracking
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_channel: Mapped[str | None] = mapped_column(String(50), nullable=True)  # kakao, slack, email
    notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # AI-generated image
    ai_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_image_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="posts")
    analytics: Mapped[list["Analytics"]] = relationship(
        "Analytics", back_populates="post", cascade="all, delete-orphan"
    )
    approved_by: Mapped["Account | None"] = relationship("Account", foreign_keys=[approved_by_id])

    def __repr__(self) -> str:
        return f"<Post {self.platform.value} - {self.status.value}>"
