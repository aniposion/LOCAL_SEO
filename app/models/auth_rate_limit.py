"""Persistent auth rate limit buckets."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class AuthRateLimitBucket(BaseModel):
    """Persist auth rate limiting state across processes and instances."""

    __tablename__ = "auth_rate_limit_buckets"

    action: Mapped[str] = mapped_column(String(50), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    bucket_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<AuthRateLimitBucket {self.action}:{self.scope} {self.hit_count}>"
