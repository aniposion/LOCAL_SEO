"""Location (business) model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.analytics import Analytics
    from app.models.channel import Channel
    from app.models.post import Post
    from app.models.report import Report
    from app.models.schedule import Schedule
    from app.models.seo_score import SEOScore


class Location(BaseModel):
    """Business location model."""

    __tablename__ = "locations"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="US", nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Contact
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Business details
    business_hours: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    services: Mapped[list | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Platform IDs
    gbp_location_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ig_business_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="locations")
    channels: Mapped[list["Channel"]] = relationship(
        "Channel", back_populates="location", cascade="all, delete-orphan"
    )
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="location", cascade="all, delete-orphan"
    )
    analytics: Mapped[list["Analytics"]] = relationship(
        "Analytics", back_populates="location", cascade="all, delete-orphan"
    )
    seo_scores: Mapped[list["SEOScore"]] = relationship(
        "SEOScore", back_populates="location", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="location", cascade="all, delete-orphan"
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="location", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Location {self.name}>"
