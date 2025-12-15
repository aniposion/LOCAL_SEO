"""Billing schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SubscribeRequest(BaseModel):
    """Subscription request."""

    plan_id: str
    success_url: str
    cancel_url: str


class SubscribeResponse(BaseModel):
    """Subscription response with Stripe checkout URL."""

    checkout_url: str
    session_id: str


class SubscriptionStatus(BaseModel):
    """Subscription status response."""

    account_id: UUID
    plan_id: str | None = None
    status: str  # active, canceled, past_due, etc.
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class WebhookEvent(BaseModel):
    """Stripe webhook event."""

    type: str
    data: dict
