"""End-to-end tests for Dashboard summary (P12)."""

from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient

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


async def _seed_account(
    client: AsyncClient, **overrides: object,
) -> dict:
    body = {**VALID_ACCOUNT, **overrides}
    resp = await client.post("/api/accounts", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _seed_instrument(
    client: AsyncClient, **overrides: object,
) -> dict:
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


async def _seed_trade(
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


async def _close_position(
    client: AsyncClient,
    position_id: str,
    closed_at: str = "2026-06-15T12:00:00Z",
) -> dict:
    resp = await client.patch(
        f"/api/positions/{position_id}",
        json={"status": "closed", "closed_at": closed_at},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_empty_user(auth_client: AsyncClient) -> None:
    """No positions → all counts 0, win_rate null, arrays empty."""
    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["closed"]["count"] == 0
    assert data["closed"]["win_rate"] is None
    assert data["closed"]["per_currency_pnl"] == []
    assert data["closed"]["monthly_pnl"] == []
    assert data["open"]["count"] == 0
    assert data["open"]["per_currency_net_cash_flow"] == []


async def test_only_open_single_currency(
    auth_client: AsyncClient,
) -> None:
    """Only open positions, single currency → closed block empty, open filled."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos1 = await _seed_position(auth_client, acct["id"], instr["id"])
    pos2 = await _seed_position(auth_client, acct["id"], instr["id"])

    t1 = await _seed_trade(
        auth_client, pos1["id"], instr["id"],
        action="buy", quantity="10", price="30",
    )
    t2 = await _seed_trade(
        auth_client, pos2["id"], instr["id"],
        action="sell", quantity="20", price="10",
    )
    expected_total = Decimal(t1["cash_flow"]) + Decimal(t2["cash_flow"])

    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["closed"]["count"] == 0
    assert data["closed"]["win_rate"] is None
    assert data["closed"]["per_currency_pnl"] == []
    assert data["closed"]["monthly_pnl"] == []

    assert data["open"]["count"] == 2
    assert len(data["open"]["per_currency_net_cash_flow"]) == 1
    usd = data["open"]["per_currency_net_cash_flow"][0]
    assert usd["currency"] == "USD"
    assert Decimal(usd["amount"]) == expected_total


async def test_only_closed_single_currency(
    auth_client: AsyncClient,
) -> None:
    """Only closed positions: per_currency_pnl, monthly_pnl, win_rate."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)

    # Winner: sell → positive pnl
    pos1 = await _seed_position(auth_client, acct["id"], instr["id"])
    t1a = await _seed_trade(
        auth_client, pos1["id"], instr["id"],
        action="sell", quantity="10", price="50",
    )
    await _close_position(
        auth_client, pos1["id"], closed_at="2026-03-15T12:00:00Z",
    )

    # Loser: buy → negative pnl
    pos2 = await _seed_position(auth_client, acct["id"], instr["id"])
    t2a = await _seed_trade(
        auth_client, pos2["id"], instr["id"],
        action="buy", quantity="10", price="50",
    )
    await _close_position(
        auth_client, pos2["id"], closed_at="2026-04-20T12:00:00Z",
    )

    expected_pnl_total = Decimal(t1a["cash_flow"]) + Decimal(t2a["cash_flow"])

    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["open"]["count"] == 0
    assert data["open"]["per_currency_net_cash_flow"] == []

    assert data["closed"]["count"] == 2
    assert Decimal(data["closed"]["win_rate"]) == Decimal("0.5")

    cpnl = data["closed"]["per_currency_pnl"]
    assert len(cpnl) == 1
    assert cpnl[0]["currency"] == "USD"
    assert Decimal(cpnl[0]["amount"]) == expected_pnl_total

    mpnl = data["closed"]["monthly_pnl"]
    assert len(mpnl) == 2
    mar = [m for m in mpnl if m["month"] == "2026-03"]
    assert len(mar) == 1
    assert Decimal(mar[0]["amount"]) == Decimal(t1a["cash_flow"])
    apr = [m for m in mpnl if m["month"] == "2026-04"]
    assert len(apr) == 1
    assert Decimal(apr[0]["amount"]) == Decimal(t2a["cash_flow"])


async def test_mixed_open_closed_two_currencies(
    auth_client: AsyncClient,
) -> None:
    """Mixed open + closed across USD and EUR → correct currency splits."""
    acct_usd = await _seed_account(auth_client)
    eur_acct = await _seed_account(
        auth_client, name="EUR Acct", base_currency="EUR",
    )
    instr_usd = await _seed_instrument(auth_client)
    instr_eur = await _seed_instrument(
        auth_client, symbol="SAP", currency="EUR",
    )

    # Open USD
    open_usd = await _seed_position(
        auth_client, acct_usd["id"], instr_usd["id"],
    )
    t_open_usd = await _seed_trade(
        auth_client, open_usd["id"], instr_usd["id"],
        action="buy", quantity="1", price="100",
    )

    # Open EUR
    open_eur = await _seed_position(
        auth_client, eur_acct["id"], instr_eur["id"],
    )
    t_open_eur = await _seed_trade(
        auth_client, open_eur["id"], instr_eur["id"],
        action="sell", quantity="2", price="50",
    )

    # Closed USD: winner
    closed_usd = await _seed_position(
        auth_client, acct_usd["id"], instr_usd["id"],
    )
    t_closed_usd = await _seed_trade(
        auth_client, closed_usd["id"], instr_usd["id"],
        action="sell", quantity="3", price="100",
    )
    await _close_position(
        auth_client, closed_usd["id"], closed_at="2026-01-10T00:00:00Z",
    )

    # Closed EUR: loser
    closed_eur = await _seed_position(
        auth_client, eur_acct["id"], instr_eur["id"],
    )
    t_closed_eur = await _seed_trade(
        auth_client, closed_eur["id"], instr_eur["id"],
        action="buy", quantity="1", price="50",
    )
    await _close_position(
        auth_client, closed_eur["id"], closed_at="2026-02-10T00:00:00Z",
    )

    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["closed"]["count"] == 2
    assert Decimal(data["closed"]["win_rate"]) == Decimal("0.5")

    cpnl = data["closed"]["per_currency_pnl"]
    assert len(cpnl) == 2
    assert cpnl[0]["currency"] == "EUR"
    assert Decimal(cpnl[0]["amount"]) == Decimal(t_closed_eur["cash_flow"])
    assert cpnl[1]["currency"] == "USD"
    assert Decimal(cpnl[1]["amount"]) == Decimal(t_closed_usd["cash_flow"])

    mpnl = data["closed"]["monthly_pnl"]
    assert len(mpnl) == 2
    assert mpnl[0]["month"] == "2026-01"
    assert mpnl[0]["currency"] == "USD"
    assert Decimal(mpnl[0]["amount"]) == Decimal(t_closed_usd["cash_flow"])
    assert mpnl[1]["month"] == "2026-02"
    assert mpnl[1]["currency"] == "EUR"
    assert Decimal(mpnl[1]["amount"]) == Decimal(t_closed_eur["cash_flow"])

    assert data["open"]["count"] == 2
    opncf = data["open"]["per_currency_net_cash_flow"]
    assert len(opncf) == 2
    assert opncf[0]["currency"] == "EUR"
    assert Decimal(opncf[0]["amount"]) == Decimal(t_open_eur["cash_flow"])
    assert opncf[1]["currency"] == "USD"
    assert Decimal(opncf[1]["amount"]) == Decimal(t_open_usd["cash_flow"])


async def test_win_rate_all_wins(auth_client: AsyncClient) -> None:
    """All closed are wins → win_rate == 1.0."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)

    for _ in range(3):
        pos = await _seed_position(auth_client, acct["id"], instr["id"])
        await _seed_trade(
            auth_client, pos["id"], instr["id"],
            action="sell", quantity="1", price="100",
        )
        await _close_position(auth_client, pos["id"])

    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    assert Decimal(resp.json()["closed"]["win_rate"]) == Decimal("1.0")


async def test_win_rate_all_losses(auth_client: AsyncClient) -> None:
    """All closed are losses → win_rate == 0."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)

    for _ in range(3):
        pos = await _seed_position(auth_client, acct["id"], instr["id"])
        await _seed_trade(
            auth_client, pos["id"], instr["id"],
            action="buy", quantity="1", price="100",
        )
        await _close_position(auth_client, pos["id"])

    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    assert Decimal(resp.json()["closed"]["win_rate"]) == Decimal("0")


async def test_win_rate_breakeven_counts_as_loss(
    auth_client: AsyncClient,
) -> None:
    """pnl_realized == 0 counts as loss → not win."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)

    # Winner
    pos1 = await _seed_position(auth_client, acct["id"], instr["id"])
    await _seed_trade(
        auth_client, pos1["id"], instr["id"],
        action="sell", quantity="1", price="100",
    )
    await _close_position(auth_client, pos1["id"])

    # Breakeven: no trades → pnl_realized = 0
    pos2 = await _seed_position(auth_client, acct["id"], instr["id"])
    await _close_position(auth_client, pos2["id"])

    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["closed"]["count"] == 2
    assert Decimal(data["closed"]["win_rate"]) == Decimal("0.5")


async def test_win_rate_no_closed(auth_client: AsyncClient) -> None:
    """No closed positions → win_rate is None."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    await _seed_position(auth_client, acct["id"], instr["id"])

    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    assert resp.json()["closed"]["win_rate"] is None


async def test_archived_trades_excluded_from_open_snapshot(
    auth_client: AsyncClient,
) -> None:
    """Open position with 2 trades; archive 1 → net_cash_flow reflects only other."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])

    t1 = await _seed_trade(
        auth_client, pos["id"], instr["id"],
        action="sell", quantity="10", price="30",
    )
    t2 = await _seed_trade(
        auth_client, pos["id"], instr["id"],
        action="sell", quantity="5", price="20",
    )

    # Archive t1
    del_resp = await auth_client.delete(f"/api/trades/{t1['id']}")
    assert del_resp.status_code == 204

    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["open"]["count"] == 1
    assert len(data["open"]["per_currency_net_cash_flow"]) == 1
    assert (
        Decimal(data["open"]["per_currency_net_cash_flow"][0]["amount"])
        == Decimal(t2["cash_flow"])
    )


async def test_cross_user_isolation(
    auth_client: AsyncClient,
    second_user_client: AsyncClient,
) -> None:
    """User A's positions are invisible in user B's dashboard."""
    acct_a = await _seed_account(auth_client, name="Alice Acct")
    await _seed_account(second_user_client, name="Bob Acct")
    instr = await _seed_instrument(auth_client)

    pos_a = await _seed_position(auth_client, acct_a["id"], instr["id"])
    await _seed_trade(
        auth_client, pos_a["id"], instr["id"],
        action="sell", quantity="5", price="100",
    )
    await _close_position(auth_client, pos_a["id"])

    bob_resp = await second_user_client.get("/api/dashboard/summary")
    assert bob_resp.status_code == 200
    bob_data = bob_resp.json()
    assert bob_data["closed"]["count"] == 0
    assert bob_data["open"]["count"] == 0

    alice_resp = await auth_client.get("/api/dashboard/summary")
    assert alice_resp.status_code == 200
    assert alice_resp.json()["closed"]["count"] == 1


async def test_requires_auth(client: AsyncClient) -> None:
    """Unauthenticated GET /api/dashboard/summary → 401."""
    resp = await client.get("/api/dashboard/summary")
    assert resp.status_code == 401


async def test_monthly_bucket_utc(auth_client: AsyncClient) -> None:
    """closed_at near month boundary → bucketed by UTC month."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])
    await _seed_trade(
        auth_client, pos["id"], instr["id"],
        action="sell", quantity="1", price="100",
    )

    # 2026-04-30 23:30:00 UTC → bucket 2026-04
    await _close_position(
        auth_client, pos["id"], closed_at="2026-04-30T23:30:00Z",
    )

    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    mpnl = resp.json()["closed"]["monthly_pnl"]
    assert len(mpnl) == 1
    assert mpnl[0]["month"] == "2026-04"


async def test_monthly_bucket_non_utc_offset(
    auth_client: AsyncClient,
) -> None:
    """closed_at with +02:00 offset normalizes to UTC before bucketing."""
    acct = await _seed_account(auth_client)
    instr = await _seed_instrument(auth_client)
    pos = await _seed_position(auth_client, acct["id"], instr["id"])
    await _seed_trade(
        auth_client, pos["id"], instr["id"],
        action="sell", quantity="1", price="100",
    )

    # 2026-05-01 01:30:00+02:00 == 2026-04-30 23:30:00 UTC → bucket 2026-04
    await _close_position(
        auth_client, pos["id"],
        closed_at="2026-05-01T01:30:00+02:00",
    )

    resp = await auth_client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    mpnl = resp.json()["closed"]["monthly_pnl"]
    assert len(mpnl) == 1
    assert mpnl[0]["month"] == "2026-04"
