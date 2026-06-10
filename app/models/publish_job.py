"""Publish Job model for reliable publishing system."""

import enum
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now_aware
from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.post import Post


class PublishJobStatus(str, enum.Enum):
    """Publish job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PublishJob(BaseModel):
    """Publish job queue for reliable publishing."""

    __tablename__ = "publish_jobs"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        index=True,
    )

    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    # 'gbp', 'instagram', 'facebook'

    status: Mapped[PublishJobStatus] = mapped_column(
        Enum(PublishJobStatus), default=PublishJobStatus.PENDING
    )

    # Retry management
    tries: Mapped[int] = mapped_column(Integer, default=0)
    max_tries: Mapped[int] = mapped_column(Integer, default=5)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Idempotency
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )

    # Error tracking
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Platform response
    platform_post_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    platform_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Payload snapshots (for audit/debugging)
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="publish_jobs")

    def __repr__(self) -> str:
        return f"<PublishJob {self.platform} status={self.status.value}>"

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return (
            self.status in [PublishJobStatus.PENDING, PublishJobStatus.FAILED]
            and self.tries < self.max_tries
        )


class PlatformToken(BaseModel):
    """Platform OAuth tokens management."""

    __tablename__ = "platform_tokens"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
    )

    platform: Mapped[str] = mapped_column(String(30), nullable=False)

    # Tokens
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Token status
    status: Mapped[str] = mapped_column(String(30), default="active")
    # 'active', 'expiring_soon', 'expired', 'revoked', 'reauth_required'

    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Additional metadata
    scopes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    account_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        # Unique constraint on location + platform
        {"sqlite_autoincrement": True},
    )

    def __repr__(self) -> str:
        return f"<PlatformToken {self.platform} status={self.status}>"

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return utc_now_aware() > self.expires_at

    @property
    def is_expiring_soon(self) -> bool:
        """Check if token expires within 7 days."""
        if not self.expires_at:
            return False
        return utc_now_aware() + timedelta(days=7) > self.expires_at


class RateLimitTracker(BaseModel):
    """Track API rate limits per platform."""

    __tablename__ = "rate_limit_tracker"

    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Rate limit window
    requests_count: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    window_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    max_requests: Mapped[int] = mapped_column(Integer, default=100)

    def __repr__(self) -> str:
        return f"<RateLimitTracker {self.platform}: {self.requests_count}/{self.max_requests}>"

    @property
    def is_limited(self) -> bool:
        """Check if rate limit is exceeded."""
        return self.requests_count >= self.max_requests

    def reset_if_window_expired(self) -> bool:
        """Reset counter if window has expired."""
        if not self.window_start:
            return False
        if utc_now_aware() > self.window_start + timedelta(seconds=self.window_seconds):
            self.requests_count = 0
            self.window_start = utc_now_aware()
            return True
        return False
