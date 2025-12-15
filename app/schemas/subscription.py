"""Subscription and billing schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.subscription import PlanType, SubscriptionStatus


class PlanInfo(BaseModel):
    """Plan information."""

    id: str
    name: str
    price_monthly: float
    price_yearly: float
    features: list[str]
    limits: dict


class SubscriptionCreate(BaseModel):
    """Create subscription request."""

    plan_type: PlanType
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|yearly)$")


class SubscriptionResponse(BaseModel):
    """Subscription response."""

    id: UUID
    account_id: UUID
    plan_type: PlanType
    status: SubscriptionStatus
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    locations_limit: int
    posts_per_month: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckoutSessionRequest(BaseModel):
    """Stripe checkout session request."""

    plan_type: PlanType
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|yearly)$")
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    """Stripe checkout session response."""

    checkout_url: str
    session_id: str


class PortalSessionRequest(BaseModel):
    """Stripe customer portal request."""

    return_url: str


class PortalSessionResponse(BaseModel):
    """Stripe customer portal response."""

    portal_url: str


class PaymentHistoryResponse(BaseModel):
    """Payment history item."""

    id: UUID
    amount: float
    currency: str
    status: str
    description: str | None
    invoice_url: str | None
    receipt_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageStats(BaseModel):
    """Current usage statistics."""

    locations_used: int
    locations_limit: int
    posts_this_month: int
    posts_limit: int
    api_calls_today: int
    api_calls_limit: int


class PlanLimits(BaseModel):
    """Plan limits response."""

    plan_type: PlanType
    locations: int
    posts_per_month: int
    api_calls_per_day: int
    features: list[str]
