"""SEO Score model for performance scoring."""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, Text
from sqlalchemy import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


class SEOScore(BaseModel):
    """SEO performance score model."""

    __tablename__ = "seo_scores"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), index=True
    )

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100

    # Score breakdown
    factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Recommendations
    recommendations: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="seo_scores")

    def __repr__(self) -> str:
        return f"<SEOScore {self.score} on {self.date}>"
