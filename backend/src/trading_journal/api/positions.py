"""``Position`` CRUD endpoints (data-model.md §4.4, P8).

Ownership rule: every endpoint scopes by ``current_active_user.id``.
Cross-user access returns 404 (not 403) — same as Account / StrategyConfig.

Key design choices:
  - POST sets ``status="open"`` and derives ``currency`` from
    ``primary_instrument.currency``.
  - PATCH with ``status: "closed"`` triggers ``freeze_pnl_realized`` which
    sums all attached Trade ``cash_flow`` rows.
  - DELETE is a hard delete that only succeeds when the position has zero
    attached Trade rows.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.deps import current_active_user
from trading_journal.db import get_session
from trading_journal.models._enums import PositionStatus, StrategyType
from trading_journal.models.account import Account
from trading_journal.models.instrument import Instrument
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade
from trading_journal.models.user import User
from trading_journal.schemas.position import PositionCreate, PositionRead, PositionUpdate
from trading_journal.services.positions import freeze_pnl_realized

router = APIRouter(prefix="/positions", tags=["positions"])


async def _get_owned_position(
    session: AsyncSession, user: User, position_id: uuid.UUID
) -> Position:
    stmt = select(Position).where(
        Position.id == position_id, Position.user_id == user.id
    )
    pos = (await session.execute(stmt)).scalar_one_or_none()
    if pos is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    return pos


async def _resolve_account(
    session: AsyncSession, user: User, account_id: uuid.UUID
) -> Account:
    stmt = select(Account).where(
        Account.id == account_id,
        Account.user_id == user.id,
        Account.archived_at.is_(None),
    )
    acct = (await session.execute(stmt)).scalar_one_or_none()
    if acct is None:
        raise HTTPException(status_code=422, detail="Account not found or archived")
    return acct


async def _resolve_instrument(
    session: AsyncSession, instrument_id: uuid.UUID
) -> Instrument:
    inst = await session.get(Instrument, instrument_id)
    if inst is None:
        raise HTTPException(status_code=422, detail="Instrument not found")
    return inst


@router.post(
    "",
    response_model=PositionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_position(
    payload: PositionCreate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Position:
    await _resolve_account(session, user, payload.account_id)
    instrument = await _resolve_instrument(session, payload.primary_instrument_id)

    position = Position(
        user_id=user.id,
        account_id=payload.account_id,
        primary_instrument_id=payload.primary_instrument_id,
        strategy_type=payload.strategy_type,
        status=PositionStatus.OPEN,
        opened_at=payload.opened_at,
        capital_used=payload.capital_used,
        max_risk_at_open=payload.max_risk_at_open,
        max_reward_at_open=payload.max_reward_at_open,
        currency=instrument.currency,
        notes=payload.notes,
    )
    session.add(position)
    await session.commit()
    await session.refresh(position)
    return position


@router.get("", response_model=list[PositionRead])
async def list_positions(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status: PositionStatus | None = None,
    strategy_type: StrategyType | None = None,
) -> list[Position]:
    stmt = (
        select(Position)
        .where(Position.user_id == user.id)
        .order_by(Position.opened_at.desc(), Position.created_at.desc())
    )
    if status is not None:
        stmt = stmt.where(Position.status == status)
    if strategy_type is not None:
        stmt = stmt.where(Position.strategy_type == strategy_type)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{position_id}", response_model=PositionRead)
async def get_position(
    position_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Position:
    return await _get_owned_position(session, user, position_id)


@router.patch("/{position_id}", response_model=PositionRead)
async def update_position(
    position_id: uuid.UUID,
    payload: PositionUpdate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Position:
    position = await _get_owned_position(session, user, position_id)
    data = payload.model_dump(exclude_unset=True)

    # Reject explicit status=null (NOT NULL column).
    if "status" in data and data["status"] is None:
        raise HTTPException(
            status_code=422,
            detail="status cannot be null",
        )

    # Reject closed_at without status flip (and not already closed).
    if "closed_at" in data and data.get("status") != PositionStatus.CLOSED \
            and position.status != PositionStatus.CLOSED:
        raise HTTPException(
            status_code=422,
            detail="closed_at can only be set on closed positions",
        )

    # Reject clearing closed_at on a closed position.
    if "closed_at" in data and data["closed_at"] is None:
        will_be_closed = (
            data.get("status") == PositionStatus.CLOSED
            or (data.get("status") is None and position.status == PositionStatus.CLOSED)
        )
        if will_be_closed:
            raise HTTPException(
                status_code=422,
                detail="closed_at cannot be null on a closed position",
            )

    # Reject closed -> open.
    if "status" in data and position.status == PositionStatus.CLOSED \
            and data["status"] == PositionStatus.OPEN:
        raise HTTPException(
            status_code=422,
            detail="reopening a closed position is not supported",
        )

    transitioning_to_closed = (
        "status" in data
        and data["status"] == PositionStatus.CLOSED
        and position.status != PositionStatus.CLOSED
    )

    for field, value in data.items():
        setattr(position, field, value)

    if transitioning_to_closed:
        if position.closed_at is None:
            raise HTTPException(
                status_code=422,
                detail="closed_at is required when closing",
            )
        await freeze_pnl_realized(session, position)

    await session.commit()
    await session.refresh(position)
    return position


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(
    position_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    position = await _get_owned_position(session, user, position_id)

    trade_count = (
        await session.execute(
            select(Trade.id).where(Trade.position_id == position.id).limit(1)
        )
    ).scalar_one_or_none()
    if trade_count is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="position has attached trades; delete the trades first or archive via PATCH",
        )

    await session.delete(position)
    await session.commit()
