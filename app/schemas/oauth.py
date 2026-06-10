"""P4: OAuth Token Management schemas."""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ====================
# OAuth Token Schemas
# ====================

class OAuthTokenResponse(BaseModel):
    """OAuth token info (without sensitive data)."""
    id: UUID
    account_id: UUID
    provider: str  # google, facebook, instagram
    provider_account_id: Optional[str]
    email: Optional[str]
    status: str  # active, expired, revoked, refresh_failed
    scopes: list[str]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    last_refresh_at: Optional[datetime]
    refresh_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OAuthTokenList(BaseModel):
    """List of OAuth tokens."""
    items: list[OAuthTokenResponse]
    total: int
    expiring_soon: int  # Within 7 days
    needs_attention: int  # Expired or failed


class OAuthConnectRequest(BaseModel):
    """Request to initiate OAuth connection."""
    provider: Literal['google', 'facebook', 'instagram']
    redirect_uri: str
    scopes: Optional[list[str]] = None


class OAuthConnectResponse(BaseModel):
    """OAuth connection initiation response."""
    auth_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """OAuth callback data."""
    code: str
    state: str
    provider: str


class OAuthCallbackResponse(BaseModel):
    """OAuth callback result."""
    success: bool
    provider: str
    email: Optional[str]
    error: Optional[str] = None


class OAuthRefreshResult(BaseModel):
    """Token refresh result."""
    token_id: UUID
    provider: str
    success: bool
    new_expiry: Optional[datetime] = None
    error: Optional[str] = None


class OAuthDisconnectResponse(BaseModel):
    """Disconnect result."""
    success: bool
    provider: str
    message: str


# ====================
# Google Business Profile
# ====================

class GBPLocation(BaseModel):
    """Google Business Profile location."""
    name: str  # accounts/{account_id}/locations/{location_id}
    title: str
    store_code: Optional[str]
    address: dict
    phone: Optional[str]
    website: Optional[str]
    categories: list[str]
    is_verified: bool


class GBPLocationList(BaseModel):
    """List of GBP locations."""
    locations: list[GBPLocation]
    total: int


class GBPReview(BaseModel):
    """Google review."""
    review_id: str
    reviewer_name: str
    reviewer_photo_url: Optional[str]
    star_rating: int
    comment: Optional[str]
    create_time: datetime
    update_time: Optional[datetime]
    reply: Optional[dict]  # {"comment": str, "updateTime": datetime}


class GBPReviewList(BaseModel):
    """List of reviews."""
    reviews: list[GBPReview]
    total: int
    average_rating: float
    next_page_token: Optional[str] = None


class GBPReviewReplyRequest(BaseModel):
    """Reply to a review."""
    comment: str = Field(..., min_length=1, max_length=4096)


class GBPInsights(BaseModel):
    """GBP performance insights."""
    period_start: datetime
    period_end: datetime
    
    # Actions
    calls: int
    directions: int
    website_clicks: int
    
    # Views
    search_views: int
    maps_views: int
    
    # Queries
    direct_queries: int  # Searched by name
    discovery_queries: int  # Searched by category
    branded_queries: int
    
    # Photos
    photo_views_merchant: int
    photo_views_customer: int


class GBPPostCreate(BaseModel):
    """Create a GBP post."""
    summary: str = Field(..., min_length=1, max_length=1500)
    call_to_action: Optional[dict] = None  # {"actionType": "CALL", "url": "..."}
    media: Optional[list[dict]] = None  # [{"mediaFormat": "PHOTO", "sourceUrl": "..."}]
    event: Optional[dict] = None  # {"title": "...", "schedule": {...}}
    offer: Optional[dict] = None  # {"couponCode": "...", "redeemOnlineUrl": "..."}


class GBPPostResponse(BaseModel):
    """GBP post response."""
    name: str
    summary: str
    state: str  # LIVE, REJECTED, etc
    create_time: datetime
    update_time: Optional[datetime]
    search_url: Optional[str]


# ====================
# Connection Status
# ====================

class ConnectionStatus(BaseModel):
    """Overall connection status for account."""
    google: Optional[OAuthTokenResponse] = None
    facebook: Optional[OAuthTokenResponse] = None
    instagram: Optional[OAuthTokenResponse] = None
    
    google_locations: int = 0
    google_connected: bool = False
    facebook_connected: bool = False
    instagram_connected: bool = False
    
    needs_attention: list[str] = []  # Providers with issues
