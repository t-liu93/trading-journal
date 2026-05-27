"""TradePlan CRUD endpoints — append-only event stream (P11).

Four endpoints: POST (append), GET list, GET current, GET by revision_no.
No PATCH, no DELETE — revisions are permanent.

Key design choices (settled decisions from the P11 plan):
  - Nested sub-resource URLs under ``/positions/{pid}/trade-plans``.
  - Server-allocated revision_no via MAX+1 per position.
  - GET list ordered oldest-first (revision_no ASC).
  - No strategy_type restriction.
  - Closed-position is NOT a lock for TradePlan writes.
  - Owner-scoped via Position.user_id.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.deps import current_active_user
from trading_journal.db import get_session
from trading_journal.models.position import Position
from trading_journal.models.trade_plan import TradePlan
from trading_journal.models.user import User
from trading_journal.schemas.trade_plan import TradePlanCreate, TradePlanRead
from trading_journal.services.trade_plans import allocate_next_revision_no

router = APIRouter(prefix="/positions", tags=["trade-plans"])


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


# ─────────────────── Endpoints ───────────────────


@router.post(
    "/{position_id}/trade-plans",
    response_model=TradePlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_trade_plan(
    position_id: uuid.UUID,
    payload: TradePlanCreate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TradePlan:
    await _resolve_position(session, user, position_id)

    revision_no = await allocate_next_revision_no(session, position_id)
    plan = TradePlan(
        position_id=position_id,
        revision_no=revision_no,
        effective_at=payload.effective_at,
        planned_entry=payload.planned_entry,
        planned_stop_loss=payload.planned_stop_loss,
        planned_take_profit=payload.planned_take_profit,
        target_rr=payload.target_rr,
        thesis=payload.thesis,
        reason=payload.reason,
    )
    session.add(plan)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # Retry once with a fresh allocation
        revision_no = await allocate_next_revision_no(session, position_id)
        plan.revision_no = revision_no
        session.add(plan)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "concurrent revision allocation failed; please retry",
            ) from None
    await session.refresh(plan)
    return plan


@router.get(
    "/{position_id}/trade-plans",
    response_model=list[TradePlanRead],
)
async def list_trade_plans(
    position_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TradePlan]:
    await _resolve_position(session, user, position_id)
    stmt = (
        select(TradePlan)
        .where(TradePlan.position_id == position_id)
        .order_by(TradePlan.revision_no.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get(
    "/{position_id}/trade-plans/current",
    response_model=TradePlanRead,
)
async def get_current_trade_plan(
    position_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TradePlan:
    await _resolve_position(session, user, position_id)
    stmt = (
        select(TradePlan)
        .where(TradePlan.position_id == position_id)
        .order_by(TradePlan.revision_no.desc())
        .limit(1)
    )
    plan = (await session.execute(stmt)).scalar_one_or_none()
    if plan is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "no current plan; append one first",
        )
    return plan


@router.get(
    "/{position_id}/trade-plans/{revision_no}",
    response_model=TradePlanRead,
)
async def get_trade_plan_by_revision(
    position_id: uuid.UUID,
    revision_no: int,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TradePlan:
    await _resolve_position(session, user, position_id)
    stmt = select(TradePlan).where(
        TradePlan.position_id == position_id,
        TradePlan.revision_no == revision_no,
    )
    plan = (await session.execute(stmt)).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revision not found")
    return plan
