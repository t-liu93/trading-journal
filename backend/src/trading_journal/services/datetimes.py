"""Shared timestamp normalization for SQLite's naive UTC convention."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def to_utc_naive(value: datetime) -> datetime:
    """Interpret naive datetimes as UTC and normalize aware values to UTC."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def parse_entry_datetime(
    value: datetime,
    *,
    default_timezone: str,
    input_timezone: str | None = None,
) -> datetime:
    """Parse MCP entry time to UTC without changing REST's naive-as-UTC rule.

    A supplied IANA timezone validates offset-bearing values and interprets
    naive values. Ambiguous or nonexistent local wall times require an offset.
    """
    timezone_name = input_timezone if input_timezone is not None else default_timezone
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown IANA timezone: {timezone_name}") from exc

    if value.tzinfo is not None and value.utcoffset() is not None:
        if input_timezone is not None:
            local = value.replace(tzinfo=None)
            candidates = _valid_local_candidates(local, zone)
            if not candidates:
                raise ValueError("Local time does not exist in the supplied timezone")
            if not any(candidate.utcoffset() == value.utcoffset() for candidate in candidates):
                raise ValueError("Datetime offset does not agree with the supplied timezone")
        return value.astimezone(UTC)

    candidates = _valid_local_candidates(value, zone)
    if not candidates:
        raise ValueError("Local time does not exist in the supplied timezone")
    offsets = {candidate.utcoffset() for candidate in candidates}
    if len(offsets) > 1:
        raise ValueError("Local time is ambiguous; provide an explicit UTC offset")
    return candidates[0].astimezone(UTC)


def _valid_local_candidates(value: datetime, zone: ZoneInfo) -> list[datetime]:
    candidates: list[datetime] = []
    for fold in (0, 1):
        candidate = value.replace(tzinfo=zone, fold=fold)
        if candidate.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == value:
            if not any(candidate.utcoffset() == existing.utcoffset() for existing in candidates):
                candidates.append(candidate)
    return candidates
