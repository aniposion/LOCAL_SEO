"""Billing models for production-grade Stripe integration."""

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, Index
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel, get_json_type

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.subscription import Subscription

JSON = get_json_type()


def utcnow_aware() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


# ============================================
# ENUMS
# ============================================

class InvoiceStatus(str, enum.Enum):
    """Invoice status."""
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class PaymentStatus(str, enum.Enum):
    """Payment status."""
    SUCCEEDED = "succeeded"
    PENDING = "pending"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class RefundStatus(str, enum.Enum):
    """Refund status."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class RefundReason(str, enum.Enum):
    """Refund reason."""
    DUPLICATE = "duplicate"
    FRAUDULENT = "fraudulent"
    REQUESTED_BY_CUSTOMER = "requested_by_customer"
    EXPIRED_UNCAPTURED_CHARGE = "expired_uncaptured_charge"


class DisputeStatus(str, enum.Enum):
    """Dispute status."""
    WARNING_NEEDS_RESPONSE = "warning_needs_response"
    WARNING_UNDER_REVIEW = "warning_under_review"
    WARNING_CLOSED = "warning_closed"
    NEEDS_RESPONSE = "needs_response"
    UNDER_REVIEW = "under_review"
    WON = "won"
    LOST = "lost"


class DisputeReason(str, enum.Enum):
    """Dispute reason."""
    BANK_CANNOT_PROCESS = "bank_cannot_process"
    CHECK_RETURNED = "check_returned"
    CREDIT_NOT_PROCESSED = "credit_not_processed"
    CUSTOMER_INITIATED = "customer_initiated"
    DEBIT_NOT_AUTHORIZED = "debit_not_authorized"
    DUPLICATE = "duplicate"
    FRAUDULENT = "fraudulent"
    GENERAL = "general"
    INCORRECT_ACCOUNT_DETAILS = "incorrect_account_details"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    PRODUCT_NOT_RECEIVED = "product_not_received"
    PRODUCT_UNACCEPTABLE = "product_unacceptable"
    SUBSCRIPTION_CANCELED = "subscription_canceled"
    UNRECOGNIZED = "unrecognized"


class WebhookEventStatus(str, enum.Enum):
    """Webhook event processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DunningStatus(str, enum.Enum):
    """Dunning (payment failure handling) status."""
    NONE = "none"
    RETRYING = "retrying"
    GRACE_PERIOD = "grace_period"
    RESTRICTED = "restricted"
    SUSPENDED = "suspended"


class BillingAuditAction(str, enum.Enum):
    """Billing audit log actions."""
    SUBSCRIPTION_CREATED = "subscription_created"
    SUBSCRIPTION_UPDATED = "subscription_updated"
    SUBSCRIPTION_CANCELED = "subscription_canceled"
    SUBSCRIPTION_RESUMED = "subscription_resumed"
    PLAN_CHANGED = "plan_changed"
    ADDON_ADDED = "addon_added"
    ADDON_REMOVED = "addon_removed"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    REFUND_CREATED = "refund_created"
    DISPUTE_CREATED = "dispute_created"
    DISPUTE_UPDATED = "dispute_updated"
    PAYMENT_METHOD_ADDED = "payment_method_added"
    PAYMENT_METHOD_REMOVED = "payment_method_removed"
    PAYMENT_METHOD_DEFAULT_CHANGED = "payment_method_default_changed"
    BILLING_INFO_UPDATED = "billing_info_updated"
    INVOICE_SENT = "invoice_sent"


# ============================================
# SUBSCRIPTION ITEMS (ADD-ONS)
# ============================================

class SubscriptionItem(BaseModel):
    """Subscription line items for tracking add-ons and plan components."""

    __tablename__ = "subscription_items"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    
    # Stripe IDs
    stripe_subscription_item_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    stripe_price_id: Mapped[str] = mapped_column(String(255), nullable=False)
    stripe_product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Item details
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_amount: Mapped[int] = mapped_column(Integer, default=0)  # in cents
    
    # Flags
    is_addon: Mapped[bool] = mapped_column(Boolean, default=False)
    is_base_plan: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("idx_subscription_items_subscription", "subscription_id"),
        Index("idx_subscription_items_stripe", "stripe_subscription_item_id"),
    )


