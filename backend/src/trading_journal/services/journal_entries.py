"""Prepare immutable, side-effect-free MCP journal entry previews."""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, DecimalException
from typing import Any, cast
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import InstrumentKind, PositionStatus
from trading_journal.models.account import Account
from trading_journal.models.instrument import ForexPair, Instrument, OptionContract
from trading_journal.models.journal_entry_draft import JournalEntryDraft
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade
from trading_journal.schemas.instrument import InstrumentCreate
from trading_journal.schemas.journal_entry import (
    EntryLeg,
    ExistingInstrument,
    PendingInstrument,
    PrepareEntryRequest,
)
from trading_journal.services.datetimes import parse_entry_datetime
from trading_journal.services.instruments import (
    _database_numeric_bind_value,
    _database_numeric_value,
    instrument_read,
    resolve_instrument_spec,
)
from trading_journal.services.journal_context import get_journal_context
from trading_journal.services.mcp_tokens import McpPrincipal
from trading_journal.services.ownership import resolve_owned_position
from trading_journal.services.trades import (
    compute_cash_flow,
    normalize_order_group_ids,
    resolve_multiplier,
    validate_action_kind,
    validate_option_quantity_integer,
)

DRAFT_LIFETIME = timedelta(hours=24)


async def _entry_currency(
    session: AsyncSession,
    instrument: Instrument | None,
    pending: InstrumentCreate | None,
) -> str:
    """Return the currency used to account for this instrument's trade cash flow."""
    if instrument is not None:
        if instrument.kind is InstrumentKind.FOREX:
            pair = await session.get(ForexPair, instrument.id)
            if pair is None:
                raise ValueError("forex pair details are missing")
            return pair.quote_currency
        return instrument.currency
    assert pending is not None
    if pending.kind == "forex":
        return pending.quote_currency
    return pending.currency


async def _validate_entry_leg_currency(
    session: AsyncSession,
    reference: ExistingInstrument | PendingInstrument,
    expected_currency: str,
    index: int,
) -> None:
    instrument, pending, _ = await _resolve_reference(
        session, reference, f"legs.{index}.instrument"
    )
    try:
        actual_currency = await _entry_currency(session, instrument, pending)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={f"legs.{index}.instrument": str(exc)}) from exc
    if actual_currency != expected_currency:
        raise HTTPException(
            status_code=422,
            detail={
                f"legs.{index}.instrument": (
                    f"currency {actual_currency} does not match Position currency "
                    f"{expected_currency}"
                )
            },
        )


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        _jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _request_conflict() -> HTTPException:
    return HTTPException(status_code=409, detail="request_id already used with different content")


async def _resolve_reference(
    session: AsyncSession,
    reference: ExistingInstrument | PendingInstrument,
    field_path: str,
) -> tuple[Instrument | None, InstrumentCreate | None, dict[str, object]]:
    if isinstance(reference, ExistingInstrument):
        instrument = await session.get(Instrument, reference.instrument_id)
        if instrument is None:
            raise HTTPException(
                status_code=422,
                detail={field_path: "instrument not found"},
            )
        return (
            instrument,
            None,
            (await instrument_read(session, instrument)).model_dump(mode="json"),
        )
    spec = reference.pending
    try:
        instrument = await resolve_instrument_spec(session, spec)
    except ValueError as exc:
        path = f"{field_path}.pending" if isinstance(reference, PendingInstrument) else field_path
        raise HTTPException(status_code=422, detail={path: str(exc)}) from exc
    if instrument is not None:
        return (
            instrument,
            None,
            (await instrument_read(session, instrument)).model_dump(mode="json"),
        )
    description = spec.model_dump(mode="json")
    if spec.kind == "option":
        strike = _numeric_preview(
            session, OptionContract.__table__.c.strike, spec.strike, f"{field_path}.pending.strike"
        )
        description["strike"] = str(strike)
        description["option"] = {
            "opt_type": spec.opt_type.value,
            "strike": str(strike),
            "expiry": spec.expiry.isoformat(),
            "multiplier": spec.multiplier,
            "style": spec.style.value,
            "underlying_symbol": spec.underlying_symbol,
            "underlying_exchange": spec.underlying_exchange,
        }
    elif spec.kind == "forex":
        pip_size = _numeric_preview(
            session, ForexPair.__table__.c.pip_size, spec.pip_size, f"{field_path}.pending.pip_size"
        )
        contract_size = (
            _numeric_preview(
                session,
                ForexPair.__table__.c.contract_size,
                spec.contract_size,
                f"{field_path}.pending.contract_size",
            )
            if spec.contract_size is not None
            else None
        )
        description["pip_size"] = str(pip_size)
        description["contract_size"] = str(contract_size) if contract_size is not None else None
        description["forex"] = {
            "base_currency": spec.base_currency,
            "quote_currency": spec.quote_currency,
            "pip_size": str(pip_size),
            "contract_size": str(contract_size) if contract_size is not None else None,
        }
    return None, spec, description


