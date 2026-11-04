"""Shared MCP query and instrument-core regression tests."""

import asyncio
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from trading_journal.models._enums import InstrumentKind, OptType
from trading_journal.models.instrument import Instrument
from trading_journal.schemas.instrument import ForexCreate, OptionCreate, StockCreate
from trading_journal.services.instruments import get_or_create_instrument, resolve_instrument_spec
from trading_journal.services.journal_queries import (
    list_accounts,
    list_positions,
    search_instruments,
)


async def test_pending_option_lookup_is_read_only(db_session_maker) -> None:
    async with db_session_maker() as session:
        pending = OptionCreate(
            kind="option",
            underlying_symbol="READONLY",
            currency="USD",
            opt_type="call",
            strike=Decimal("10"),
            expiry=date(2027, 1, 15),
        )
        assert await resolve_instrument_spec(session, pending) is None
        assert await session.scalar(select(func.count()).select_from(Instrument)) == 0


async def test_instrument_resolution_checks_complete_specifications(
    auth_client: AsyncClient, db_session_maker: async_sessionmaker[AsyncSession]
) -> None:
    stock = await auth_client.post(
        "/api/instruments",
        json={"kind": "stock", "symbol": "DUAL", "currency": "USD", "exchange": "X"},
    )
    assert stock.status_code == 201
    same_symbol_other_currency = await auth_client.post(
        "/api/instruments",
        json={"kind": "stock", "symbol": "DUAL", "currency": "EUR", "exchange": "X"},
    )
    assert same_symbol_other_currency.status_code == 201
    option = await auth_client.post(
        "/api/instruments",
        json={
            "kind": "option", "underlying_symbol": "DUAL", "underlying_exchange": "X",
            "currency": "USD", "opt_type": "call", "strike": "10",
            "expiry": "2027-01-15", "style": "american",
        },
    )
    assert option.status_code == 201
    async with db_session_maker() as session:
        same = OptionCreate(
            kind="option", underlying_symbol="DUAL", underlying_exchange="X",
            currency="USD", opt_type="call", strike=Decimal("10"),
            expiry=date(2027, 1, 15), style="american",
        )
        found = await resolve_instrument_spec(session, same)
        assert found is not None and str(found.id) == option.json()["id"]
        conflict = same.model_copy(update={"style": "european"})
        with pytest.raises(ValueError, match="conflicting"):
            await resolve_instrument_spec(session, conflict)


async def test_forex_read_only_resolution_uses_persisted_numeric_precision(
    auth_client: AsyncClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    payload = {
        "kind": "forex",
        "symbol": "READPRECISION",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "pip_size": "0.000100001",
        "contract_size": "100000.12345",
    }
    created = await auth_client.post("/api/instruments", json=payload)
    assert created.status_code == 201, created.text

    async with db_session_maker() as session:
        resolved = await resolve_instrument_spec(
            session,
            ForexCreate.model_validate(payload),
        )
    assert resolved is not None
    assert str(resolved.id) == created.json()["id"]


async def test_bounded_queries_filter_before_pagination(
    auth_client: AsyncClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    account_a = await auth_client.post(
        "/api/accounts",
        json={"name": "A", "broker": "B", "account_type": "cash", "base_currency": "USD"},
    )
    account_b = await auth_client.post(
        "/api/accounts",
        json={"name": "B", "broker": "B", "account_type": "cash", "base_currency": "USD"},
    )
    instrument_a = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "PAGEA", "currency": "USD"}
    )
    instrument_b = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "PAGEB", "currency": "USD"}
    )
    assert all(row.status_code == 201 for row in (account_a, account_b, instrument_a, instrument_b))
    position_a = await auth_client.post(
        "/api/positions",
        json={
            "account_id": account_a.json()["id"],
            "primary_instrument_id": instrument_a.json()["id"],
            "strategy_type": "spot_stock", "opened_at": "2026-01-01T00:00:00Z",
        },
    )
    position_b = await auth_client.post(
        "/api/positions",
        json={
            "account_id": account_b.json()["id"],
            "primary_instrument_id": instrument_b.json()["id"],
            "strategy_type": "spot_stock", "opened_at": "2026-01-02T00:00:00Z",
        },
    )
    assert position_a.status_code == position_b.status_code == 201
    async with db_session_maker() as session:
        # Locate the owning user from the position created above without relying
        # on response enrichment or a caller-supplied owner field.
        from trading_journal.models.position import Position

        owner_id = (
            await session.execute(
                select(Position.user_id).where(
                    Position.id == uuid.UUID(position_a.json()["id"])
                )
            )
        ).scalar_one()
        accounts, account_more = await list_accounts(session, owner_id, limit=1)
        assert len(accounts) == 1 and account_more
        positions, position_more = await list_positions(
            session,
            owner_id,
            account_id=uuid.UUID(account_b.json()["id"]),
            limit=1,
        )
        assert len(positions) == 1 and not position_more
        instruments, instrument_more = await search_instruments(
            session,
            kind=InstrumentKind.STOCK,
            symbol="PAGEB",
            limit=1,
        )
        assert [row.symbol for row in instruments] == ["PAGEB"]
        assert not instrument_more


