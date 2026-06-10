"""AI usage cost tracking model."""
import uuid
from decimal import Decimal
from sqlalchemy import Column, BigInteger, String, Numeric, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import BaseModel


class AiUsageCost(BaseModel):
    """
    AI usage cost tracking.
    
    Records every AI API call cost for monitoring and cap enforcement.
    CRITICAL: Cost cap must be checked BEFORE API call to prevent overspending.
    """
    __tablename__ = "ai_usage_costs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Feature and provider
    feature = Column(String(50), nullable=False, index=True)
    # 'competitor_analysis', 'social_card', 'review_response', 'content_generation'
    api_provider = Column(String(50), nullable=False)
    # 'gemini', 'imagen', 'google_places'
    
    # Cost tracking
    cost_usd = Column(Numeric(10, 6), nullable=False)  # Accurate to $0.000001
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)
    api_calls = Column(Integer, default=1)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<AiUsageCost {self.feature} ${self.cost_usd} user={self.user_id}>"
    
    @property
    def cost_float(self) -> float:
        """Get cost as float."""
        return float(self.cost_usd) if isinstance(self.cost_usd, Decimal) else self.cost_usd
