"""TradePlan service layer — revision number allocation (P11)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.trade_plan import TradePlan


async def allocate_next_revision_no(
    session: AsyncSession, position_id: uuid.UUID
) -> int:
    """Return ``MAX(revision_no) + 1`` for *position_id*, or 1 if no prior
    revisions exist.

    Concurrency note: the unique ``(position_id, revision_no)`` constraint
    on ``trade_plans`` is the authoritative serializer. If two concurrent
    appends compute the same next number, the second INSERT raises
    IntegrityError; the router catches it and either retries once or
    surfaces 503. Single-user MVP makes this essentially unreachable.
    """
    stmt = select(func.max(TradePlan.revision_no)).where(
        TradePlan.position_id == position_id
    )
    current = (await session.execute(stmt)).scalar()
    return 1 if current is None else current + 1
