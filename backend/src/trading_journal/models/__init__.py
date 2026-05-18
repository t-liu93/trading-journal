"""Aggregate ORM imports.

Importing this module is sufficient to populate ``Base.metadata`` with every
table so Alembic autogenerate can see the full schema.
"""

from trading_journal.models.account import Account
from trading_journal.models.instrument import ForexPair, Instrument, OptionContract
from trading_journal.models.position import Position
from trading_journal.models.strategy_config import StrategyConfig
from trading_journal.models.strategy_meta import PmccCycleMeta, WheelCycleMeta
from trading_journal.models.trade import Trade
from trading_journal.models.trade_plan import TradePlan
from trading_journal.models.user import AccessToken, User

__all__ = [
    "AccessToken",
    "Account",
    "ForexPair",
    "Instrument",
    "OptionContract",
    "PmccCycleMeta",
    "Position",
    "StrategyConfig",
    "Trade",
    "TradePlan",
    "User",
    "WheelCycleMeta",
]
