"""MCP-facing deterministic context values."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from trading_journal.models._enums import StrategyType, TradeAction


class JournalContextRead(BaseModel):
    """Time and supported enum values used to interpret agent requests."""

    model_config = ConfigDict(frozen=True)

    now_utc: datetime
    timezone: str
    now_local: datetime
    strategies: tuple[StrategyType, ...]
    trade_actions: tuple[TradeAction, ...]
