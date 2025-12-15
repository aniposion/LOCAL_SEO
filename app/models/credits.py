"""Credits model for usage tracking and billing."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.account import Account


class CreditTransactionType(str, enum.Enum):
    """Credit transaction types."""
    
    # Credits added
    MONTHLY_ALLOCATION = "monthly_allocation"  # Monthly plan credits
    PURCHASE = "purchase"  # Purchased credits
    BONUS = "bonus"  # Bonus/promotional credits
    REFUND = "refund"  # Refunded credits
    ADMIN_GRANT = "admin_grant"  # Admin granted credits
    
    # Credits used
    SMS_USAGE = "sms_usage"
    AI_CONTENT_USAGE = "ai_content_usage"
    AI_IMAGE_USAGE = "ai_image_usage"
    AI_RESPONSE_USAGE = "ai_response_usage"
    OVERAGE_CHARGE = "overage_charge"  # Generic overage


class CreditBalance(BaseModel):
    """User credit balance model."""
    
    __tablename__ = "credit_balances"
    
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    
    # Current balance
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bonus_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Monthly allocation tracking
    monthly_allocation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_allocation_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_allocation_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Lifetime stats
    total_credits_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_credits_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_credits_purchased: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationships
    account: Mapped["Account"] = relationship("Account", backref="credit_balance")
    
    def __repr__(self) -> str:
        return f"<CreditBalance {self.balance} + {self.bonus_balance} bonus>"
    
    @property
    def total_available(self) -> int:
        """Total available credits (balance + bonus)."""
        return self.balance + self.bonus_balance
    
    def can_afford(self, amount: int) -> bool:
        """Check if user can afford the credit cost."""
        return self.total_available >= amount
    
    def deduct(self, amount: int) -> bool:
        """Deduct credits. Uses bonus first, then regular balance."""
        if not self.can_afford(amount):
            return False
        
        remaining = amount
        
        # Use bonus credits first
        if self.bonus_balance > 0:
            bonus_used = min(self.bonus_balance, remaining)
            self.bonus_balance -= bonus_used
            remaining -= bonus_used
        
        # Use regular balance
        if remaining > 0:
            self.balance -= remaining
        
        self.total_credits_used += amount
        return True


class CreditTransaction(BaseModel):
    """Credit transaction history."""
    
    __tablename__ = "credit_transactions"
    
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Transaction details
    type: Mapped[CreditTransactionType] = mapped_column(
        Enum(CreditTransactionType), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # Positive = add, Negative = deduct
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Description
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Reference (e.g., payment ID, admin ID)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Admin who performed the action (if applicable)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    
    def __repr__(self) -> str:
        return f"<CreditTransaction {self.type.value}: {self.amount}>"


class UsageRecord(BaseModel):
    """Daily usage tracking for rate limiting."""
    
    __tablename__ = "usage_records"
    
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Usage type
    usage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # sms, ai_content, ai_image, ai_response
    
    # Date tracking
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Counts
    daily_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Last usage timestamp (for cooldown)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    def __repr__(self) -> str:
        return f"<UsageRecord {self.usage_type}: {self.daily_count}/day>"
