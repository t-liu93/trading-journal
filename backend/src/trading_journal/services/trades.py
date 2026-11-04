"""Trade service layer — cash-flow formula and action-kind guards (P9)."""

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import InstrumentKind, TradeAction
from trading_journal.models.instrument import Instrument, OptionContract
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade
from trading_journal.schemas.trade import TradeCreate
from trading_journal.services.datetimes import to_utc_naive

_SELL_SIDE_ACTIONS = {TradeAction.SELL, TradeAction.STO, TradeAction.STC}
_OPTION_ACTIONS = {TradeAction.BTO, TradeAction.STO, TradeAction.BTC, TradeAction.STC}
_NONOPTION_ACTIONS = {TradeAction.BUY, TradeAction.SELL}


def normalize_order_group_ids(
    order_group_ids: Sequence[uuid.UUID | None], *, generate_for_multiple: bool
) -> list[uuid.UUID | None]:
    """Apply the shared REST/entry semantics for a batch of Trade legs."""
    supplied = {group_id for group_id in order_group_ids if group_id is not None}
    if len(supplied) > 1:
        raise ValueError("rows in a multi-leg POST must share order_group_id")
    if supplied:
        group_id = next(iter(supplied))
    elif generate_for_multiple and len(order_group_ids) > 1:
        group_id = uuid.uuid4()
    else:
        group_id = None
    return [group_id] * len(order_group_ids)


def compute_cash_flow(
    action: TradeAction,
    price: Decimal,
    quantity: Decimal,
    multiplier: int,
    commission: Decimal,
    fees: Decimal,
) -> Decimal:
    """Signed net cash impact (per macro §6④)."""
    sign = Decimal(1) if action in _SELL_SIDE_ACTIONS else Decimal(-1)
    gross = sign * price * quantity * Decimal(multiplier)
    return gross - commission - fees


def validate_action_kind(action: TradeAction, kind: InstrumentKind) -> None:
    """Raise ValueError if action <-> kind mismatch."""
    if action in _OPTION_ACTIONS and kind is not InstrumentKind.OPTION:
        raise ValueError(
            f"action '{action.value}' requires an option instrument, "
            f"got '{kind.value}'"
        )
    if action in _NONOPTION_ACTIONS and kind is InstrumentKind.OPTION:
        raise ValueError(
            f"action '{action.value}' requires a stock or forex instrument, "
            f"got 'option'"
        )


def validate_option_quantity_integer(
    action: TradeAction, kind: InstrumentKind, quantity: Decimal
) -> None:
    """Options must trade in integer contract counts."""
    if kind is InstrumentKind.OPTION and quantity % 1 != 0:
        raise ValueError(
            f"option quantity must be an integer number of contracts, got {quantity}"
        )


async def resolve_multiplier(
    session: AsyncSession, instrument: Instrument
) -> int:
    """For options return ``OptionContract.multiplier``; else 1."""
    if instrument.kind is not InstrumentKind.OPTION:
        return 1
    contract = await session.get(OptionContract, instrument.id)
    if contract is None:
        raise ValueError(
            f"instrument {instrument.id} is kind=option but has no OptionContract row"
        )
    return contract.multiplier


async def create_trades_atomic(
    session: AsyncSession,
    position: Position,
    rows: list[TradeCreate],
) -> list[Trade]:
    """Validate every row, compute cash_flow, insert atomically.

    Caller is responsible for the surrounding session transaction commit.
    Raises ValueError on any validation failure.
    """
    trades: list[Trade] = []
    for row in rows:
        instrument = await session.get(Instrument, row.instrument_id)
        if instrument is None:
            raise ValueError(f"instrument {row.instrument_id} not found")

        validate_action_kind(row.action, instrument.kind)
        validate_option_quantity_integer(row.action, instrument.kind, row.quantity)

        multiplier = await resolve_multiplier(session, instrument)
        cash_flow = compute_cash_flow(
            row.action,
            row.price,
            row.quantity,
            multiplier,
            row.commission,
            row.fees,
        )

        trades.append(
            Trade(
                position_id=position.id,
                account_id=position.account_id,
                instrument_id=row.instrument_id,
                action=row.action,
                quantity=row.quantity,
                price=row.price,
                commission=row.commission,
                fees=row.fees,
                cash_flow=cash_flow,
                executed_at=to_utc_naive(row.executed_at),
                order_group_id=row.order_group_id,
                notes=row.notes,
            )
        )

    session.add_all(trades)
    await session.flush()

    for t in trades:
        await session.refresh(t)

    return trades
