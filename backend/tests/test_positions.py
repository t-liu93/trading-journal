"""End-to-end tests for Position CRUD (P8)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select

from trading_journal.models.position import Position
from trading_journal.models.trade import Trade
from trading_journal.services.positions import freeze_pnl_realized

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 5, 20, 14, 30, tzinfo=UTC)

VALID_ACCOUNT = {
    "name": "IBKR Margin",
    "broker": "IBKR",
    "account_type": "margin",
    "base_currency": "USD",
}

VALID_STOCK_INSTRUMENT = {
    "kind": "stock",
    "symbol": "AAPL",
    "currency": "USD",
}


async def _seed_account(client: AsyncClient, **overrides: object) -> dict:
    body = {**VALID_ACCOUNT, **overrides}
    resp = await client.post("/api/accounts", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _seed_instrument(client: AsyncClient, **overrides: object) -> dict:
    body = {**VALID_STOCK_INSTRUMENT, **overrides}
    resp = await client.post("/api/instruments", json=body)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


async def _seed_position(
    client: AsyncClient,
    account_id: str,
    instrument_id: str,
    **overrides: object,
) -> dict:
    body = {
        "account_id": account_id,
        "primary_instrument_id": instrument_id,
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
        **overrides,
    }
    resp = await client.post("/api/positions", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


async def test_freeze_pnl_realized_zero_trades(
    db_session_maker,
) -> None:
    """Position with no trades → pnl_realized = 0."""
    async with db_session_maker() as session:
        pos_id = uuid.uuid4()
        await session.execute(
            insert(Position).values(
                id=pos_id,
                user_id=uuid.uuid4(),
                account_id=uuid.uuid4(),
                primary_instrument_id=uuid.uuid4(),
                strategy_type="spot_stock",
                status="open",
                opened_at=NOW,
                currency="USD",
            )
        )
        await session.commit()

        pos = (await session.execute(
            select(Position).where(Position.id == pos_id)
        )).scalar_one()

        result = await freeze_pnl_realized(session, pos)
        assert result == Decimal("0")
        assert pos.pnl_realized == Decimal("0")


async def test_freeze_pnl_realized_sums_cash_flow(
    db_session_maker,
) -> None:
    """3 trades with mixed signs → sum is exact."""
    async with db_session_maker() as session:
        pos_id = uuid.uuid4()
        await session.execute(
            insert(Position).values(
                id=pos_id,
                user_id=uuid.uuid4(),
                account_id=uuid.uuid4(),
                primary_instrument_id=uuid.uuid4(),
                strategy_type="spot_stock",
                status="open",
                opened_at=NOW,
                currency="USD",
            )
        )
        cash_flows = [Decimal("500"), Decimal("-200.50"), Decimal("100")]
        for cf in cash_flows:
            await session.execute(
                insert(Trade).values(
                    id=uuid.uuid4(),
                    position_id=pos_id,
                    account_id=uuid.uuid4(),
                    instrument_id=uuid.uuid4(),
                    action="buy",
                    quantity=Decimal("10"),
                    price=Decimal("50"),
                    cash_flow=cf,
                    executed_at=NOW,
                )
            )
        await session.commit()

        pos = (await session.execute(
            select(Position).where(Position.id == pos_id)
        )).scalar_one()

        result = await freeze_pnl_realized(session, pos)
        expected = sum(cash_flows)
        assert result == expected
        assert pos.pnl_realized == expected


# ---------------------------------------------------------------------------
# POST /positions
# ---------------------------------------------------------------------------


async def test_create_201_with_required_fields(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "open"
    assert data["currency"] == "USD"
    assert data["pnl_realized"] is None
    assert data["closed_at"] is None
    uuid.UUID(data["id"])
    uuid.UUID(data["user_id"])


async def test_create_with_optional_fields(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
        "capital_used": "5000",
        "max_risk_at_open": "3000",
        "max_reward_at_open": "8000",
        "notes": "test notes",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert Decimal(data["capital_used"]) == Decimal("5000")
    assert Decimal(data["max_risk_at_open"]) == Decimal("3000")
    assert Decimal(data["max_reward_at_open"]) == Decimal("8000")
    assert data["notes"] == "test notes"


async def test_create_rejects_unknown_field_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
        "totally_unknown": "x",
    })
    assert resp.status_code == 422


async def test_create_rejects_missing_opened_at_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
    })
    assert resp.status_code == 422


async def test_create_rejects_status_in_body_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
        "status": "open",
    })
    assert resp.status_code == 422


async def test_create_rejects_currency_in_body_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
        "currency": "USD",
    })
    assert resp.status_code == 422


async def test_create_rejects_pnl_realized_in_body_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
        "pnl_realized": "0",
    })
    assert resp.status_code == 422


async def test_create_rejects_unknown_account_422(auth_client: AsyncClient) -> None:
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": str(uuid.uuid4()),
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
    })
    assert resp.status_code == 422


async def test_create_rejects_other_users_account_422(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    bob_acct = await _seed_account(second_user_client, name="Bob Acct")
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": bob_acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
    })
    assert resp.status_code == 422


async def test_create_rejects_archived_account_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    await auth_client.delete(f"/api/accounts/{acct['id']}")
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
    })
    assert resp.status_code == 422


async def test_create_rejects_unknown_instrument_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": str(uuid.uuid4()),
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
    })
    assert resp.status_code == 422


async def test_create_rejects_bad_strategy_type_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "cowabunga",
        "opened_at": NOW.isoformat(),
    })
    assert resp.status_code == 422


@pytest.mark.parametrize("bad", ["0", "-1", "-0.01"])
async def test_create_rejects_nonpositive_capital_used_422(
    auth_client: AsyncClient, bad: str
) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
        "capital_used": bad,
    })
    assert resp.status_code == 422


async def test_create_derives_currency_from_instrument(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    # Stock USD
    instr_usd = await _seed_instrument(auth_client)
    resp = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": instr_usd["id"],
        "strategy_type": "spot_stock",
        "opened_at": NOW.isoformat(),
    })
    assert resp.status_code == 201
    assert resp.json()["currency"] == "USD"

    # Forex EURUSD → instrument currency is USD (quote currency)
    forex_resp = await auth_client.post("/api/instruments", json={
        "kind": "forex",
        "symbol": "EURUSD",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "pip_size": "0.0001",
    })
    assert forex_resp.status_code in (200, 201)
    forex_instr = forex_resp.json()
    resp2 = await auth_client.post("/api/positions", json={
        "account_id": acct["id"],
        "primary_instrument_id": forex_instr["id"],
        "strategy_type": "spot_forex",
        "opened_at": NOW.isoformat(),
    })
    assert resp2.status_code == 201
    assert resp2.json()["currency"] == "USD"


# ---------------------------------------------------------------------------
# GET /positions (list)
# ---------------------------------------------------------------------------


async def test_list_returns_only_current_user_rows(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    acct_a = await _seed_account(auth_client, name="Alice Acct")
    acct_b = await _seed_account(second_user_client, name="Bob Acct")
    instr = await _seed_instrument(auth_client)

    await _seed_position(auth_client, acct_a["id"], instr["id"])
    await _seed_position(
        second_user_client, acct_b["id"], instr["id"],
    )

    alice_list = (await auth_client.get("/api/positions")).json()
    bob_list = (await second_user_client.get("/api/positions")).json()

    assert len(alice_list) == 1
    assert len(bob_list) == 1
    assert alice_list[0]["user_id"] != bob_list[0]["user_id"]


async def test_list_orders_by_opened_at_desc(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)

    await _seed_position(auth_client, acct["id"], instr["id"], opened_at="2026-01-01T00:00:00Z")
    await _seed_position(auth_client, acct["id"], instr["id"], opened_at="2026-06-01T00:00:00Z")
    await _seed_position(auth_client, acct["id"], instr["id"], opened_at="2026-03-01T00:00:00Z")

    data = (await auth_client.get("/api/positions")).json()
    dates = [d["opened_at"] for d in data]
    assert dates == sorted(dates, reverse=True)


async def test_list_filter_status_open(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)

    pos = await _seed_position(auth_client, acct["id"], instr["id"])
    # Close it
    await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed", "closed_at": "2026-06-01T00:00:00Z",
    })

    data = (await auth_client.get("/api/positions", params={"status": "open"})).json()
    assert len(data) == 0


async def test_list_filter_status_closed(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)

    pos = await _seed_position(auth_client, acct["id"], instr["id"])
    await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed", "closed_at": "2026-06-01T00:00:00Z",
    })

    data = (await auth_client.get("/api/positions", params={"status": "closed"})).json()
    assert len(data) == 1
    assert data[0]["status"] == "closed"


async def test_list_filter_strategy_type(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)

    await _seed_position(auth_client, acct["id"], instr["id"], strategy_type="spot_stock")
    await _seed_position(auth_client, acct["id"], instr["id"], strategy_type="wheel")

    data = (await auth_client.get("/api/positions", params={"strategy_type": "wheel"})).json()
    assert len(data) == 1
    assert data[0]["strategy_type"] == "wheel"


async def test_list_filter_combined(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)

    pos1 = await _seed_position(auth_client, acct["id"], instr["id"], strategy_type="spot_stock")
    await _seed_position(auth_client, acct["id"], instr["id"], strategy_type="wheel")
    # Close pos1
    await auth_client.patch(f"/api/positions/{pos1['id']}", json={
        "status": "closed", "closed_at": "2026-06-01T00:00:00Z",
    })

    data = (await auth_client.get("/api/positions", params={
        "status": "closed", "strategy_type": "spot_stock",
    })).json()
    assert len(data) == 1
    assert data[0]["status"] == "closed"
    assert data[0]["strategy_type"] == "spot_stock"


async def test_list_rejects_bad_filter_422(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/api/positions", params={"status": "cowabunga"})
    assert resp.status_code == 422


async def test_list_rejects_bad_strategy_type_422(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/api/positions", params={"strategy_type": "cowabunga"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /positions/{id}
# ---------------------------------------------------------------------------


async def test_get_200(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.get(f"/api/positions/{pos['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == pos["id"]


async def test_get_404_unknown(auth_client: AsyncClient) -> None:
    resp = await auth_client.get(f"/api/positions/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    acct_a = await _seed_account(auth_client, name="Alice Acct")
    await _seed_account(second_user_client, name="Bob Acct")
    instr = await _seed_instrument(auth_client)

    alice_pos = await _seed_position(auth_client, acct_a["id"], instr["id"])
    resp = await second_user_client.get(f"/api/positions/{alice_pos['id']}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /positions/{id}
# ---------------------------------------------------------------------------


async def test_patch_updates_notes(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "notes": "Updated notes",
    })
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Updated notes"


async def test_patch_updates_snapshot_fields(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "capital_used": "6000",
        "max_risk_at_open": "4000",
        "max_reward_at_open": "10000",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["capital_used"]) == Decimal("6000")
    assert Decimal(data["max_risk_at_open"]) == Decimal("4000")
    assert Decimal(data["max_reward_at_open"]) == Decimal("10000")


async def test_patch_rejects_account_id_change_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "account_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 422


async def test_patch_rejects_primary_instrument_id_change_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "primary_instrument_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 422


async def test_patch_rejects_strategy_type_change_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "strategy_type": "wheel",
    })
    assert resp.status_code == 422


async def test_patch_rejects_opened_at_change_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "opened_at": "2026-01-01T00:00:00Z",
    })
    assert resp.status_code == 422


async def test_patch_rejects_currency_change_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "currency": "EUR",
    })
    assert resp.status_code == 422


async def test_patch_rejects_pnl_realized_change_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "pnl_realized": "100",
    })
    assert resp.status_code == 422


async def test_patch_close_transition_freezes_pnl_realized(
    auth_client: AsyncClient, db_session_maker,
) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    # Seed 3 trades via raw SQL (P9 doesn't exist yet).
    cash_flows = [Decimal("500"), Decimal("-200.50"), Decimal("100")]
    async with db_session_maker() as session:
        for cf in cash_flows:
            await session.execute(
                insert(Trade).values(
                    id=uuid.uuid4(),
                    position_id=uuid.UUID(pos["id"]),
                    account_id=uuid.UUID(acct["id"]),
                    instrument_id=uuid.UUID(instr["id"]),
                    action="buy",
                    quantity=Decimal("10"),
                    price=Decimal("50"),
                    cash_flow=cf,
                    executed_at=NOW,
                )
            )
        await session.commit()

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed",
        "closed_at": "2026-06-15T20:00:00Z",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "closed"
    assert Decimal(data["pnl_realized"]) == sum(cash_flows)
    # Explicit closed_at wins over the last-fill derivation (trades use NOW).
    assert "2026-06-15" in data["closed_at"]


async def test_patch_close_transition_with_zero_trades(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed",
        "closed_at": "2026-06-15T20:00:00Z",
    })
    assert resp.status_code == 200
    assert Decimal(resp.json()["pnl_realized"]) == Decimal("0")


async def test_patch_close_without_closed_at_derives_from_last_trade(
    auth_client: AsyncClient, db_session_maker,
) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    # Two fills at different times; the later one defines the close date.
    early = datetime(2026, 5, 20, 14, 30, tzinfo=UTC)
    late = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
    async with db_session_maker() as session:
        for ts, cf in ((early, Decimal("500")), (late, Decimal("-300"))):
            await session.execute(
                insert(Trade).values(
                    id=uuid.uuid4(),
                    position_id=uuid.UUID(pos["id"]),
                    account_id=uuid.UUID(acct["id"]),
                    instrument_id=uuid.UUID(instr["id"]),
                    action="buy",
                    quantity=Decimal("10"),
                    price=Decimal("50"),
                    cash_flow=cf,
                    executed_at=ts,
                )
            )
        await session.commit()

    # Close WITHOUT closed_at -> derived from the last fill's executed_at.
    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "closed"
    assert data["closed_at"] is not None
    assert "2026-06-01" in data["closed_at"]


async def test_patch_close_without_closed_at_ignores_archived_last_trade(
    auth_client: AsyncClient, db_session_maker,
) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    active = datetime(2026, 5, 25, 14, 30, tzinfo=UTC)
    archived = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
    async with db_session_maker() as session:
        await session.execute(
            insert(Trade).values(
                id=uuid.uuid4(),
                position_id=uuid.UUID(pos["id"]),
                account_id=uuid.UUID(acct["id"]),
                instrument_id=uuid.UUID(instr["id"]),
                action="buy",
                quantity=Decimal("10"),
                price=Decimal("50"),
                cash_flow=Decimal("500"),
                executed_at=active,
            )
        )
        await session.execute(
            insert(Trade).values(
                id=uuid.uuid4(),
                position_id=uuid.UUID(pos["id"]),
                account_id=uuid.UUID(acct["id"]),
                instrument_id=uuid.UUID(instr["id"]),
                action="buy",
                quantity=Decimal("10"),
                price=Decimal("50"),
                cash_flow=Decimal("-300"),
                executed_at=archived,
                archived_at=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
        )
        await session.commit()

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["closed_at"] is not None
    assert "2026-05-25" in data["closed_at"]
    assert Decimal(data["pnl_realized"]) == Decimal("500")
    assert Decimal(data["net_cash_flow"]) == Decimal("500")


async def test_patch_close_without_closed_at_no_trades_falls_back_to_now(
    auth_client: AsyncClient,
) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    # No trades to anchor the date -> close still succeeds, closed_at set to now.
    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["closed_at"] is not None


async def test_patch_rejects_closed_at_on_open_position_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "closed_at": "2026-06-15T20:00:00Z",
    })
    assert resp.status_code == 422


async def test_patch_allows_closed_at_amend_when_already_closed(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    # Close first
    await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed",
        "closed_at": "2026-06-15T20:00:00Z",
    })

    # Amend closed_at
    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "closed_at": "2026-06-20T20:00:00Z",
    })
    assert resp.status_code == 200
    assert "2026-06-20" in resp.json()["closed_at"]


async def test_patch_rejects_reopen_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    # Close first
    await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed",
        "closed_at": "2026-06-15T20:00:00Z",
    })

    # Try to reopen
    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "open",
    })
    assert resp.status_code == 422


async def test_patch_rejects_null_status_422(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": None,
    })
    assert resp.status_code == 422


async def test_patch_rejects_clearing_closed_at_on_closed_position_422(
    auth_client: AsyncClient,
) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    # Close first
    await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed",
        "closed_at": "2026-06-15T20:00:00Z",
    })

    # Try to clear closed_at while closed
    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "closed_at": None,
    })
    assert resp.status_code == 422


async def test_patch_pnl_realized_immutable_after_close(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    # Close
    close_resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "status": "closed",
        "closed_at": "2026-06-15T20:00:00Z",
    })
    pnl_after_close = close_resp.json()["pnl_realized"]

    # Patch notes — pnl_realized should not change
    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "notes": "still closed",
    })
    assert resp.status_code == 200
    assert resp.json()["pnl_realized"] == pnl_after_close


async def test_patch_advances_updated_at(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    original_updated_at = pos["updated_at"]

    resp = await auth_client.patch(f"/api/positions/{pos['id']}", json={
        "notes": "updated",
    })
    assert resp.status_code == 200
    # SQLite second-precision may be the same; check it's at least not earlier.
    assert resp.json()["updated_at"] >= original_updated_at


async def test_patch_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    acct_a = await _seed_account(auth_client, name="Alice Acct")
    await _seed_account(second_user_client, name="Bob Acct")
    instr = await _seed_instrument(auth_client)

    alice_pos = await _seed_position(auth_client, acct_a["id"], instr["id"])
    resp = await second_user_client.patch(
        f"/api/positions/{alice_pos['id']}", json={"notes": "hax"}
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /positions/{id}
# ---------------------------------------------------------------------------


async def test_delete_204_when_no_trades(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.delete(f"/api/positions/{pos['id']}")
    assert resp.status_code == 204

    # Row is gone
    resp2 = await auth_client.get(f"/api/positions/{pos['id']}")
    assert resp2.status_code == 404


async def test_delete_409_when_trades_exist(
    auth_client: AsyncClient, db_session_maker,
) -> None:
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    async with db_session_maker() as session:
        await session.execute(
            insert(Trade).values(
                id=uuid.uuid4(),
                position_id=uuid.UUID(pos["id"]),
                account_id=uuid.UUID(acct["id"]),
                instrument_id=uuid.UUID(instr["id"]),
                action="buy",
                quantity=Decimal("10"),
                price=Decimal("50"),
                cash_flow=Decimal("100"),
                executed_at=NOW,
            )
        )
        await session.commit()

    resp = await auth_client.delete(f"/api/positions/{pos['id']}")
    assert resp.status_code == 409
    assert "trades" in resp.json()["detail"].lower()


async def test_delete_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    acct_a = await _seed_account(auth_client, name="Alice Acct")
    await _seed_account(second_user_client, name="Bob Acct")
    instr = await _seed_instrument(auth_client)

    alice_pos = await _seed_position(auth_client, acct_a["id"], instr["id"])
    resp = await second_user_client.delete(f"/api/positions/{alice_pos['id']}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/positions"),
        ("GET", "/api/positions"),
        ("GET", "/api/positions/00000000-0000-0000-0000-000000000000"),
        ("PATCH", "/api/positions/00000000-0000-0000-0000-000000000000"),
        ("DELETE", "/api/positions/00000000-0000-0000-0000-000000000000"),
    ],
)
async def test_requires_auth(client: AsyncClient, method: str, path: str) -> None:
    resp = await client.request(
        method,
        path,
        json={
            "account_id": str(uuid.uuid4()),
            "primary_instrument_id": str(uuid.uuid4()),
            "strategy_type": "spot_stock",
            "opened_at": NOW.isoformat(),
        } if method in {"POST", "PATCH"} else None,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# P12: net_cash_flow
# ---------------------------------------------------------------------------


async def _p12_seed_trade(
    client: AsyncClient,
    position_id: str,
    instrument_id: str,
    *,
    action: str = "buy",
    quantity: str = "10",
    price: str = "50",
) -> dict:
    """Create a single trade via the P9 API. cash_flow is server-computed."""
    body = {
        "position_id": position_id,
        "instrument_id": instrument_id,
        "action": action,
        "quantity": quantity,
        "price": price,
        "commission": "0",
        "fees": "0",
        "executed_at": NOW.isoformat(),
    }
    resp = await client.post("/api/trades", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()[0]


async def test_net_cash_flow_zero_when_no_trades(
    auth_client: AsyncClient,
) -> None:
    """Newly-created position has net_cash_flow == 0 in list + detail."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    await _seed_position(auth_client, acct["id"], instr["id"])

    # list
    list_resp = await auth_client.get("/api/positions")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) == 1
    assert Decimal(data[0]["net_cash_flow"]) == Decimal("0")

    # detail
    detail_resp = await auth_client.get(f"/api/positions/{data[0]['id']}")
    assert detail_resp.status_code == 200
    assert Decimal(detail_resp.json()["net_cash_flow"]) == Decimal("0")


