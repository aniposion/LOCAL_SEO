"""Revenue profile models for revenue-centric ROI calculations."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


class RevenueProfile(BaseModel):
    """Business-specific assumptions used for revenue-centric ROI."""

    __tablename__ = "revenue_profiles"

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    business_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)

    average_order_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("150.00"), nullable=False
    )
    gross_margin_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("30.00"), nullable=False
    )
    call_to_booking_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("35.00"), nullable=False
    )
    booking_to_visit_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("80.00"), nullable=False
    )
    visit_to_sale_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("90.00"), nullable=False
    )
    missed_call_recovery_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("20.00"), nullable=False
    )
    review_to_conversion_lift_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("3.00"), nullable=False
    )
    owner_hourly_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("50.00"), nullable=False
    )

    location: Mapped["Location"] = relationship("Location", back_populates="revenue_profile")
