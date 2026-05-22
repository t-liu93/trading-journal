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
from trading_journal.models.instrument import Instrument
from trading_journal.models.user import User
from trading_journal.schemas.instrument import InstrumentCreate, InstrumentRead

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
) -> Instrument:
    # P6.1: stock only. P6.2/P6.3 add option/forex branches.
    instrument, created = await _get_or_create_stock(
        session,
        symbol=payload.symbol,
        currency=payload.currency,
        exchange=payload.exchange,
    )
    await session.commit()
    await session.refresh(instrument)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return instrument


@router.get("", response_model=list[InstrumentRead])
async def list_instruments(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    kind: InstrumentKind | None = _kind_param,
    q: str | None = _q_param,
    limit: int = _limit_param,
) -> list[Instrument]:
    stmt = select(Instrument).order_by(Instrument.symbol, Instrument.created_at).limit(limit)
    if kind is not None:
        stmt = stmt.where(Instrument.kind == kind)
    if q is not None:
        stmt = stmt.where(Instrument.symbol.ilike(f"{q}%"))
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{instrument_id}", response_model=InstrumentRead)
async def get_instrument(
    instrument_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Instrument:
    instrument = await session.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found")
    return instrument
