"""Position service layer — business logic separated from the router.

P8 introduces ``freeze_pnl_realized`` (sums Trade cash flows on close).
P12 adds ``compute_net_cash_flows`` for read-time derived aggregation.
"""

import uuid
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import PositionStatus, StrategyType
from trading_journal.models.instrument import Instrument
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade
from trading_journal.services.datetimes import to_utc_naive
from trading_journal.services.ownership import resolve_owned_account


async def freeze_pnl_realized(session: AsyncSession, position: Position) -> Decimal:
    """Sum ``cash_flow`` over non-archived Trade rows for *position*; assign to
    ``position.pnl_realized``; return the value.  Caller commits.
    Archived trades are excluded so that frozen pnl_realized stays consistent
    with the read-time net_cash_flow (P12 invariant).
    """
    stmt = select(func.coalesce(func.sum(Trade.cash_flow), 0)).where(
        Trade.position_id == position.id,
        Trade.archived_at.is_(None),
    )
    total: Decimal = (await session.execute(stmt)).scalar_one()
    position.pnl_realized = total
    return total


async def latest_trade_executed_at(
    session: AsyncSession, position: Position
) -> datetime | None:
    """Return MAX(``executed_at``) over non-archived Trade rows for *position*,
    or ``None`` when the position has no non-archived trades.

    Used on close to set ``position.closed_at`` to the moment the last fill
    completed — symmetric with ``opened_at`` being derived from the first fill
    (see PositionFormModal). This keeps the derived ``days_held`` tied to the
    actual holding period rather than the instant the user clicked "Close".
    Archived trades are excluded for consistency with the pnl_realized /
    net_cash_flow aggregates (P12 invariant).
    """
    stmt = select(func.max(Trade.executed_at)).where(
        Trade.position_id == position.id,
        Trade.archived_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def earliest_active_trade_executed_at(
    session: AsyncSession, position: Position
) -> datetime | None:
    """Return MIN executed_at for active fills, or None when there are none."""
    stmt = select(func.min(Trade.executed_at)).where(
        Trade.position_id == position.id,
        Trade.archived_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def maintain_opened_at_from_active_trades(
    session: AsyncSession, position: Position
) -> datetime | None:
    """Set opening date to the earliest active fill, preserving it for an empty set."""
    earliest = await earliest_active_trade_executed_at(session, position)
    if earliest is not None:
        position.opened_at = earliest
    return earliest


async def compute_net_cash_flows(
    session: AsyncSession,
    position_ids: Iterable[uuid.UUID],
) -> dict[uuid.UUID, Decimal]:
    """Return {position_id: SUM(trade.cash_flow)} for the given positions,
    excluding archived trades. Positions with no non-archived trades are
    NOT in the returned dict — callers should default missing entries to
    Decimal("0").

    Single SQL query: SELECT position_id, SUM(cash_flow) FROM trades
    WHERE position_id IN (...) AND archived_at IS NULL GROUP BY position_id.
    """
    ids = list(position_ids)
    if not ids:
        return {}

    stmt = (
        select(Trade.position_id, func.sum(Trade.cash_flow).label("total"))
        .where(Trade.position_id.in_(ids), Trade.archived_at.is_(None))
        .group_by(Trade.position_id)
    )
    rows = (await session.execute(stmt)).all()
    return {row.position_id: row.total for row in rows}


async def create_position(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    primary_instrument_id: uuid.UUID,
    strategy_type: StrategyType,
    opened_at: datetime,
    capital_used: Decimal | None = None,
    max_risk_at_open: Decimal | None = None,
    max_reward_at_open: Decimal | None = None,
    notes: str | None = None,
) -> Position:
    """Validate references and construct an open Position; caller commits."""
    await resolve_owned_account(session, user_id, account_id)
    instrument = await session.get(Instrument, primary_instrument_id)
    if instrument is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Instrument not found")
    position = Position(
        user_id=user_id,
        account_id=account_id,
        primary_instrument_id=primary_instrument_id,
        strategy_type=strategy_type,
        status=PositionStatus.OPEN,
        opened_at=to_utc_naive(opened_at),
        capital_used=capital_used,
        max_risk_at_open=max_risk_at_open,
        max_reward_at_open=max_reward_at_open,
        currency=instrument.currency,
        notes=notes,
    )
    session.add(position)
    await session.flush()
    return position


async def detect_auto_close(session: AsyncSession, position: Position) -> bool:
    """Reserved for a future auto-close detector.  P8 does not implement.
    Routers do not call this yet."""
    raise NotImplementedError
