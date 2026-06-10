"""Stripe webhook event model for idempotency."""
from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import BaseModel


class StripeEvent(BaseModel):
    """
    Stripe webhook event model.
    
    CRITICAL: event_id has UNIQUE constraint to prevent duplicate processing.
    Multiple webhook deliveries will fail on INSERT, ensuring exactly-once processing.
    """
    __tablename__ = "stripe_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSONB, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<StripeEvent {self.event_id} type={self.event_type}>"
