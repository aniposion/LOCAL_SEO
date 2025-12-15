"""Schedule model for automated posting."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


class Schedule(BaseModel):
    """Posting schedule model."""

    __tablename__ = "schedules"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), index=True
    )

    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    cron_expr: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rrule: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Preferences
    topic_prefs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="schedules")

    def __repr__(self) -> str:
        return f"<Schedule {self.platform} - {self.cron_expr}>"