async def test_net_cash_flow_sums_non_archived_trades(
    auth_client: AsyncClient,
) -> None:
    """3 trades with known values; net_cash_flow matches the sum."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    t1 = await _p12_seed_trade(
        auth_client, pos["id"], instr["id"],
        action="buy", quantity="10", price="50",
    )
    t2 = await _p12_seed_trade(
        auth_client, pos["id"], instr["id"],
        action="sell", quantity="5", price="41",
    )
    t3 = await _p12_seed_trade(
        auth_client, pos["id"], instr["id"],
        action="buy", quantity="2", price="50",
    )

    expected = (
        Decimal(t1["cash_flow"])
        + Decimal(t2["cash_flow"])
        + Decimal(t3["cash_flow"])
    )

    list_data = (await auth_client.get("/api/positions")).json()
    assert Decimal(list_data[0]["net_cash_flow"]) == expected

    detail_data = (
        await auth_client.get(f"/api/positions/{pos['id']}")
    ).json()
    assert Decimal(detail_data["net_cash_flow"]) == expected


async def test_net_cash_flow_excludes_archived_trades(
    auth_client: AsyncClient,
) -> None:
    """Soft-delete one trade; net_cash_flow drops by that trade's cash_flow."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    t1 = await _p12_seed_trade(
        auth_client, pos["id"], instr["id"],
        action="buy", quantity="10", price="30",
    )
    t2 = await _p12_seed_trade(
        auth_client, pos["id"], instr["id"],
        action="sell", quantity="10", price="20",
    )

    # Archive t1
    del_resp = await auth_client.delete(f"/api/trades/{t1['id']}")
    assert del_resp.status_code == 204

    detail = (
        await auth_client.get(f"/api/positions/{pos['id']}")
    ).json()
    assert Decimal(detail["net_cash_flow"]) == Decimal(t2["cash_flow"])


