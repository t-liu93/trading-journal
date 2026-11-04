"""Build stable journal context for agent clients."""

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from trading_journal.config import get_settings
from trading_journal.models._enums import StrategyType, TradeAction
from trading_journal.schemas.journal_context import JournalContextRead

Clock = Callable[[], datetime]


def get_journal_context(
    *, clock: Clock | None = None, timezone_name: str | None = None
) -> JournalContextRead:
    """Return UTC/local time and enum choices, reading the clock exactly once."""
    timezone_name = timezone_name or get_settings().journal_timezone
    zone = ZoneInfo(timezone_name)
    instant = (clock or (lambda: datetime.now(UTC)))()
    if instant.tzinfo is None or instant.utcoffset() is None:
        instant = instant.replace(tzinfo=UTC)
    instant = instant.astimezone(UTC)
    return JournalContextRead(
        now_utc=instant,
        timezone=timezone_name,
        now_local=instant.astimezone(zone),
        strategies=tuple(StrategyType),
        trade_actions=tuple(TradeAction),
    )
