"""Instrument list query rules."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import InstrumentKind
from trading_journal.models.instrument import Instrument, OptionContract


def current_utc_date() -> date:
    """Return today's UTC date; replaceable in tests for expiry boundaries."""
    return datetime.now(UTC).date()


def instrument_query(
    *,
    kind: InstrumentKind | None = None,
    q: str | None = None,
    include_expired: bool = True,
    option_underlying_id: uuid.UUID | None = None,
) -> Select[tuple[Instrument]]:
    """Build a filtered list query. Underlying/expiry rules only affect options."""
    stmt = select(Instrument)
    if kind is not None:
        stmt = stmt.where(Instrument.kind == kind)
    if q is not None:
        stmt = stmt.where(Instrument.symbol.ilike(f"{q}%"))
    if not include_expired:
        active_option_ids = select(OptionContract.instrument_id).where(
            OptionContract.expiry >= current_utc_date()
        )
        stmt = stmt.where(
            (Instrument.kind != InstrumentKind.OPTION)
            | Instrument.id.in_(active_option_ids)
        )
    if option_underlying_id is not None:
        option_ids = select(OptionContract.instrument_id).where(
            OptionContract.underlying_id == option_underlying_id
        )
        stmt = stmt.where(
            (Instrument.kind != InstrumentKind.OPTION)
            | Instrument.id.in_(option_ids)
        )
    return stmt


async def list_instruments(
    session: AsyncSession,
    *,
    kind: InstrumentKind | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_expired: bool = True,
    option_underlying_id: uuid.UUID | None = None,
) -> list[Instrument]:
    stmt = instrument_query(
        kind=kind,
        q=q,
        include_expired=include_expired,
        option_underlying_id=option_underlying_id,
    )
    stmt = stmt.order_by(Instrument.symbol, Instrument.created_at, Instrument.id)
    result = await session.execute(stmt.offset(offset).limit(limit))
    return list(result.scalars().all())
