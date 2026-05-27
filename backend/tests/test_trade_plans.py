"""End-to-end tests for TradePlan event-stream CRUD (P11).

TradePlan is a per-Position append-only event stream of plan revisions.
Four endpoints: POST (append), GET list, GET current, GET by revision_no.
No PATCH, no DELETE.

Settled decisions under test:
  - Server-allocated revision_no (MAX+1 per position).
  - Strictly append-only — no PATCH, no DELETE endpoint.
  - GET list ordered oldest-first (revision_no ASC).
  - No strategy_type restriction.
  - Closed-position is NOT a lock for TradePlan writes.
  - Owner-scoped via Position.user_id.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select

from trading_journal.models.position import Position
from trading_journal.models.trade_plan import TradePlan
from trading_journal.services.trade_plans import allocate_next_revision_no

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 5, 20, 14, 30, tzinfo=UTC)

VALID_ACCOUNT = {
    "name": "FX Account",
    "broker": "OANDA",
    "account_type": "margin",
    "base_currency": "USD",
}

VALID_FOREX = {
    "kind": "forex",
    "symbol": "EURUSD",
    "base_currency": "EUR",
    "quote_currency": "USD",
    "pip_size": "0.0001",
}

VALID_STOCK = {"kind": "stock", "symbol": "AAPL", "currency": "USD"}


async def _seed_account(client: AsyncClient, **overrides: object) -> dict:
    body = {**VALID_ACCOUNT, **overrides}
    resp = await client.post("/api/accounts", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _seed_forex(client: AsyncClient, **overrides: object) -> dict:
    body = {**VALID_FOREX, **overrides}
    resp = await client.post("/api/instruments", json=body)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


async def _seed_stock(client: AsyncClient, **overrides: object) -> dict:
    body = {**VALID_STOCK, **overrides}
    resp = await client.post("/api/instruments", json=body)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


async def _seed_position(
    client: AsyncClient,
    account_id: str,
    instrument_id: str,
    strategy_type: str = "spot_forex",
    **overrides: object,
) -> dict:
    body = {
        "account_id": account_id,
        "primary_instrument_id": instrument_id,
        "strategy_type": strategy_type,
        "opened_at": NOW.isoformat(),
        **overrides,
    }
    resp = await client.post("/api/positions", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _seed_fixtures(client: AsyncClient) -> tuple[dict, dict, dict]:
    """Return (account, forex_instrument, open_position)."""
    acct = await _seed_account(client)
    fx = await _seed_forex(client)
    pos = await _seed_position(client, acct["id"], fx["id"])
    return acct, fx, pos


async def _seed_closed_position(
    client: AsyncClient,
) -> tuple[dict, dict, dict]:
    """Return (account, forex_instrument, closed_position)."""
    acct = await _seed_account(client)
    fx = await _seed_forex(client)
    pos = await _seed_position(client, acct["id"], fx["id"])
    close_resp = await client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-08-01T20:00:00Z"},
    )
    assert close_resp.status_code == 200, close_resp.text
    return acct, fx, pos


# ---------------------------------------------------------------------------
# Service-layer tests (no HTTP)
# ---------------------------------------------------------------------------


async def test_allocate_next_revision_no_empty_returns_1(
    db_session_maker,
) -> None:
    async with db_session_maker() as session:
        pos_id = uuid.uuid4()
        result = await allocate_next_revision_no(session, pos_id)
        assert result == 1


async def test_allocate_next_revision_no_sequential(db_session_maker) -> None:
    async with db_session_maker() as session:
        pos_id = uuid.uuid4()
        for i in range(1, 4):
            await session.execute(
                insert(TradePlan).values(
                    id=uuid.uuid4(),
                    position_id=pos_id,
                    revision_no=i,
                    effective_at=NOW,
                )
            )
        await session.commit()
        result = await allocate_next_revision_no(session, pos_id)
        assert result == 4


async def test_allocate_next_revision_no_isolated_per_position(
    db_session_maker,
) -> None:
    async with db_session_maker() as session:
        pos_a = uuid.uuid4()
        pos_b = uuid.uuid4()
        for i in range(1, 4):
            await session.execute(
                insert(TradePlan).values(
                    id=uuid.uuid4(),
                    position_id=pos_a,
                    revision_no=i,
                    effective_at=NOW,
                )
            )
            await session.execute(
                insert(TradePlan).values(
                    id=uuid.uuid4(),
                    position_id=pos_b,
                    revision_no=i,
                    effective_at=NOW,
                )
            )
        await session.commit()
        assert await allocate_next_revision_no(session, pos_a) == 4
        assert await allocate_next_revision_no(session, pos_b) == 4


# ---------------------------------------------------------------------------
# POST /positions/{pid}/trade-plans
# ---------------------------------------------------------------------------


async def test_create_first_revision_201_revision_no_is_1(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["revision_no"] == 1
    assert data["position_id"] == pos["id"]
    assert data["created_at"] is not None
    assert data["planned_entry"] is None
    assert data["thesis"] is None


async def test_create_with_all_fields(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    payload = {
        "effective_at": "2026-06-01T08:00:00Z",
        "planned_entry": "1.0850",
        "planned_stop_loss": "1.0800",
        "planned_take_profit": "1.0950",
        "target_rr": "2.0",
        "thesis": "Breakout retest of weekly resistance turned support.",
        "reason": "Initial plan",
    }
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans", json=payload
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert Decimal(data["planned_entry"]) == Decimal("1.0850")
    assert Decimal(data["planned_stop_loss"]) == Decimal("1.0800")
    assert Decimal(data["planned_take_profit"]) == Decimal("1.0950")
    assert Decimal(data["target_rr"]) == Decimal("2.0")
    assert data["thesis"] == "Breakout retest of weekly resistance turned support."
    assert data["reason"] == "Initial plan"


async def test_create_second_revision_revision_no_is_2(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-03T14:30:00Z", "reason": "Moved SL to BE"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["revision_no"] == 2


async def test_create_third_revision_revision_no_is_3(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    for i in range(2):
        await auth_client.post(
            f"/api/positions/{pos['id']}/trade-plans",
            json={"effective_at": f"2026-06-0{i+1}T08:00:00Z"},
        )
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-05T08:00:00Z"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["revision_no"] == 3


async def test_create_rejects_position_id_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "position_id": pos["id"]},
    )
    assert resp.status_code == 422


async def test_create_rejects_revision_no_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "revision_no": 42},
    )
    assert resp.status_code == 422


async def test_create_rejects_id_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={
            "effective_at": "2026-06-01T08:00:00Z",
            "id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 422


async def test_create_rejects_created_at_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={
            "effective_at": "2026-06-01T08:00:00Z",
            "created_at": "2026-01-01T00:00:00Z",
        },
    )
    assert resp.status_code == 422


async def test_create_rejects_missing_effective_at_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"thesis": "No effective_at"},
    )
    assert resp.status_code == 422


async def test_create_rejects_negative_planned_entry_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "planned_entry": "-1.0"},
    )
    assert resp.status_code == 422


async def test_create_rejects_zero_planned_entry_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "planned_entry": "0"},
    )
    assert resp.status_code == 422


async def test_create_rejects_negative_planned_stop_loss_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "planned_stop_loss": "-0.5"},
    )
    assert resp.status_code == 422


async def test_create_rejects_negative_planned_take_profit_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "planned_take_profit": "-1.0"},
    )
    assert resp.status_code == 422


async def test_create_rejects_negative_target_rr_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "target_rr": "-0.5"},
    )
    assert resp.status_code == 422


async def test_create_allows_thesis_only(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "thesis": "Just a thesis"},
    )
    assert resp.status_code == 201
    assert resp.json()["thesis"] == "Just a thesis"
    assert resp.json()["planned_entry"] is None


async def test_create_404_unknown_position(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        f"/api/positions/{uuid.uuid4()}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    assert resp.status_code == 404


async def test_create_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, alice_pos = await _seed_fixtures(auth_client)
    resp = await second_user_client.post(
        f"/api/positions/{alice_pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    assert resp.status_code == 404


async def test_create_append_allowed_on_closed_position(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_closed_position(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={
            "effective_at": "2026-08-01T20:00:00Z",
            "reason": "Post-mortem revision",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["revision_no"] == 1


async def test_create_does_not_mutate_position(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    get_resp = await auth_client.get(f"/api/positions/{pos['id']}")
    assert get_resp.status_code == 200
    original_updated_at = get_resp.json().get("updated_at")

    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )

    get_resp2 = await auth_client.get(f"/api/positions/{pos['id']}")
    assert get_resp2.status_code == 200
    assert get_resp2.json().get("updated_at") == original_updated_at


# ---------------------------------------------------------------------------
# GET /positions/{pid}/trade-plans (list)
# ---------------------------------------------------------------------------


async def test_list_empty_returns_empty_array(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.get(f"/api/positions/{pos['id']}/trade-plans")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_oldest_first(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={
            "effective_at": "2026-06-01T08:00:00Z",
            "planned_entry": "1.0850",
        },
    )
    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={
            "effective_at": "2026-06-03T14:30:00Z",
            "planned_entry": "1.0900",
            "reason": "Updated",
        },
    )
    resp = await auth_client.get(f"/api/positions/{pos['id']}/trade-plans")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["revision_no"] == 1
    assert data[1]["revision_no"] == 2
    assert Decimal(data[0]["planned_entry"]) == Decimal("1.0850")
    assert Decimal(data[1]["planned_entry"]) == Decimal("1.0900")


async def test_list_isolated_per_position(auth_client: AsyncClient) -> None:
    acct = await _seed_account(auth_client)
    fx = await _seed_forex(auth_client)
    pos_a = await _seed_position(auth_client, acct["id"], fx["id"])
    pos_b = await _seed_position(
        auth_client, acct["id"], fx["id"], strategy_type="spot_forex"
    )

    await auth_client.post(
        f"/api/positions/{pos_a['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    await auth_client.post(
        f"/api/positions/{pos_b['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    await auth_client.post(
        f"/api/positions/{pos_b['id']}/trade-plans",
        json={"effective_at": "2026-06-02T08:00:00Z"},
    )

    resp_a = await auth_client.get(f"/api/positions/{pos_a['id']}/trade-plans")
    assert len(resp_a.json()) == 1

    resp_b = await auth_client.get(f"/api/positions/{pos_b['id']}/trade-plans")
    assert len(resp_b.json()) == 2


async def test_list_404_unknown_position(auth_client: AsyncClient) -> None:
    resp = await auth_client.get(f"/api/positions/{uuid.uuid4()}/trade-plans")
    assert resp.status_code == 404


async def test_list_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, alice_pos = await _seed_fixtures(auth_client)
    resp = await second_user_client.get(
        f"/api/positions/{alice_pos['id']}/trade-plans"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /positions/{pid}/trade-plans/current
# ---------------------------------------------------------------------------


async def test_get_current_404_when_no_revisions(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.get(
        f"/api/positions/{pos['id']}/trade-plans/current"
    )
    assert resp.status_code == 404


async def test_get_current_returns_latest_after_one(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "thesis": "First"},
    )
    resp = await auth_client.get(
        f"/api/positions/{pos['id']}/trade-plans/current"
    )
    assert resp.status_code == 200
    assert resp.json()["revision_no"] == 1


async def test_get_current_returns_latest_after_multiple(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    for i in range(3):
        await auth_client.post(
            f"/api/positions/{pos['id']}/trade-plans",
            json={"effective_at": f"2026-06-0{i+1}T08:00:00Z"},
        )
    resp = await auth_client.get(
        f"/api/positions/{pos['id']}/trade-plans/current"
    )
    assert resp.status_code == 200
    assert resp.json()["revision_no"] == 3


async def test_get_current_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, alice_pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{alice_pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    resp = await second_user_client.get(
        f"/api/positions/{alice_pos['id']}/trade-plans/current"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /positions/{pid}/trade-plans/{revision_no}
# ---------------------------------------------------------------------------


async def test_get_specific_revision_200(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={
            "effective_at": "2026-06-01T08:00:00Z",
            "planned_entry": "1.0850",
        },
    )
    resp = await auth_client.get(
        f"/api/positions/{pos['id']}/trade-plans/1"
    )
    assert resp.status_code == 200
    assert resp.json()["revision_no"] == 1
    assert Decimal(resp.json()["planned_entry"]) == Decimal("1.0850")


async def test_get_specific_revision_404_unknown(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    resp = await auth_client.get(
        f"/api/positions/{pos['id']}/trade-plans/99"
    )
    assert resp.status_code == 404


async def test_get_specific_revision_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, alice_pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{alice_pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    resp = await second_user_client.get(
        f"/api/positions/{alice_pos['id']}/trade-plans/1"
    )
    assert resp.status_code == 404


async def test_get_specific_revision_route_does_not_clash_with_current(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "thesis": "Rev 1"},
    )
    # /current should route to the dedicated handler
    resp_current = await auth_client.get(
        f"/api/positions/{pos['id']}/trade-plans/current"
    )
    assert resp_current.status_code == 200
    assert resp_current.json()["thesis"] == "Rev 1"

    # /1 should return revision 1
    resp_1 = await auth_client.get(
        f"/api/positions/{pos['id']}/trade-plans/1"
    )
    assert resp_1.status_code == 200
    assert resp_1.json()["thesis"] == "Rev 1"


async def test_get_specific_revision_422_on_non_int(
    auth_client: AsyncClient,
) -> None:
    """Non-int path param triggers FastAPI parameter validation → 422."""
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.get(
        f"/api/positions/{pos['id']}/trade-plans/abc"
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Append-only invariants
# ---------------------------------------------------------------------------


async def test_no_patch_endpoint(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/trade-plans/1",
        json={"reason": "oops"},
    )
    assert resp.status_code == 405


async def test_no_delete_endpoint(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z"},
    )
    resp = await auth_client.delete(
        f"/api/positions/{pos['id']}/trade-plans/1"
    )
    assert resp.status_code == 405


async def test_no_root_delete_endpoint(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.delete(
        f"/api/positions/{pos['id']}/trade-plans"
    )
    assert resp.status_code == 405


async def test_no_patch_on_current(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_fixtures(auth_client)
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/trade-plans/current",
        json={"reason": "oops"},
    )
    assert resp.status_code == 405


# ---------------------------------------------------------------------------
# Parent Position DELETE protection
# ---------------------------------------------------------------------------


async def test_position_delete_409_when_trade_plans_exist(
    auth_client: AsyncClient,
) -> None:
    """DELETE /positions/{id} must 409 when plan revisions exist (even without trades)."""
    _, _, pos = await _seed_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={"effective_at": "2026-06-01T08:00:00Z", "thesis": "Protected"},
    )
    resp = await auth_client.delete(f"/api/positions/{pos['id']}")
    assert resp.status_code == 409
    assert "plan revisions" in resp.json()["detail"]

    # Position still exists
    resp2 = await auth_client.get(f"/api/positions/{pos['id']}")
    assert resp2.status_code == 200

    # Plan revisions still accessible
    resp3 = await auth_client.get(f"/api/positions/{pos['id']}/trade-plans")
    assert resp3.status_code == 200
    assert len(resp3.json()) == 1


# ---------------------------------------------------------------------------
# Strategy-type neutrality
# ---------------------------------------------------------------------------


async def test_create_allows_non_spot_forex_strategy(
    auth_client: AsyncClient,
) -> None:
    """TradePlan is strategy-agnostic; wheel/iron_condor positions also allowed."""
    acct = await _seed_account(auth_client)
    stock = await _seed_stock(auth_client)
    pos = await _seed_position(
        auth_client, acct["id"], stock["id"], strategy_type="wheel"
    )
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/trade-plans",
        json={
            "effective_at": "2026-06-01T08:00:00Z",
            "thesis": "Wheel thesis — sell puts on AAPL",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["thesis"] == "Wheel thesis — sell puts on AAPL"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_DUMMY_UUID = "00000000-0000-0000-0000-000000000001"

_AUTH_CASES = [
    ("POST", "/api/positions/{pid}/trade-plans", {"effective_at": "2026-06-01T08:00:00Z"}),
    ("GET", "/api/positions/{pid}/trade-plans", None),
    ("GET", "/api/positions/{pid}/trade-plans/current", None),
    ("GET", "/api/positions/{pid}/trade-plans/1", None),
]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    _AUTH_CASES,
    ids=[f"{m}-{p.split('/')[-1]}" for m, p, _ in _AUTH_CASES],
)
async def test_requires_auth(
    client: AsyncClient, method: str, path: str, body: dict | None
) -> None:
    pid = _DUMMY_UUID
    resp = await client.request(method, path.format(pid=pid), json=body)
    assert resp.status_code == 401
