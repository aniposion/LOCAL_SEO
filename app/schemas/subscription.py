"""Subscription and billing schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.subscription import FREE_PREVIEW_PLAN, PlanType, SubscriptionStatus


class PlanInfo(BaseModel):
    """Plan information."""

    id: str
    name: str
    price_monthly: float
    price_yearly: float
    features: list[str]
    limits: dict
    setup_fee: float | None = None
    sales_motion: str | None = None
    publicly_listed: bool = True
    managed_service: bool = False
    minimum_term_months: int | None = None


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
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|yearly)$")
    current_price: float | None = None
    trial_end: datetime | None = None
    active_addons: list[str] = Field(default_factory=list)
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

    plan: str
    locations_used: int
    locations_limit: int
    posts_this_month: int
    posts_limit: int
    api_calls_today: int
    api_calls_limit: int


class DunningStatusResponse(BaseModel):
    """Dunning status for billing UI."""

    in_dunning: bool
    state: str
    days_remaining: int | None = None
    message: str | None = None
    portal_url: str | None = None
    portal_available: bool | None = None
    portal_source: str | None = None
    portal_error: str | None = None


class PlanLimits(BaseModel):
    """Plan limits response."""

    plan_type: PlanType
    locations: int
    posts_per_month: int
    api_calls_per_day: int
    features: list[str]


# ============================================
# NEW BILLING SCHEMAS
# ============================================

class TrialStartRequest(BaseModel):
    """Start trial request."""
    
    plan_type: PlanType = FREE_PREVIEW_PLAN


class TrialStartResponse(BaseModel):
    """Trial start response."""
    
    status: str
    plan_type: PlanType
    trial_end: datetime
    message: str


class SubscriptionPreviewRequest(BaseModel):
    """Subscription change preview request."""
    
    new_plan_type: PlanType
    add_ons: list[str] = []


class SubscriptionPreviewResponse(BaseModel):
    """Subscription change preview response."""
    
    current_plan: dict
    new_plan: dict
    proration: dict
    effective: str
    preview_line_items: list[dict]


class SubscriptionChangeRequest(BaseModel):
    """Subscription change request."""
    
    new_plan_type: PlanType
    add_ons: list[str] = []
    prorate: bool = True


class CancelSubscriptionRequest(BaseModel):
    """Cancel subscription request."""
    
    cancel_at_period_end: bool = True
    reason: str | None = None
    feedback: str | None = None


class CancelSubscriptionResponse(BaseModel):
    """Cancel subscription response."""
    
    status: str
    cancel_at_period_end: bool
    current_period_end: str | None
    message: str


class ResumeSubscriptionResponse(BaseModel):
    """Resume subscription response."""
    
    status: str
    cancel_at_period_end: bool
    message: str


class InvoiceResponse(BaseModel):
    """Invoice response."""
    
    id: str
    number: str | None
    status: str
    amount: int
    amount_paid: int
    amount_due: int
    currency: str
    created_at: str
    paid_at: str | None
    pdf_url: str | None
    hosted_url: str | None
    line_items: list[dict]


class InvoiceListResponse(BaseModel):
    """Invoice list response."""
    
    invoices: list[InvoiceResponse]
    total_count: int
    has_more: bool


class PaymentMethodResponse(BaseModel):
    """Payment method response."""
    
    id: str
    type: str
    card: dict
    is_default: bool
    created_at: str


class AddPaymentMethodRequest(BaseModel):
    """Add payment method request."""
    
    payment_method_id: str
    set_as_default: bool = True


class BillingInfoRequest(BaseModel):
    """Billing info update request."""
    
    company_name: str | None = None
    tax_id: str | None = None
    tax_id_type: str | None = None
    address: dict | None = None
    billing_email: str | None = None


class BillingInfoResponse(BaseModel):
    """Billing info response."""
    
    company_name: str | None
    tax_id: str | None
    tax_id_type: str | None
    address: dict | None
    billing_email: str | None


class BillingAuditEntry(BaseModel):
    """Account-scoped billing audit entry."""

    id: UUID
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    old_value: dict | None = None
    new_value: dict | None = None
    description: str | None = None
    extra_data: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BillingAuditListResponse(BaseModel):
    """Recent billing audit entries for the current account."""

    items: list[BillingAuditEntry]
    total: int
    source: str = "billing_audit_log"


class BillingWebhookEventEntry(BaseModel):
    """Recent Stripe webhook events associated with the current account."""

    id: int
    event_id: str
    event_type: str
    account_match_source: str
    related_customer: str | None = None
    related_subscription: str | None = None
    created_at: datetime | None = None
    processed_at: datetime | None = None


class BillingWebhookEventListResponse(BaseModel):
    """Recent Stripe webhook events associated with the current account."""

    items: list[BillingWebhookEventEntry]
    total: int
    source: str = "stripe_events"
