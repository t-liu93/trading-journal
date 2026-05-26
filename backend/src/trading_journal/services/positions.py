"""Position service layer — business logic separated from the router.

P8 introduces ``freeze_pnl_realized`` (sums Trade cash flows on close).
A future auto-close detector will also live here.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.position import Position
from trading_journal.models.trade import Trade


async def freeze_pnl_realized(session: AsyncSession, position: Position) -> Decimal:
    """Sum ``cash_flow`` over all Trade rows for *position*; assign to
    ``position.pnl_realized``; return the value.  Caller commits.
    """
    stmt = select(func.coalesce(func.sum(Trade.cash_flow), 0)).where(
        Trade.position_id == position.id,
    )
    total: Decimal = (await session.execute(stmt)).scalar_one()
    position.pnl_realized = total
    return total


async def detect_auto_close(session: AsyncSession, position: Position) -> bool:
    """Reserved for a future auto-close detector.  P8 does not implement.
    Routers do not call this yet."""
    raise NotImplementedError
