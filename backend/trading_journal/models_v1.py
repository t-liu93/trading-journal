from __future__ import annotations

from datetime import date, datetime  # noqa: TC003
from enum import Enum

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel
from sqlmodel import Enum as SQLEnum


class TradeType(str, Enum):
    SELL_PUT = "SELL_PUT"
    ASSIGNMENT = "ASSIGNMENT"
    SELL_CALL = "SELL_CALL"
    EXERCISE_CALL = "EXERCISE_CALL"


class TradeStrategy(str, Enum):
    WHEELS = "WHEEL"
    FX = "FX"
    SPOT = "SPOT"
    OTHER = "OTHER"


class CycleStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class FundingSource(str, Enum):
    CASH = "CASH"
    MARGIN = "MARGIN"
    MIXED = "MIXED"


class Trades(SQLModel, table=True):
    __tablename__ = "trades"
    id: str | None = Field(default=None, primary_key=True)
    user_id: str
    symbol: str
    underlying_currency: str
    trade_type: TradeType = Field(sa_column=Column(SQLEnum(TradeType, name="trade_type_enum"), nullable=False))
    trade_strategy: TradeStrategy = Field(sa_column=Column(SQLEnum(TradeStrategy, name="trade_strategy_enum"), nullable=False))
    trade_time_utc: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    expiry_date: date | None = Field(default=None, nullable=True)
    strike_price_cents: int | None = Field(default=None, nullable=True)
    quantity: int
    price_cents: int
    gross_cash_flow_cents: int
    commission_cents: int
    net_cash_flow_cents: int
    cycle_id: str | None = Field(default=None, foreign_key="cycles.id", nullable=True)
    cycle: Cycles | None = Relationship(back_populates="trades")


class Cycles(SQLModel, table=True):
    __tablename__ = "cycles"
    id: str | None = Field(default=None, primary_key=True)
    user_id: str
    symbol: str
    underlying_currency: str
    start_date: date
    end_date: date | None = Field(default=None, nullable=True)
    status: CycleStatus = Field(sa_column=Column(SQLEnum(CycleStatus, name="cycle_status_enum"), nullable=False))
    funding_source: FundingSource = Field(sa_column=Column(SQLEnum(FundingSource, name="funding_source_enum"), nullable=False))
    capital_exposure_cents: int
    loan_amount_cents: int | None = Field(default=None, nullable=True)
    loan_interest_rate_bps: int | None = Field(default=None, nullable=True)
    trades: list[Trades] = Relationship(back_populates="cycle")