def _numeric_preview(session: AsyncSession, column: Any, value: Decimal, path: str) -> Decimal:
    """Return the value this dialect stores, rejecting values outside Numeric precision."""
    numeric_type = column.type
    precision = numeric_type.precision
    scale = numeric_type.scale
    try:
        limit: Decimal | None = None
        if precision is not None and scale is not None:
            limit = Decimal(10) ** (precision - scale)
            if abs(value) >= limit:
                raise DecimalException("value exceeds Numeric precision")
        stored_value = _database_numeric_value(session, numeric_type, value)
        if limit is not None and abs(stored_value) >= limit:
            raise DecimalException("stored value exceeds Numeric precision")
        return stored_value
    except (DecimalException, OverflowError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail={path: "value exceeds supported numeric precision"}
        ) from exc


def _positive_numeric_preview(
    session: AsyncSession, column: Any, value: Decimal, path: str
) -> Decimal:
    """Validate Numeric support and preserve a schema's strict-positive domain."""
    stored_value = _numeric_preview(session, column, value, path)
    if stored_value <= 0:
        raise HTTPException(
            status_code=422,
            detail={path: "value must remain positive at supported numeric precision"},
        )
    return stored_value


def _pending_natural_key(session: AsyncSession, spec: InstrumentCreate) -> tuple[object, ...]:
    """Describe a pending reference using the same fields as instrument lookup."""
    if spec.kind == "stock":
        return ("stock", spec.symbol.strip().upper(), spec.currency, spec.exchange)
    if spec.kind == "option":
        strike = _database_numeric_bind_value(
            session, OptionContract.__table__.c.strike.type, spec.strike
        )
        underlying = (
            spec.underlying_symbol.strip().upper(),
            spec.currency,
            spec.underlying_exchange,
        )
        return (
            "option",
            *underlying,
            spec.opt_type,
            strike,
            spec.expiry,
            spec.multiplier,
        )
    return ("forex", spec.symbol.strip().upper())


def _pending_conflicting_field(
    session: AsyncSession, left: InstrumentCreate, right: InstrumentCreate
) -> str | None:
    """Return the first differing specification field for equal natural keys."""
    if left.kind == "forex" and right.kind == "forex":
        if left.base_currency != right.base_currency:
            return "base_currency"
        if left.quote_currency != right.quote_currency:
            return "quote_currency"
        if _database_numeric_value(
            session, ForexPair.__table__.c.pip_size.type, left.pip_size
        ) != _database_numeric_value(session, ForexPair.__table__.c.pip_size.type, right.pip_size):
            return "pip_size"
        left_contract_size = (
            _database_numeric_value(
                session, ForexPair.__table__.c.contract_size.type, left.contract_size
            )
            if left.contract_size is not None
            else None
        )
        right_contract_size = (
            _database_numeric_value(
                session, ForexPair.__table__.c.contract_size.type, right.contract_size
            )
            if right.contract_size is not None
            else None
        )
        if left_contract_size != right_contract_size:
            return "contract_size"
    if left.kind == "option" and right.kind == "option" and left.style != right.style:
        return "style"
    return None


def _validate_pending_descriptor_storage(
    session: AsyncSession, spec: InstrumentCreate, field_path: str
) -> None:
    """Reject pending fields outside SQLite ORM column ranges before any SQL bind."""
    if spec.kind == "option":
        if spec.multiplier > 2**63 - 1:
            raise HTTPException(
                status_code=422,
                detail={f"{field_path}.multiplier": "value exceeds supported integer precision"},
            )
        _positive_numeric_preview(
            session,
            OptionContract.__table__.c.strike,
            spec.strike,
            f"{field_path}.strike",
        )
    elif spec.kind == "forex":
        _positive_numeric_preview(
            session,
            ForexPair.__table__.c.pip_size,
            spec.pip_size,
            f"{field_path}.pip_size",
        )
        if spec.contract_size is not None:
            _positive_numeric_preview(
                session,
                ForexPair.__table__.c.contract_size,
                spec.contract_size,
                f"{field_path}.contract_size",
            )