async def test_net_cash_flow_isolated_per_position(
    auth_client: AsyncClient,
) -> None:
    """Two positions with separate trades; sums don't bleed across."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos1 = await _seed_position(auth_client, acct["id"], instr["id"])
    pos2 = await _seed_position(auth_client, acct["id"], instr["id"])

    t1a = await _p12_seed_trade(
        auth_client, pos1["id"], instr["id"],
        action="buy", quantity="10", price="10",
    )
    t1b = await _p12_seed_trade(
        auth_client, pos1["id"], instr["id"],
        action="sell", quantity="10", price="20",
    )
    t2a = await _p12_seed_trade(
        auth_client, pos2["id"], instr["id"],
        action="buy", quantity="5", price="100",
    )

    expected1 = Decimal(t1a["cash_flow"]) + Decimal(t1b["cash_flow"])
    expected2 = Decimal(t2a["cash_flow"])

    d1 = (
        await auth_client.get(f"/api/positions/{pos1['id']}")
    ).json()
    d2 = (
        await auth_client.get(f"/api/positions/{pos2['id']}")
    ).json()

    assert Decimal(d1["net_cash_flow"]) == expected1
    assert Decimal(d2["net_cash_flow"]) == expected2


async def test_net_cash_flow_closed_matches_pnl_realized(
    auth_client: AsyncClient,
) -> None:
    """After closing, net_cash_flow == pnl_realized."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    await _p12_seed_trade(
        auth_client, pos["id"], instr["id"],
        action="buy", quantity="10", price="40",
    )
    await _p12_seed_trade(
        auth_client, pos["id"], instr["id"],
        action="sell", quantity="10", price="50",
    )

    close_resp = await auth_client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-06-15T20:00:00Z"},
    )
    assert close_resp.status_code == 200
    data = close_resp.json()
    assert Decimal(data["net_cash_flow"]) == Decimal(data["pnl_realized"])


