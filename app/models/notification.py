"""Notification history, delivery audit, and push subscription models."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUID, BaseModel


class NotificationEvent(BaseModel):
    """Persisted notification inbox event for an account."""

    __tablename__ = "notification_events"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_notification_events_account_read", "account_id", "read"),
    )


class NotificationDeliveryLog(BaseModel):
    """Delivery audit record for a single channel attempt."""

    __tablename__ = "notification_delivery_logs"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional link to the inbox event that triggered this delivery attempt.
    notification_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(),
        ForeignKey("notification_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Channel used: inbox, push, email, sms, slack
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    # Outcome: delivered, failed, unavailable, skipped
    delivery_status: Mapped[str] = mapped_column(String(50), nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_ndl_account_status", "account_id", "delivery_status"),
        Index("ix_ndl_event_id", "notification_event_id"),
    )


class PushSubscriptionRecord(BaseModel):
    """Persisted web-push subscription for an account device."""

    __tablename__ = "push_subscriptions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The push endpoint URL issued by the browser's push service.
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False)
    # ECDH public key for payload encryption (base64url).
    p256dh_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # HMAC authentication secret (base64url).
    auth_key: Mapped[str] = mapped_column(String(512), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), default="web", nullable=False)

    __table_args__ = (
        # Each endpoint is unique per account (same browser can re-subscribe without duplicates).
        UniqueConstraint("account_id", "endpoint", name="uq_push_sub_account_endpoint"),
        Index("ix_push_subs_account_id", "account_id"),
    )
