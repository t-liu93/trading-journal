"""Regression coverage for side-effect-free MCP entry preparation."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from trading_journal.models._enums import PositionStatus
from trading_journal.models.instrument import Instrument
from trading_journal.models.journal_entry_draft import JournalEntryDraft
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade
from trading_journal.services.journal_entries import prepare_entry
from trading_journal.services.mcp_tokens import McpPrincipal, issue_token


async def test_prepare_pending_option_is_preview_only_and_retry_is_stable(
    auth_client, db_session_maker, monkeypatch
) -> None:
    account = await auth_client.post(
        "/api/accounts",
        json={"name": "Draft", "broker": "Demo", "account_type": "cash", "base_currency": "USD"},
    )
    stock = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "DRAFTBASE", "currency": "USD"}
    )
    assert account.status_code == stock.status_code == 201
    position_response = await auth_client.post(
        "/api/positions",
        json={
            "account_id": account.json()["id"],
            "primary_instrument_id": stock.json()["id"],
            "strategy_type": "spot_stock",
            "opened_at": "2026-05-01T00:00:00Z",
        },
    )
    assert position_response.status_code == 201
    async with db_session_maker() as session:
        owner_id = await session.scalar(select(Position.user_id).limit(1))
        if owner_id is None:
            from trading_journal.models.account import Account

            owner_id = await session.scalar(
                select(Account.user_id).where(Account.id == uuid.UUID(account.json()["id"]))
            )
        assert owner_id is not None
        token_row, _ = await issue_token(
            session, user_id=owner_id, name="draft test", profile="entry", expires_at=None
        )
        principal = McpPrincipal(owner_id, token_row.id, "entry")
        request_id = uuid.uuid4()
        payload = {
            "request_id": str(request_id),
            "kind": "open_position",
            "position": {
                "account_id": account.json()["id"],
                "primary_instrument": {"instrument_id": stock.json()["id"]},
                "strategy_type": "spot_stock",
            },
            "legs": [
                {
                    "instrument": {"instrument_id": stock.json()["id"]},
                    "action": "buy",
                    "quantity": "2",
                    "price": "10.1234567",
                    "executed_at": "2026-06-01T10:00:00",
                    "timezone": "Europe/Amsterdam",
                },
                {
                    "instrument": {
                        "pending": {
                            "kind": "option",
                            "underlying_symbol": "NEWOPT",
                            "currency": "USD",
                            "opt_type": "call",
                            "strike": "12.3456789",
                            "expiry": "2027-01-15",
                        }
                    },
                    "action": "bto",
                    "quantity": "1",
                    "price": "1.2",
                    "executed_at": "2026-06-01T10:01:00+02:00",
                },
            ],
        }
        before_instruments = await session.scalar(select(func.count()).select_from(Instrument))
        before_positions = await session.scalar(select(func.count()).select_from(Position))
        invalid = {**payload, "request_id": str(uuid.uuid4()), "user_id": str(owner_id)}
        with pytest.raises(HTTPException) as invalid_fields:
            await prepare_entry(session, principal, invalid)
        assert invalid_fields.value.status_code == 422
        fractional = {**payload, "request_id": str(uuid.uuid4())}
        fractional["legs"] = [dict(payload["legs"][1], quantity="0.5")]
        with pytest.raises(HTTPException) as invalid_quantity:
            await prepare_entry(session, principal, fractional)
        assert invalid_quantity.value.status_code == 422
        draft = await prepare_entry(
            session, principal, payload, clock=datetime(2026, 6, 1, tzinfo=UTC)
        )
        assert draft.preview["legs"][1]["pending_instrument"]["multiplier"] == 100
        assert draft.preview["legs"][0]["commission"] == "0.0000"
        assert draft.defaults["legs.1.instrument.multiplier"] == 100
        assert draft.defaults["legs.1.instrument.style"] == "american"
        expiry = draft.expires_at
        frozen_preview = draft.preview
        await session.commit()
        from types import SimpleNamespace

        monkeypatch.setattr(
            "trading_journal.services.journal_entries.get_journal_context",
            lambda: SimpleNamespace(timezone="Pacific/Auckland"),
        )
        retry_payload = {**payload}
        retry = await prepare_entry(
            session, principal, retry_payload, clock=datetime(2026, 6, 2, tzinfo=UTC)
        )
        assert retry.id == draft.id
        assert retry.expires_at == expiry
        assert retry.preview == frozen_preview
        with pytest.raises(HTTPException) as conflict:
            await prepare_entry(session, principal, {**payload, "legs": payload["legs"][:1]})
        assert conflict.value.status_code == 409
        assert (
            await session.scalar(select(func.count()).select_from(Instrument)) == before_instruments
        )
        assert await session.scalar(select(func.count()).select_from(Position)) == before_positions
        assert await session.scalar(select(func.count()).select_from(Trade)) == 0
        assert await session.scalar(select(func.count()).select_from(JournalEntryDraft)) == 1
        add_request = {
            "request_id": str(uuid.uuid4()),
            "kind": "add_trades",
            "position_id": position_response.json()["id"],
            "legs": [
                {
                    "instrument": {"instrument_id": stock.json()["id"]},
                    "action": "buy",
                    "quantity": "1",
                    "price": "8",
                    "executed_at": "2026-06-01T00:00:00Z",
                }
            ],
        }
        addition = await prepare_entry(session, principal, add_request)
        assert addition.preview["position"]["position_id"] == position_response.json()["id"]
        target = await session.get(Position, uuid.UUID(position_response.json()["id"]))
        assert target is not None
        target.status = PositionStatus.CLOSED
        with pytest.raises(HTTPException) as closed:
            await prepare_entry(
                session, principal, {**add_request, "request_id": str(uuid.uuid4())}
            )
        assert closed.value.status_code == 409
        other_credential, _ = await issue_token(
            session, user_id=owner_id, name="other entry", profile="entry", expires_at=None
        )
        independent = await prepare_entry(
            session,
            McpPrincipal(owner_id, other_credential.id, "entry"),
            retry_payload,
        )
        assert independent.id != draft.id
        assert independent.credential_id == other_credential.id
        assert "tj_mcp_" not in str(independent.source)
        concurrent_payload = {**payload, "request_id": str(uuid.uuid4())}
        await session.commit()

        async def concurrently_prepare() -> uuid.UUID:
            async with db_session_maker() as concurrent_session:
                result = await prepare_entry(concurrent_session, principal, concurrent_payload)
                await concurrent_session.commit()
                return result.id

        concurrent_ids = await asyncio.gather(concurrently_prepare(), concurrently_prepare())
        assert concurrent_ids[0] == concurrent_ids[1]


async def test_prepare_rejects_read_profile_and_request_control_fields(db_session_maker) -> None:
    async with db_session_maker() as session:
        principal = McpPrincipal(uuid.uuid4(), uuid.uuid4(), "read")
        with pytest.raises(HTTPException) as denied:
            await prepare_entry(session, principal, {})
        assert denied.value.status_code == 403


async def test_prepare_normalizes_order_groups_for_open_and_add_entries(
    auth_client, db_session_maker
) -> None:
    from trading_journal.models.account import Account

    account = await auth_client.post(
        "/api/accounts",
        json={"name": "Groups", "broker": "Demo", "account_type": "cash", "base_currency": "USD"},
    )
    stock = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "GROUPS", "currency": "USD"}
    )
    assert account.status_code == stock.status_code == 201
    position = await auth_client.post(
        "/api/positions",
        json={
            "account_id": account.json()["id"],
            "primary_instrument_id": stock.json()["id"],
            "strategy_type": "spot_stock",
            "opened_at": "2026-05-01T00:00:00Z",
        },
    )
    assert position.status_code == 201

    async with db_session_maker() as session:
        owner_id = await session.scalar(
            select(Account.user_id).where(Account.id == uuid.UUID(account.json()["id"]))
        )
        assert owner_id is not None
        token, _ = await issue_token(
            session, user_id=owner_id, name="groups", profile="entry", expires_at=None
        )
        principal = McpPrincipal(owner_id, token.id, "entry")

        def request(kind: str, groups: list[str | None]) -> dict[str, object]:
            legs = [
                {
                    "instrument": {"instrument_id": stock.json()["id"]},
                    "action": "buy",
                    "quantity": "1",
                    "price": "1",
                    "executed_at": f"2026-06-01T10:{index:02d}:00Z",
                    "order_group_id": group,
                }
                for index, group in enumerate(groups)
            ]
            result: dict[str, object] = {
                "request_id": str(uuid.uuid4()),
                "kind": kind,
                "legs": legs,
            }
            if kind == "open_position":
                result["position"] = {
                    "account_id": account.json()["id"],
                    "primary_instrument": {"instrument_id": stock.json()["id"]},
                    "strategy_type": "spot_stock",
                }
            else:
                result["position_id"] = position.json()["id"]
            return result

        first_group = str(uuid.uuid4())
        second_group = str(uuid.uuid4())
        for kind in ("open_position", "add_trades"):
            before = await session.scalar(select(func.count()).select_from(JournalEntryDraft))
            conflict = request(kind, [first_group, second_group])
            with pytest.raises(HTTPException) as error:
                await prepare_entry(session, principal, conflict)
            assert error.value.status_code == 422
            assert "legs.order_group_id" in error.value.detail
            assert (
                await session.scalar(select(func.count()).select_from(JournalEntryDraft)) == before
            )

            for supplied in (
                [first_group, None],
                [None, None],
                [first_group, first_group],
                [first_group],
                [None],
            ):
                payload = request(kind, supplied)
                draft = await prepare_entry(session, principal, payload)
                normalized_groups = [
                    leg["order_group_id"] for leg in draft.normalized_input["legs"]
                ]
                preview_groups = [leg["order_group_id"] for leg in draft.preview["legs"]]
                if len(supplied) == 1 and supplied[0] is None:
                    assert normalized_groups == preview_groups == [None]
                else:
                    assert normalized_groups == preview_groups
                    assert len(set(normalized_groups)) == 1
                    assert normalized_groups[0] is not None
                await session.flush()
                retry = await prepare_entry(session, principal, payload)
                assert retry.id == draft.id
                assert [leg["order_group_id"] for leg in retry.preview["legs"]] == preview_groups

        assert await session.scalar(select(func.count()).select_from(Position)) == 1
        assert await session.scalar(select(func.count()).select_from(Trade)) == 0


async def test_prepare_reports_entry_field_paths_and_enforces_numeric_and_open_dates(
    auth_client, db_session_maker, monkeypatch
) -> None:
    from types import SimpleNamespace

    from sqlalchemy import select

    from trading_journal.models.account import Account

    monkeypatch.setattr(
        "trading_journal.services.journal_entries.get_journal_context",
        lambda: SimpleNamespace(timezone="Europe/Amsterdam"),
    )

    account = await auth_client.post(
        "/api/accounts",
        json={
            "name": "Validation",
            "broker": "Demo",
            "account_type": "cash",
            "base_currency": "USD",
        },
    )
    stock = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "VALIDATE", "currency": "USD"}
    )
    assert account.status_code == stock.status_code == 201
    async with db_session_maker() as session:
        owner_id = await session.scalar(
            select(Account.user_id).where(Account.id == uuid.UUID(account.json()["id"]))
        )
        assert owner_id is not None
        token, _ = await issue_token(
            session, user_id=owner_id, name="validation", profile="entry", expires_at=None
        )
        principal = McpPrincipal(owner_id, token.id, "entry")
        base = {
            "request_id": str(uuid.uuid4()),
            "kind": "open_position",
            "position": {
                "account_id": account.json()["id"],
                "primary_instrument": {"instrument_id": stock.json()["id"]},
                "strategy_type": "spot_stock",
            },
            "legs": [
                {
                    "instrument": {"instrument_id": stock.json()["id"]},
                    "action": "buy",
                    "quantity": "1",
                    "price": "10",
                    "executed_at": "2026-06-01T10:00:00Z",
                }
            ],
        }

        for opened_at in (None, "2025-01-01T00:00:00Z", "2027-01-01T00:00:00Z"):
            invalid_date = {
                **base,
                "request_id": str(uuid.uuid4()),
                "position": dict(base["position"]),
            }
            if opened_at is not None:
                invalid_date["position"]["opened_at"] = opened_at
            elif "opened_at" in invalid_date["position"]:
                del invalid_date["position"]["opened_at"]
            invalid_date["legs"] = [{**base["legs"][0], "executed_at": "2026-03-29T02:30:00"}]
            with pytest.raises(HTTPException) as gap:
                await prepare_entry(session, principal, invalid_date)
            assert gap.value.status_code == 422
            assert "legs.0.executed_at" in gap.value.detail

        for executed_at, timezone in (
            ("2026-10-25T02:30:00", "Europe/Amsterdam"),
            ("2026-06-01T10:00:00", "Mars/Olympus"),
            ("2026-06-01T10:00:00+00:00", "Europe/Amsterdam"),
        ):
            invalid_time = {
                **base,
                "request_id": str(uuid.uuid4()),
                "legs": [{**base["legs"][0], "executed_at": executed_at, "timezone": timezone}],
            }
            with pytest.raises(HTTPException) as time_error:
                await prepare_entry(session, principal, invalid_time)
            assert time_error.value.status_code == 422
            assert "legs.0.timezone" in time_error.value.detail

        for opened_at in ("2025-01-01T00:00:00Z", "2027-01-01T00:00:00Z"):
            invalid_date = {
                **base,
                "request_id": str(uuid.uuid4()),
                "position": {**base["position"], "opened_at": opened_at},
            }
            with pytest.raises(HTTPException) as mismatch:
                await prepare_entry(session, principal, invalid_date)
            assert mismatch.value.status_code == 422
            assert "position.opened_at" in mismatch.value.detail

        bad_reference = {
            **base,
            "request_id": str(uuid.uuid4()),
            "legs": [{**base["legs"][0], "instrument": {"instrument_id": str(uuid.uuid4())}}],
        }
        with pytest.raises(HTTPException) as missing_leg:
            await prepare_entry(session, principal, bad_reference)
        assert missing_leg.value.status_code == 422
        assert "legs.0.instrument" in missing_leg.value.detail

        bad_primary = {
            **base,
            "request_id": str(uuid.uuid4()),
            "position": {
                **base["position"],
                "primary_instrument": {"instrument_id": str(uuid.uuid4())},
            },
        }
        with pytest.raises(HTTPException) as missing_primary:
            await prepare_entry(session, principal, bad_primary)
        assert missing_primary.value.status_code == 422
        assert "position.primary_instrument" in missing_primary.value.detail

        from trading_journal.schemas.instrument import ForexCreate
        from trading_journal.services.instruments import get_or_create_instrument

        existing_forex = ForexCreate.model_validate(
            {
                "kind": "forex",
                "symbol": "EUR/USD",
                "base_currency": "EUR",
                "quote_currency": "USD",
                "pip_size": "0.0001",
            }
        )
        await get_or_create_instrument(session, existing_forex)
        conflicting_forex = {
            **base,
            "request_id": str(uuid.uuid4()),
            "legs": [
                {
                    **base["legs"][0],
                    "instrument": {
                        "pending": {
                            "kind": "forex",
                            "symbol": "EUR/USD",
                            "base_currency": "EUR",
                            "quote_currency": "USD",
                            "pip_size": "0.0002",
                        }
                    },
                }
            ],
        }
        with pytest.raises(HTTPException) as spec_conflict:
            await prepare_entry(session, principal, conflicting_forex)
        assert spec_conflict.value.status_code == 422
        assert "legs.0.instrument.pending" in spec_conflict.value.detail

        for field, value, expected_path in (
            ("price", "1e100", "legs.0.price"),
            ("quantity", "1e100", "legs.0.quantity"),
            ("commission", "1e100", "legs.0.commission"),
            ("fees", "1e100", "legs.0.fees"),
        ):
            huge_value = {
                **base,
                "request_id": str(uuid.uuid4()),
                "legs": [{**base["legs"][0], field: value}],
            }
            with pytest.raises(HTTPException) as value_range:
                await prepare_entry(session, principal, huge_value)
            assert value_range.value.status_code == 422
            assert expected_path in value_range.value.detail

        overflow_cash_flow = {
            **base,
            "request_id": str(uuid.uuid4()),
            "legs": [
                {
                    **base["legs"][0],
                    "price": "999999999999",
                    "quantity": "9999999999",
                }
            ],
        }
        with pytest.raises(HTTPException) as cash_flow_range:
            await prepare_entry(session, principal, overflow_cash_flow)
        assert cash_flow_range.value.status_code == 422
        assert "legs.0.price" in cash_flow_range.value.detail

        oversized_contract = {
            **base,
            "request_id": str(uuid.uuid4()),
            "legs": [
                {
                    **base["legs"][0],
                    "instrument": {
                        "pending": {
                            "kind": "option",
                            "underlying_symbol": "VALIDATE",
                            "currency": "USD",
                            "opt_type": "call",
                            "strike": "1e100",
                            "expiry": "2027-01-15",
                        }
                    },
                }
            ],
        }
        with pytest.raises(HTTPException) as contract_range:
            await prepare_entry(session, principal, oversized_contract)
        assert contract_range.value.status_code == 422
        assert "legs.0.instrument.pending.strike" in contract_range.value.detail

        from trading_journal.schemas.instrument import OptionCreate
        from trading_journal.services.instruments import get_or_create_instrument

        option_spec = OptionCreate.model_validate(
            {
                "kind": "option",
                "underlying_symbol": "VALIDATE",
                "currency": "USD",
                "opt_type": "call",
                "strike": "12.3456789",
                "expiry": "2027-01-15",
            }
        )
        existing_option, created = await get_or_create_instrument(session, option_spec)
        assert created
        for instrument_reference in (
            {"instrument_id": str(existing_option.id)},
            {"pending": option_spec.model_dump(mode="json")},
        ):
            huge_option_quantity = {
                **base,
                "request_id": str(uuid.uuid4()),
                "legs": [
                    {
                        **base["legs"][0],
                        "instrument": instrument_reference,
                        "action": "bto",
                        "quantity": "1e100",
                    }
                ],
            }
            before_drafts = await session.scalar(
                select(func.count()).select_from(JournalEntryDraft)
            )
            with pytest.raises(HTTPException) as option_quantity_range:
                await prepare_entry(session, principal, huge_option_quantity)
            assert option_quantity_range.value.status_code == 422
            assert option_quantity_range.value.detail == {
                "legs.0.quantity": "value exceeds supported numeric precision"
            }
            assert (
                await session.scalar(select(func.count()).select_from(JournalEntryDraft))
                == before_drafts
            )

        huge_capital = {
            **base,
            "request_id": str(uuid.uuid4()),
            "position": {**base["position"], "capital_used": "1e100"},
        }
        with pytest.raises(HTTPException) as capital_range:
            await prepare_entry(session, principal, huge_capital)
        assert capital_range.value.status_code == 422
        assert "position.capital_used" in capital_range.value.detail

        for field in ("max_risk_at_open", "max_reward_at_open"):
            huge_value = {
                **base,
                "request_id": str(uuid.uuid4()),
                "position": {**base["position"], field: "1e100"},
            }
            with pytest.raises(HTTPException) as value_range:
                await prepare_entry(session, principal, huge_value)
            assert value_range.value.status_code == 422
            assert f"position.{field}" in value_range.value.detail

        valid = await prepare_entry(session, principal, base)
        assert valid.preview["position"]["opened_at_utc"] == "2026-06-01T10:00:00+00:00"
        assert valid.normalized_input["legs"][0]["timezone"] is None


async def test_prepare_hides_foreign_account_and_keeps_archived_account_rule(
    auth_client, second_user_client, db_session_maker
) -> None:
    from sqlalchemy import select

    from trading_journal.models.account import Account

    account = await auth_client.post(
        "/api/accounts",
        json={"name": "Owned", "broker": "Demo", "account_type": "cash", "base_currency": "USD"},
    )
    stock = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "OWNERTEST", "currency": "USD"}
    )
    foreign = await second_user_client.post(
        "/api/accounts",
        json={"name": "Foreign", "broker": "Demo", "account_type": "cash", "base_currency": "USD"},
    )
    assert account.status_code == stock.status_code == foreign.status_code == 201
    async with db_session_maker() as session:
        owner_id = await session.scalar(
            select(Account.user_id).where(Account.id == uuid.UUID(account.json()["id"]))
        )
        assert owner_id is not None
        token, _ = await issue_token(
            session, user_id=owner_id, name="ownership", profile="entry", expires_at=None
        )
        principal = McpPrincipal(owner_id, token.id, "entry")
        payload = {
            "request_id": str(uuid.uuid4()),
            "kind": "open_position",
            "position": {
                "account_id": foreign.json()["id"],
                "primary_instrument": {"instrument_id": stock.json()["id"]},
                "strategy_type": "spot_stock",
            },
            "legs": [
                {
                    "instrument": {"instrument_id": stock.json()["id"]},
                    "action": "buy",
                    "quantity": "1",
                    "price": "10",
                    "executed_at": "2026-06-01T10:00:00Z",
                }
            ],
        }
        with pytest.raises(HTTPException) as foreign_error:
            await prepare_entry(session, principal, payload)
        assert foreign_error.value.status_code == 404
        with pytest.raises(HTTPException) as missing_error:
            await prepare_entry(
                session,
                principal,
                {
                    **payload,
                    "request_id": str(uuid.uuid4()),
                    "position": {**payload["position"], "account_id": str(uuid.uuid4())},
                },
            )
        assert missing_error.value.status_code == 404
        archived = await session.get(Account, uuid.UUID(account.json()["id"]))
        assert archived is not None
        from datetime import UTC, datetime

        archived.archived_at = datetime.now(UTC)
        with pytest.raises(HTTPException) as archived_error:
            await prepare_entry(
                session,
                principal,
                {
                    **payload,
                    "request_id": str(uuid.uuid4()),
                    "position": {**payload["position"], "account_id": account.json()["id"]},
                },
            )
        assert archived_error.value.status_code == 422


async def test_prepare_numeric_preview_matches_migrated_sqlite_writes(
    auth_client, db_session_maker
) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from sqlalchemy import select

    from trading_journal.models._enums import StrategyType
    from trading_journal.models.account import Account
    from trading_journal.models.instrument import ForexPair, OptionContract
    from trading_journal.schemas.instrument import ForexCreate, OptionCreate
    from trading_journal.schemas.trade import TradeCreate
    from trading_journal.services.instruments import get_or_create_instrument
    from trading_journal.services.positions import create_position
    from trading_journal.services.trades import create_trades_atomic

    account_response = await auth_client.post(
        "/api/accounts",
        json={
            "name": "Precision",
            "broker": "Demo",
            "account_type": "cash",
            "base_currency": "USD",
        },
    )
    stock_response = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "PRECISION", "currency": "USD"}
    )
    assert account_response.status_code == stock_response.status_code == 201
    async with db_session_maker() as session:
        account_id = uuid.UUID(account_response.json()["id"])
        instrument_id = uuid.UUID(stock_response.json()["id"])
        user_id = await session.scalar(select(Account.user_id).where(Account.id == account_id))
        assert user_id is not None
        credential, _ = await issue_token(
            session, user_id=user_id, name="precision", profile="entry", expires_at=None
        )
        principal = McpPrincipal(user_id, credential.id, "entry")
        executed_at = datetime(2026, 6, 1, 10, tzinfo=UTC)
        payload = {
            "request_id": str(uuid.uuid4()),
            "kind": "open_position",
            "position": {
                "account_id": str(account_id),
                "primary_instrument": {"instrument_id": str(instrument_id)},
                "strategy_type": "spot_stock",
                "opened_at": executed_at.isoformat(),
                "capital_used": "1.23456",
            },
            "legs": [
                {
                    "instrument": {"instrument_id": str(instrument_id)},
                    "action": "buy",
                    "quantity": "0.000000005",
                    "price": "1.2345678",
                    "commission": "1.23445",
                    "executed_at": executed_at.isoformat(),
                }
            ],
        }
        draft = await prepare_entry(session, principal, payload)
        position = await create_position(
            session,
            user_id=user_id,
            account_id=account_id,
            primary_instrument_id=instrument_id,
            strategy_type=StrategyType.SPOT_STOCK,
            opened_at=executed_at,
            capital_used=Decimal("1.23456"),
        )
        await session.flush()
        await session.refresh(position)
        trades = await create_trades_atomic(
            session,
            position,
            [
                TradeCreate.model_validate(
                    {
                        "position_id": position.id,
                        "instrument_id": instrument_id,
                        "action": "buy",
                        "quantity": "0.000000005",
                        "price": "1.2345678",
                        "commission": "1.23445",
                        "fees": "0",
                        "executed_at": executed_at,
                    }
                )
            ],
        )
        leg_preview = draft.preview["legs"][0]
        assert leg_preview["quantity"] == str(trades[0].quantity)
        assert leg_preview["price"] == str(trades[0].price)
        assert leg_preview["commission"] == str(trades[0].commission)
        assert leg_preview["cash_flow"] == str(trades[0].cash_flow)
        assert draft.preview["position"]["capital_used"] == str(position.capital_used)

        pending_option = OptionCreate.model_validate(
            {
                "kind": "option",
                "underlying_symbol": "PRECISION",
                "currency": "USD",
                "opt_type": "call",
                "strike": "12.3456789",
                "expiry": "2027-01-15",
            }
        )
        option_preview_request = {
            **payload,
            "request_id": str(uuid.uuid4()),
            "legs": [
                {
                    "instrument": {"pending": pending_option.model_dump(mode="json")},
                    "action": "bto",
                    "quantity": "1",
                    "price": "1",
                    "executed_at": executed_at.isoformat(),
                }
            ],
        }
        option_draft = await prepare_entry(session, principal, option_preview_request)
        option, created = await get_or_create_instrument(session, pending_option)
        assert created
        contract = await session.get(OptionContract, option.id)
        assert contract is not None
        assert option_draft.preview["legs"][0]["pending_instrument"]["strike"] == str(
            contract.strike
        )
        assert option_draft.normalized_input["legs"][0]["instrument"]["pending"]["strike"] == (
            "12.3456789"
        )
        from trading_journal.services.instruments import resolve_instrument_spec

        normalized_option = OptionCreate.model_validate(
            option_draft.normalized_input["legs"][0]["instrument"]["pending"]
        )
        normalized_resolution = await resolve_instrument_spec(session, normalized_option)
        assert normalized_resolution is not None
        assert normalized_resolution.id == option.id

        existing_option_payload = {
            **payload,
            "request_id": str(uuid.uuid4()),
            "position": {
                **payload["position"],
                "primary_instrument": {"pending": pending_option.model_dump(mode="json")},
            },
            "legs": [
                {
                    **option_preview_request["legs"][0],
                    "instrument": {"pending": pending_option.model_dump(mode="json")},
                },
                {
                    **option_preview_request["legs"][0],
                    "instrument": {"pending": pending_option.model_dump(mode="json")},
                },
            ],
        }
        existing_option_draft = await prepare_entry(session, principal, existing_option_payload)
        option_id = str(option.id)
        assert existing_option_draft.normalized_input["position"]["primary_instrument"] == {
            "instrument_id": option_id
        }
        assert [leg["instrument"] for leg in existing_option_draft.normalized_input["legs"]] == [
            {"instrument_id": option_id},
            {"instrument_id": option_id},
        ]
        assert existing_option_draft.preview["position"]["primary_instrument"]["id"] == option_id
        assert [leg["instrument"]["id"] for leg in existing_option_draft.preview["legs"]] == [
            option_id,
            option_id,
        ]
        assert all(
            leg["pending_instrument"] is None for leg in existing_option_draft.preview["legs"]
        )

        pending_forex = ForexCreate.model_validate(
            {
                "kind": "forex",
                "symbol": "EUR/USD",
                "base_currency": "EUR",
                "quote_currency": "USD",
                "pip_size": "0.123456789",
                "contract_size": "1.23456",
            }
        )
        forex_payload = {
            **payload,
            "request_id": str(uuid.uuid4()),
            "legs": [
                {
                    "instrument": {"pending": pending_forex.model_dump(mode="json")},
                    "action": "buy",
                    "quantity": "1",
                    "price": "1",
                    "executed_at": executed_at.isoformat(),
                }
            ],
        }
        forex_draft = await prepare_entry(session, principal, forex_payload)
        forex, created = await get_or_create_instrument(session, pending_forex)
        assert created
        pair = await session.get(ForexPair, forex.id)
        assert pair is not None
        forex_preview = forex_draft.preview["legs"][0]["pending_instrument"]
        assert forex_preview["pip_size"] == str(pair.pip_size)
        assert forex_preview["contract_size"] == str(pair.contract_size)
        assert forex_draft.normalized_input["legs"][0]["instrument"]["pending"]["pip_size"] == (
            "0.123456789"
        )
        normalized_forex = ForexCreate.model_validate(
            forex_draft.normalized_input["legs"][0]["instrument"]["pending"]
        )
        normalized_forex_resolution = await resolve_instrument_spec(session, normalized_forex)
        assert normalized_forex_resolution is not None
        assert normalized_forex_resolution.id == forex.id


async def test_prepare_keeps_position_currency_separate_across_existing_and_pending_instruments(
    auth_client, db_session_maker
) -> None:
    """MCP drafts must not combine instrument cash flows across currencies."""
    from trading_journal.models.account import Account

    account = await auth_client.post(
        "/api/accounts",
        json={"name": "Currency", "broker": "Demo", "account_type": "cash", "base_currency": "USD"},
    )
    usd_stock = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "CURUSD", "currency": "USD"}
    )
    eur_stock = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "CUREUR", "currency": "EUR"}
    )
    eur_option = await auth_client.post(
        "/api/instruments",
        json={
            "kind": "option",
            "underlying_symbol": "CUROPT",
            "currency": "EUR",
            "opt_type": "call",
            "strike": "10",
            "expiry": "2027-01-15",
        },
    )
    eur_forex = await auth_client.post(
        "/api/instruments",
        json={
            "kind": "forex",
            "symbol": "CURUSD-EUR",
            "base_currency": "USD",
            "quote_currency": "EUR",
            "pip_size": "0.0001",
        },
    )
    assert all(
        r.status_code in (200, 201) for r in (account, usd_stock, eur_stock, eur_option, eur_forex)
    )
    usd_position = await auth_client.post(
        "/api/positions",
        json={
            "account_id": account.json()["id"],
            "primary_instrument_id": usd_stock.json()["id"],
            "strategy_type": "spot_stock",
            "opened_at": "2026-07-15T12:00:00Z",
        },
    )
    eur_position = await auth_client.post(
        "/api/positions",
        json={
            "account_id": account.json()["id"],
            "primary_instrument_id": eur_stock.json()["id"],
            "strategy_type": "spot_stock",
            "opened_at": "2026-07-15T12:00:00Z",
        },
    )
    assert usd_position.status_code == eur_position.status_code == 201

    pending_eur_stock = {"kind": "stock", "symbol": "CURPENDEUR", "currency": "EUR"}
    pending_eur_option = {
        "kind": "option",
        "underlying_symbol": "CURPENDOPT",
        "currency": "EUR",
        "opt_type": "call",
        "strike": "10",
        "expiry": "2027-01-15",
    }
    pending_eur_forex = {
        "kind": "forex",
        "symbol": "CURPEND-USD-EUR",
        "base_currency": "USD",
        "quote_currency": "EUR",
        "pip_size": "0.0001",
    }
    pending_usd_forex = {
        "kind": "forex",
        "symbol": "CURPEND-EUR-USD",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "pip_size": "0.0001",
    }

    async with db_session_maker() as session:
        owner_id = await session.scalar(
            select(Account.user_id).where(Account.id == uuid.UUID(account.json()["id"]))
        )
        assert owner_id is not None
        token, _ = await issue_token(
            session, user_id=owner_id, name="currency entry", profile="entry", expires_at=None
        )
        principal = McpPrincipal(owner_id, token.id, "entry")

        def leg(reference: dict[str, object], action: str = "buy") -> dict[str, object]:
            return {
                "instrument": reference,
                "action": action,
                "quantity": "1",
                "price": "1",
                "executed_at": "2026-07-15T12:00:00Z",
            }

        def request(
            kind: str, primary: dict[str, object], instrument_leg: dict[str, object]
        ) -> dict[str, object]:
            result: dict[str, object] = {
                "request_id": str(uuid.uuid4()),
                "kind": kind,
                "legs": [instrument_leg],
            }
            if kind == "open_position":
                result["position"] = {
                    "account_id": account.json()["id"],
                    "primary_instrument": primary,
                    "strategy_type": "spot_stock",
                }
            else:
                result["position_id"] = primary["position_id"]
            return result

        before_instruments = await session.scalar(select(func.count()).select_from(Instrument))
        before_positions = await session.scalar(select(func.count()).select_from(Position))
        before_trades = await session.scalar(select(func.count()).select_from(Trade))
        before_drafts = await session.scalar(select(func.count()).select_from(JournalEntryDraft))
        wrong_currency_legs = [
            {"instrument_id": eur_stock.json()["id"]},
            {"instrument_id": eur_option.json()["id"]},
            {"instrument_id": eur_forex.json()["id"]},
            {"pending": pending_eur_stock},
            {"pending": pending_eur_option},
            {"pending": pending_eur_forex},
        ]
        for reference in wrong_currency_legs:
            invalid = request(
                "open_position",
                {"instrument_id": usd_stock.json()["id"]},
                leg(reference, "bto" if reference in wrong_currency_legs[1:2] else "buy"),
            )
            with pytest.raises(HTTPException) as error:
                await prepare_entry(session, principal, invalid)
            assert error.value.status_code == 422
            assert "legs.0.instrument" in error.value.detail

        later_leg_mismatch = request(
            "open_position",
            {"instrument_id": usd_stock.json()["id"]},
            leg({"instrument_id": usd_stock.json()["id"]}),
        )
        later_leg_mismatch["legs"].append(leg({"pending": pending_eur_forex}))
        with pytest.raises(HTTPException) as later_error:
            await prepare_entry(session, principal, later_leg_mismatch)
        assert later_error.value.status_code == 422
        assert "legs.1.instrument" in later_error.value.detail

        for reference in (
            {"instrument_id": usd_stock.json()["id"]},
            {"pending": pending_usd_forex},
        ):
            invalid = request(
                "add_trades",
                {"position_id": eur_position.json()["id"]},
                leg(reference),
            )
            with pytest.raises(HTTPException) as error:
                await prepare_entry(session, principal, invalid)
            assert error.value.status_code == 422
            assert "legs.0.instrument" in error.value.detail

        # Account.base_currency is not the Position currency contract. Existing and pending
        # primaries, and forex legs with a matching quote currency, remain valid.
        valid_requests = [
            request(
                "open_position",
                {"instrument_id": eur_stock.json()["id"]},
                leg({"instrument_id": eur_forex.json()["id"]}),
            ),
            request(
                "open_position",
                {"pending": pending_eur_stock},
                leg({"pending": pending_eur_forex}),
            ),
            request(
                "open_position",
                {
                    "pending": {
                        "kind": "forex",
                        "symbol": "CURPRIMARY-USD-EUR",
                        "base_currency": "USD",
                        "quote_currency": "EUR",
                        "pip_size": "0.0001",
                    }
                },
                leg({"instrument_id": eur_stock.json()["id"]}),
            ),
            request(
                "open_position",
                {"instrument_id": usd_stock.json()["id"]},
                leg({"instrument_id": usd_stock.json()["id"]}),
            ),
            request(
                "add_trades",
                {"position_id": eur_position.json()["id"]},
                leg({"instrument_id": eur_forex.json()["id"]}),
            ),
        ]
        for valid in valid_requests:
            await prepare_entry(session, principal, valid)
        assert (
            await session.scalar(select(func.count()).select_from(Instrument)) == before_instruments
        )
        assert await session.scalar(select(func.count()).select_from(Position)) == before_positions
        assert await session.scalar(select(func.count()).select_from(Trade)) == before_trades
        assert await session.scalar(
            select(func.count()).select_from(JournalEntryDraft)
        ) == before_drafts + len(valid_requests)


async def test_prepare_rejects_conflicting_pending_batch_specs_without_writes(
    auth_client, db_session_maker
) -> None:
    account = await auth_client.post(
        "/api/accounts",
        json={
            "name": "Batch specs",
            "broker": "Demo",
            "account_type": "cash",
            "base_currency": "USD",
        },
    )
    stock = await auth_client.post(
        "/api/instruments", json={"kind": "stock", "symbol": "BATCHBASE", "currency": "USD"}
    )
    assert account.status_code == stock.status_code == 201
    async with db_session_maker() as session:
        from trading_journal.models.account import Account

        owner_id = await session.scalar(
            select(Account.user_id).where(Account.id == uuid.UUID(account.json()["id"]))
        )
        assert owner_id is not None
        token_row, _ = await issue_token(
            session, user_id=owner_id, name="batch spec test", profile="entry", expires_at=None
        )
        principal = McpPrincipal(owner_id, token_row.id, "entry")

        def leg(reference: dict[str, object], action: str = "buy") -> dict[str, object]:
            return {
                "instrument": reference,
                "action": action,
                "quantity": "1",
                "price": "1",
                "executed_at": "2026-06-01T10:00:00Z",
            }

        def request(
            refs: list[dict[str, object]], *, primary: dict[str, object] | None = None
        ) -> dict[str, object]:
            return {
                "request_id": str(uuid.uuid4()),
                "kind": "open_position",
                "position": {
                    "account_id": account.json()["id"],
                    "primary_instrument": primary or {"instrument_id": stock.json()["id"]},
                    "strategy_type": "spot_stock",
                },
                "legs": [
                    leg(ref, "bto" if ref.get("pending", {}).get("kind") == "option" else "buy")
                    for ref in refs
                ],
            }

        before = (
            await session.scalar(select(func.count()).select_from(Instrument)),
            await session.scalar(select(func.count()).select_from(Position)),
            await session.scalar(select(func.count()).select_from(Trade)),
            await session.scalar(select(func.count()).select_from(JournalEntryDraft)),
        )
        cases = [
            (
                request(
                    [
                        {
                            "pending": {
                                "kind": "forex",
                                "symbol": "BATCHFX",
                                "base_currency": "EUR",
                                "quote_currency": "USD",
                                "pip_size": "0.0001",
                            }
                        },
                        {
                            "pending": {
                                "kind": "forex",
                                "symbol": "batchfx",
                                "base_currency": "EUR",
                                "quote_currency": "USD",
                                "pip_size": "0.0002",
                            }
                        },
                    ]
                ),
                "legs.1.instrument.pending.pip_size",
            ),
            (
                request(
                    [
                        {
                            "pending": {
                                "kind": "forex",
                                "symbol": "BATCHBASEFX",
                                "base_currency": "EUR",
                                "quote_currency": "USD",
                                "pip_size": "0.0001",
                            }
                        },
                        {
                            "pending": {
                                "kind": "forex",
                                "symbol": "batchbasefx",
                                "base_currency": "GBP",
                                "quote_currency": "USD",
                                "pip_size": "0.0001",
                            }
                        },
                    ]
                ),
                "legs.1.instrument.pending.base_currency",
            ),
            (
                request(
                    [
                        {
                            "pending": {
                                "kind": "forex",
                                "symbol": "BATCHQUOTEFX",
                                "base_currency": "EUR",
                                "quote_currency": "USD",
                                "pip_size": "0.0001",
                            }
                        },
                        {
                            "pending": {
                                "kind": "forex",
                                "symbol": "batchquotefx",
                                "base_currency": "EUR",
                                "quote_currency": "GBP",
                                "pip_size": "0.0001",
                            }
                        },
                    ]
                ),
                "legs.1.instrument.pending.quote_currency",
            ),
            (
                request(
                    [
                        {
                            "pending": {
                                "kind": "forex",
                                "symbol": "BATCHCONTRACT",
                                "base_currency": "EUR",
                                "quote_currency": "USD",
                                "pip_size": "0.0001",
                                "contract_size": "100000",
                            }
                        },
                        {
                            "pending": {
                                "kind": "forex",
                                "symbol": "batchcontract",
                                "base_currency": "EUR",
                                "quote_currency": "USD",
                                "pip_size": "0.0001",
                                "contract_size": "200000",
                            }
                        },
                    ]
                ),
                "legs.1.instrument.pending.contract_size",
            ),
            (
                request(
                    [
                        {
                            "pending": {
                                "kind": "option",
                                "underlying_symbol": "BATCHOPT",
                                "currency": "USD",
                                "opt_type": "call",
                                "strike": "10",
                                "expiry": "2027-01-15",
                                "style": "american",
                            }
                        },
                        {
                            "pending": {
                                "kind": "option",
                                "underlying_symbol": "batchopt",
                                "currency": "USD",
                                "opt_type": "call",
                                "strike": "10.000000",
                                "expiry": "2027-01-15",
                                "style": "european",
                            }
                        },
                    ]
                ),
                "legs.1.instrument.pending.style",
            ),
            (
                request(
                    [
                        {
                            "pending": {
                                "kind": "forex",
                                "symbol": "PRIMARYFX",
                                "base_currency": "EUR",
                                "quote_currency": "USD",
                                "pip_size": "0.0001",
                            }
                        }
                    ],
                    primary={
                        "pending": {
                            "kind": "forex",
                            "symbol": "primaryfx",
                            "base_currency": "EUR",
                            "quote_currency": "USD",
                            "pip_size": "0.0002",
                        }
                    },
                ),
                "legs.0.instrument.pending.pip_size",
            ),
        ]
        oversized_missing_underlying = {
            "kind": "option",
            "underlying_symbol": "TOOBIGMISSING",
            "currency": "USD",
            "opt_type": "call",
            "strike": "10",
            "expiry": "2027-01-15",
            "multiplier": 2**63,
        }
        oversized_existing_underlying = {
            **oversized_missing_underlying,
            "underlying_symbol": "BATCHBASE",
        }
        cases.extend(
            [
                (
                    request([{"pending": oversized_missing_underlying}]),
                    "legs.0.instrument.pending.multiplier",
                ),
                (
                    request([{"pending": oversized_existing_underlying}]),
                    "legs.0.instrument.pending.multiplier",
                ),
                (
                    request(
                        [{"instrument_id": stock.json()["id"]}],
                        primary={"pending": oversized_missing_underlying},
                    ),
                    "position.primary_instrument.pending.multiplier",
                ),
                (
                    request(
                        [{"instrument_id": stock.json()["id"]}],
                        primary={"pending": oversized_existing_underlying},
                    ),
                    "position.primary_instrument.pending.multiplier",
                ),
                (
                    request(
                        [
                            {
                                "pending": {
                                    "kind": "option",
                                    "underlying_symbol": "TOOBIGSTRIKE",
                                    "currency": "USD",
                                    "opt_type": "call",
                                    "strike": "1000000000000",
                                    "expiry": "2027-01-15",
                                }
                            }
                        ]
                    ),
                    "legs.0.instrument.pending.strike",
                ),
                (
                    request(
                        [
                            {
                                "pending": {
                                    "kind": "forex",
                                    "symbol": "TOOBIGPIP",
                                    "base_currency": "EUR",
                                    "quote_currency": "USD",
                                    "pip_size": "100",
                                }
                            }
                        ]
                    ),
                    "legs.0.instrument.pending.pip_size",
                ),
                (
                    request(
                        [
                            {
                                "pending": {
                                    "kind": "forex",
                                    "symbol": "TOOBIGCONTRACT",
                                    "base_currency": "EUR",
                                    "quote_currency": "USD",
                                    "pip_size": "0.0001",
                                    "contract_size": "100000000000000",
                                }
                            }
                        ]
                    ),
                    "legs.0.instrument.pending.contract_size",
                ),
            ]
        )
        tiny_positive = "1e-100"
        cases.extend(
            [
                (
                    request([{"instrument_id": stock.json()["id"]}])
                    | {
                        "legs": [
                            leg({"instrument_id": stock.json()["id"]}) | {"quantity": tiny_positive}
                        ]
                    },
                    "legs.0.quantity",
                ),
                (
                    request([{"instrument_id": stock.json()["id"]}])
                    | {
                        "position": {
                            "account_id": account.json()["id"],
                            "primary_instrument": {"instrument_id": stock.json()["id"]},
                            "strategy_type": "spot_stock",
                            "capital_used": tiny_positive,
                        }
                    },
                    "position.capital_used",
                ),
                (
                    request([{"instrument_id": stock.json()["id"]}])
                    | {
                        "position": {
                            "account_id": account.json()["id"],
                            "primary_instrument": {"instrument_id": stock.json()["id"]},
                            "strategy_type": "spot_stock",
                            "max_risk_at_open": tiny_positive,
                        }
                    },
                    "position.max_risk_at_open",
                ),
                (
                    request([{"instrument_id": stock.json()["id"]}])
                    | {
                        "position": {
                            "account_id": account.json()["id"],
                            "primary_instrument": {"instrument_id": stock.json()["id"]},
                            "strategy_type": "spot_stock",
                            "max_reward_at_open": tiny_positive,
                        }
                    },
                    "position.max_reward_at_open",
                ),
                (
                    request(
                        [
                            {
                                "pending": {
                                    "kind": "option",
                                    "underlying_symbol": "TINYSTRIKE",
                                    "currency": "USD",
                                    "opt_type": "call",
                                    "strike": tiny_positive,
                                    "expiry": "2027-01-15",
                                }
                            }
                        ]
                    ),
                    "legs.0.instrument.pending.strike",
                ),
                (
                    request(
                        [
                            {
                                "pending": {
                                    "kind": "forex",
                                    "symbol": "TINYPIP",
                                    "base_currency": "EUR",
                                    "quote_currency": "USD",
                                    "pip_size": tiny_positive,
                                }
                            }
                        ]
                    ),
                    "legs.0.instrument.pending.pip_size",
                ),
                (
                    request(
                        [
                            {
                                "pending": {
                                    "kind": "forex",
                                    "symbol": "TINYCONTRACT",
                                    "base_currency": "EUR",
                                    "quote_currency": "USD",
                                    "pip_size": "0.0001",
                                    "contract_size": tiny_positive,
                                }
                            }
                        ]
                    ),
                    "legs.0.instrument.pending.contract_size",
                ),
            ]
        )
        for invalid, expected_field in cases:
            with pytest.raises(HTTPException) as error:
                await prepare_entry(session, principal, invalid)
            assert error.value.status_code == 422
            assert expected_field in error.value.detail
            current = (
                await session.scalar(select(func.count()).select_from(Instrument)),
                await session.scalar(select(func.count()).select_from(Position)),
                await session.scalar(select(func.count()).select_from(Trade)),
                await session.scalar(select(func.count()).select_from(JournalEntryDraft)),
            )
            assert current == before

        boundary = request([{"pending": {**oversized_missing_underlying, "multiplier": 2**63 - 1}}])
        boundary["legs"][0]["price"] = "0"
        boundary["legs"][0]["quantity"] = "1"
        boundary["position"].update(
            {"capital_used": "0.0001", "max_risk_at_open": None, "max_reward_at_open": None}
        )
        supported = await prepare_entry(session, principal, boundary)
        assert supported.preview["legs"][0]["multiplier"] == 2**63 - 1
        assert supported.preview["legs"][0]["price"] == "0.000000"
        assert supported.preview["legs"][0]["cash_flow"] == "-0.0000"
        assert supported.preview["position"]["capital_used"] == "0.0001"
        assert supported.preview["position"]["max_risk_at_open"] is None
        minimum_quantity = request([{"instrument_id": stock.json()["id"]}])
        minimum_quantity["legs"][0].update({"quantity": "0.00000001", "price": "0"})
        minimum_quantity_draft = await prepare_entry(session, principal, minimum_quantity)
        assert minimum_quantity_draft.preview["legs"][0]["quantity"] == "1E-8"
        assert minimum_quantity_draft.preview["legs"][0]["cash_flow"] == "-0.0000"
        minimum_option = request(
            [
                {
                    "pending": {
                        "kind": "option",
                        "underlying_symbol": "MINSTRIKE",
                        "currency": "USD",
                        "opt_type": "call",
                        "strike": "0.000001",
                        "expiry": "2027-01-15",
                    }
                }
            ]
        )
        minimum_option_draft = await prepare_entry(session, principal, minimum_option)
        assert minimum_option_draft.preview["legs"][0]["pending_instrument"]["strike"] == (
            "0.000001"
        )
        minimum_forex = request(
            [
                {
                    "pending": {
                        "kind": "forex",
                        "symbol": "MINFOREX",
                        "base_currency": "EUR",
                        "quote_currency": "USD",
                        "pip_size": "0.00000001",
                        "contract_size": "0.0001",
                    }
                }
            ]
        )
        minimum_forex_draft = await prepare_entry(session, principal, minimum_forex)
        assert minimum_forex_draft.preview["legs"][0]["pending_instrument"]["pip_size"] == ("1E-8")

        equivalent = request(
            [
                {
                    "pending": {
                        "kind": "forex",
                        "symbol": "EQFX",
                        "base_currency": "EUR",
                        "quote_currency": "USD",
                        "pip_size": "0.00010000",
                        "contract_size": "100000.0000",
                    }
                },
                {
                    "pending": {
                        "kind": "forex",
                        "symbol": "eqfx",
                        "base_currency": "EUR",
                        "quote_currency": "USD",
                        "pip_size": "0.0001",
                        "contract_size": "100000",
                    }
                },
            ]
        )
        draft = await prepare_entry(session, principal, equivalent)
        assert len(draft.preview["legs"]) == 2
        assert (
            draft.preview["legs"][0]["pending_instrument"]["forex"]
            == draft.preview["legs"][1]["pending_instrument"]["forex"]
        )
        distinct = request(
            [
                {
                    "pending": {
                        "kind": "forex",
                        "symbol": "DISTINCT1",
                        "base_currency": "EUR",
                        "quote_currency": "USD",
                        "pip_size": "0.0001",
                    }
                },
                {
                    "pending": {
                        "kind": "forex",
                        "symbol": "DISTINCT2",
                        "base_currency": "EUR",
                        "quote_currency": "USD",
                        "pip_size": "0.0002",
                    }
                },
            ]
        )
        await prepare_entry(session, principal, distinct)
        assert await session.scalar(select(func.count()).select_from(Instrument)) == before[0]
        assert await session.scalar(select(func.count()).select_from(Position)) == before[1]
        assert await session.scalar(select(func.count()).select_from(Trade)) == before[2]
        assert (
            await session.scalar(select(func.count()).select_from(JournalEntryDraft))
            == before[3] + 6
        )
