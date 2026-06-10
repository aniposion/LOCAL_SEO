"""Authentication schemas."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    """User signup request with full profile."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    timezone: str = Field(default="UTC", max_length=50)
    language: str = Field(default="en", max_length=10)
    accept_terms: bool = Field(description="User must accept terms of service")
    accept_privacy: bool = Field(description="User must accept privacy policy")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v

    @field_validator("accept_terms", "accept_privacy")
    @classmethod
    def must_accept(cls, v: bool) -> bool:
        """Ensure terms and privacy are accepted."""
        if not v:
            raise ValueError("You must accept the terms and privacy policy")
        return v


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiration in seconds")


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str | None = None


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class PasswordResetRequest(BaseModel):
    """Password reset request (forgot password)."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation with token."""

    token: str
    new_password: str = Field(min_length=8, max_length=128)


class EmailVerificationRequest(BaseModel):
    """Email verification request."""

    token: str


class ResendVerificationRequest(BaseModel):
    """Resend verification email request."""

    email: EmailStr


class UserProfileResponse(BaseModel):
    """User profile response."""

    id: UUID
    email: str
    full_name: str | None
    company_name: str | None
    phone: str | None
    timezone: str
    language: str
    role: str
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    """User profile update request."""

    full_name: str | None = Field(None, min_length=2, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    timezone: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=10)
