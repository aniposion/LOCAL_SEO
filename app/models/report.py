"""Report model for weekly reports."""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


class Report(BaseModel):
    """Weekly report model."""

    __tablename__ = "reports"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), index=True
    )

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Email tracking
    email_sent: Mapped[bool] = mapped_column(default=False, nullable=False)
    email_sent_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report {self.period_start} - {self.period_end}>"
