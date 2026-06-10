"""Location schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LocationBase(BaseModel):
    """Base location schema."""

    name: str = Field(max_length=255)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "US"
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None
    website_url: str | None = None
    business_hours: dict | None = None
    services: list[str] | None = None
    description: str | None = None


class LocationCreate(LocationBase):
    """Location creation schema."""

    pass


class LocationUpdate(BaseModel):
    """Location update schema."""

    name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None
    website_url: str | None = None
    business_hours: dict | None = None
    services: list[str] | None = None
    description: str | None = None
    gbp_location_id: str | None = None
    ig_business_id: str | None = None


class LocationResponse(LocationBase):
    """Location response schema."""

    id: UUID
    account_id: UUID
    gbp_location_id: str | None = None
    ig_business_id: str | None = None
    gbp_connected: bool = False
    gbp_status: str | None = None
    instagram_connected: bool = False
    instagram_status: str | None = None
    website_connected: bool = False
    website_status: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocationHealth(BaseModel):
    """Location health check response."""

    location_id: UUID
    gbp_connected: bool = False
    gbp_status: str | None = None
    instagram_connected: bool = False
    instagram_status: str | None = None
    website_connected: bool = False
    website_status: str | None = None
