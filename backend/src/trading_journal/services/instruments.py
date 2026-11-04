"""Instrument list query rules."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.type_api import TypeEngine

from trading_journal.models._enums import InstrumentKind
from trading_journal.models.instrument import ForexPair, Instrument, OptionContract
from trading_journal.schemas.instrument import (
    ForexCreate,
    ForexPairRead,
    InstrumentCreate,
    InstrumentRead,
    OptionContractRead,
    OptionCreate,
    StockCreate,
)
from trading_journal.services.write_guard import acquire_instrument_write_guard


def current_utc_date() -> date:
    """Return today's UTC date; replaceable in tests for expiry boundaries."""
    return datetime.now(UTC).date()


def instrument_query(
    *,
    kind: InstrumentKind | None = None,
    q: str | None = None,
    include_expired: bool = True,
    option_underlying_id: uuid.UUID | None = None,
    related_underlying_id: uuid.UUID | None = None,
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
    if related_underlying_id is not None:
        related_options = select(OptionContract.instrument_id).where(
            OptionContract.underlying_id == related_underlying_id
        )
        stmt = stmt.where(
            (Instrument.id == related_underlying_id)
            | Instrument.id.in_(related_options)
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
    related_underlying_id: uuid.UUID | None = None,
) -> list[Instrument]:
    stmt = instrument_query(
        kind=kind,
        q=q,
        include_expired=include_expired,
        option_underlying_id=option_underlying_id,
        related_underlying_id=related_underlying_id,
    )
    stmt = stmt.order_by(Instrument.symbol, Instrument.created_at, Instrument.id)
    result = await session.execute(stmt.offset(offset).limit(limit))
    return list(result.scalars().all())


async def instrument_read(session: AsyncSession, instrument: Instrument) -> InstrumentRead:
    """Serialize an instrument with its complete optional contract block."""
    read = InstrumentRead.model_validate(instrument)
    if instrument.kind is InstrumentKind.OPTION:
        contract = await session.get(OptionContract, instrument.id)
        if contract is not None:
            read.option = OptionContractRead.model_validate(contract)
    elif instrument.kind is InstrumentKind.FOREX:
        pair = await session.get(ForexPair, instrument.id)
        if pair is not None:
            read.forex = ForexPairRead.model_validate(pair)
    return read


async def find_stock(
    session: AsyncSession, *, symbol: str, currency: str, exchange: str | None
) -> Instrument | None:
    """Look up a stock by the existing website natural key."""
    stmt = select(Instrument).where(
        Instrument.kind == InstrumentKind.STOCK,
        Instrument.symbol == symbol.strip().upper(),
        Instrument.currency == currency,
        Instrument.exchange == exchange if exchange is not None else Instrument.exchange.is_(None),
    )
    return await _one_or_conflict(session, stmt, "stock")


async def _one_or_conflict(
    session: AsyncSession, stmt: Select[tuple[Instrument]], label: str
) -> Instrument | None:
    result = await session.execute(stmt.limit(2))
    rows = list(result.scalars().all())
    if len(rows) > 1:
        raise ValueError(f"multiple matching {label} instruments exist")
    return rows[0] if rows else None


async def resolve_instrument_spec(
    session: AsyncSession, payload: InstrumentCreate
) -> Instrument | None:
    """Read-only lookup by established natural keys; never creates dependencies."""
    if isinstance(payload, StockCreate):
        return await find_stock(
            session,
            symbol=payload.symbol,
            currency=payload.currency,
            exchange=payload.exchange,
        )
    if isinstance(payload, OptionCreate):
        underlying = await find_stock(
            session,
            symbol=payload.underlying_symbol,
            currency=payload.currency,
            exchange=payload.underlying_exchange,
        )
        if underlying is None:
            return None
        stmt = (
            select(Instrument)
            .join(OptionContract, OptionContract.instrument_id == Instrument.id)
            .where(
                OptionContract.underlying_id == underlying.id,
                OptionContract.opt_type == payload.opt_type,
                OptionContract.strike == payload.strike,
                OptionContract.expiry == payload.expiry,
                OptionContract.multiplier == payload.multiplier,
            )
        )
        instrument = await _one_or_conflict(session, stmt, "option")
        if instrument is not None:
            contract = await session.get(OptionContract, instrument.id)
            if contract is None or contract.style != payload.style:
                raise ValueError("matching option has conflicting contract specifications")
        return instrument
    return await _resolve_forex_spec(session, payload)


async def _resolve_forex_spec(
    session: AsyncSession, payload: ForexCreate
) -> Instrument | None:
    stmt = select(Instrument).where(
        Instrument.kind == InstrumentKind.FOREX,
        Instrument.symbol == payload.symbol.strip().upper(),
    )
    instrument = await _one_or_conflict(session, stmt, "forex")
    if instrument is None:
        return None
    pair = await session.get(ForexPair, instrument.id)
    if pair is None or (
        pair.base_currency != payload.base_currency
        or pair.quote_currency != payload.quote_currency
        or _database_numeric_value(
            session, ForexPair.__table__.c.pip_size.type, payload.pip_size
        )
        != pair.pip_size
        or _optional_database_numeric_value(
            session,
            ForexPair.__table__.c.contract_size.type,
            payload.contract_size,
        )
        != pair.contract_size
    ):
        raise ValueError("matching forex pair has conflicting specifications")
    return instrument


def _database_numeric_value(
    session: AsyncSession, column_type: TypeEngine[Any], value: Decimal
) -> Decimal:
    """Apply this database dialect's Numeric bind/read conversion to a value."""
    dialect = session.get_bind().dialect
    numeric_type = column_type.dialect_impl(dialect)
    bind = numeric_type.bind_processor(dialect)
    result = numeric_type.result_processor(dialect, None)
    bound_value = bind(value) if bind is not None else value
    converted = result(bound_value) if result is not None else bound_value
    if not isinstance(converted, Decimal):
        raise TypeError("Numeric dialect conversion did not return Decimal")
    return converted


def _optional_database_numeric_value(
    session: AsyncSession,
    column_type: TypeEngine[Any],
    value: Decimal | None,
) -> Decimal | None:
    return (
        None
        if value is None
        else _database_numeric_value(session, column_type, value)
    )


async def get_or_create_instrument(
    session: AsyncSession, payload: InstrumentCreate
) -> tuple[Instrument, bool]:
    """Resolve or create an instrument without committing; caller owns transaction."""
    await acquire_instrument_write_guard(session)
    existing = await resolve_instrument_spec(session, payload)
    if existing is not None:
        return existing, False

    if isinstance(payload, StockCreate):
        instrument = Instrument(
            kind=InstrumentKind.STOCK,
            symbol=payload.symbol.strip().upper(),
            currency=payload.currency,
            exchange=payload.exchange,
        )
        session.add(instrument)
        await session.flush()
        return instrument, True

    if isinstance(payload, OptionCreate):
        underlying = await get_or_create_instrument(
            session,
            StockCreate(
                kind="stock",
                symbol=payload.underlying_symbol,
                currency=payload.currency,
                exchange=payload.underlying_exchange,
            ),
        )
        instrument = Instrument(
            kind=InstrumentKind.OPTION,
            symbol=payload.underlying_symbol.strip().upper(),
            currency=payload.currency,
            exchange=payload.underlying_exchange,
        )
        session.add(instrument)
        await session.flush()
        session.add(
            OptionContract(
                instrument_id=instrument.id,
                underlying_id=underlying[0].id,
                opt_type=payload.opt_type,
                strike=payload.strike,
                expiry=payload.expiry,
                multiplier=payload.multiplier,
                style=payload.style,
            )
        )
        await session.flush()
        return instrument, True

    instrument = Instrument(
        kind=InstrumentKind.FOREX,
        symbol=payload.symbol.strip().upper(),
        currency=payload.quote_currency,
    )
    session.add(instrument)
    await session.flush()
    session.add(
        ForexPair(
            instrument_id=instrument.id,
            base_currency=payload.base_currency,
            quote_currency=payload.quote_currency,
            pip_size=payload.pip_size,
            contract_size=payload.contract_size,
        )
    )
    await session.flush()
    return instrument, True
