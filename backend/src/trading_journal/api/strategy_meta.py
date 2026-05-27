"""Strategy-meta CRUD endpoints — nested under ``/positions/{pid}/…`` (P10).

Eight endpoints: four for ``WheelCycleMeta``, four for ``PmccCycleMeta``.
All are owner-scoped via the parent ``Position.user_id``.

Key design choices (settled decisions from the P10 plan):
  - Nested sub-resource URLs — no flat collection.
  - Strict ``strategy_type`` matching — wheel meta only on wheel positions,
    PMCC meta only on PMCC positions.
  - PMCC LEAP triple-validation on POST and PATCH.
  - Closed-position is NOT a lock for meta writes.
  - POST is create-only (409 if already exists); PATCH is the amend path.
  - DELETE is hard delete (no soft-delete column on meta tables).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.deps import current_active_user
from trading_journal.db import get_session
from trading_journal.models._enums import StrategyType
from trading_journal.models.position import Position
from trading_journal.models.strategy_meta import PmccCycleMeta, WheelCycleMeta
from trading_journal.models.user import User
from trading_journal.schemas.strategy_meta import (
    PmccMetaCreate,
    PmccMetaRead,
    PmccMetaUpdate,
    WheelMetaCreate,
    WheelMetaRead,
    WheelMetaUpdate,
)
from trading_journal.services.strategy_meta import (
    validate_leap_instrument,
    validate_strategy_type_match,
)

router = APIRouter(prefix="/positions", tags=["strategy-meta"])


# ─────────────────── Helpers ───────────────────


async def _resolve_position(
    session: AsyncSession, user: User, position_id: uuid.UUID
) -> Position:
    stmt = select(Position).where(
        Position.id == position_id, Position.user_id == user.id
    )
    pos = (await session.execute(stmt)).scalar_one_or_none()
    if pos is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Position not found")
    return pos


async def _get_wheel_meta_or_404(
    session: AsyncSession, position_id: uuid.UUID
) -> WheelCycleMeta:
    meta = await session.get(WheelCycleMeta, position_id)
    if meta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Wheel meta not found")
    return meta


async def _get_pmcc_meta_or_404(
    session: AsyncSession, position_id: uuid.UUID
) -> PmccCycleMeta:
    meta = await session.get(PmccCycleMeta, position_id)
    if meta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PMCC meta not found")
    return meta


# ─────────────────── WheelCycleMeta ───────────────────


@router.post(
    "/{position_id}/wheel-meta",
    response_model=WheelMetaRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_wheel_meta(
    position_id: uuid.UUID,
    payload: WheelMetaCreate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WheelCycleMeta:
    pos = await _resolve_position(session, user, position_id)
    try:
        validate_strategy_type_match(pos, StrategyType.WHEEL)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    existing = await session.get(WheelCycleMeta, position_id)
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "meta already exists for this position; use PATCH",
        )

    meta = WheelCycleMeta(
        position_id=position_id,
        funding_source=payload.funding_source,
        loan_amount=payload.loan_amount,
        interest_rate_apr=payload.interest_rate_apr,
        interest_accrued=payload.interest_accrued,
    )
    session.add(meta)
    await session.commit()
    await session.refresh(meta)
    return meta


@router.get(
    "/{position_id}/wheel-meta",
    response_model=WheelMetaRead,
)
async def get_wheel_meta(
    position_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WheelCycleMeta:
    await _resolve_position(session, user, position_id)
    return await _get_wheel_meta_or_404(session, position_id)


@router.patch(
    "/{position_id}/wheel-meta",
    response_model=WheelMetaRead,
)
async def update_wheel_meta(
    position_id: uuid.UUID,
    payload: WheelMetaUpdate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WheelCycleMeta:
    await _resolve_position(session, user, position_id)
    meta = await _get_wheel_meta_or_404(session, position_id)
    data = payload.model_dump(exclude_unset=True)
    if "funding_source" in data and data["funding_source"] is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "funding_source cannot be null",
        )
    for field, value in data.items():
        setattr(meta, field, value)
    await session.commit()
    await session.refresh(meta)
    return meta


@router.delete(
    "/{position_id}/wheel-meta",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wheel_meta(
    position_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await _resolve_position(session, user, position_id)
    meta = await _get_wheel_meta_or_404(session, position_id)
    await session.delete(meta)
    await session.commit()


# ─────────────────── PmccCycleMeta ───────────────────


@router.post(
    "/{position_id}/pmcc-meta",
    response_model=PmccMetaRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_pmcc_meta(
    position_id: uuid.UUID,
    payload: PmccMetaCreate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PmccCycleMeta:
    pos = await _resolve_position(session, user, position_id)
    try:
        validate_strategy_type_match(pos, StrategyType.PMCC)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    try:
        await validate_leap_instrument(session, pos, payload.leap_instrument_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    existing = await session.get(PmccCycleMeta, position_id)
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "meta already exists for this position; use PATCH",
        )

    meta = PmccCycleMeta(
        position_id=position_id,
        leap_instrument_id=payload.leap_instrument_id,
    )
    session.add(meta)
    await session.commit()
    await session.refresh(meta)
    return meta


@router.get(
    "/{position_id}/pmcc-meta",
    response_model=PmccMetaRead,
)
async def get_pmcc_meta(
    position_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PmccCycleMeta:
    await _resolve_position(session, user, position_id)
    return await _get_pmcc_meta_or_404(session, position_id)


@router.patch(
    "/{position_id}/pmcc-meta",
    response_model=PmccMetaRead,
)
async def update_pmcc_meta(
    position_id: uuid.UUID,
    payload: PmccMetaUpdate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PmccCycleMeta:
    await _resolve_position(session, user, position_id)
    meta = await _get_pmcc_meta_or_404(session, position_id)
    data = payload.model_dump(exclude_unset=True)
    if "leap_instrument_id" in data and data["leap_instrument_id"] is not None:
        pos = await _resolve_position(session, user, position_id)
        try:
            await validate_leap_instrument(
                session, pos, data["leap_instrument_id"]
            )
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)
            ) from exc
    if "leap_instrument_id" in data and data["leap_instrument_id"] is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "leap_instrument_id cannot be null",
        )
    for field, value in data.items():
        setattr(meta, field, value)
    await session.commit()
    await session.refresh(meta)
    return meta


@router.delete(
    "/{position_id}/pmcc-meta",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_pmcc_meta(
    position_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await _resolve_position(session, user, position_id)
    meta = await _get_pmcc_meta_or_404(session, position_id)
    await session.delete(meta)
    await session.commit()