# ============================================
# INVOICES
# ============================================

class Invoice(BaseModel):
    """Invoice model with full Stripe invoice data."""

    __tablename__ = "invoices"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    
    # Stripe IDs
    stripe_invoice_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Invoice number (e.g., 2025-000123)
    number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Status
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus), default=InvoiceStatus.DRAFT, nullable=False
    )
    
    # Amounts (in cents)
    subtotal: Mapped[int] = mapped_column(Integer, default=0)
    tax: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_paid: Mapped[int] = mapped_column(Integer, default=0)
    amount_due: Mapped[int] = mapped_column(Integer, default=0)
    amount_remaining: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    
    # URLs from Stripe
    hosted_invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Billing period
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Line items (cached for display)
    line_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    
    # Customer billing info snapshot
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_address: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    customer_tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Retry tracking
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_payment_attempt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_invoices_account", "account_id"),
        Index("idx_invoices_stripe", "stripe_invoice_id"),
        Index("idx_invoices_status", "status"),
        Index("idx_invoices_created", "created_at"),
    )


# ============================================
# PAYMENTS
# ============================================

class Payment(BaseModel):
    """Payment model for tracking all payments."""

    __tablename__ = "payments"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Stripe IDs
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    stripe_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Amount
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # in cents
    amount_refunded: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    
    # Status
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False
    )
    
    # Payment method info (cached)
    payment_method_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_method_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    payment_method_brand: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_method_exp_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_method_exp_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Failure info
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Description
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Receipt URL
    receipt_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_payments_account", "account_id"),
        Index("idx_payments_invoice", "invoice_id"),
        Index("idx_payments_status", "status"),
        Index("idx_payments_created", "created_at"),
    )


# ============================================
# REFUNDS
# ============================================

class Refund(BaseModel):
    """Refund model for tracking all refunds."""

    __tablename__ = "refunds"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Stripe IDs
    stripe_refund_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    stripe_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Amount
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # in cents
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    
    # Status & reason
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus), default=RefundStatus.PENDING, nullable=False
    )
    reason: Mapped[RefundReason | None] = mapped_column(
        Enum(RefundReason), nullable=True
    )
    
    # Internal tracking
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Failure info
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_refunds_account", "account_id"),
        Index("idx_refunds_payment", "payment_id"),
        Index("idx_refunds_stripe", "stripe_refund_id"),
    )


# ============================================
# DISPUTES (CHARGEBACKS)
# ============================================

class Dispute(BaseModel):
    """Dispute model for tracking chargebacks."""

    __tablename__ = "disputes"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Stripe IDs
    stripe_dispute_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    stripe_charge_id: Mapped[str] = mapped_column(String(255), nullable=False)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Amount
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # in cents
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    
    # Status & reason
    status: Mapped[DisputeStatus] = mapped_column(
        Enum(DisputeStatus), nullable=False
    )
    reason: Mapped[DisputeReason | None] = mapped_column(
        Enum(DisputeReason), nullable=True
    )
    
    # Evidence snapshot for defense
    evidence_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Structure: {
    #   "customer_email": str,
    #   "signup_date": str,
    #   "plan_at_dispute": str,
    #   "total_payments": int,
    #   "last_login": str,
    #   "usage_stats": dict,
    #   "ip_addresses": list[str],
    #   "service_logs": list[dict],
    # }
    
    # Evidence due date
    evidence_due_by: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Resolution
    is_charge_refundable: Mapped[bool] = mapped_column(Boolean, default=False)
    network_reason_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Internal notes
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_disputes_account", "account_id"),
        Index("idx_disputes_stripe", "stripe_dispute_id"),
        Index("idx_disputes_status", "status"),
    )


