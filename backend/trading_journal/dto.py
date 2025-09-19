from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import SQLModel

if TYPE_CHECKING:
    from datetime import date, datetime

    from trading_journal.models import TradeStrategy, TradeType, UnderlyingCurrency


class TradeBase(SQLModel):
    user_id: int
    friendly_name: str | None
    symbol: str
    underlying_currency: UnderlyingCurrency
    trade_type: TradeType
    trade_strategy: TradeStrategy
    trade_date: date
    trade_time_utc: datetime