async def _validate_pending_descriptor_batch(
    session: AsyncSession, request: PrepareEntryRequest
) -> None:
    """Reject conflicting unresolved natural keys before saving a draft."""
    references: list[tuple[str, PendingInstrument]] = []
    if request.position is not None and isinstance(
        request.position.primary_instrument, PendingInstrument
    ):
        references.append(("position.primary_instrument", request.position.primary_instrument))
    references.extend(
        (f"legs.{index}.instrument", leg.instrument)
        for index, leg in enumerate(request.legs)
        if isinstance(leg.instrument, PendingInstrument)
    )

    pending_by_key: dict[tuple[object, ...], tuple[str, InstrumentCreate]] = {}
    for field_path, reference in references:
        spec = reference.pending
        descriptor_path = f"{field_path}.pending"
        _validate_pending_descriptor_storage(session, spec, descriptor_path)
        try:
            existing = await resolve_instrument_spec(session, spec)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={descriptor_path: str(exc)}) from exc
        if existing is not None:
            continue
        try:
            natural_key = _pending_natural_key(session, spec)
        except (DecimalException, OverflowError, TypeError, ValueError) as exc:
            path = f"{field_path}.pending.strike"
            raise HTTPException(
                status_code=422, detail={path: "value exceeds supported numeric precision"}
            ) from exc
        previous = pending_by_key.get(natural_key)
        if previous is None:
            pending_by_key[natural_key] = (field_path, spec)
            continue
        conflict_field = _pending_conflicting_field(session, previous[1], spec)
        if conflict_field is not None:
            path = f"{field_path}.pending.{conflict_field}"
            raise HTTPException(
                status_code=422,
                detail={
                    path: "conflicts with another pending instrument using the same natural key"
                },
            )


def _freeze_resolved_reference(
    reference: ExistingInstrument | PendingInstrument,
    instrument: Instrument | None,
    normalized_reference: dict[str, Any],
) -> None:
    """Freeze a pending natural-key reference when preview resolved it to an ID."""
    if isinstance(reference, PendingInstrument) and instrument is not None:
        normalized_reference.clear()
        normalized_reference["instrument_id"] = str(instrument.id)


async def _resolve_entry_account(
    session: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
) -> Account:
    account = await session.get(Account, account_id)
    if account is None or account.user_id != user_id:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.archived_at is not None:
        raise HTTPException(status_code=422, detail="Account not found or archived")
    return account


async def _leg_preview(
    session: AsyncSession,
    leg: EntryLeg,
    index: int,
    executed: datetime,
    timezone_default: str,
    order_group_id: uuid.UUID | None,
) -> tuple[dict[str, object], dict[str, object]]:
    instrument, pending, instrument_preview = await _resolve_reference(
        session, leg.instrument, f"legs.{index}.instrument"
    )
    if instrument is not None:
        kind = instrument.kind
    else:
        assert pending is not None
        kind = InstrumentKind(pending.kind)
    try:
        if instrument is not None:
            multiplier = await resolve_multiplier(session, instrument)
        elif pending is not None and pending.kind == "option":
            multiplier = pending.multiplier
        else:
            multiplier = 1
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={f"legs.{index}.instrument": str(exc)}) from exc
    try:
        validate_action_kind(leg.action, kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={f"legs.{index}.action": str(exc)}) from exc
    quantity = _positive_numeric_preview(
        session, Trade.__table__.c.quantity, leg.quantity, f"legs.{index}.quantity"
    )
    try:
        validate_option_quantity_integer(leg.action, kind, leg.quantity)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={f"legs.{index}.action": str(exc)}) from exc
    defaults: dict[str, object] = {}
    commission = leg.commission if leg.commission is not None else Decimal("0")
    fees = leg.fees if leg.fees is not None else Decimal("0")
    if leg.commission is None:
        defaults[f"legs.{index}.commission"] = "0"
    if leg.fees is None:
        defaults[f"legs.{index}.fees"] = "0"
    if pending is not None and pending.kind == "option":
        if "multiplier" not in pending.model_fields_set:
            defaults[f"legs.{index}.instrument.multiplier"] = pending.multiplier
        if "style" not in pending.model_fields_set:
            defaults[f"legs.{index}.instrument.style"] = pending.style.value
    price = _numeric_preview(session, Trade.__table__.c.price, leg.price, f"legs.{index}.price")
    stored_commission = _numeric_preview(
        session, Trade.__table__.c.commission, commission, f"legs.{index}.commission"
    )
    stored_fees = _numeric_preview(session, Trade.__table__.c.fees, fees, f"legs.{index}.fees")
    try:
        raw_cash_flow = compute_cash_flow(
            leg.action, leg.price, leg.quantity, multiplier, commission, fees
        )
    except DecimalException as exc:
        raise HTTPException(
            status_code=422,
            detail={f"legs.{index}.price": "cash flow exceeds supported numeric precision"},
        ) from exc
    cash_flow = _numeric_preview(
        session, Trade.__table__.c.cash_flow, raw_cash_flow, f"legs.{index}.price"
    )
    return {
        "instrument": instrument_preview,
        "pending_instrument": instrument_preview if pending is not None else None,
        "action": leg.action.value,
        "quantity": str(quantity),
        "price": str(price),
        "multiplier": multiplier,
        "commission": str(stored_commission),
        "fees": str(stored_fees),
        "cash_flow": str(cash_flow),
        "input_executed_at": leg.executed_at.isoformat(),
        "input_timezone": leg.timezone,
        "server_default_timezone": timezone_default,
        "server_default_time": executed.astimezone(ZoneInfo(timezone_default)).isoformat(),
        "executed_at_utc": executed.isoformat(),
        "order_group_id": str(order_group_id) if order_group_id else None,
        "notes": leg.notes,
    }, defaults


