"""``Instrument`` CRUD endpoints (data-model.md §4.3, P6).

Instruments are **global** — no ``user_id``. All endpoints still require auth,
but there is no per-user filtering. Every user sees the same dictionary.

Endpoints: GET /instruments (list/search), GET /instruments/{id},
POST /instruments (get-or-create). No PATCH/DELETE.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status  # noqa: A005
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.deps import current_active_user
from trading_journal.db import get_session
from trading_journal.models._enums import InstrumentKind
from trading_journal.models.instrument import Instrument
from trading_journal.models.user import User
from trading_journal.schemas.instrument import (
    InstrumentCreate,
    InstrumentRead,
)
from trading_journal.services.instruments import (
    get_or_create_instrument,
    instrument_read,
)
from trading_journal.services.instruments import (
    list_instruments as query_instruments,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])

_kind_param = Query(default=None)
_q_param = Query(default=None)
_limit_param = Query(default=50, ge=1, le=200)
_offset_param = Query(default=0, ge=0)


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
    try:
        instrument, created = await get_or_create_instrument(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(instrument)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return await instrument_read(session, instrument)


@router.get("", response_model=list[InstrumentRead])
async def list_instruments(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    kind: InstrumentKind | None = _kind_param,
    q: str | None = _q_param,
    limit: int = _limit_param,
    offset: int = _offset_param,
    include_expired: bool = True,
    option_underlying_id: uuid.UUID | None = None,
    related_underlying_id: uuid.UUID | None = None,
) -> list[InstrumentRead]:
    instruments = await query_instruments(
        session,
        kind=kind,
        q=q,
        limit=limit,
        offset=offset,
        include_expired=include_expired,
        option_underlying_id=option_underlying_id,
        related_underlying_id=related_underlying_id,
    )
    reads = []
    for inst in instruments:
        reads.append(await instrument_read(session, inst))
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
    return await instrument_read(session, instrument)
