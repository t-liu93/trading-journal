"""Bounded, ownership-scoped queries used by the MCP journal tools."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import InstrumentKind, OptType, PositionStatus, StrategyType
from trading_journal.models.account import Account
from trading_journal.models.instrument import Instrument, OptionContract
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade
from trading_journal.services.instruments import current_utc_date
from trading_journal.services.ownership import resolve_owned_position
from trading_journal.services.positions import compute_net_cash_flows

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _page(limit: int, offset: int) -> None:
    fields = []
    if not 1 <= limit <= MAX_PAGE_SIZE:
        fields.append({"path": "limit", "message": "must be between 1 and 200"})
    if offset < 0:
        fields.append({"path": "offset", "message": "must be nonnegative"})
    if fields:
        raise HTTPException(status_code=422, detail={"code": "invalid_fields", "fields": fields})


async def _fetch_page[T](
    session: AsyncSession, stmt: Select[tuple[T]], *, limit: int, offset: int
) -> tuple[list[T], bool]:
    _page(limit, offset)
    rows = list((await session.execute(stmt.offset(offset).limit(limit + 1))).scalars().all())
    return rows[:limit], len(rows) > limit


async def list_accounts(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    include_archived: bool = False,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> tuple[list[Account], bool]:
    stmt = select(Account).where(Account.user_id == user_id).order_by(Account.name, Account.id)
    if not include_archived:
        stmt = stmt.where(Account.archived_at.is_(None))
    rows, more = await _fetch_page(session, stmt, limit=limit, offset=offset)
    return rows, more


async def search_instruments(
    session: AsyncSession,
    *,
    kind: InstrumentKind | None = None,
    symbol: str | None = None,
    currency: str | None = None,
    exchange: str | None = None,
    option_underlying_id: uuid.UUID | None = None,
    expiry: date | None = None,
    strike: Decimal | None = None,
    opt_type: OptType | None = None,
    include_expired: bool = True,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> tuple[list[Instrument], bool]:
    stmt = select(Instrument)
    if kind is not None:
        stmt = stmt.where(Instrument.kind == kind)
    if symbol is not None:
        stmt = stmt.where(Instrument.symbol.ilike(f"{symbol.strip()}%"))
    if currency is not None:
        stmt = stmt.where(Instrument.currency == currency)
    if exchange is not None:
        stmt = stmt.where(Instrument.exchange == exchange)
    option_identity_filters = []
    if option_underlying_id is not None:
        option_identity_filters.append(OptionContract.underlying_id == option_underlying_id)
    if expiry is not None:
        option_identity_filters.append(OptionContract.expiry == expiry)
    if strike is not None:
        option_identity_filters.append(OptionContract.strike == strike)
    if opt_type is not None:
        option_identity_filters.append(OptionContract.opt_type == opt_type)

    # Explicit option identity filters describe option contracts and must not
    # let stock/forex rows bypass them. The expiry visibility switch alone is
    # intentionally different: it hides expired options while keeping the
    # mixed instrument list used by the REST picker.
    if option_identity_filters:
        option_ids = select(OptionContract.instrument_id).where(*option_identity_filters)
        stmt = stmt.where(Instrument.kind == InstrumentKind.OPTION)
        if not include_expired:
            option_ids = option_ids.where(OptionContract.expiry >= current_utc_date())
        stmt = stmt.where(Instrument.id.in_(option_ids))
    elif not include_expired:
        active_option_ids = select(OptionContract.instrument_id).where(
            OptionContract.expiry >= current_utc_date()
        )
        stmt = stmt.where(
            (Instrument.kind != InstrumentKind.OPTION)
            | Instrument.id.in_(active_option_ids)
        )
    stmt = stmt.order_by(Instrument.symbol, Instrument.created_at, Instrument.id)
    rows, more = await _fetch_page(session, stmt, limit=limit, offset=offset)
    return rows, more


async def list_positions(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID | None = None,
    primary_instrument_id: uuid.UUID | None = None,
    strategy_type: StrategyType | None = None,
    position_status: PositionStatus | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> tuple[list[Position], bool]:
    stmt = select(Position).where(Position.user_id == user_id)
    if account_id is not None:
        stmt = stmt.where(Position.account_id == account_id)
    if primary_instrument_id is not None:
        stmt = stmt.where(Position.primary_instrument_id == primary_instrument_id)
    if strategy_type is not None:
        stmt = stmt.where(Position.strategy_type == strategy_type)
    if position_status is not None:
        stmt = stmt.where(Position.status == position_status)
    stmt = stmt.order_by(Position.opened_at.desc(), Position.created_at.desc(), Position.id)
    rows, more = await _fetch_page(session, stmt, limit=limit, offset=offset)
    positions = rows
    cash_flows = await compute_net_cash_flows(session, [position.id for position in positions])
    for position in positions:
        cast(Any, position).net_cash_flow = cash_flows.get(position.id, Decimal("0"))
    return positions, more


async def get_position(
    session: AsyncSession, user_id: uuid.UUID, position_id: uuid.UUID
) -> tuple[Position, Instrument, Decimal]:
    position = await resolve_owned_position(session, user_id, position_id)
    instrument = await session.get(Instrument, position.primary_instrument_id)
    if instrument is None:
        raise ValueError("position primary instrument is missing")
    cash_flow = (await compute_net_cash_flows(session, [position.id])).get(
        position.id, Decimal("0")
    )
    return position, instrument, cash_flow


async def list_trades(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    position_id: uuid.UUID,
    include_archived: bool = False,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> tuple[list[Trade], bool]:
    await resolve_owned_position(session, user_id, position_id)
    stmt = select(Trade).where(Trade.position_id == position_id)
    if not include_archived:
        stmt = stmt.where(Trade.archived_at.is_(None))
    stmt = stmt.order_by(Trade.executed_at.desc(), Trade.id)
    rows, more = await _fetch_page(session, stmt, limit=limit, offset=offset)
    return rows, more
