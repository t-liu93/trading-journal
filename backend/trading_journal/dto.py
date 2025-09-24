from __future__ import annotations

from datetime import date, datetime  # noqa: TC003

from pydantic import BaseModel
from sqlmodel import SQLModel

from trading_journal.models import TradeStrategy, TradeType, UnderlyingCurrency  # noqa: TC001


class UserBase(SQLModel):
    username: str
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserRead(UserBase):
    id: int


class SessionsBase(SQLModel):
    user_id: int


class SessionRead(SessionsBase):
    id: int
    expires_at: datetime
    last_seen_at: datetime | None
    last_used_ip: str | None
    user_agent: str | None


class SessionsCreate(SessionsBase):
    expires_at: datetime


class SessionsUpdate(SQLModel):
    expires_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_used_ip: str | None = None
    user_agent: str | None = None


class ExchangesBase(SQLModel):
    name: str
    notes: str | None = None


class ExchangesCreate(ExchangesBase):
    user_id: int


class ExchangesRead(ExchangesBase):
    id: int


class CycleBase(SQLModel):
    friendly_name: str | None = None
    status: str
    end_date: date | None = None
    funding_source: str | None = None
    capital_exposure_cents: int | None = None
    loan_amount_cents: int | None = None
    loan_interest_rate_bps: int | None = None
    trades: list[TradeRead] | None = None
    exchange: ExchangesRead | None = None


class CycleCreate(CycleBase):
    user_id: int
    symbol: str
    exchange_id: int
    underlying_currency: UnderlyingCurrency
    start_date: date


class CycleUpdate(CycleBase):
    id: int


class CycleRead(CycleCreate):
    id: int


class TradeBase(SQLModel):
    friendly_name: str | None = None
    symbol: str
    exchange_id: int
    underlying_currency: UnderlyingCurrency
    trade_type: TradeType
    trade_strategy: TradeStrategy
    trade_date: date
    quantity: int
    price_cents: int
    commission_cents: int
    notes: str | None = None
    cycle_id: int | None = None


class TradeCreate(TradeBase):
    user_id: int | None = None
    trade_time_utc: datetime | None = None
    gross_cash_flow_cents: int | None = None
    net_cash_flow_cents: int | None = None
    quantity_multiplier: int = 1
    expiry_date: date | None = None
    strike_price_cents: int | None = None
    is_invalidated: bool = False
    invalidated_at: datetime | None = None
    replaced_by_trade_id: int | None = None


class TradeNoteUpdate(BaseModel):
    id: int
    notes: str | None = None


class TradeFriendlyNameUpdate(BaseModel):
    id: int
    friendly_name: str


class TradeRead(TradeCreate):
    id: int


SessionsCreate.model_rebuild()
CycleBase.model_rebuild()
