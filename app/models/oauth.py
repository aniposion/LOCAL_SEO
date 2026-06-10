"""P4: Token Ops Console models."""

import enum
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now_aware
from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.location import Location


class OAuthProvider(str, enum.Enum):
    """Supported OAuth providers."""
    GOOGLE = "google"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


class OAuthStatus(str, enum.Enum):
    """OAuth token status."""
    HEALTHY = "healthy"
    NEEDS_REAUTH = "needs_reauth"
    DEGRADED = "degraded"
    REVOKED = "revoked"


class OAuthEventType(str, enum.Enum):
    """OAuth event types for audit log."""
    CREATED = "created"
    REFRESHED = "refreshed"
    REFRESH_FAILED = "refresh_failed"
    REVOKED = "revoked"
    REAUTHORIZED = "reauthorized"
    USED = "used"
    SCOPES_CHANGED = "scopes_changed"


class OAuthToken(BaseModel):
    """OAuth token management with health tracking.
    
    Tokens are stored as references to Secret Manager paths,
    not as plaintext in the database.
    """
    
    __tablename__ = "oauth_tokens"
    __table_args__ = (
        UniqueConstraint('account_id', 'location_id', 'provider', name='uq_oauth_token'),
    )
    
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    location_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    
    provider: Mapped[OAuthProvider] = mapped_column(
        Enum(
            OAuthProvider,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False
    )
    
    # Tokens stored as Secret Manager references (not plaintext!)
    access_token_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    refresh_token_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Token metadata
    scopes: Mapped[list | None] = mapped_column(ARRAY(String(100)), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Health status
    status: Mapped[OAuthStatus] = mapped_column(
        Enum(
            OAuthStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=OAuthStatus.HEALTHY,
        nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Refresh tracking
    refresh_failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="oauth_tokens")
    location: Mapped["Location"] = relationship("Location", back_populates="oauth_tokens")
    events: Mapped[list["OAuthEvent"]] = relationship(
        "OAuthEvent", back_populates="token", cascade="all, delete-orphan",
        order_by="OAuthEvent.created_at.desc()"
    )
    
    @property
    def is_healthy(self) -> bool:
        """Check if token is in healthy state."""
        return self.status == OAuthStatus.HEALTHY
    
    @property
    def needs_refresh(self) -> bool:
        """Check if token needs refresh (expires within 1 hour)."""
        if self.status != OAuthStatus.HEALTHY:
            return False
        return utc_now_aware() + timedelta(hours=1) >= self.expires_at


class OAuthEvent(BaseModel):
    """OAuth event audit log."""
    
    __tablename__ = "oauth_events"
    
    token_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("oauth_tokens.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    event_type: Mapped[OAuthEventType] = mapped_column(
        Enum(
            OAuthEventType,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False
    )
    event_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # IP/User Agent for security
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    token: Mapped["OAuthToken"] = relationship("OAuthToken", back_populates="events")
