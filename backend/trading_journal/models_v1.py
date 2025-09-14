from datetime import date, datetime  # noqa: TC003
from enum import Enum

from sqlalchemy import Date, Text, UniqueConstraint
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel


class TradeType(str, Enum):
    SELL_PUT = "SELL_PUT"
    ASSIGNMENT = "ASSIGNMENT"
    SELL_CALL = "SELL_CALL"
    EXERCISE_CALL = "EXERCISE_CALL"
    LONG_SPOT = "LONG_SPOT"
    CLOSE_LONG_SPOT = "CLOSE_LONG_SPOT"
    SHORT_SPOT = "SHORT_SPOT"
    CLOSE_SHORT_SPOT = "CLOSE_SHORT_SPOT"
    LONG_CFD = "LONG_CFD"
    CLOSE_LONG_CFD = "CLOSE_LONG_CFD"
    SHORT_CFD = "SHORT_CFD"
    CLOSE_SHORT_CFD = "CLOSE_SHORT_CFD"
    LONG_OTHER = "LONG_OTHER"
    CLOSE_LONG_OTHER = "CLOSE_LONG_OTHER"
    SHORT_OTHER = "SHORT_OTHER"
    CLOSE_SHORT_OTHER = "CLOSE_SHORT_OTHER"


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
    __table_args__ = (
        UniqueConstraint(
            "user_id", "friendly_name", name="uq_trades_user_friendly_name"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    # allow null while user may omit friendly_name; uniqueness enforced per-user by constraint
    friendly_name: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    symbol: str = Field(sa_column=Column(Text, nullable=False))
    underlying_currency: str = Field(sa_column=Column(Text, nullable=False))
    trade_type: TradeType = Field(sa_column=Column(Text, nullable=False))
    trade_strategy: TradeStrategy = Field(sa_column=Column(Text, nullable=False))
    trade_time_utc: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    expiry_date: date | None = Field(default=None, nullable=True)
    strike_price_cents: int | None = Field(default=None, nullable=True)
    quantity: int
    price_cents: int
    gross_cash_flow_cents: int
    commission_cents: int
    net_cash_flow_cents: int
    cycle_id: int | None = Field(
        default=None, foreign_key="cycles.id", nullable=True, index=True
    )
    cycle: "Cycles" = Relationship(back_populates="trades")


class Cycles(SQLModel, table=True):
    __tablename__ = "cycles"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "friendly_name", name="uq_cycles_user_friendly_name"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    friendly_name: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    symbol: str = Field(sa_column=Column(Text, nullable=False))
    underlying_currency: str = Field(sa_column=Column(Text, nullable=False))
    status: CycleStatus = Field(sa_column=Column(Text, nullable=False))
    funding_source: FundingSource = Field(sa_column=Column(Text, nullable=True))
    capital_exposure_cents: int | None = Field(default=None, nullable=True)
    loan_amount_cents: int | None = Field(default=None, nullable=True)
    loan_interest_rate_bps: int | None = Field(default=None, nullable=True)
    start_date: date = Field(sa_column=Column(Date, nullable=False))
    end_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    trades: list["Trades"] = Relationship(back_populates="cycle")


class Users(SQLModel, table=True):
    __tablename__ = "users"
    id: int | None = Field(default=None, primary_key=True)
    # unique=True already creates an index; no need to also set index=True
    username: str = Field(sa_column=Column(Text, nullable=False, unique=True))
    password_hash: str = Field(sa_column=Column(Text, nullable=False))
    is_active: bool = Field(default=True, nullable=False)
