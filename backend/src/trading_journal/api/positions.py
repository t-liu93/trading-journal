"""``Position`` CRUD endpoints (data-model.md §4.4, P8).

Ownership rule: every endpoint scopes by ``current_active_user.id``.
Cross-user access returns 404 (not 403) — same as Account / StrategyConfig.

Key design choices:
  - POST sets ``status="open"`` and derives ``currency`` from
    ``primary_instrument.currency``.
  - PATCH with ``status: "closed"`` triggers ``freeze_pnl_realized`` which
    sums all attached Trade ``cash_flow`` rows. When ``closed_at`` is omitted
    it is derived from the last fill (MAX Trade ``executed_at``), falling back
    to now() only when the position has no trades; an explicit ``closed_at``
    still wins.
  - DELETE is a hard delete that only succeeds when the position has zero
    attached Trade rows and zero TradePlan revisions.
  - P12: ``net_cash_flow`` is derived at read time and injected into every
    PositionRead response.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
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
from trading_journal.models.trade_plan import TradePlan
from trading_journal.models.user import User
from trading_journal.schemas.position import PositionCreate, PositionRead, PositionUpdate
from trading_journal.services.positions import (
    compute_net_cash_flows,
    freeze_pnl_realized,
    latest_trade_executed_at,
)

router = APIRouter(prefix="/positions", tags=["positions"])


def _to_utc(dt: datetime) -> datetime:
    """Normalize a timezone-aware datetime to UTC (strip tzinfo).

    SQLite/aiosqlite does not preserve timezone offsets, so we normalize
    before storing to ensure consistent month bucketing in aggregation queries.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _position_to_read(pos: Position, net_cash_flow: Decimal) -> PositionRead:
    """Convert a Position ORM object to PositionRead with the derived net_cash_flow."""
    row = {c.key: getattr(pos, c.key) for c in type(pos).__table__.columns}
    row["net_cash_flow"] = net_cash_flow
    return PositionRead.model_validate(row)


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
) -> PositionRead:
    await _resolve_account(session, user, payload.account_id)
    instrument = await _resolve_instrument(session, payload.primary_instrument_id)

    position = Position(
        user_id=user.id,
        account_id=payload.account_id,
        primary_instrument_id=payload.primary_instrument_id,
        strategy_type=payload.strategy_type,
        status=PositionStatus.OPEN,
        opened_at=_to_utc(payload.opened_at),
        capital_used=payload.capital_used,
        max_risk_at_open=payload.max_risk_at_open,
        max_reward_at_open=payload.max_reward_at_open,
        currency=instrument.currency,
        notes=payload.notes,
    )
    session.add(position)
    await session.commit()
    await session.refresh(position)
    return _position_to_read(position, Decimal("0"))


@router.get("", response_model=list[PositionRead])
async def list_positions(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status: PositionStatus | None = None,
    strategy_type: StrategyType | None = None,
) -> list[PositionRead]:
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
    positions = list(result.scalars().all())

    ncf_map = await compute_net_cash_flows(session, [p.id for p in positions])
    return [_position_to_read(p, ncf_map.get(p.id, Decimal("0"))) for p in positions]


@router.get("/{position_id}", response_model=PositionRead)
async def get_position(
    position_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PositionRead:
    position = await _get_owned_position(session, user, position_id)
    ncf_map = await compute_net_cash_flows(session, [position.id])
    return _position_to_read(position, ncf_map.get(position.id, Decimal("0")))


@router.patch("/{position_id}", response_model=PositionRead)
async def update_position(
    position_id: uuid.UUID,
    payload: PositionUpdate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PositionRead:
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

    if "closed_at" in data and data["closed_at"] is not None:
        data["closed_at"] = _to_utc(data["closed_at"])

    for field, value in data.items():
        setattr(position, field, value)

    if transitioning_to_closed:
        if position.closed_at is None:
            # Derive the close date from the last fill (symmetric with
            # opened_at = first fill). Fall back to now() only when the
            # position has no trades to anchor the date to.
            last_executed = await latest_trade_executed_at(session, position)
            position.closed_at = (
                last_executed
                if last_executed is not None
                else _to_utc(datetime.now(UTC))
            )
        await freeze_pnl_realized(session, position)

    await session.commit()
    await session.refresh(position)
    ncf_map = await compute_net_cash_flows(session, [position.id])
    return _position_to_read(position, ncf_map.get(position.id, Decimal("0")))


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
            detail=(
                "position has attached trades and cannot be deleted; "
                "trades are retained for audit even if archived"
            ),
        )

    plan_count = (
        await session.execute(
            select(TradePlan.id).where(TradePlan.position_id == position.id).limit(1)
        )
    ).scalar_one_or_none()
    if plan_count is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "position has attached plan revisions and cannot be deleted; "
                "trade plans are append-only and permanently retained"
            ),
        )

    await session.delete(position)
    await session.commit()
