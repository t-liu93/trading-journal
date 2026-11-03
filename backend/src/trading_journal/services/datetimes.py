"""Shared timestamp normalization for SQLite's naive UTC convention."""

from datetime import UTC, datetime


def to_utc_naive(value: datetime) -> datetime:
    """Interpret naive datetimes as UTC and normalize aware values to UTC."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