async def prepare_entry(
    session: AsyncSession,
    principal: McpPrincipal,
    submitted: dict[str, Any],
    *,
    clock: datetime | None = None,
) -> JournalEntryDraft:
    """Validate and save a draft only; caller controls the transaction commit."""
    if principal.profile != "entry":
        raise HTTPException(status_code=403, detail="entry credential required")
    digest = _digest(submitted)
    try:
        request_id = uuid.UUID(str(submitted["request_id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="request_id must be a UUID") from exc
    existing = await session.scalar(
        select(JournalEntryDraft).where(
            JournalEntryDraft.user_id == principal.user_id,
            JournalEntryDraft.credential_id == principal.credential_id,
            JournalEntryDraft.request_id == request_id,
        )
    )
    if existing is not None:
        if existing.request_digest != digest:
            raise _request_conflict()
        return existing
    try:
        request = PrepareEntryRequest.model_validate(submitted)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await _validate_pending_descriptor_batch(session, request)
    if (request.kind == "open_position") != (
        request.position is not None and request.position_id is None
    ):
        raise HTTPException(
            status_code=422, detail="kind and position target are mutually exclusive"
        )
    if request.kind == "add_trades" and (
        request.position_id is None or request.position is not None
    ):
        raise HTTPException(status_code=422, detail="add_trades requires position_id only")
    try:
        order_group_ids = normalize_order_group_ids(
            [leg.order_group_id for leg in request.legs], generate_for_multiple=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"legs.order_group_id": str(exc)}) from exc
    now = clock or datetime.now(UTC)
    now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    timezone_default = get_journal_context().timezone
    leg_times: list[datetime] = []
    for index, leg in enumerate(request.legs):
        try:
            leg_times.append(
                parse_entry_datetime(
                    leg.executed_at,
                    default_timezone=timezone_default,
                    input_timezone=leg.timezone,
                )
            )
        except ValueError as exc:
            path = (
                f"legs.{index}.timezone"
                if leg.timezone is not None
                else f"legs.{index}.executed_at"
            )
            raise HTTPException(status_code=422, detail={path: str(exc)}) from exc
    normalized: dict[str, object] = request.model_dump(mode="json")
    normalized_legs = normalized["legs"]
    assert isinstance(normalized_legs, list)
    for index, leg in enumerate(request.legs):
        normalized_leg = normalized_legs[index]
        assert isinstance(normalized_leg, dict)
        normalized_leg["order_group_id"] = (
            str(order_group_ids[index]) if order_group_ids[index] is not None else None
        )
        normalized_instrument = normalized_leg.get("instrument")
        assert isinstance(normalized_instrument, dict)
        resolved_instrument, _, _ = await _resolve_reference(
            session, leg.instrument, f"legs.{index}.instrument"
        )
        _freeze_resolved_reference(leg.instrument, resolved_instrument, normalized_instrument)
    if request.position is not None:
        normalized_position_input = normalized.get("position")
        assert isinstance(normalized_position_input, dict)
        normalized_primary = normalized_position_input.get("primary_instrument")
        assert isinstance(normalized_primary, dict)
        resolved_primary, _, _ = await _resolve_reference(
            session, request.position.primary_instrument, "position.primary_instrument"
        )
        _freeze_resolved_reference(
            request.position.primary_instrument, resolved_primary, normalized_primary
        )
    legs_preview: list[dict[str, object]] = []
    preview: dict[str, object] = {"kind": request.kind, "legs": legs_preview}
    defaults: dict[str, object] = {}
    position_currency: str
    if request.kind == "open_position":
        position = request.position
        assert position is not None
        try:
            await _resolve_entry_account(session, principal.user_id, position.account_id)
        except HTTPException as exc:
            if exc.status_code == 422:
                raise HTTPException(
                    status_code=422, detail={"position.account_id": exc.detail}
                ) from exc
            raise
        inst, pending, inst_preview = await _resolve_reference(
            session, position.primary_instrument, "position.primary_instrument"
        )
        try:
            position_currency = await _entry_currency(session, inst, pending)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"position.primary_instrument": str(exc)},
            ) from exc
        if position.opened_at is not None:
            try:
                opened = parse_entry_datetime(position.opened_at, default_timezone=timezone_default)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422, detail={"position.opened_at": str(exc)}
                ) from exc
            earliest = min(leg_times)
            if opened != earliest:
                raise HTTPException(
                    status_code=422,
                    detail={"position.opened_at": "must match the earliest leg execution time"},
                )
            opened_at = earliest.isoformat()
            opened_input = position.opened_at.isoformat()
        else:
            opened_at = min(leg_times).isoformat()
            opened_input = None
            defaults["position.opened_at"] = "earliest leg execution time"
        normalized_position = normalized.get("position")
        assert isinstance(normalized_position, dict)
        normalized_position["opened_at"] = opened_at
        preview_position_values: dict[str, str | None] = {}
        for field in ("capital_used", "max_risk_at_open", "max_reward_at_open"):
            value = getattr(position, field)
            preview_position_values[field] = (
                str(
                    _positive_numeric_preview(
                        session, Position.__table__.c[field], value, f"position.{field}"
                    )
                )
                if value is not None
                else None
            )
            normalized_position[field] = preview_position_values[field]
        preview["position"] = {
            "account_id": str(position.account_id),
            "primary_instrument": inst_preview,
            "pending_instrument": inst_preview if pending else None,
            "strategy_type": position.strategy_type.value,
            "opened_at_input": opened_input,
            "opened_at_utc": opened_at,
            **preview_position_values,
            "notes": position.notes,
        }
        if inst is None and pending is not None:
            defaults["position.currency"] = (
                pending.currency if pending.kind != "forex" else pending.quote_currency
            )
    else:
        assert request.position_id is not None
        target = await resolve_owned_position(session, principal.user_id, request.position_id)
        if target.status is not PositionStatus.OPEN:
            raise HTTPException(status_code=409, detail="closed Position is read-only")
        position_currency = target.currency
        preview["position"] = {
            "position_id": str(target.id),
            "account_id": str(target.account_id),
            "status": target.status.value,
        }
    for index, leg in enumerate(request.legs):
        await _validate_entry_leg_currency(session, leg.instrument, position_currency, index)
        leg_preview, leg_defaults = await _leg_preview(
            session, leg, index, leg_times[index], timezone_default, order_group_ids[index]
        )
        legs_preview.append(leg_preview)
        normalized_leg = normalized_legs[index]
        assert isinstance(normalized_leg, dict)
        normalized_leg["executed_at"] = str(leg_preview["executed_at_utc"])
        normalized_leg["timezone"] = None
        defaults.update(leg_defaults)
    draft = JournalEntryDraft(
        user_id=principal.user_id,
        credential_id=principal.credential_id,
        request_id=request.request_id,
        request_digest=digest,
        normalized_input=_jsonable(normalized),
        preview=_jsonable(preview),
        defaults=defaults,
        source={"credential_id": str(principal.credential_id), "profile": principal.profile},
        created_at=now,
        expires_at=now + DRAFT_LIFETIME,
    )
    session.add(draft)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        winner = cast(
            JournalEntryDraft | None,
            await session.scalar(
                select(JournalEntryDraft).where(
                    JournalEntryDraft.user_id == principal.user_id,
                    JournalEntryDraft.credential_id == principal.credential_id,
                    JournalEntryDraft.request_id == request.request_id,
                )
            ),
        )
        if winner is not None and winner.request_digest == digest:
            return winner
        if winner is not None:
            raise _request_conflict() from None
        raise
    except OperationalError as exc:
        await session.rollback()
        message = str(exc.orig).lower()
        if "locked" not in message and "busy" not in message:
            raise
        winner = cast(
            JournalEntryDraft | None,
            await session.scalar(
                select(JournalEntryDraft).where(
                    JournalEntryDraft.user_id == principal.user_id,
                    JournalEntryDraft.credential_id == principal.credential_id,
                    JournalEntryDraft.request_id == request.request_id,
                )
            ),
        )
        if winner is not None and winner.request_digest == digest:
            return winner
        if winner is not None:
            raise _request_conflict() from exc
        raise
    return draft
