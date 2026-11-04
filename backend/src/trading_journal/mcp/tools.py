"""D02 MCP tools; every invocation authenticates its own request context."""

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any, TypeVar, cast

from fastapi import HTTPException
from mcp.server import MCPServer
from mcp.server.mcpserver.context import Context
from pydantic import ValidationError

from trading_journal.auth.mcp import authenticate_bearer_header
from trading_journal.db import get_session_maker
from trading_journal.models._enums import InstrumentKind, OptType, PositionStatus, StrategyType
from trading_journal.schemas.account import AccountRead
from trading_journal.schemas.journal_entry import EntryCommitResult, EntryPreview
from trading_journal.schemas.position import PositionRead
from trading_journal.schemas.trade import TradeRead
from trading_journal.services.instruments import instrument_read
from trading_journal.services.journal_context import get_journal_context
from trading_journal.services.journal_entries import commit_entry, prepare_entry
from trading_journal.services.journal_queries import (
    DEFAULT_PAGE_SIZE,
    get_position,
    list_accounts,
    list_positions,
    list_trades,
    search_instruments,
)
from trading_journal.services.mcp_tokens import McpPrincipal


def _json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, uuid.UUID)):
        return value.isoformat() if isinstance(value, date) else str(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _dump(model: Any) -> dict[str, Any]:
    return cast(dict[str, Any], _json(model.model_dump(mode="json")))


async def _principal(ctx: Context[Any, Any], *, entry: bool = False) -> McpPrincipal:
    headers = ctx.headers or {}
    async with get_session_maker()() as session:
        principal = await authenticate_bearer_header(session, headers.get("authorization"))
    if entry and principal.profile != "entry":
        raise HTTPException(status_code=403, detail="entry credential required")
    return principal


def _error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ValidationError):
        problems = [
            {"path": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
            for item in exc.errors()
        ]
        return {"ok": False, "error": {"code": "invalid_fields", "fields": problems}}
    if isinstance(exc, HTTPException):
        detail = exc.detail
        code = "request_failed"
        message = "request could not be completed"
        if isinstance(detail, dict):
            default_code = "request_conflict" if exc.status_code == 409 else "invalid_fields"
            code = str(detail.get("code", default_code))
            message = str(detail.get("message", "request could not be completed"))
            if code == "invalid_fields":
                fields = detail.get("fields")
                if isinstance(fields, list):
                    return {"ok": False, "error": {"code": code, "fields": fields}}
                return {
                    "ok": False,
                    "error": {
                        "code": code,
                        "fields": [
                            {"path": str(path), "message": str(problem)}
                            for path, problem in detail.items()
                        ],
                    },
                }
        elif isinstance(detail, str):
            message = detail
            if exc.status_code == 404:
                code = "missing_resource"
            elif exc.status_code == 409:
                code = "request_conflict"
            elif exc.status_code == 422:
                return {
                    "ok": False,
                    "error": {
                        "code": "invalid_fields",
                        "fields": [{"path": "request", "message": message}],
                    },
                }
        if exc.status_code == 403:
            code = "permission_denied"
        if exc.status_code == 503:
            code = "entry_commit_retryable"
        return {"ok": False, "error": {"code": code, "message": message}}
    return {
        "ok": False,
        "error": {"code": "request_failed", "message": "request could not be completed"},
    }


ToolCallable = TypeVar("ToolCallable", bound=Callable[..., Any])

PREPARE_ENTRY_DESCRIPTION = """Prepare one immutable batch from a complete structured
`request` object.
Required top-level fields are `request_id` (caller-generated UUID), `kind` (`open_position` or
`add_trades`), and non-empty `legs` (array). For `open_position`, include `position` and omit
`position_id`; `position` has `account_id`, `primary_instrument`, `strategy_type`, and optional
`opened_at`, `capital_used`, `max_risk_at_open`, `max_reward_at_open`, and `notes`. The
`add_trades` branch
include `position_id` and omit `position`. Each leg has `instrument`, `action`, `quantity`, `price`,
and `executed_at`, with optional `timezone`, `commission`, `fees`, `order_group_id`, and `notes`.
Use decimal strings for amounts and ISO-8601 strings for dates/times. An `instrument` reference is
exactly one of `{\"instrument_id\": UUID}` or `{\"pending\": descriptor}`. A pending stock
descriptor
has `kind: stock`, `symbol`, `currency`, optional `exchange`; an option has `kind: option`,
`underlying_symbol`, `currency`, `opt_type`, `strike`, `expiry`, optional `underlying_exchange`,
`multiplier`, and `style`; a forex descriptor has `kind: forex`, `symbol`, `base_currency`,
`quote_currency`, `pip_size`, optional `contract_size`. Omitted commission/fees use zero and the
preview shows them; option multiplier/style defaults are also shown. Offset-bearing execution times
are honored; timezone-less times use supplied `timezone` or the server default. DST-ambiguous or
nonexistent local times require an explicit offset. Unknown fields and mismatched alternatives are
rejected. Retries must send the original complete `request` unchanged so request identity is
preserved. Show the server preview and obtain explicit chat confirmation before calling
`commit_entry` with its `draft_id`."""


def _register(
    server: MCPServer, name: str, description: str
) -> Callable[[ToolCallable], ToolCallable]:
    return server.tool(name=name, description=description, structured_output=True)


def register_tools(server: MCPServer) -> None:
    """Register exactly the eight tools in the milestone contract."""

    @_register(
        server,
        "get_context",
        (
            "Current UTC/local time, default timezone, strategies, and Trade actions. Consult "
            "first; ask the user to clarify missing entry data."
        ),
    )
    async def get_context_tool(ctx: Context[Any, Any]) -> dict[str, Any]:
        try:
            await _principal(ctx)
            return {"ok": True, "result": _dump(get_journal_context())}
        except Exception as exc:
            return _error(exc)

    @_register(
        server,
        "list_accounts",
        "List owned, non-archived accounts by default; filters are applied before pagination.",
    )
    async def list_accounts_tool(
        ctx: Context[Any, Any],
        include_archived: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> dict[str, Any]:
        try:
            principal = await _principal(ctx)
            async with get_session_maker()() as session:
                items, more = await list_accounts(
                    session,
                    principal.user_id,
                    include_archived=include_archived,
                    limit=limit,
                    offset=offset,
                )
                return {
                    "ok": True,
                    "result": {
                        "items": [_dump(AccountRead.model_validate(x)) for x in items],
                        "has_more": more,
                    },
                }
        except Exception as exc:
            return _error(exc)

    @_register(
        server,
        "search_instruments",
        (
            "Search instruments by exact contract filters. Expired options are included by "
            "default; complete option/forex specifications are returned. Ask the user to choose "
            "among multiple candidates."
        ),
    )
    async def search_instruments_tool(
        ctx: Context[Any, Any],
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
    ) -> dict[str, Any]:
        try:
            await _principal(ctx)
            async with get_session_maker()() as session:
                items, more = await search_instruments(
                    session,
                    kind=kind,
                    symbol=symbol,
                    currency=currency,
                    exchange=exchange,
                    option_underlying_id=option_underlying_id,
                    expiry=expiry,
                    strike=strike,
                    opt_type=opt_type,
                    include_expired=include_expired,
                    limit=limit,
                    offset=offset,
                )
                serialized = [_dump(await instrument_read(session, item)) for item in items]
                return {"ok": True, "result": {"items": serialized, "has_more": more}}
        except Exception as exc:
            return _error(exc)

    @_register(
        server,
        "list_positions",
        "List owned Positions with optional account, primary instrument, strategy, and status.",
    )
    async def list_positions_tool(
        ctx: Context[Any, Any],
        account_id: uuid.UUID | None = None,
        primary_instrument_id: uuid.UUID | None = None,
        strategy_type: StrategyType | None = None,
        status: PositionStatus | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> dict[str, Any]:
        try:
            principal = await _principal(ctx)
            async with get_session_maker()() as session:
                items, more = await list_positions(
                    session,
                    principal.user_id,
                    account_id=account_id,
                    primary_instrument_id=primary_instrument_id,
                    strategy_type=strategy_type,
                    position_status=status,
                    limit=limit,
                    offset=offset,
                )
                return {
                    "ok": True,
                    "result": {
                        "items": [_dump(PositionRead.model_validate(x)) for x in items],
                        "has_more": more,
                    },
                }
        except Exception as exc:
            return _error(exc)

    @_register(
        server,
        "get_position",
        "Get one owned Position with primary instrument and cash flow; Trade history is paginated.",
    )
    async def get_position_tool(ctx: Context[Any, Any], position_id: uuid.UUID) -> dict[str, Any]:
        try:
            principal = await _principal(ctx)
            async with get_session_maker()() as session:
                position, instrument, cash_flow = await get_position(
                    session, principal.user_id, position_id
                )
                position_values = {
                    name: getattr(position, name)
                    for name in PositionRead.model_fields
                    if name != "net_cash_flow"
                }
                position_values["net_cash_flow"] = cash_flow
                result = _dump(PositionRead.model_validate(position_values))
                result["primary_instrument"] = _dump(await instrument_read(session, instrument))
                result["net_cash_flow"] = str(cash_flow)
                return {"ok": True, "result": result}
        except Exception as exc:
            return _error(exc)

    @_register(
        server,
        "list_trades",
        "List fills for an owned Position; archived fills are excluded by default.",
    )
    async def list_trades_tool(
        ctx: Context[Any, Any],
        position_id: uuid.UUID,
        include_archived: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> dict[str, Any]:
        try:
            principal = await _principal(ctx)
            async with get_session_maker()() as session:
                items, more = await list_trades(
                    session,
                    principal.user_id,
                    position_id=position_id,
                    include_archived=include_archived,
                    limit=limit,
                    offset=offset,
                )
                return {
                    "ok": True,
                    "result": {
                        "items": [_dump(TradeRead.model_validate(x)) for x in items],
                        "has_more": more,
                    },
                }
        except Exception as exc:
            return _error(exc)

    @_register(
        server,
        "prepare_entry",
        PREPARE_ENTRY_DESCRIPTION,
    )
    async def prepare_entry_tool(ctx: Context[Any, Any], request: dict[str, Any]) -> dict[str, Any]:
        try:
            principal = await _principal(ctx, entry=True)
            async with get_session_maker()() as session:
                draft = await prepare_entry(session, principal, request)
                await session.commit()
                return {
                    "ok": True,
                    "result": _dump(
                        EntryPreview(
                            draft_id=draft.id,
                            request_id=draft.request_id,
                            expires_at=draft.expires_at,
                            preview=draft.preview,
                            defaults=draft.defaults,
                        )
                    ),
                }
        except Exception as exc:
            return _error(exc)

    @_register(
        server,
        "commit_entry",
        (
            "Commit only a previously prepared draft_id. After uncertain or lost responses, "
            "safely retry with the exact same draft_id; do not create a replacement batch."
        ),
    )
    async def commit_entry_tool(ctx: Context[Any, Any], draft_id: uuid.UUID) -> dict[str, Any]:
        try:
            principal = await _principal(ctx, entry=True)
            async with get_session_maker()() as session:
                result: EntryCommitResult = await commit_entry(session, principal, draft_id)
                return {"ok": True, "result": _dump(result)}
        except Exception as exc:
            return _error(exc)
