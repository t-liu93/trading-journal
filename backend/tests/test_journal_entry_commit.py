"""Atomic MCP journal entry commit and retry regressions."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from trading_journal.models.account import Account
from trading_journal.models.instrument import Instrument, OptionContract
from trading_journal.models.journal_entry_draft import JournalEntryDraft
from trading_journal.models.mcp_token import McpToken
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade
from trading_journal.models.user import User
from trading_journal.services.journal_entries import commit_entry, prepare_entry
from trading_journal.services.mcp_tokens import McpPrincipal, issue_token


async def _entry_setup(auth_client, db_session_maker):
    account_response = await auth_client.post(
        "/api/accounts",
        json={"name": "Commit", "broker": "Demo", "account_type": "cash", "base_currency": "USD"},
    )
    stock_response = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "COMMIT", "currency": "USD"}
    )
    assert account_response.status_code == stock_response.status_code == 201
    async with db_session_maker() as session:
        owner_id = await session.scalar(
            select(Account.user_id).where(Account.id == uuid.UUID(account_response.json()["id"]))
        )
        assert owner_id is not None
        token, _ = await issue_token(
            session, user_id=owner_id, name="commit test", profile="entry", expires_at=None
        )
        principal = McpPrincipal(owner_id, token.id, "entry")
        await session.commit()
    return account_response.json(), stock_response.json(), principal


async def _prepare(session, principal, account, stock, *, kind="open_position", position_id=None):
    payload = {
        "request_id": str(uuid.uuid4()),
        "kind": kind,
        "legs": [
            {
                "instrument": {"instrument_id": stock["id"]},
                "action": "buy",
                "quantity": "2.123456789",
                "price": "10.12345678",
                "executed_at": "2026-06-01T10:00:00Z",
            },
            {
                "instrument": {
                    "pending": {
                        "kind": "option",
                        "underlying_symbol": "COMMITOPT",
                        "currency": "USD",
                        "opt_type": "call",
                        "strike": "12.3456789",
                        "expiry": "2027-01-15",
                    }
                },
                "action": "bto",
                "quantity": "1",
                "price": "1.23456789",
                "executed_at": "2026-06-01T10:01:00Z",
            },
        ],
    }
    if kind == "open_position":
        pending_stock = {
            "pending": {"kind": "stock", "symbol": "NEWCOMMIT", "currency": "USD"}
        }
        payload["legs"][0]["instrument"] = pending_stock
        payload["position"] = {
            "account_id": account["id"],
            "primary_instrument": pending_stock,
            "strategy_type": "spot_stock",
        }
    else:
        payload["position_id"] = position_id
        payload["legs"] = payload["legs"][:1]
    return await prepare_entry(session, principal, payload)


async def test_commit_new_position_pending_instruments_is_atomic_and_retryable(
    auth_client, db_session_maker
) -> None:
    account, stock, principal = await _entry_setup(auth_client, db_session_maker)
    async with db_session_maker() as session:
        draft = await _prepare(session, principal, account, stock)
        await session.commit()
        preview = draft.preview
    async with db_session_maker() as session:
        result = await commit_entry(
            session, principal, draft.id, clock=draft.expires_at - timedelta(seconds=1)
        )
    assert len(result.trade_ids) == 2
    assert result.position_url == f"/positions/{result.position_id}"
    assert result.trade_urls[0].startswith(result.position_url)
    async with db_session_maker() as session:
        position = await session.get(Position, result.position_id)
        saved_trades = list(
            (
                await session.scalars(select(Trade).where(Trade.position_id == result.position_id))
            ).all()
        )
        option = await session.scalar(
            select(OptionContract)
            .join(Instrument, OptionContract.instrument_id == Instrument.id)
            .where(Instrument.symbol == "COMMITOPT")
        )
        persisted_draft = await session.get(JournalEntryDraft, draft.id)
        assert position is not None and option is not None and persisted_draft is not None
        assert persisted_draft.state == "committed"
        assert len(saved_trades) == 2
        assert position.opened_at == datetime(2026, 6, 1, 10, 0)
        assert saved_trades[0].quantity == Decimal("2.12345679")
        assert saved_trades[0].price == Decimal("10.123457")
        assert saved_trades[0].cash_flow == Decimal(preview["legs"][0]["cash_flow"])
        assert saved_trades[0].order_group_id == saved_trades[1].order_group_id
        assert await session.scalar(select(func.count()).select_from(Position)) == 1
    async with db_session_maker() as retry_session:
        retry = await commit_entry(
            retry_session,
            principal,
            draft.id,
            clock=draft.expires_at + timedelta(days=1),
        )
    assert retry == result


async def test_commit_failure_rolls_back_instruments_position_trades_and_consumption(
    auth_client, db_session_maker, monkeypatch
) -> None:
    from trading_journal.services import journal_entries

    account, stock, principal = await _entry_setup(auth_client, db_session_maker)
    async with db_session_maker() as session:
        draft = await _prepare(session, principal, account, stock)
        draft_id = draft.id
        await session.commit()
    async with db_session_maker() as session:
        before_instruments = await session.scalar(select(func.count()).select_from(Instrument))
        original = journal_entries.create_trades_atomic

        async def fail_after_create(session, position, rows):
            await original(session, position, rows)
            raise RuntimeError("injected after trade flush")

        monkeypatch.setattr(journal_entries, "create_trades_atomic", fail_after_create)
        with pytest.raises(RuntimeError, match="injected"):
            await commit_entry(session, principal, draft_id)
        await session.rollback()
    async with db_session_maker() as check:
        persisted = await check.get(JournalEntryDraft, draft_id)
        assert persisted is not None and persisted.state == "pending"
        assert await check.scalar(select(func.count()).select_from(Position)) == 0
        assert await check.scalar(select(func.count()).select_from(Trade)) == 0
        assert (
            await check.scalar(select(func.count()).select_from(Instrument)) == before_instruments
        )
        assert await check.scalar(select(func.count()).select_from(OptionContract)) == 0


@pytest.mark.parametrize(
    ("expiry_target", "expected_status"),
    [("draft", 409), ("credential", 401)],
)
async def test_expiry_is_rechecked_after_waiting_for_sqlite_write_slot(
    auth_client, db_session_maker, expiry_target: str, expected_status: int
) -> None:
    """Real SQLite contention must not let a deadline expire during lock wait."""
    from trading_journal.services.write_guard import acquire_instrument_write_guard

    account, stock, principal = await _entry_setup(auth_client, db_session_maker)
    async with db_session_maker() as setup:
        draft = await _prepare(setup, principal, account, stock)
        draft_id = draft.id
        deadline = datetime.now(UTC) + timedelta(seconds=0.5)
        if expiry_target == "draft":
            draft.expires_at = deadline
        else:
            token = await setup.get(McpToken, principal.credential_id)
            assert token is not None
            token.expires_at = deadline
        await setup.commit()

    async with db_session_maker() as holder:
        await acquire_instrument_write_guard(holder)
        async with db_session_maker() as contender:
            task = asyncio.create_task(commit_entry(contender, principal, draft_id))
            await asyncio.sleep(0.8)
            assert datetime.now(UTC) > deadline
            await holder.rollback()
            with pytest.raises(HTTPException) as expired:
                await task
            assert expired.value.status_code == expected_status

    async with db_session_maker() as check:
        saved_draft = await check.get(JournalEntryDraft, draft_id)
        assert saved_draft is not None and saved_draft.state == "pending"
        assert "result" not in saved_draft.source
        assert await check.scalar(select(func.count()).select_from(Instrument)) == 1
        assert await check.scalar(select(func.count()).select_from(OptionContract)) == 0
        assert await check.scalar(select(func.count()).select_from(Position)) == 0
        assert await check.scalar(select(func.count()).select_from(Trade)) == 0


async def test_commit_rechecks_closed_revoked_inactive_and_foreign_principal(
    auth_client, second_user_client, db_session_maker
) -> None:
    account, stock, principal = await _entry_setup(auth_client, db_session_maker)
    async with db_session_maker() as session:
        draft = await _prepare(session, principal, account, stock)
        draft_id = draft.id
        await session.commit()
        token = await session.get(McpToken, principal.credential_id)
        assert token is not None
        token.revoked_at = datetime.now(UTC)
        await session.commit()
        with pytest.raises(HTTPException) as revoked:
            await commit_entry(session, principal, draft_id)
        assert revoked.value.status_code == 401

    # A valid credential cannot take over another credential's draft.
    async with db_session_maker() as session:
        replacement, _ = await issue_token(
            session, user_id=principal.user_id, name="replacement", profile="entry", expires_at=None
        )
        other_principal = McpPrincipal(principal.user_id, replacement.id, "entry")
        await session.commit()
        with pytest.raises(HTTPException) as wrong_credential:
            await commit_entry(session, other_principal, draft_id)
        assert wrong_credential.value.status_code == 404
        user = await session.get(User, principal.user_id)
        assert user is not None
        user.is_active = False
        await session.commit()
        with pytest.raises(HTTPException) as inactive:
            await commit_entry(session, other_principal, draft_id)
        assert inactive.value.status_code == 401

    second_account = await second_user_client.post(
        "/api/accounts",
        json={"name": "Other", "broker": "Demo", "account_type": "cash", "base_currency": "USD"},
    )
    assert second_account.status_code == 201
    async with db_session_maker() as session:
        foreign_id = uuid.UUID(second_account.json()["id"])
        foreign_owner = await session.scalar(
            select(Account.user_id).where(Account.id == foreign_id)
        )
        assert foreign_owner is not None
        foreign_token, _ = await issue_token(
            session, user_id=foreign_owner, name="foreign", profile="entry", expires_at=None
        )
        foreign_principal = McpPrincipal(foreign_owner, foreign_token.id, "entry")
        # No draft exists under the foreign user/credential pair.
        with pytest.raises(HTTPException) as foreign:
            await commit_entry(session, foreign_principal, draft_id)
        assert foreign.value.status_code == 404


async def test_add_trades_keeps_existing_archived_account_rule_and_closed_lock(
    auth_client, db_session_maker
) -> None:
    account, stock, principal = await _entry_setup(auth_client, db_session_maker)
    position_response = await auth_client.post(
        "/api/positions",
        json={
            "account_id": account["id"],
            "primary_instrument_id": stock["id"],
            "strategy_type": "spot_stock",
            "opened_at": "2026-07-01T00:00:00Z",
        },
    )
    assert position_response.status_code == 201
    position_id = uuid.UUID(position_response.json()["id"])
    async with db_session_maker() as session:
        draft = await _prepare(
            session, principal, account, stock, kind="add_trades", position_id=str(position_id)
        )
        draft_id = draft.id
        await session.commit()
        account_row = await session.get(Account, uuid.UUID(account["id"]))
        assert account_row is not None
        account_row.archived_at = datetime.now(UTC)
        await session.commit()
        # Existing additions retain Trade's current behavior with archived accounts.
        result = await commit_entry(session, principal, draft_id)
        assert result.position_id == position_id
        assert len(result.trade_ids) == 1
        position = await session.get(Position, position_id)
        assert position is not None
        assert position.opened_at == datetime(2026, 6, 1, 10, 0)

    # A separate prepared addition must observe a Position closed after preview.
    async with db_session_maker() as session:
        second = await _prepare(
            session, principal, account, stock, kind="add_trades", position_id=str(position_id)
        )
        second_id = second.id
        await session.commit()
        position = await session.get(Position, position_id)
        assert position is not None
        position.status = "closed"  # enum string is accepted by SQLAlchemy's non-native enum
        await session.commit()
        with pytest.raises(HTTPException) as closed:
            await commit_entry(session, principal, second_id)
        assert closed.value.status_code == 409


async def test_stale_pending_orm_instance_cannot_hide_committed_result(
    auth_client, db_session_maker
) -> None:
    account, stock, principal = await _entry_setup(auth_client, db_session_maker)
    async with db_session_maker() as prepare_session:
        draft = await _prepare(prepare_session, principal, account, stock)
        draft_id = draft.id
        await prepare_session.commit()
    stale_session = db_session_maker()
    try:
        stale = await stale_session.get(JournalEntryDraft, draft_id)
        assert stale is not None and stale.state == "pending"
        async with db_session_maker() as winner_session:
            winner = await commit_entry(winner_session, principal, draft_id)
        retry = await commit_entry(stale_session, principal, draft_id)
        assert retry == winner
    finally:
        await stale_session.close()
    async with db_session_maker() as check:
        persisted = await check.get(JournalEntryDraft, draft_id)
        assert persisted is not None and persisted.state == "committed"
        assert await check.scalar(select(func.count()).select_from(Position)) == 1
        assert await check.scalar(select(func.count()).select_from(Trade)) == 2


async def test_sqlite_contention_is_marked_retryable(
    auth_client, db_session_maker, monkeypatch
) -> None:
    from trading_journal.services import journal_entries

    account, stock, principal = await _entry_setup(auth_client, db_session_maker)
    async with db_session_maker() as session:
        draft = await _prepare(session, principal, account, stock)
        draft_id = draft.id
        await session.commit()
    original = journal_entries.acquire_instrument_write_guard

    async def locked(session):
        raise OperationalError("update", {}, RuntimeError("database is locked"))

    async with db_session_maker() as session:
        monkeypatch.setattr(journal_entries, "acquire_instrument_write_guard", locked)
        with pytest.raises(HTTPException) as retryable:
            await commit_entry(session, principal, draft_id)
        assert retryable.value.status_code == 503
        assert retryable.value.detail == {"code": "entry_commit_retryable", "retryable": True}
    monkeypatch.setattr(journal_entries, "acquire_instrument_write_guard", original)
    async with db_session_maker() as session:
        assert len((await commit_entry(session, principal, draft_id)).trade_ids) == 2


async def test_independent_sessions_concurrent_and_lost_response_retries_share_ids(
    auth_client, db_session_maker, db_engine
) -> None:
    account, stock, principal = await _entry_setup(auth_client, db_session_maker)
    async with db_session_maker() as session:
        draft = await _prepare(session, principal, account, stock)
        draft_id = draft.id
        await session.commit()
    second_engine = create_async_engine(str(db_engine.url))
    second_maker = async_sessionmaker(second_engine, expire_on_commit=False, class_=AsyncSession)

    async def commit_with(maker):
        async with maker() as session:
            return await commit_entry(session, principal, draft_id)

    try:
        first, second = await asyncio.gather(
            commit_with(db_session_maker), commit_with(second_maker)
        )
        assert first == second
        # Simulate losing the first response: the next independent connection
        # reads the saved result and does not create another row.
        third = await commit_with(second_maker)
        assert third == first
    finally:
        await second_engine.dispose()
    async with db_session_maker() as session:
        assert await session.scalar(select(func.count()).select_from(Position)) == 1
        assert await session.scalar(select(func.count()).select_from(Trade)) == 2


async def test_pending_expiry_and_account_archive_are_rechecked(
    auth_client, db_session_maker
) -> None:
    account, stock, principal = await _entry_setup(auth_client, db_session_maker)
    async with db_session_maker() as session:
        draft = await _prepare(session, principal, account, stock)
        draft_id = draft.id
        expires_at = draft.expires_at
        await session.commit()
        row = await session.get(Account, uuid.UUID(account["id"]))
        assert row is not None
        row.archived_at = datetime.now(UTC)
        await session.commit()
        with pytest.raises(HTTPException) as archived:
            await commit_entry(session, principal, draft_id)
        assert archived.value.status_code == 422
        await session.rollback()
        row = await session.get(Account, uuid.UUID(account["id"]))
        assert row is not None
        row.archived_at = None
        await session.commit()
        with pytest.raises(HTTPException) as expired:
            await commit_entry(
                session, principal, draft_id, clock=expires_at + timedelta(seconds=1)
            )
        assert expired.value.status_code == 409
