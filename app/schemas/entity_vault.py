"""P5: Entity Vault schemas - Business information management."""

from datetime import datetime, time
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# ====================
# Business Hours
# ====================

class DayHours(BaseModel):
    """Operating hours for a single day."""
    is_open: bool = True
    open_time: Optional[time] = Field(None, description="Opening time, e.g. 09:00")
    close_time: Optional[time] = Field(None, description="Closing time, e.g. 18:00")
    breaks: list[dict] = Field(default_factory=list)  # [{"start": "12:00", "end": "13:00"}]


class BusinessHours(BaseModel):
    """Weekly business hours."""
    monday: DayHours = Field(default_factory=DayHours)
    tuesday: DayHours = Field(default_factory=DayHours)
    wednesday: DayHours = Field(default_factory=DayHours)
    thursday: DayHours = Field(default_factory=DayHours)
    friday: DayHours = Field(default_factory=DayHours)
    saturday: DayHours = Field(default_factory=lambda: DayHours(is_open=False))
    sunday: DayHours = Field(default_factory=lambda: DayHours(is_open=False))
    
    timezone: str = "America/New_York"
    
    def is_currently_open(self) -> bool:
        """Check if business is currently open."""
        from datetime import datetime
        import pytz
        
        tz = pytz.timezone(self.timezone)
        now = datetime.now(tz)
        day_name = now.strftime("%A").lower()
        day_hours: DayHours = getattr(self, day_name)
        
        if not day_hours.is_open:
            return False
        
        if day_hours.open_time and day_hours.close_time:
            current_time = now.time()
            return day_hours.open_time <= current_time <= day_hours.close_time
        
        return True


class SpecialHours(BaseModel):
    """Special hours for holidays or events."""
    date: str  # YYYY-MM-DD
    is_closed: bool = False
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    reason: Optional[str] = None


# ====================
# Address & Location
# ====================

class Address(BaseModel):
    """Business address."""
    street1: str = Field(..., min_length=1, max_length=200)
    street2: Optional[str] = Field(None, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=50)
    postal_code: str = Field(..., min_length=5, max_length=20)
    country: str = Field(default="US", max_length=2)
    
    def formatted(self) -> str:
        """Return formatted address string."""
        parts = [self.street1]
        if self.street2:
            parts.append(self.street2)
        parts.append(f"{self.city}, {self.state} {self.postal_code}")
        return ", ".join(parts)


