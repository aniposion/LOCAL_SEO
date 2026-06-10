"""Revenue profile schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class RevenueProfileBase(BaseModel):
    """Revenue inputs used for ROI calculations."""

    business_type: str | None = Field(default=None, max_length=100)
    currency: str = Field(default="USD", max_length=10)
    average_order_value: Decimal = Field(default=Decimal("150.00"), ge=0)
    gross_margin_percent: Decimal = Field(default=Decimal("30.00"), ge=0, le=100)
    call_to_booking_rate: Decimal = Field(default=Decimal("35.00"), ge=0, le=100)
    booking_to_visit_rate: Decimal = Field(default=Decimal("80.00"), ge=0, le=100)
    visit_to_sale_rate: Decimal = Field(default=Decimal("90.00"), ge=0, le=100)
    missed_call_recovery_rate: Decimal = Field(default=Decimal("20.00"), ge=0, le=100)
    review_to_conversion_lift_percent: Decimal = Field(default=Decimal("3.00"), ge=0, le=100)
    owner_hourly_value: Decimal = Field(default=Decimal("50.00"), ge=0)


class RevenueProfileCreate(RevenueProfileBase):
    """Create revenue profile payload."""


class RevenueProfileUpdate(BaseModel):
    """Partial update payload for revenue profile."""

    business_type: str | None = Field(default=None, max_length=100)
    currency: str | None = Field(default=None, max_length=10)
    average_order_value: Decimal | None = Field(default=None, ge=0)
    gross_margin_percent: Decimal | None = Field(default=None, ge=0, le=100)
    call_to_booking_rate: Decimal | None = Field(default=None, ge=0, le=100)
    booking_to_visit_rate: Decimal | None = Field(default=None, ge=0, le=100)
    visit_to_sale_rate: Decimal | None = Field(default=None, ge=0, le=100)
    missed_call_recovery_rate: Decimal | None = Field(default=None, ge=0, le=100)
    review_to_conversion_lift_percent: Decimal | None = Field(default=None, ge=0, le=100)
    owner_hourly_value: Decimal | None = Field(default=None, ge=0)


class RevenueProfileResponse(RevenueProfileBase):
    """Revenue profile response."""

    id: UUID
    location_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RevenueProjectionResponse(BaseModel):
    """Simple projection summary derived from a revenue profile."""

    location_id: UUID
    estimated_bookings_from_calls: int
    estimated_visits_from_calls: int
    estimated_sales_from_calls: int
    estimated_revenue_from_calls: Decimal
    estimated_gross_profit_from_calls: Decimal
    missed_call_recovery_revenue: Decimal
