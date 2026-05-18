"""Smoke tests for the ORM model layer."""

from trading_journal.db import Base
from trading_journal.models import (
    AccessToken,
    Account,
    ForexPair,
    Instrument,
    OptionContract,
    PmccCycleMeta,
    Position,
    StrategyConfig,
    Trade,
    TradePlan,
    User,
    WheelCycleMeta,
)

EXPECTED_TABLES = {
    "users",
    "access_tokens",
    "accounts",
    "instruments",
    "option_contracts",
    "forex_pairs",
    "positions",
    "trades",
    "trade_plans",
    "strategy_configs",
    "wheel_cycle_metas",
    "pmcc_cycle_metas",
}


def test_models_can_be_imported() -> None:
    """All public model classes resolve to mapped SQLAlchemy classes."""
    classes = (
        User,
        AccessToken,
        Account,
        Instrument,
        OptionContract,
        ForexPair,
        Position,
        Trade,
        TradePlan,
        StrategyConfig,
        WheelCycleMeta,
        PmccCycleMeta,
    )
    for cls in classes:
        assert hasattr(cls, "__tablename__"), f"{cls.__name__} not mapped"


def test_base_metadata_registers_full_schema() -> None:
    """Importing ``models`` populates Base.metadata with every expected table."""
    actual = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - actual
    unexpected = actual - EXPECTED_TABLES
    assert not missing, f"missing tables: {sorted(missing)}"
    assert not unexpected, f"unexpected tables: {sorted(unexpected)}"