async def test_explicit_option_identity_filters_only_return_matching_options(
    auth_client: AsyncClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    stock = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "FILTEROPT", "currency": "USD"}
    )
    forex = await auth_client.post(
        "/api/instruments",
        json={
            "kind": "forex", "symbol": "FILTEROPTUSD", "base_currency": "EUR",
            "quote_currency": "USD", "pip_size": "0.0001",
        },
    )
    option = await auth_client.post(
        "/api/instruments",
        json={
            "kind": "option", "underlying_symbol": "FILTEROPT", "currency": "USD",
            "opt_type": "call", "strike": "25", "expiry": "2027-01-15",
        },
    )
    assert all(response.status_code == 201 for response in (stock, forex, option))

    async with db_session_maker() as session:
        matches, has_more = await search_instruments(
            session,
            expiry=date(2027, 1, 15),
            opt_type=OptType.CALL,
            limit=1,
        )
        assert [row.id for row in matches] == [uuid.UUID(option.json()["id"])]
        assert not has_more

        unmatched, unmatched_more = await search_instruments(
            session,
            expiry=date(2099, 1, 1),
            opt_type=OptType.PUT,
            limit=1,
        )
        assert unmatched == []
        assert not unmatched_more

        # Expiry visibility alone retains the mixed-kind picker semantics.
        mixed, _mixed_more = await search_instruments(
            session,
            include_expired=False,
            limit=10,
        )
        mixed_ids = {row.id for row in mixed}
        assert uuid.UUID(stock.json()["id"]) in mixed_ids
        assert uuid.UUID(forex.json()["id"]) in mixed_ids


async def test_same_natural_key_from_independent_sessions_serializes(db_engine) -> None:
    """Exercise the guard through two engines and sessions on one SQLite file."""
    database_url = str(db_engine.url)
    engine_a = create_async_engine(database_url, connect_args={"timeout": 10})
    engine_b = create_async_engine(database_url, connect_args={"timeout": 10})
    maker_a = async_sessionmaker(engine_a, expire_on_commit=False, class_=AsyncSession)
    maker_b = async_sessionmaker(engine_b, expire_on_commit=False, class_=AsyncSession)
    payload = StockCreate(kind="stock", symbol="RACE", currency="USD", exchange="NASDAQ")

    async def insert(maker: async_sessionmaker[AsyncSession]) -> str:
        async with maker() as session:
            instrument, _created = await get_or_create_instrument(session, payload)
            instrument_id = str(instrument.id)
            await session.commit()
            return instrument_id

    try:
        first_id, second_id = await asyncio.gather(insert(maker_a), insert(maker_b))
        assert first_id == second_id
        async with maker_a() as session:
            count = await session.scalar(
                select(func.count()).select_from(Instrument).where(
                    Instrument.kind == InstrumentKind.STOCK,
                    Instrument.symbol == "RACE",
                    Instrument.currency == "USD",
                    Instrument.exchange == "NASDAQ",
                )
            )
            assert count == 1
    finally:
        await engine_a.dispose()
        await engine_b.dispose()
