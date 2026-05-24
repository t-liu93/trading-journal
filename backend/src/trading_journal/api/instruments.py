"""``Instrument`` CRUD endpoints (data-model.md §4.3, P6).

Instruments are **global** — no ``user_id``. All endpoints still require auth,
but there is no per-user filtering. Every user sees the same dictionary.

Endpoints: GET /instruments (list/search), GET /instruments/{id},
POST /instruments (get-or-create). No PATCH/DELETE.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status  # noqa: A005
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.deps import current_active_user
from trading_journal.db import get_session
from trading_journal.models._enums import InstrumentKind
from trading_journal.models.instrument import ForexPair, Instrument, OptionContract
from trading_journal.models.user import User
from trading_journal.schemas.instrument import (
    ForexCreate,
    ForexPairRead,
    InstrumentCreate,
    InstrumentRead,
    OptionContractRead,
    OptionCreate,
    StockCreate,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])

_kind_param = Query(default=None)
_q_param = Query(default=None)
_limit_param = Query(default=50, ge=1, le=200)


async def _get_or_create_stock(
    session: AsyncSession,
    symbol: str,
    currency: str,
    exchange: str | None,
) -> tuple[Instrument, bool]:
    """Get-or-create a stock instrument. Returns (instrument, created)."""
    normalized = symbol.upper()
    stmt = select(Instrument).where(
        Instrument.kind == InstrumentKind.STOCK,
        Instrument.symbol == normalized,
        Instrument.currency == currency,
    )
    if exchange is not None:
        stmt = stmt.where(Instrument.exchange == exchange)
    else:
        stmt = stmt.where(Instrument.exchange.is_(None))

    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing, False

    instrument = Instrument(
        kind=InstrumentKind.STOCK,
        symbol=normalized,
        currency=currency,
        exchange=exchange,
    )
    session.add(instrument)
    await session.flush()
    return instrument, True


async def _to_read(instrument: Instrument, session: AsyncSession) -> InstrumentRead:
    """Build InstrumentRead, populating extension blocks when applicable."""
    read = InstrumentRead.model_validate(instrument)
    if instrument.kind == InstrumentKind.OPTION:
        oc = await session.get(OptionContract, instrument.id)
        if oc is not None:
            read.option = OptionContractRead.model_validate(oc)
    elif instrument.kind == InstrumentKind.FOREX:
        fp = await session.get(ForexPair, instrument.id)
        if fp is not None:
            read.forex = ForexPairRead.model_validate(fp)
    return read


async def _create_stock(
    payload: StockCreate,
    session: AsyncSession,
) -> tuple[Instrument, bool]:
    return await _get_or_create_stock(
        session,
        symbol=payload.symbol,
        currency=payload.currency,
        exchange=payload.exchange,
    )


async def _create_option(
    payload: OptionCreate,
    session: AsyncSession,
) -> tuple[Instrument, bool]:
    underlying, _ = await _get_or_create_stock(
        session,
        symbol=payload.underlying_symbol,
        currency=payload.currency,
        exchange=payload.underlying_exchange,
    )

    normalized_symbol = payload.underlying_symbol.upper().strip()

    stmt = select(Instrument).join(
        OptionContract, OptionContract.instrument_id == Instrument.id
    ).where(
        OptionContract.underlying_id == underlying.id,
        OptionContract.opt_type == payload.opt_type,
        OptionContract.strike == payload.strike,
        OptionContract.expiry == payload.expiry,
        OptionContract.multiplier == payload.multiplier,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing, False

    instrument = Instrument(
        kind=InstrumentKind.OPTION,
        symbol=normalized_symbol,
        currency=payload.currency,
        exchange=payload.underlying_exchange,
    )
    session.add(instrument)
    await session.flush()

    option_contract = OptionContract(
        instrument_id=instrument.id,
        underlying_id=underlying.id,
        opt_type=payload.opt_type,
        strike=payload.strike,
        expiry=payload.expiry,
        multiplier=payload.multiplier,
        style=payload.style,
    )
    session.add(option_contract)
    await session.flush()
    return instrument, True


async def _create_forex(
    payload: ForexCreate,
    session: AsyncSession,
) -> tuple[Instrument, bool]:
    normalized = payload.symbol.upper().strip()
    currency = payload.quote_currency

    stmt = select(Instrument).where(
        Instrument.kind == InstrumentKind.FOREX,
        Instrument.symbol == normalized,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing, False

    instrument = Instrument(
        kind=InstrumentKind.FOREX,
        symbol=normalized,
        currency=currency,
    )
    session.add(instrument)
    await session.flush()

    forex_pair = ForexPair(
        instrument_id=instrument.id,
        base_currency=payload.base_currency,
        quote_currency=payload.quote_currency,
        pip_size=payload.pip_size,
        contract_size=payload.contract_size,
    )
    session.add(forex_pair)
    await session.flush()
    return instrument, True


@router.post(
    "",
    response_model=InstrumentRead,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_200_OK: {"model": InstrumentRead}},
)
async def create_instrument(
    payload: InstrumentCreate,
    response: Response,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InstrumentRead:
    if isinstance(payload, StockCreate):
        instrument, created = await _create_stock(payload, session)
    elif isinstance(payload, OptionCreate):
        instrument, created = await _create_option(payload, session)
    else:
        instrument, created = await _create_forex(payload, session)

    await session.commit()
    await session.refresh(instrument)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return await _to_read(instrument, session)


@router.get("", response_model=list[InstrumentRead])
async def list_instruments(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    kind: InstrumentKind | None = _kind_param,
    q: str | None = _q_param,
    limit: int = _limit_param,
) -> list[InstrumentRead]:
    stmt = select(Instrument).order_by(Instrument.symbol, Instrument.created_at).limit(limit)
    if kind is not None:
        stmt = stmt.where(Instrument.kind == kind)
    if q is not None:
        stmt = stmt.where(Instrument.symbol.ilike(f"{q}%"))
    result = await session.execute(stmt)
    instruments = list(result.scalars().all())
    reads = []
    for inst in instruments:
        reads.append(await _to_read(inst, session))
    return reads


@router.get("/{instrument_id}", response_model=InstrumentRead)
async def get_instrument(
    instrument_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InstrumentRead:
    instrument = await session.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found")
    return await _to_read(instrument, session)