# ============================================
# WEBHOOK EVENT LOG
# ============================================

class WebhookEventLog(BaseModel):
    """Webhook event log for idempotency and debugging."""

    __tablename__ = "webhook_events_log"

    # Stripe event ID (unique for idempotency)
    stripe_event_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    
    # Event type
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Processing status
    status: Mapped[WebhookEventStatus] = mapped_column(
        Enum(WebhookEventStatus), default=WebhookEventStatus.PENDING, nullable=False
    )
    
    # Payload (stored for debugging)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Related entity (optional, for quick lookup)
    related_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Error info
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Processing time
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("idx_webhook_events_stripe", "stripe_event_id"),
        Index("idx_webhook_events_type", "event_type"),
        Index("idx_webhook_events_status", "status"),
        Index("idx_webhook_events_created", "created_at"),
    )


# ============================================
# BILLING AUDIT LOG
# ============================================

class BillingAuditLog(BaseModel):
    """Audit log for billing-related actions."""

    __tablename__ = "billing_audit_log"

    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Action
    action: Mapped[BillingAuditAction] = mapped_column(
        Enum(BillingAuditAction), nullable=False
    )
    
    # Entity reference
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Change tracking
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Request context
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Additional context
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # renamed from 'metadata' (reserved)

    __table_args__ = (
        Index("idx_billing_audit_account", "account_id"),
        Index("idx_billing_audit_action", "action"),
        Index("idx_billing_audit_created", "created_at"),
    )


# ============================================
# BILLING INFO (TAX/BUSINESS INFO)
# ============================================

class BillingInfo(BaseModel):
    """Billing/tax information for invoices."""

    __tablename__ = "billing_info"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    
    # Business info
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # VAT ID, EIN, etc.
    tax_id_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 'eu_vat', 'us_ein', etc.
    tax_exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Billing address
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    
    # Contact
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Preferences
    invoice_footer: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_currency: Mapped[str] = mapped_column(String(3), default="usd")
    
    # Stripe sync
    stripe_tax_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_billing_info_account", "account_id"),
    )


# ============================================
# ADD-ON MODELS
# ============================================

class AddonStatus(str, enum.Enum):
    """Subscription add-on status."""
    ACTIVE = "active"
    PENDING_CANCEL = "pending_cancel"
    CANCELED = "canceled"


class AddonDefinition(BaseModel):
    """Add-on product definitions (seeded data)."""
    
    __tablename__ = "addon_definitions"
    
    # Override id to be string instead of UUID
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_monthly: Mapped[float] = mapped_column(Float, nullable=False)
    price_yearly: Mapped[float] = mapped_column(Float, nullable=False)
    stripe_price_id_monthly: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_price_id_yearly: Mapped[str | None] = mapped_column(String(100), nullable=True)
    min_plan: Mapped[str] = mapped_column(String(20), default="pro")
    feature_flag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    subscriptions: Mapped[list["SubscriptionAddon"]] = relationship(
        "SubscriptionAddon", back_populates="addon_definition"
    )


class SubscriptionAddon(BaseModel):
    """Add-ons attached to a subscription."""
    
    __tablename__ = "subscription_addons"
    
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    addon_id: Mapped[str] = mapped_column(
        ForeignKey("addon_definitions.id"),
        nullable=False,
    )
    stripe_subscription_item_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[AddonStatus] = mapped_column(
        Enum(AddonStatus),
        default=AddonStatus.ACTIVE,
    )
    attached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow_aware,
    )
    cancel_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        "Subscription", back_populates="addons"
    )
    addon_definition: Mapped["AddonDefinition"] = relationship(
        "AddonDefinition", back_populates="subscriptions"
    )
    
    __table_args__ = (
        Index("idx_subscription_addons_subscription", "subscription_id"),
        Index("idx_subscription_addons_status", "status"),
        Index("idx_subscription_addons_addon", "addon_id"),
    )
