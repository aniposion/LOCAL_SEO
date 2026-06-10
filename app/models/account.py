"""Account model for user authentication."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.subscription import Subscription
    from app.models.oauth import OAuthToken


class AccountRole(str, enum.Enum):
    """User roles."""

    OWNER = "owner"
    MANAGER = "manager"
    AGENCY = "agency"
    ADMIN = "admin"


class Account(BaseModel):
    """User account model."""

    __tablename__ = "accounts"

    # Basic auth
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Profile
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    
    # Notification preferences
    notification_channel: Mapped[str] = mapped_column(
        String(20), default="email", nullable=False
    )  # "email", "sms", or "both"
    
    # OAuth
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Role and status
    role: Mapped[AccountRole] = mapped_column(
        Enum(AccountRole), default=AccountRole.OWNER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Email verification
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_token_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Password reset
    password_reset_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_reset_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Terms and privacy
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    privacy_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Last activity
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Agency settings (JSON) - team members, white label, etc.
    settings: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )

    # Relationships
    locations: Mapped[list["Location"]] = relationship(
        "Location", back_populates="account", cascade="all, delete-orphan"
    )
    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription", back_populates="account", uselist=False, cascade="all, delete-orphan"
    )
    onboarding_audit: Mapped["OnboardingAudit | None"] = relationship(
        "OnboardingAudit", back_populates="account", uselist=False, cascade="all, delete-orphan"
    )
    onboarding_progress: Mapped["OnboardingProgress | None"] = relationship(
        "OnboardingProgress", back_populates="account", uselist=False, cascade="all, delete-orphan"
    )
    
    # P4: OAuth tokens
    oauth_tokens: Mapped[list["OAuthToken"]] = relationship(
        "OAuthToken", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Account {self.email}>"
    
    @property
    def display_name(self) -> str:
        """Get display name."""
        return self.full_name or self.email.split("@")[0]
