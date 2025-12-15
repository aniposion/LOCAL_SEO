"""Analytics model for performance tracking."""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.post import Post


class Analytics(BaseModel):
    """Performance analytics snapshot model."""

    __tablename__ = "analytics"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), index=True
    )
    post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("posts.id", ondelete="SET NULL"), nullable=True
    )

    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # GBP metrics
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direction_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Instagram metrics
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Website metrics
    page_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unique_visitors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_time_on_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Raw data
    source_raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="analytics")
    post: Mapped["Post | None"] = relationship("Post", back_populates="analytics")

    def __repr__(self) -> str:
        return f"<Analytics {self.platform} {self.date}>"