async def test_archived_before_close_preserves_invariant(
    auth_client: AsyncClient,
) -> None:
    """Archive a trade, then close position → pnl_realized == net_cash_flow."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    t1 = await _p12_seed_trade(
        auth_client, pos["id"], instr["id"],
        action="sell", quantity="10", price="10",
    )
    t2 = await _p12_seed_trade(
        auth_client, pos["id"], instr["id"],
        action="buy", quantity="4", price="10",
    )

    # Archive t1 before closing
    await auth_client.delete(f"/api/trades/{t1['id']}")

    close_resp = await auth_client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-06-15T20:00:00Z"},
    )
    assert close_resp.status_code == 200
    data = close_resp.json()
    # Both pnl_realized and net_cash_flow should equal t2's cash_flow only
    assert Decimal(data["pnl_realized"]) == Decimal(t2["cash_flow"])
    assert Decimal(data["net_cash_flow"]) == Decimal(t2["cash_flow"])


async def test_net_cash_flow_list_endpoint_does_one_query_per_request(
    auth_client: AsyncClient,
    db_engine,
) -> None:
    """5 positions × 3 trades: list endpoint issues one SUM-GROUP-BY, not N."""
    from sqlalchemy import event

    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)

    positions = []
    for _ in range(5):
        p = await _seed_position(auth_client, acct["id"], instr["id"])
        positions.append(p)

    expected_per_pos: dict[str, Decimal] = {}
    for p in positions:
        total = Decimal("0")
        for _ in range(3):
            t = await _p12_seed_trade(
                auth_client, p["id"], instr["id"],
                action="buy", quantity="1", price="10",
            )
            total += Decimal(t["cash_flow"])
        expected_per_pos[p["id"]] = total

    # Hook the sync_engine to count SUM-GROUP-BY queries.
    sum_group_queries: list[str] = []

    @event.listens_for(db_engine.sync_engine, "before_cursor_execute")
    def _capture(
        conn, cursor, statement, params, context, executemany,
    ) -> None:
        upper = statement.upper()
        if "SUM" in upper and "GROUP BY" in upper:
            sum_group_queries.append(statement)

    try:
        resp = await auth_client.get("/api/positions")
    finally:
        event.remove(
            db_engine.sync_engine, "before_cursor_execute", _capture,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    for item in data:
        assert Decimal(item["net_cash_flow"]) == expected_per_pos[item["id"]]
    assert len(sum_group_queries) == 1
