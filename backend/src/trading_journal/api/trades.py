"""``Trade`` CRUD endpoints (data-model.md §4.5, P9).

Ownership rule: every endpoint scopes through ``Position.user_id``.
Trade has no direct ``user_id`` — cross-user ``position_id`` -> 404.

Key design choices:
  - POST accepts a single object or a non-empty array (multi-leg).
  - ``cash_flow`` is server-computed; ``account_id`` is server-derived.
  - DELETE is soft-delete via ``archived_at``.
  - PATCH allows only ``notes`` changes.
  - Closed-position lock: POST/PATCH/DELETE return 409 when parent is closed.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.deps import current_active_user
from trading_journal.db import get_session
from trading_journal.models._enums import PositionStatus
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade
from trading_journal.models.user import User
from trading_journal.schemas.trade import TradeCreate, TradeRead, TradeUpdate
from trading_journal.services.trades import create_trades_atomic

router = APIRouter(prefix="/trades", tags=["trades"])


async def _resolve_position(
    session: AsyncSession, user: User, position_id: uuid.UUID
) -> Position:
    stmt = select(Position).where(
        Position.id == position_id, Position.user_id == user.id
    )
    pos = (await session.execute(stmt)).scalar_one_or_none()
    if pos is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    return pos


async def _get_owned_trade(
    session: AsyncSession, user: User, trade_id: uuid.UUID
) -> Trade:
    stmt = (
        select(Trade)
        .join(Position, Trade.position_id == Position.id)
        .where(Trade.id == trade_id, Position.user_id == user.id)
    )
    trade = (await session.execute(stmt)).scalar_one_or_none()
    if trade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    return trade


def _normalize_payload(
    body: TradeCreate | list[TradeCreate],
) -> tuple[list[TradeCreate], bool]:
    """Return ``(rows, was_array)``. Empty array -> 422."""
    if isinstance(body, list):
        if not body:
            raise HTTPException(status_code=422, detail="trade array must be non-empty")
        return body, True
    return [body], False


_CLOSED_POSITION_MSG = "parent position is closed; trades on closed positions are immutable"


@router.post(
    "",
    response_model=list[TradeRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_trades(
    body: TradeCreate | list[TradeCreate],
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Trade]:
    rows, was_array = _normalize_payload(body)

    # All rows must share the same position_id.
    distinct_positions = {row.position_id for row in rows}
    if len(distinct_positions) > 1:
        raise HTTPException(
            status_code=422,
            detail="all rows in a multi-leg POST must share the same position_id",
        )

    # order_group_id: if any row supplies it, all must agree.
    supplied_ogids = {row.order_group_id for row in rows if row.order_group_id}
    if len(supplied_ogids) > 1:
        raise HTTPException(
            status_code=422,
            detail="rows in a multi-leg POST must share order_group_id",
        )
    if supplied_ogids:
        group_id = supplied_ogids.pop()
    elif was_array and len(rows) > 1:
        group_id = uuid.uuid4()
    else:
        group_id = None
    for row in rows:
        row.order_group_id = group_id

    position = await _resolve_position(session, user, rows[0].position_id)
    if position.status is PositionStatus.CLOSED:
        raise HTTPException(status_code=409, detail=_CLOSED_POSITION_MSG)

    try:
        trades = await create_trades_atomic(session, position, rows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await session.commit()
    return trades


@router.get("", response_model=list[TradeRead])
async def list_trades(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    position_id: uuid.UUID | None = None,
    order_group_id: uuid.UUID | None = None,
    include_archived: bool = False,
) -> list[Trade]:
    if position_id is not None:
        await _resolve_position(session, user, position_id)

    stmt = (
        select(Trade)
        .join(Position, Trade.position_id == Position.id)
        .where(Position.user_id == user.id)
        .order_by(Trade.executed_at.desc(), Trade.id.asc())
    )
    if not include_archived:
        stmt = stmt.where(Trade.archived_at.is_(None))
    if position_id is not None:
        stmt = stmt.where(Trade.position_id == position_id)
    if order_group_id is not None:
        stmt = stmt.where(Trade.order_group_id == order_group_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{trade_id}", response_model=TradeRead)
async def get_trade(
    trade_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Trade:
    return await _get_owned_trade(session, user, trade_id)


@router.patch("/{trade_id}", response_model=TradeRead)
async def update_trade(
    trade_id: uuid.UUID,
    payload: TradeUpdate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Trade:
    trade = await _get_owned_trade(session, user, trade_id)

    if trade.archived_at is not None:
        raise HTTPException(status_code=409, detail="cannot modify an archived trade")

    position = await _resolve_position(session, user, trade.position_id)
    if position.status is PositionStatus.CLOSED:
        raise HTTPException(status_code=409, detail=_CLOSED_POSITION_MSG)

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(trade, field, value)

    await session.commit()
    await session.refresh(trade)
    return trade


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(
    trade_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    trade = await _get_owned_trade(session, user, trade_id)

    if trade.archived_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade already archived")

    position = await _resolve_position(session, user, trade.position_id)
    if position.status is PositionStatus.CLOSED:
        raise HTTPException(status_code=409, detail=_CLOSED_POSITION_MSG)

    from sqlalchemy import func

    trade.archived_at = func.now()
    await session.commit()