class GeoCoordinates(BaseModel):
    """Geographic coordinates."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


# ====================
# Contact Information
# ====================

class ContactInfo(BaseModel):
    """Business contact information."""
    primary_phone: Optional[str] = Field(None, pattern=r"^\+?[\d\s\-\(\)]+$")
    secondary_phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    website: Optional[HttpUrl] = None
    
    # Social media
    facebook_url: Optional[HttpUrl] = None
    instagram_url: Optional[HttpUrl] = None
    twitter_url: Optional[HttpUrl] = None
    linkedin_url: Optional[HttpUrl] = None
    youtube_url: Optional[HttpUrl] = None
    tiktok_url: Optional[HttpUrl] = None


# ====================
# Business Attributes
# ====================

class ServiceArea(BaseModel):
    """Service area definition."""
    type: Literal["radius", "zip_codes", "cities", "custom"] = "radius"
    radius_miles: Optional[float] = None
    zip_codes: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    custom_description: Optional[str] = None


class PaymentMethod(BaseModel):
    """Accepted payment methods."""
    cash: bool = True
    credit_cards: bool = True
    debit_cards: bool = True
    apple_pay: bool = False
    google_pay: bool = False
    samsung_pay: bool = False
    paypal: bool = False
    venmo: bool = False
    check: bool = False
    invoice: bool = False
    financing: bool = False


class Amenities(BaseModel):
    """Business amenities."""
    # Accessibility
    wheelchair_accessible: bool = False
    wheelchair_accessible_restroom: bool = False
    wheelchair_accessible_seating: bool = False
    
    # Parking
    free_parking: bool = False
    paid_parking: bool = False
    street_parking: bool = False
    valet_parking: bool = False
    
    # WiFi
    free_wifi: bool = False
    
    # Dining (for restaurants)
    outdoor_seating: bool = False
    reservations: bool = False
    takeout: bool = False
    delivery: bool = False
    dine_in: bool = False
    catering: bool = False
    
    # Other
    kids_friendly: bool = False
    pet_friendly: bool = False
    lgbtq_friendly: bool = False


# ====================
# Entity Vault (Main)
# ====================

class EntityVaultBase(BaseModel):
    """Base entity vault data."""
    # Basic Info
    business_name: str = Field(..., min_length=1, max_length=200)
    legal_name: Optional[str] = Field(None, max_length=200)
    dba_names: list[str] = Field(default_factory=list)  # Doing Business As
    
    # Description
    short_description: Optional[str] = Field(None, max_length=250)
    long_description: Optional[str] = Field(None, max_length=5000)
    
    # Categories
    primary_category: Optional[str] = None  # GBP category
    secondary_categories: list[str] = Field(default_factory=list)
    
    # Year established
    year_established: Optional[int] = Field(None, ge=1800, le=2100)


class EntityVaultCreate(EntityVaultBase):
    """Create entity vault."""
    location_id: UUID
    
    address: Address
    coordinates: Optional[GeoCoordinates] = None
    contact: ContactInfo = Field(default_factory=ContactInfo)
    hours: BusinessHours = Field(default_factory=BusinessHours)
    special_hours: list[SpecialHours] = Field(default_factory=list)
    
    service_area: Optional[ServiceArea] = None
    payment_methods: PaymentMethod = Field(default_factory=PaymentMethod)
    amenities: Amenities = Field(default_factory=Amenities)
    
    # Media
    logo_url: Optional[HttpUrl] = None
    cover_photo_url: Optional[HttpUrl] = None
    photo_urls: list[str] = Field(default_factory=list)
    
    # Custom attributes
    custom_attributes: dict = Field(default_factory=dict)


class EntityVaultUpdate(BaseModel):
    """Update entity vault."""
    business_name: Optional[str] = None
    legal_name: Optional[str] = None
    dba_names: Optional[list[str]] = None
    
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    
    primary_category: Optional[str] = None
    secondary_categories: Optional[list[str]] = None
    
    year_established: Optional[int] = None
    
    address: Optional[Address] = None
    coordinates: Optional[GeoCoordinates] = None
    contact: Optional[ContactInfo] = None
    hours: Optional[BusinessHours] = None
    special_hours: Optional[list[SpecialHours]] = None
    
    service_area: Optional[ServiceArea] = None
    payment_methods: Optional[PaymentMethod] = None
    amenities: Optional[Amenities] = None
    
    logo_url: Optional[HttpUrl] = None
    cover_photo_url: Optional[HttpUrl] = None
    photo_urls: Optional[list[str]] = None
    
    custom_attributes: Optional[dict] = None


class EntityVaultResponse(EntityVaultBase):
    """Entity vault response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    
    address: Address
    coordinates: Optional[GeoCoordinates]
    contact: ContactInfo
    hours: BusinessHours
    special_hours: list[SpecialHours]
    
    service_area: Optional[ServiceArea]
    payment_methods: PaymentMethod
    amenities: Amenities
    
    logo_url: Optional[str]
    cover_photo_url: Optional[str]
    photo_urls: list[str]
    
    custom_attributes: dict
    
    # Sync status
    gbp_sync_status: Optional[str] = None  # synced, pending, error
    gbp_last_synced_at: Optional[datetime] = None
    
    created_at: datetime
    updated_at: datetime


# ====================
# NAP Consistency
# ====================

class NAPEntry(BaseModel):
    """Name, Address, Phone entry for consistency check."""
    source: str  # google, facebook, yelp, yellowpages, etc
    source_url: Optional[str] = None
    
    name: str
    address: str
    phone: Optional[str]
    
    is_consistent: bool = True
    inconsistencies: list[str] = Field(default_factory=list)
    
    last_checked_at: datetime
    last_updated_at: Optional[datetime] = None


class NAPConsistencyReport(BaseModel):
    """NAP consistency report."""
    location_id: UUID
    
    # Master data
    master_name: str
    master_address: str
    master_phone: Optional[str]
    
    # Entries from various sources
    entries: list[NAPEntry]
    
    # Summary
    total_sources: int
    consistent_count: int
    inconsistent_count: int
    consistency_score: float  # 0-100
    
    # Issues
    issues: list[dict]  # [{"source": "yelp", "field": "phone", "expected": "...", "found": "..."}]
    
    generated_at: datetime


# ====================
# Sync Operations
# ====================

class SyncRequest(BaseModel):
    """Request to sync entity vault to platforms."""
    platforms: list[str] = Field(default_factory=lambda: ["google"])  # google, facebook, yelp
    fields: Optional[list[str]] = None  # Specific fields to sync, or None for all
    force: bool = False  # Force sync even if no changes


class SyncResult(BaseModel):
    """Sync operation result."""
    platform: str
    success: bool
    fields_synced: list[str]
    error: Optional[str] = None
    synced_at: datetime


class SyncResponse(BaseModel):
    """Sync operation response."""
    location_id: UUID
    results: list[SyncResult]
    all_success: bool
