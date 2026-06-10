"""Models for social response history and audit logging."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


class SocialResponseMode(str, enum.Enum):
    """How a response was triggered."""

    MANUAL = "manual"
    AUTO = "auto"


class SocialResponseLog(BaseModel):
    """Audit log for social message responses."""

    __tablename__ = "social_response_logs"

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="instagram")
    message_type: Mapped[str] = mapped_column(String(50), nullable=False, default="dm")
    response_mode: Mapped[SocialResponseMode] = mapped_column(
        Enum(SocialResponseMode),
        nullable=False,
        default=SocialResponseMode.MANUAL,
    )
    message_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    sender_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    location: Mapped["Location"] = relationship("Location", back_populates="social_response_logs")


class SocialAutomationSettings(BaseModel):
    """Persisted settings for social response automation."""

    __tablename__ = "social_automation_settings"

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        unique=True,
    )
    auto_respond_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_respond_dms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_respond_comments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    response_delay_seconds: Mapped[int] = mapped_column(nullable=False, default=60)
    excluded_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    high_priority_alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    high_priority_alert_channel: Mapped[str] = mapped_column(String(20), nullable=False, default="preferred")

    location: Mapped["Location"] = relationship("Location", back_populates="social_automation_settings")
