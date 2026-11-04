from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from trading_journal.config import Settings
from trading_journal.models._enums import StrategyType, TradeAction
from trading_journal.schemas.journal_context import JournalContextRead
from trading_journal.services.datetimes import parse_entry_datetime
from trading_journal.services.journal_context import get_journal_context


def test_timezone_defaults_to_utc_and_rejects_unknown_values() -> None:
    assert Settings(_env_file=None).journal_timezone == "UTC"
    assert Settings(_env_file=None, journal_timezone="Europe/Amsterdam").journal_timezone == (
        "Europe/Amsterdam"
    )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, journal_timezone="Mars/Olympus")


@pytest.mark.parametrize(
    ("instant", "expected_local"),
    [
        (
            datetime(2026, 1, 15, 12, tzinfo=UTC),
            datetime(2026, 1, 15, 13, tzinfo=ZoneInfo("Europe/Amsterdam")),
        ),
        (
            datetime(2026, 7, 15, 12, tzinfo=UTC),
            datetime(2026, 7, 15, 14, tzinfo=ZoneInfo("Europe/Amsterdam")),
        ),
    ],
)
def test_context_uses_one_injected_clock_for_winter_and_summer(
    instant: datetime, expected_local: datetime
) -> None:
    calls = 0

    def clock() -> datetime:
        nonlocal calls
        calls += 1
        return instant

    context = get_journal_context(clock=clock, timezone_name="Europe/Amsterdam")
    assert calls == 1
    assert context.now_utc == instant
    assert context.now_local == expected_local
    assert context.timezone == "Europe/Amsterdam"
    assert context.strategies == tuple(StrategyType)
    assert context.trade_actions == tuple(TradeAction)
    assert JournalContextRead.model_validate(context.model_dump()) == context


def test_context_interprets_naive_injected_clock_as_utc() -> None:
    context = get_journal_context(
        clock=lambda: datetime(2026, 1, 1), timezone_name="Europe/Amsterdam"
    )
    assert context.now_utc == datetime(2026, 1, 1, tzinfo=UTC)


def test_entry_datetime_naive_uses_input_timezone_then_server_default() -> None:
    local = datetime(2026, 1, 15, 12)
    assert parse_entry_datetime(local, default_timezone="UTC", input_timezone="Asia/Tokyo") == (
        datetime(2026, 1, 15, 3, tzinfo=UTC)
    )
    assert parse_entry_datetime(local, default_timezone="Europe/Amsterdam") == datetime(
        2026, 1, 15, 11, tzinfo=UTC
    )


def test_entry_datetime_offset_and_iana_timezone_must_agree() -> None:
    value = datetime.fromisoformat("2026-07-15T12:00:00+02:00")
    assert parse_entry_datetime(value, default_timezone="UTC") == datetime(
        2026, 7, 15, 10, tzinfo=UTC
    )
    assert parse_entry_datetime(
        value, default_timezone="UTC", input_timezone="Europe/Amsterdam"
    ) == datetime(2026, 7, 15, 10, tzinfo=UTC)
    with pytest.raises(ValueError, match="does not agree"):
        parse_entry_datetime(
            value, default_timezone="UTC", input_timezone="Europe/London"
        )


@pytest.mark.parametrize("local", [datetime(2026, 3, 29, 2, 30), datetime(2026, 10, 25, 2, 30)])
def test_entry_datetime_rejects_nonexistent_and_ambiguous_local_times(local: datetime) -> None:
    with pytest.raises(ValueError):
        parse_entry_datetime(local, default_timezone="Europe/Amsterdam")


def test_explicit_offset_resolves_ambiguous_time_but_not_nonexistent_time() -> None:
    ambiguous = datetime.fromisoformat("2026-10-25T02:30:00+02:00")
    assert parse_entry_datetime(
        ambiguous, default_timezone="UTC", input_timezone="Europe/Amsterdam"
    ) == datetime.fromisoformat("2026-10-25T00:30:00+00:00")
    nonexistent = datetime.fromisoformat("2026-03-29T02:30:00+01:00")
    with pytest.raises(ValueError, match="does not exist"):
        parse_entry_datetime(
            nonexistent, default_timezone="UTC", input_timezone="Europe/Amsterdam"
        )
