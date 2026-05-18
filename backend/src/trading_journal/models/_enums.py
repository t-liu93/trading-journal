"""Shared Python enums used as SQLAlchemy column types across models.

Values are the canonical string forms persisted to the database. Adding a new
value is a 1-line change here plus an Alembic migration that alters the enum.
"""

from enum import Enum, StrEnum


def enum_values(enum_cls: type[Enum]) -> list[str]:
    """``values_callable`` for SQLAlchemy ``Enum`` columns: persist ``.value``.

    SQLAlchemy's default is to persist ``Enum.name`` (uppercase here). We want
    the lowercase canonical string from ``.value`` instead.
    """
    return [member.value for member in enum_cls]


class InstrumentKind(StrEnum):
    STOCK = "stock"
    OPTION = "option"
    FOREX = "forex"


class OptType(StrEnum):
    CALL = "call"
    PUT = "put"


class OptionStyle(StrEnum):
    AMERICAN = "american"
    EUROPEAN = "european"


class AccountType(StrEnum):
    CASH = "cash"
    MARGIN = "margin"
    PAPER = "paper"


class StrategyType(StrEnum):
    WHEEL = "wheel"
    IRON_CONDOR = "iron_condor"
    PMCC = "pmcc"
    SPOT_STOCK = "spot_stock"
    SPOT_FOREX = "spot_forex"


class PositionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class TradeAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    BTO = "bto"
    STO = "sto"
    BTC = "btc"
    STC = "stc"


class FundingSource(StrEnum):
    CASH = "cash"
    MIXED = "mixed"
    MARGIN = "margin"
