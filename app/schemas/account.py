"""Account schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models.account import AccountRole


class AccountBase(BaseModel):
    """Base account schema."""

    email: EmailStr


class AccountCreate(AccountBase):
    """Account creation schema."""

    password: str


class AccountUpdate(BaseModel):
    """Account update schema."""

    email: EmailStr | None = None
    role: AccountRole | None = None
    is_active: bool | None = None


class AccountResponse(AccountBase):
    """Account response schema."""

    id: UUID
    role: AccountRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
