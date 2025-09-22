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
    exchange: str
    underlying_currency: UnderlyingCurrency
    trade_type: TradeType
    trade_strategy: TradeStrategy
    trade_date: date
    trade_time_utc: datetime
    quantity: int
    price_cents: int
    gross_cash_flow_cents: int
    commission_cents: int
    net_cash_flow_cents: int
    notes: str | None
    cycle_id: int | None = None


class TradeCreate(TradeBase):
    expiry_date: date | None = None
    strike_price_cents: int | None = None
    is_invalidated: bool = False
    invalidated_at: datetime | None = None
    replaced_by_trade_id: int | None = None


class TradeRead(TradeBase):
    id: int
    is_invalidated: bool
    invalidated_at: datetime | None


class UserBase(SQLModel):
    username: str
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
