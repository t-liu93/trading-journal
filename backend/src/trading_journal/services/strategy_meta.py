"""Strategy-meta service layer — cross-table validation helpers (P10)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import InstrumentKind, StrategyType
from trading_journal.models.instrument import Instrument, OptionContract
from trading_journal.models.position import Position


def validate_strategy_type_match(position: Position, expected: StrategyType) -> None:
    """Raise ``ValueError`` if ``position.strategy_type`` != *expected*.

    The router maps this to 422.
    """
    if position.strategy_type is not expected:
        raise ValueError(
            f"position.strategy_type is '{position.strategy_type.value}', "
            f"meta requires '{expected.value}'"
        )


async def validate_leap_instrument(
    session: AsyncSession,
    position: Position,
    leap_instrument_id: uuid.UUID,
) -> None:
    """Three checks for PMCC LEAP validation (settled decision §1).

    All failures raise ``ValueError`` with a specific message; the router
    maps to 422.
    """
    instrument = await session.get(Instrument, leap_instrument_id)
    if instrument is None:
        raise ValueError("leap instrument not found")
    if instrument.kind is not InstrumentKind.OPTION:
        raise ValueError(
            "leap_instrument_id must reference an option instrument"
        )
    contract = await session.get(OptionContract, leap_instrument_id)
    if contract is None:
        raise ValueError(
            f"instrument {leap_instrument_id} is kind=option but has no "
            "OptionContract row"
        )
    if contract.underlying_id != position.primary_instrument_id:
        raise ValueError(
            "leap option's underlying does not match position's primary instrument"
        )
