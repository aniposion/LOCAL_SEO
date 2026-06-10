"""P5: Entity Truth Vault & Approval Analysis models."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.post import Post


class EntityVault(BaseModel):
    """Business truth data for consistent content generation.
    
    Contains all verified facts about a business:
    - Services & pricing
    - Brand voice & tone
    - Forbidden/required phrases
    - FAQ
    - SEO keywords
    - NAP (Name, Address, Phone)
    """
    
    __tablename__ = "entity_vaults"
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Business facts
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Services & Pricing
    # Format: [{"name": "...", "description": "...", "price_range": "$50-100", "keywords": [...]}]
    services: Mapped[list] = mapped_column(JSONB, default=[], nullable=False)
    price_range: Mapped[str | None] = mapped_column(String(50), nullable=True)  # $, $$, $$$, $$$$
    
    # Brand voice
    tone: Mapped[str] = mapped_column(
        String(50), default="professional_friendly", nullable=False
    )  # professional, casual, luxurious, expert, friendly
    
    # Content rules
    forbidden_phrases: Mapped[list] = mapped_column(
        ARRAY(String(100)), default=[], nullable=False
    )  # ["최고", "best", "1등", "guaranteed"]
    required_phrases: Mapped[list] = mapped_column(
        ARRAY(String(100)), default=[], nullable=False
    )  # ["예약 환영", "free consultation"]
    
    # NAP (Name, Address, Phone)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    website: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # P5 Extended: Full address JSON
    full_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Format: {"street1": "...", "street2": "...", "city": "...", "state": "...", "postal_code": "...", "country": "US"}
    
    # P5: Geographic coordinates
    coordinates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Format: {"latitude": 40.7128, "longitude": -74.0060}
    
    # P5: Contact information
    contact_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Format: {"primary_phone": "...", "email": "...", "facebook_url": "...", "instagram_url": "..."}
    
    # P5: Business hours
    business_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Format: {"monday": {"is_open": true, "open_time": "09:00", "close_time": "18:00"}, ...}
    special_hours: Mapped[list | None] = mapped_column(JSONB, default=[], nullable=True)
    # Format: [{"date": "2024-12-25", "is_closed": true, "reason": "Christmas"}]
    hours_timezone: Mapped[str | None] = mapped_column(String(50), default="America/New_York")
    
    # P5: Business attributes
    payment_methods: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Format: {"cash": true, "credit_cards": true, "apple_pay": false, ...}
    
    amenities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Format: {"wheelchair_accessible": true, "free_wifi": true, ...}
    
    service_area: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Format: {"type": "radius", "radius_miles": 25, "zip_codes": [...]}
    
    # P5: Categories
    primary_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    secondary_categories: Mapped[list | None] = mapped_column(JSONB, default=[], nullable=True)
    
    # P5: Media
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    photo_urls: Mapped[list | None] = mapped_column(JSONB, default=[], nullable=True)
    
    # P5: Sync status
    gbp_sync_status: Mapped[str | None] = mapped_column(String(20), default="pending")
    gbp_last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # P5: Custom attributes
    custom_attributes: Mapped[dict | None] = mapped_column(JSONB, default={}, nullable=True)
    
    # FAQ for content generation
    # Format: [{"question": "...", "answer": "..."}]
    faq: Mapped[list] = mapped_column(JSONB, default=[], nullable=False)
    
    # SEO Keywords
    primary_keywords: Mapped[list] = mapped_column(
        ARRAY(String(100)), default=[], nullable=False
    )  # Main service keywords
    secondary_keywords: Mapped[list] = mapped_column(
        ARRAY(String(100)), default=[], nullable=False
    )  # Supporting keywords
    local_keywords: Mapped[list] = mapped_column(
        ARRAY(String(100)), default=[], nullable=False
    )  # "near me", "{city}" variants
    
    # Compliance notes
    compliance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="entity_vault")


class ApprovalAnalysis(BaseModel):
    """AI-generated analysis for post approval.
    
    Analyzes content for:
    - Policy/risk flags
    - Keyword coverage
    - Brand tone consistency
    - Auto-fix suggestions
    """
    
    __tablename__ = "approval_analyses"
    
    post_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Risk Analysis (0 = safe, 100 = high risk)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Format: [{"type": "exaggeration", "message": "...", "severity": "high", "suggestion": "..."}]
    risk_flags: Mapped[list] = mapped_column(JSONB, default=[], nullable=False)
    
    # Keyword Coverage (0-100)
    keyword_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    keywords_found: Mapped[list] = mapped_column(
        ARRAY(String(100)), default=[], nullable=False
    )
    keywords_missing: Mapped[list] = mapped_column(
        ARRAY(String(100)), default=[], nullable=False
    )
    
    # Brand Consistency (0-100)
    tone_match_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    forbidden_found: Mapped[list] = mapped_column(
        ARRAY(String(100)), default=[], nullable=False
    )
    
    # Auto-fix Suggestions
    # Format: [{"original": "...", "suggested": "...", "reason": "..."}]
    suggestions: Mapped[list] = mapped_column(JSONB, default=[], nullable=False)
    
    # Vault version used (for cache invalidation)
    vault_version_used: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="approval_analysis")
    
    @property
    def is_safe(self) -> bool:
        """Check if content is safe to publish."""
        return self.risk_score < 30 and len(self.forbidden_found) == 0
    
    @property
    def needs_review(self) -> bool:
        """Check if content needs manual review."""
        return self.risk_score >= 30 or len(self.risk_flags) > 0
