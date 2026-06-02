"""Dashboard service layer — read-time aggregation (P12)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import PositionStatus
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade
from trading_journal.schemas.dashboard import (
    ClosedSummary,
    CurrencyAmount,
    DashboardSummary,
    MonthCurrencyAmount,
    OpenSummary,
)


def _utc_month_key(dt: datetime) -> str:
    """Extract YYYY-MM from a datetime, normalizing to UTC first."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC)
    return dt.strftime("%Y-%m")


async def compute_summary(
    session: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID | None = None,
) -> DashboardSummary:
    """Return the V1 dashboard summary for a given user.

    All queries scope by ``Position.user_id == user_id``; when ``account_id`` is
    given they are further narrowed to that account (the ``user_id`` filter still
    applies, so a foreign account id simply yields an empty summary rather than
    leaking another user's data). Archived trades are excluded from open-side
    net_cash_flow rollups (closed-side uses Position.pnl_realized directly, which
    was already computed with the correct trade set frozen at close).
    """
    # closed: count + win_rate + per_currency_pnl + monthly_pnl
    closed_stmt = (
        select(
            Position.currency,
            Position.pnl_realized,
            Position.closed_at,
        )
        .where(
            Position.user_id == user_id,
            Position.status == PositionStatus.CLOSED,
        )
    )
    if account_id is not None:
        closed_stmt = closed_stmt.where(Position.account_id == account_id)
    closed_rows = (await session.execute(closed_stmt)).all()

    closed_count = len(closed_rows)
    wins = sum(1 for r in closed_rows if (r.pnl_realized or 0) > 0)
    win_rate = (
        Decimal(wins) / Decimal(closed_count) if closed_count > 0 else None
    )

    per_currency_pnl: dict[str, Decimal] = {}
    monthly_pnl: dict[tuple[str, str], Decimal] = {}
    for r in closed_rows:
        amt = r.pnl_realized or Decimal("0")
        per_currency_pnl[r.currency] = per_currency_pnl.get(r.currency, Decimal("0")) + amt
        month_key = _utc_month_key(r.closed_at)
        monthly_pnl[(month_key, r.currency)] = (
            monthly_pnl.get((month_key, r.currency), Decimal("0")) + amt
        )

    # open: count + per_currency_net_cash_flow
    open_stmt = (
        select(
            Position.id,
            Position.currency,
        )
        .where(
            Position.user_id == user_id,
            Position.status == PositionStatus.OPEN,
        )
    )
    if account_id is not None:
        open_stmt = open_stmt.where(Position.account_id == account_id)
    open_rows = (await session.execute(open_stmt)).all()
    open_count = len(open_rows)
    open_position_ids = [r.id for r in open_rows]
    currency_by_position = {r.id: r.currency for r in open_rows}

    # batch SUM(cash_flow) for all open positions in one query
    open_ncf_map: dict[uuid.UUID, Decimal] = {}
    if open_position_ids:
        ncf_stmt = (
            select(Trade.position_id, func.sum(Trade.cash_flow).label("total"))
            .where(
                Trade.position_id.in_(open_position_ids),
                Trade.archived_at.is_(None),
            )
            .group_by(Trade.position_id)
        )
        open_ncf_map = {
            row.position_id: row.total
            for row in (await session.execute(ncf_stmt)).all()
        }

    open_per_currency: dict[str, Decimal] = {}
    for pid, currency in currency_by_position.items():
        amt = open_ncf_map.get(pid, Decimal("0"))
        open_per_currency[currency] = open_per_currency.get(currency, Decimal("0")) + amt

    return DashboardSummary(
        closed=ClosedSummary(
            count=closed_count,
            win_rate=win_rate,
            per_currency_pnl=[
                CurrencyAmount(currency=c, amount=a)
                for c, a in sorted(per_currency_pnl.items())
            ],
            monthly_pnl=[
                MonthCurrencyAmount(month=m, currency=c, amount=a)
                for (m, c), a in sorted(monthly_pnl.items())
            ],
        ),
        open=OpenSummary(
            count=open_count,
            per_currency_net_cash_flow=[
                CurrencyAmount(currency=c, amount=a)
                for c, a in sorted(open_per_currency.items())
            ],
        ),
    )
