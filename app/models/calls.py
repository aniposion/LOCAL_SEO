"""P3: Missed Call Text Back models."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


class ThreadStatus(str, enum.Enum):
    """SMS thread status."""
    OPEN = "open"
    CLOSED = "closed"
    SPAM = "spam"


class MessageDirection(str, enum.Enum):
    """SMS message direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class TwilioNumber(BaseModel):
    """Twilio phone number configuration."""
    
    __tablename__ = "twilio_numbers"
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    twilio_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    forward_to: Mapped[str] = mapped_column(String(20), nullable=False)
    
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    
    # Settings
    missed_call_sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sms_template: Mapped[str] = mapped_column(
        Text, 
        default="Hi! Sorry we missed your call at {business_name}. How can we help? Reply here or call {forward_to}",
        nullable=False
    )
    
    # Stats (denormalized)
    total_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missed_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sms_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="twilio_numbers")
    call_logs: Mapped[list["CallLog"]] = relationship(
        "CallLog", back_populates="twilio_number_rel", cascade="all, delete-orphan"
    )


class CallLog(BaseModel):
    """Individual call log entry."""
    
    __tablename__ = "call_logs"
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    twilio_number_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("twilio_numbers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Call details
    twilio_call_sid: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    caller_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    call_status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed, no-answer, busy, failed
    call_duration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # seconds
    
    # SMS response
    sms_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sms_message_sid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Thread reference
    thread_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sms_threads.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Tags for categorization
    tags: Mapped[list] = mapped_column(ARRAY(String(50)), default=[], nullable=False)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location")
    twilio_number_rel: Mapped["TwilioNumber"] = relationship("TwilioNumber", back_populates="call_logs")
    thread: Mapped["SMSThread"] = relationship("SMSThread", back_populates="call_logs")
    
    @hybrid_property
    def is_missed(self) -> bool:
        """Check if call was missed."""
        return self.call_status in ('no-answer', 'busy')


class SMSThread(BaseModel):
    """SMS conversation thread."""
    
    __tablename__ = "sms_threads"
    __table_args__ = (
        UniqueConstraint('location_id', 'customer_phone', 'twilio_number', name='uq_sms_thread'),
    )
    
    location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    twilio_number: Mapped[str] = mapped_column(String(20), nullable=False)
    
    status: Mapped[ThreadStatus] = mapped_column(
        Enum(
            ThreadStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=ThreadStatus.OPEN,
        nullable=False,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Tags
    tags: Mapped[list] = mapped_column(ARRAY(String(50)), default=[], nullable=False)
    
    # Relationships
    location: Mapped["Location"] = relationship("Location", back_populates="sms_threads")
    messages: Mapped[list["SMSMessage"]] = relationship(
        "SMSMessage", back_populates="thread", cascade="all, delete-orphan",
        order_by="SMSMessage.created_at"
    )
    call_logs: Mapped[list["CallLog"]] = relationship("CallLog", back_populates="thread")


class SMSMessage(BaseModel):
    """Individual SMS message in a thread."""
    
    __tablename__ = "sms_messages"
    
    thread_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sms_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(
            MessageDirection,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    
    twilio_message_sid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # queued, sent, delivered, failed
    
    # Relationships
    thread: Mapped["SMSThread"] = relationship("SMSThread", back_populates="messages")
