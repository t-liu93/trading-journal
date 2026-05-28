"""Position service layer — business logic separated from the router.

P8 introduces ``freeze_pnl_realized`` (sums Trade cash flows on close).
P12 adds ``compute_net_cash_flows`` for read-time derived aggregation.
"""

import uuid
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.position import Position
from trading_journal.models.trade import Trade


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


async def detect_auto_close(session: AsyncSession, position: Position) -> bool:
    """Reserved for a future auto-close detector.  P8 does not implement.
    Routers do not call this yet."""
    raise NotImplementedError
