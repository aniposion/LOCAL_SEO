"""Analytics event model for server-side tracking."""
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import BaseModel


class AnalyticsEvent(BaseModel):
    """
    Server-side analytics event.
    
    Single source of truth for all user actions.
    No client-side tracking = no ad blockers, no missing data.
    """
    __tablename__ = "analytics_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    session_id = Column(String(100), nullable=True)
    event_name = Column(String(100), nullable=False, index=True)
    properties = Column(JSONB, nullable=False, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<AnalyticsEvent {self.event_name} user={self.user_id}>"
