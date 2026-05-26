"""End-to-end tests for Trade CRUD (P9)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from trading_journal.models._enums import InstrumentKind, TradeAction
from trading_journal.services.trades import (
    compute_cash_flow,
    validate_action_kind,
    validate_option_quantity_integer,
)

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


async def _seed_option_instrument(
    client: AsyncClient,
    underlying_symbol: str = "AAPL",
    **overrides: object,
) -> dict:
    body = {
        "kind": "option",
        "underlying_symbol": underlying_symbol,
        "currency": "USD",
        "opt_type": "call",
        "strike": "150",
        "expiry": "2026-01-15",
        "multiplier": 100,
        **overrides,
    }
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


async def _seed_full_setup(client: AsyncClient) -> tuple[dict, dict, dict, dict]:
    """Seed account + stock instrument + option instrument + position."""
    acct = await _seed_account(client)
    stock = await _seed_instrument(client)
    option = await _seed_option_instrument(client)
    pos = await _seed_position(client, acct["id"], stock["id"])
    return acct, stock, option, pos


def _trade_row(
    position_id: str, instrument_id: str, **overrides: object
) -> dict:
    row: dict = {
        "position_id": position_id,
        "instrument_id": instrument_id,
        "action": "buy",
        "quantity": "10",
        "price": "10",
        "executed_at": NOW.isoformat(),
    }
    row.update(overrides)
    return row


async def _create_single_trade(
    client: AsyncClient,
    position_id: str,
    instrument_id: str,
    **overrides: object,
) -> dict:
    body = {
        "position_id": position_id,
        "instrument_id": instrument_id,
        "action": "buy",
        "quantity": "100",
        "price": "50.00",
        "commission": "0",
        "fees": "0",
        "executed_at": NOW.isoformat(),
    }
    body.update(overrides)
    resp = await client.post("/api/trades", json=body)
    return resp


# ---------------------------------------------------------------------------
# Service-layer tests (no HTTP)
# ---------------------------------------------------------------------------


def test_compute_cash_flow_buy_stock() -> None:
    cf = compute_cash_flow(
        action=TradeAction.BUY,
        price=Decimal("100"),
        quantity=Decimal("10"),
        multiplier=1,
        commission=Decimal("1"),
        fees=Decimal("0"),
    )
    assert cf == Decimal("-1001")


def test_compute_cash_flow_sell_stock() -> None:
    cf = compute_cash_flow(
        action=TradeAction.SELL,
        price=Decimal("100"),
        quantity=Decimal("10"),
        multiplier=1,
        commission=Decimal("1"),
        fees=Decimal("0.50"),
    )
    assert cf == Decimal("998.50")


def test_compute_cash_flow_sto_option_x100() -> None:
    cf = compute_cash_flow(
        action=TradeAction.STO,
        price=Decimal("2.50"),
        quantity=Decimal("1"),
        multiplier=100,
        commission=Decimal("1.50"),
        fees=Decimal("0"),
    )
    assert cf == Decimal("248.50")


def test_compute_cash_flow_btc_at_zero_price() -> None:
    cf = compute_cash_flow(
        action=TradeAction.BTC,
        price=Decimal("0"),
        quantity=Decimal("1"),
        multiplier=100,
        commission=Decimal("0.75"),
        fees=Decimal("0.25"),
    )
    assert cf == Decimal("-1")


def test_compute_cash_flow_btc_at_zero_price_zero_costs_equals_zero() -> None:
    cf = compute_cash_flow(
        action=TradeAction.BTC,
        price=Decimal("0"),
        quantity=Decimal("1"),
        multiplier=100,
        commission=Decimal("0"),
        fees=Decimal("0"),
    )
    assert cf == Decimal("0")


def test_compute_cash_flow_costs_subtracted_on_both_sides() -> None:
    buy_cf = compute_cash_flow(
        action=TradeAction.BUY,
        price=Decimal("10"),
        quantity=Decimal("1"),
        multiplier=1,
        commission=Decimal("2"),
        fees=Decimal("3"),
    )
    assert buy_cf == Decimal("-15")

    sell_cf = compute_cash_flow(
        action=TradeAction.SELL,
        price=Decimal("10"),
        quantity=Decimal("1"),
        multiplier=1,
        commission=Decimal("2"),
        fees=Decimal("3"),
    )
    assert sell_cf == Decimal("5")


def test_validate_action_kind_option_ok() -> None:
    validate_action_kind(TradeAction.BTO, InstrumentKind.OPTION)


def test_validate_action_kind_stock_ok() -> None:
    validate_action_kind(TradeAction.BUY, InstrumentKind.STOCK)


def test_validate_action_kind_forex_ok() -> None:
    validate_action_kind(TradeAction.SELL, InstrumentKind.FOREX)


def test_validate_action_kind_bto_on_stock_raises() -> None:
    with pytest.raises(ValueError, match="requires an option instrument"):
        validate_action_kind(TradeAction.BTO, InstrumentKind.STOCK)


def test_validate_action_kind_buy_on_option_raises() -> None:
    with pytest.raises(ValueError, match="requires a stock or forex instrument"):
        validate_action_kind(TradeAction.BUY, InstrumentKind.OPTION)


def test_validate_option_quantity_integer_fractional_raises() -> None:
    with pytest.raises(ValueError, match="integer number of contracts"):
        validate_option_quantity_integer(
            TradeAction.BTO, InstrumentKind.OPTION, Decimal("1.5")
        )


def test_validate_option_quantity_integer_stock_fractional_ok() -> None:
    validate_option_quantity_integer(
        TradeAction.BUY, InstrumentKind.STOCK, Decimal("0.5")
    )


def test_validate_option_quantity_integer_integer_ok() -> None:
    validate_option_quantity_integer(
        TradeAction.BTO, InstrumentKind.OPTION, Decimal("2")
    )


# ---------------------------------------------------------------------------
# POST /trades (single)
# ---------------------------------------------------------------------------


async def test_create_single_stock_buy_201(auth_client: AsyncClient) -> None:
    acct, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        action="buy", quantity="100", price="150.00", commission="1.00",
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert isinstance(data, list) and len(data) == 1
    trade = data[0]
    assert trade["cash_flow"] == "-15001.0000"
    assert trade["account_id"] == acct["id"]
    assert trade["order_group_id"] is None


async def test_create_single_stock_sell_cash_flow_positive(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        action="sell", quantity="10", price="100.00",
    )
    assert resp.status_code == 201
    trade = resp.json()[0]
    assert Decimal(trade["cash_flow"]) > 0


async def test_create_single_option_sto_uses_multiplier(
    auth_client: AsyncClient,
) -> None:
    _, stock, option, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], option["id"],
        action="sto", quantity="1", price="2.50", commission="0.50",
    )
    assert resp.status_code == 201
    trade = resp.json()[0]
    assert Decimal(trade["cash_flow"]) == Decimal("249.5000")


async def test_create_with_supplied_order_group_id(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    ogid = str(uuid.uuid4())
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        action="buy", quantity="10", price="10",
        order_group_id=ogid,
    )
    assert resp.status_code == 201
    assert resp.json()[0]["order_group_id"] == ogid


async def test_create_rejects_unknown_position_404(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, _ = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, str(uuid.uuid4()), stock["id"],
    )
    assert resp.status_code == 404


async def test_create_rejects_other_users_position_404(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, _, pos = await _seed_full_setup(auth_client)
    _, stock, _, _ = await _seed_full_setup(second_user_client)
    resp = await _create_single_trade(
        second_user_client, pos["id"], stock["id"],
    )
    assert resp.status_code == 404


async def test_create_rejects_unknown_instrument_422(
    auth_client: AsyncClient,
) -> None:
    _, _, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], str(uuid.uuid4()),
    )
    assert resp.status_code == 422


async def test_create_rejects_action_kind_mismatch_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        action="bto",
    )
    assert resp.status_code == 422


async def test_create_rejects_buy_on_option_422(
    auth_client: AsyncClient,
) -> None:
    _, _, option, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], option["id"],
        action="buy",
    )
    assert resp.status_code == 422


async def test_create_rejects_fractional_option_qty_422(
    auth_client: AsyncClient,
) -> None:
    _, _, option, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], option["id"],
        action="bto", quantity="1.5",
    )
    assert resp.status_code == 422


async def test_create_allows_fractional_stock_qty(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        action="buy", quantity="0.25",
    )
    assert resp.status_code == 201


async def test_create_rejects_negative_quantity_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        quantity="-1",
    )
    assert resp.status_code == 422


async def test_create_rejects_zero_quantity_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        quantity="0",
    )
    assert resp.status_code == 422


async def test_create_rejects_negative_price_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        price="-1",
    )
    assert resp.status_code == 422


async def test_create_allows_zero_price_for_btc(
    auth_client: AsyncClient,
) -> None:
    _, _, option, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], option["id"],
        action="btc", quantity="1", price="0",
    )
    assert resp.status_code == 201


async def test_create_allows_zero_price_for_stc(
    auth_client: AsyncClient,
) -> None:
    _, _, option, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], option["id"],
        action="stc", quantity="1", price="0",
    )
    assert resp.status_code == 201


async def test_create_rejects_negative_commission_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        commission="-1",
    )
    assert resp.status_code == 422


async def test_create_rejects_negative_fees_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        fees="-0.01",
    )
    assert resp.status_code == 422


async def test_create_rejects_account_id_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        account_id=str(uuid.uuid4()),
    )
    assert resp.status_code == 422


async def test_create_rejects_cash_flow_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        cash_flow="999",
    )
    assert resp.status_code == 422


async def test_create_rejects_broker_trade_id_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        broker_trade_id="ORD-123",
    )
    assert resp.status_code == 422


async def test_create_rejects_archived_at_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        archived_at=NOW.isoformat(),
    )
    assert resp.status_code == 422


async def test_create_409_when_position_closed(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    await auth_client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-06-15T20:00:00Z"},
    )
    resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        action="buy", quantity="1", price="1",
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /trades (array / multi-leg)
# ---------------------------------------------------------------------------


async def test_create_array_4leg_ic_open_201(
    auth_client: AsyncClient,
) -> None:
    _, stock, option, pos = await _seed_full_setup(auth_client)
    ts = NOW.isoformat()
    rows = [
        _trade_row(pos["id"], option["id"], action="sto", price="2.00", executed_at=ts),
        _trade_row(pos["id"], option["id"], action="bto", price="1.00", executed_at=ts),
        _trade_row(pos["id"], option["id"], action="stc", price="0.50", executed_at=ts),
        _trade_row(pos["id"], option["id"], action="btc", price="0.25", executed_at=ts),
    ]
    resp = await auth_client.post("/api/trades", json=rows)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert len(data) == 4
    ogids = {t["order_group_id"] for t in data}
    assert len(ogids) == 1
    assert ogids.pop() is not None
    total_cf = sum(Decimal(t["cash_flow"]) for t in data)
    assert total_cf > 0


async def test_create_array_2leg_assignment_short_put(
    auth_client: AsyncClient,
) -> None:
    _, stock, option, pos = await _seed_full_setup(auth_client)
    ts = NOW.isoformat()
    rows = [
        _trade_row(pos["id"], option["id"], action="btc", price="0.00", executed_at=ts),
        _trade_row(
            pos["id"], stock["id"], action="buy",
            quantity="100", price="150.00", executed_at=ts,
        ),
    ]
    resp = await auth_client.post("/api/trades", json=rows)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert len(data) == 2
    shared_ogid = data[0]["order_group_id"]
    assert data[1]["order_group_id"] == shared_ogid
    assert shared_ogid is not None


async def test_create_array_with_supplied_shared_ogid(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    ogid = str(uuid.uuid4())
    rows = [
        _trade_row(pos["id"], stock["id"], quantity="50", price="100", order_group_id=ogid),
        _trade_row(pos["id"], stock["id"], quantity="50", price="101", order_group_id=ogid),
    ]
    resp = await auth_client.post("/api/trades", json=rows)
    assert resp.status_code == 201
    for t in resp.json():
        assert t["order_group_id"] == ogid


async def test_create_array_rejects_mixed_position_id_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    rows = [
        _trade_row(pos["id"], stock["id"]),
        _trade_row(str(uuid.uuid4()), stock["id"]),
    ]
    resp = await auth_client.post("/api/trades", json=rows)
    assert resp.status_code == 422


async def test_create_array_rejects_mixed_ogid_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    rows = [
        _trade_row(pos["id"], stock["id"], order_group_id=str(uuid.uuid4())),
        _trade_row(pos["id"], stock["id"], order_group_id=str(uuid.uuid4())),
    ]
    resp = await auth_client.post("/api/trades", json=rows)
    assert resp.status_code == 422


async def test_create_array_rejects_one_row_fails_422_rollback(
    auth_client: AsyncClient,
) -> None:
    _, stock, option, pos = await _seed_full_setup(auth_client)
    rows = [
        _trade_row(pos["id"], stock["id"]),
        _trade_row(pos["id"], stock["id"]),
        _trade_row(pos["id"], stock["id"], action="bto"),
        _trade_row(pos["id"], stock["id"]),
    ]
    resp = await auth_client.post("/api/trades", json=rows)
    assert resp.status_code == 422

    list_resp = await auth_client.get(
        "/api/trades", params={"position_id": pos["id"]},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


async def test_create_array_rejects_empty_422(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/api/trades", json=[])
    assert resp.status_code == 422


async def test_create_array_409_when_position_closed(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    await auth_client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-06-15T20:00:00Z"},
    )
    rows = [
        _trade_row(pos["id"], stock["id"]),
        _trade_row(pos["id"], stock["id"]),
    ]
    resp = await auth_client.post("/api/trades", json=rows)
    assert resp.status_code == 409


async def test_create_array_returns_in_submit_order(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    rows = [
        _trade_row(
            pos["id"], stock["id"], action="buy",
            quantity="1", price="10", executed_at="2026-01-01T10:00:00Z",
        ),
        _trade_row(
            pos["id"], stock["id"], action="buy",
            quantity="2", price="20", executed_at="2026-01-02T10:00:00Z",
        ),
        _trade_row(
            pos["id"], stock["id"], action="sell",
            quantity="3", price="30", executed_at="2026-01-03T10:00:00Z",
        ),
    ]
    resp = await auth_client.post("/api/trades", json=rows)
    assert resp.status_code == 201
    data = resp.json()
    assert Decimal(data[0]["quantity"]) == Decimal("1")
    assert Decimal(data[1]["quantity"]) == Decimal("2")
    assert Decimal(data[2]["quantity"]) == Decimal("3")


# ---------------------------------------------------------------------------
# GET /trades (list)
# ---------------------------------------------------------------------------


async def test_list_default_excludes_archived(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = resp.json()[0]["id"]
    await auth_client.delete(f"/api/trades/{trade_id}")

    list_resp = await auth_client.get(
        "/api/trades", params={"position_id": pos["id"]},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


async def test_list_include_archived_true_shows_them(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = resp.json()[0]["id"]
    await auth_client.delete(f"/api/trades/{trade_id}")

    list_resp = await auth_client.get(
        "/api/trades",
        params={"position_id": pos["id"], "include_archived": True},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_list_filter_position_id(auth_client: AsyncClient) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    await _create_single_trade(auth_client, pos["id"], stock["id"])

    acct = await _seed_account(auth_client, name="Second Account")
    pos2 = await _seed_position(
        auth_client, acct["id"], stock["id"], strategy_type="spot_stock",
    )
    await _create_single_trade(auth_client, pos2["id"], stock["id"])

    list_resp = await auth_client.get(
        "/api/trades", params={"position_id": pos["id"]},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_list_filter_position_id_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, _, alice_pos = await _seed_full_setup(auth_client)
    resp = await second_user_client.get(
        "/api/trades", params={"position_id": alice_pos["id"]},
    )
    assert resp.status_code == 404


async def test_list_filter_position_id_404_unknown(
    auth_client: AsyncClient,
) -> None:
    resp = await auth_client.get(
        "/api/trades", params={"position_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


async def test_list_filter_order_group_id(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    ogid = str(uuid.uuid4())
    rows = [
        _trade_row(pos["id"], stock["id"], order_group_id=ogid),
        _trade_row(pos["id"], stock["id"], order_group_id=ogid),
    ]
    await auth_client.post("/api/trades", json=rows)
    await _create_single_trade(auth_client, pos["id"], stock["id"])

    list_resp = await auth_client.get(
        "/api/trades", params={"order_group_id": ogid},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 2


async def test_list_filter_combined(auth_client: AsyncClient) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    ogid = str(uuid.uuid4())
    rows = [_trade_row(pos["id"], stock["id"], order_group_id=ogid)]
    await auth_client.post("/api/trades", json=rows)
    await _create_single_trade(auth_client, pos["id"], stock["id"])

    list_resp = await auth_client.get(
        "/api/trades",
        params={"position_id": pos["id"], "order_group_id": ogid},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_list_unfiltered_returns_all_user_trades(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    await _create_single_trade(auth_client, pos["id"], stock["id"])
    await _create_single_trade(
        auth_client, pos["id"], stock["id"],
        action="sell", quantity="10", price="60",
    )

    list_resp = await auth_client.get("/api/trades")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 2


async def test_list_cross_user_isolation(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    await _create_single_trade(auth_client, pos["id"], stock["id"])

    bob_list = await second_user_client.get("/api/trades")
    assert bob_list.status_code == 200
    assert len(bob_list.json()) == 0


async def test_list_orders_executed_at_desc(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    for ts in [
        "2026-01-01T10:00:00Z",
        "2026-06-01T10:00:00Z",
        "2026-03-01T10:00:00Z",
    ]:
        await _create_single_trade(
            auth_client, pos["id"], stock["id"], executed_at=ts,
        )

    data = (await auth_client.get("/api/trades")).json()
    dates = [d["executed_at"] for d in data]
    assert dates == sorted(dates, reverse=True)


async def test_list_rejects_bad_uuid_422(auth_client: AsyncClient) -> None:
    resp = await auth_client.get(
        "/api/trades", params={"position_id": "not-a-uuid"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /trades/{id}
# ---------------------------------------------------------------------------


async def test_get_200(auth_client: AsyncClient) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.get(f"/api/trades/{trade_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == trade_id


async def test_get_returns_archived_row(auth_client: AsyncClient) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]
    await auth_client.delete(f"/api/trades/{trade_id}")

    resp = await auth_client.get(f"/api/trades/{trade_id}")
    assert resp.status_code == 200
    assert resp.json()["archived_at"] is not None


async def test_get_404_unknown(auth_client: AsyncClient) -> None:
    resp = await auth_client.get(f"/api/trades/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await second_user_client.get(f"/api/trades/{trade_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /trades/{id}
# ---------------------------------------------------------------------------


async def test_patch_notes_200(auth_client: AsyncClient) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}",
        json={"notes": "Initial entry tranche."},
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Initial entry tranche."


async def test_patch_notes_to_null_200(auth_client: AsyncClient) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(
        auth_client, pos["id"], stock["id"], notes="some notes",
    )
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}", json={"notes": None},
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] is None


async def test_patch_rejects_quantity_change_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}", json={"quantity": "200"},
    )
    assert resp.status_code == 422


async def test_patch_rejects_price_change_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}", json={"price": "999"},
    )
    assert resp.status_code == 422


async def test_patch_rejects_action_change_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}", json={"action": "sell"},
    )
    assert resp.status_code == 422


async def test_patch_rejects_cash_flow_change_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}", json={"cash_flow": "0"},
    )
    assert resp.status_code == 422


async def test_patch_rejects_position_id_change_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}",
        json={"position_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 422


async def test_patch_rejects_account_id_change_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}",
        json={"account_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 422


async def test_patch_rejects_archived_at_change_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}",
        json={"archived_at": NOW.isoformat()},
    )
    assert resp.status_code == 422


async def test_patch_409_when_position_closed(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    await auth_client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-06-15T20:00:00Z"},
    )
    resp = await auth_client.patch(
        f"/api/trades/{trade_id}",
        json={"notes": "try after close"},
    )
    assert resp.status_code == 409


async def test_patch_409_when_already_archived(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]
    await auth_client.delete(f"/api/trades/{trade_id}")

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}",
        json={"notes": "try on archived"},
    )
    assert resp.status_code == 409


async def test_patch_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await second_user_client.patch(
        f"/api/trades/{trade_id}", json={"notes": "hax"},
    )
    assert resp.status_code == 404


async def test_patch_does_not_change_cash_flow(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]
    original_cf = create_resp.json()[0]["cash_flow"]

    resp = await auth_client.patch(
        f"/api/trades/{trade_id}",
        json={"notes": "updated notes"},
    )
    assert resp.status_code == 200
    assert resp.json()["cash_flow"] == original_cf


# ---------------------------------------------------------------------------
# DELETE /trades/{id}
# ---------------------------------------------------------------------------


async def test_delete_204_sets_archived_at(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await auth_client.delete(f"/api/trades/{trade_id}")
    assert resp.status_code == 204

    get_resp = await auth_client.get(f"/api/trades/{trade_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["archived_at"] is not None


async def test_delete_list_default_excludes_after_delete(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]
    await auth_client.delete(f"/api/trades/{trade_id}")

    list_resp = await auth_client.get(
        "/api/trades", params={"position_id": pos["id"]},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


async def test_delete_get_by_id_still_works_after_delete(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]
    await auth_client.delete(f"/api/trades/{trade_id}")

    get_resp = await auth_client.get(f"/api/trades/{trade_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["archived_at"] is not None


async def test_delete_404_already_archived(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]
    await auth_client.delete(f"/api/trades/{trade_id}")

    resp = await auth_client.delete(f"/api/trades/{trade_id}")
    assert resp.status_code == 404


async def test_delete_409_when_position_closed(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    await auth_client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-06-15T20:00:00Z"},
    )
    resp = await auth_client.delete(f"/api/trades/{trade_id}")
    assert resp.status_code == 409


async def test_delete_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]

    resp = await second_user_client.delete(f"/api/trades/{trade_id}")
    assert resp.status_code == 404


async def test_delete_does_not_unlock_position_delete(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_full_setup(auth_client)
    create_resp = await _create_single_trade(auth_client, pos["id"], stock["id"])
    trade_id = create_resp.json()[0]["id"]
    await auth_client.delete(f"/api/trades/{trade_id}")

    resp = await auth_client.delete(f"/api/positions/{pos['id']}")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Cash-flow correctness across data-model §4.5.2 flows (integration)
# ---------------------------------------------------------------------------


async def test_flow_sell_put(auth_client: AsyncClient) -> None:
    _, stock, option, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], option["id"],
        action="sto", quantity="1", price="3.50",
    )
    assert resp.status_code == 201
    trade = resp.json()[0]
    assert Decimal(trade["cash_flow"]) > 0


async def test_flow_close_sell_put(auth_client: AsyncClient) -> None:
    _, stock, option, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], option["id"],
        action="btc", quantity="1", price="1.00", commission="0.50",
    )
    assert resp.status_code == 201
    trade = resp.json()[0]
    assert Decimal(trade["cash_flow"]) < 0


async def test_flow_assignment_short_put(auth_client: AsyncClient) -> None:
    _, stock, option, pos = await _seed_full_setup(auth_client)
    ts = NOW.isoformat()
    rows = [
        _trade_row(pos["id"], option["id"], action="btc", price="0.00", executed_at=ts),
        _trade_row(
            pos["id"], stock["id"], action="buy",
            quantity="100", price="150.00", executed_at=ts,
        ),
    ]
    resp = await auth_client.post("/api/trades", json=rows)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 2
    assert Decimal(data[0]["cash_flow"]) == Decimal("0")
    assert Decimal(data[1]["cash_flow"]) == Decimal("-15000.0000")


async def test_flow_worthless_expire_short_option(
    auth_client: AsyncClient,
) -> None:
    _, stock, option, pos = await _seed_full_setup(auth_client)
    resp = await _create_single_trade(
        auth_client, pos["id"], option["id"],
        action="btc", quantity="1", price="0", commission="0", fees="0",
    )
    assert resp.status_code == 201
    trade = resp.json()[0]
    assert Decimal(trade["cash_flow"]) == Decimal("0")


async def test_flow_iron_condor_open(auth_client: AsyncClient) -> None:
    _, stock, option, pos = await _seed_full_setup(auth_client)
    put = await _seed_option_instrument(
        auth_client, underlying_symbol="AAPL", opt_type="put", strike="140",
    )
    ts = NOW.isoformat()
    rows = [
        _trade_row(pos["id"], option["id"], action="sto", price="2.00", executed_at=ts),
        _trade_row(pos["id"], option["id"], action="bto", price="1.00", executed_at=ts),
        _trade_row(pos["id"], put["id"], action="sto", price="1.50", executed_at=ts),
        _trade_row(pos["id"], put["id"], action="bto", price="0.75", executed_at=ts),
    ]
    resp = await auth_client.post("/api/trades", json=rows)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 4
    total_cf = sum(Decimal(t["cash_flow"]) for t in data)
    # sto call +200 - bto call -100 + sto put +150 - bto put -75 = +175
    assert total_cf > 0


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/trades"),
        ("GET", "/api/trades"),
        ("GET", "/api/trades/00000000-0000-0000-0000-000000000000"),
        ("PATCH", "/api/trades/00000000-0000-0000-0000-000000000000"),
        ("DELETE", "/api/trades/00000000-0000-0000-0000-000000000000"),
    ],
)
async def test_requires_auth(client: AsyncClient, method: str, path: str) -> None:
    resp = await client.request(
        method,
        path,
        json={
            "position_id": str(uuid.uuid4()),
            "instrument_id": str(uuid.uuid4()),
            "action": "buy",
            "quantity": "10",
            "price": "50",
            "executed_at": NOW.isoformat(),
        } if method in {"POST", "PATCH"} else None,
    )
    assert resp.status_code == 401
