"""UTC time helpers for consistent application timestamps."""

from datetime import UTC, datetime


def utc_now_aware() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def utc_now_naive() -> datetime:
    """Return a naive datetime representing UTC."""
    return utc_now_aware().replace(tzinfo=None)
