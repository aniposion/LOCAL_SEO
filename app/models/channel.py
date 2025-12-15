"""Channel model for platform connections."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


class ChannelType(str, enum.Enum):
    """Supported channel types."""

    GBP = "GBP"  # Google Business Profile
    INSTAGRAM = "INSTAGRAM"
    WEBSITE = "WEBSITE"
    FACEBOOK = "FACEBOOK"
    TWITTER = "TWITTER"


class ChannelStatus(str, enum.Enum):
    """Channel connection status."""

    PENDING = "pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    EXPIRED = "expired"


class Channel(BaseModel):
    """Channel credentials and settings model.
    
    Credentials are stored encrypted using Fernet symmetric encryption.
    """

    __tablename__ = "channels"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), index=True
    )

    type: Mapped[ChannelType] = mapped_column(Enum(ChannelType), nullable=False)
    status: Mapped[ChannelStatus] = mapped_column(
        Enum(ChannelStatus), default=ChannelStatus.PENDING, nullable=False
    )
    
    # Encrypted credentials (stored as encrypted string, not plain JSON)
    credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Platform-specific IDs (not sensitive, stored plain)
    platform_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Token expiration tracking
    access_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Permissions/scopes granted
    scopes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="channels")

    def __repr__(self) -> str:
        return f"<Channel {self.type.value} for location {self.location_id}>"

    def set_credentials(self, credentials: dict[str, Any]) -> None:
        """Encrypt and store credentials."""
        from app.core.encryption import encrypt_credentials
        self.credentials_encrypted = encrypt_credentials(credentials)

    def get_credentials(self) -> dict[str, Any]:
        """Decrypt and return credentials."""
        if not self.credentials_encrypted:
            return {}
        from app.core.encryption import decrypt_credentials
        return decrypt_credentials(self.credentials_encrypted)

    @property
    def is_token_expired(self) -> bool:
        """Check if access token is expired."""
        if not self.access_token_expires_at:
            return False
        return datetime.now(self.access_token_expires_at.tzinfo) >= self.access_token_expires_at

    @property
    def needs_refresh(self) -> bool:
        """Check if token needs refresh (expires within 5 minutes)."""
        if not self.access_token_expires_at:
            return False
        from datetime import timedelta, timezone
        buffer = timedelta(minutes=5)
        return datetime.now(timezone.utc) >= (self.access_token_expires_at - buffer)
