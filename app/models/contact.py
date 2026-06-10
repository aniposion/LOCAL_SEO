"""Public contact request model for sales and pilot inquiries."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, get_json_type


class ContactRequestStatus(str, enum.Enum):
    """Operator workflow status for inbound contact requests."""

    NEW = "new"
    CONTACTED = "contacted"
    BOOKED = "booked"
    WON = "won"
    LOST = "lost"
    CLOSED = "closed"
    SPAM = "spam"


class ContactRequest(BaseModel):
    """A public inbound sales/support request from the contact page."""

    __tablename__ = "contact_requests"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="contact_page")
    recommended_package: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    audit_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    lead_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    sales_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    booked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    won_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ContactRequestStatus.NEW.value,
        index=True,
    )
    extra_data: Mapped[dict | None] = mapped_column(get_json_type(), nullable=True)
