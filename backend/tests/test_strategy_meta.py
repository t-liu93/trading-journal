"""End-to-end tests for strategy-meta CRUD (P10).

WheelCycleMeta and PmccCycleMeta are 1:1 Position extensions with nested
sub-resource URLs (``/positions/{pid}/wheel-meta``, ``/positions/{pid}/pmcc-meta``).

Settled decisions under test:
  - Strict strategy_type matching.
  - PMCC LEAP triple-validation (exists, kind=option, underlying matches).
  - Closed-position is NOT a lock for meta writes.
  - POST is create-only (409 on duplicate).
  - Owner-scoped via Position.user_id.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select

from trading_journal.models._enums import StrategyType
from trading_journal.models.instrument import Instrument, OptionContract
from trading_journal.models.position import Position
from trading_journal.services.strategy_meta import (
    validate_leap_instrument,
    validate_strategy_type_match,
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

VALID_STOCK = {"kind": "stock", "symbol": "AAPL", "currency": "USD"}

VALID_LEAP_OPTION = {
    "kind": "option",
    "underlying_symbol": "AAPL",
    "currency": "USD",
    "opt_type": "call",
    "strike": "150.00",
    "expiry": "2028-01-21",
    "multiplier": 100,
}


async def _seed_account(client: AsyncClient, **overrides: object) -> dict:
    body = {**VALID_ACCOUNT, **overrides}
    resp = await client.post("/api/accounts", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _seed_stock(client: AsyncClient, **overrides: object) -> dict:
    body = {**VALID_STOCK, **overrides}
    resp = await client.post("/api/instruments", json=body)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


async def _seed_option(
    client: AsyncClient, underlying_symbol: str = "AAPL", **overrides: object
) -> dict:
    body = {**VALID_LEAP_OPTION, "underlying_symbol": underlying_symbol, **overrides}
    resp = await client.post("/api/instruments", json=body)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


async def _seed_position(
    client: AsyncClient,
    account_id: str,
    instrument_id: str,
    strategy_type: str = "wheel",
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


async def _seed_wheel_fixtures(client: AsyncClient) -> tuple[dict, dict, dict]:
    """Return (account, stock_instrument, wheel_position)."""
    acct = await _seed_account(client)
    stock = await _seed_stock(client)
    pos = await _seed_position(client, acct["id"], stock["id"], strategy_type="wheel")
    return acct, stock, pos


async def _seed_pmcc_fixtures(
    client: AsyncClient,
) -> tuple[dict, dict, dict, dict]:
    """Return (account, stock_instrument, leap_option, pmcc_position)."""
    acct = await _seed_account(client)
    stock = await _seed_stock(client)
    leap = await _seed_option(client)
    pos = await _seed_position(client, acct["id"], stock["id"], strategy_type="pmcc")
    return acct, stock, leap, pos


# ---------------------------------------------------------------------------
# Service-layer tests (no HTTP)
# ---------------------------------------------------------------------------


async def test_validate_strategy_type_match_ok(db_session_maker) -> None:
    async with db_session_maker() as session:
        pos_id = uuid.uuid4()
        await session.execute(
            insert(Position).values(
                id=pos_id,
                user_id=uuid.uuid4(),
                account_id=uuid.uuid4(),
                primary_instrument_id=uuid.uuid4(),
                strategy_type="wheel",
                status="open",
                opened_at=NOW,
                currency="USD",
            )
        )
        await session.commit()
        pos = (await session.execute(
            select(Position).where(Position.id == pos_id)
        )).scalar_one()
        validate_strategy_type_match(pos, StrategyType.WHEEL)


async def test_validate_strategy_type_match_mismatch_raises(db_session_maker) -> None:
    async with db_session_maker() as session:
        pos_id = uuid.uuid4()
        await session.execute(
            insert(Position).values(
                id=pos_id,
                user_id=uuid.uuid4(),
                account_id=uuid.uuid4(),
                primary_instrument_id=uuid.uuid4(),
                strategy_type="iron_condor",
                status="open",
                opened_at=NOW,
                currency="USD",
            )
        )
        await session.commit()
        pos = (await session.execute(
            select(Position).where(Position.id == pos_id)
        )).scalar_one()
        with pytest.raises(ValueError, match="strategy_type"):
            validate_strategy_type_match(pos, StrategyType.WHEEL)


async def test_validate_leap_instrument_ok(db_session_maker) -> None:
    async with db_session_maker() as session:
        stock_id = uuid.uuid4()
        opt_id = uuid.uuid4()
        pos_id = uuid.uuid4()
        await session.execute(
            insert(Instrument).values(
                id=stock_id, kind="stock", symbol="AAPL", currency="USD"
            )
        )
        await session.execute(
            insert(Instrument).values(
                id=opt_id, kind="option", symbol="AAPL", currency="USD"
            )
        )
        await session.execute(
            insert(OptionContract).values(
                instrument_id=opt_id,
                underlying_id=stock_id,
                opt_type="call",
                strike=Decimal("150"),
                expiry=date(2028, 1, 21),
                multiplier=100,
                style="american",
            )
        )
        await session.execute(
            insert(Position).values(
                id=pos_id,
                user_id=uuid.uuid4(),
                account_id=uuid.uuid4(),
                primary_instrument_id=stock_id,
                strategy_type="pmcc",
                status="open",
                opened_at=NOW,
                currency="USD",
            )
        )
        await session.commit()
        pos = (await session.execute(
            select(Position).where(Position.id == pos_id)
        )).scalar_one()
        await validate_leap_instrument(session, pos, opt_id)


async def test_validate_leap_instrument_unknown_raises(db_session_maker) -> None:
    async with db_session_maker() as session:
        pos_id = uuid.uuid4()
        await session.execute(
            insert(Position).values(
                id=pos_id,
                user_id=uuid.uuid4(),
                account_id=uuid.uuid4(),
                primary_instrument_id=uuid.uuid4(),
                strategy_type="pmcc",
                status="open",
                opened_at=NOW,
                currency="USD",
            )
        )
        await session.commit()
        pos = (await session.execute(
            select(Position).where(Position.id == pos_id)
        )).scalar_one()
        with pytest.raises(ValueError, match="not found"):
            await validate_leap_instrument(session, pos, uuid.uuid4())


async def test_validate_leap_instrument_not_option_raises(db_session_maker) -> None:
    async with db_session_maker() as session:
        stock_id = uuid.uuid4()
        pos_id = uuid.uuid4()
        await session.execute(
            insert(Instrument).values(
                id=stock_id, kind="stock", symbol="AAPL", currency="USD"
            )
        )
        await session.execute(
            insert(Position).values(
                id=pos_id,
                user_id=uuid.uuid4(),
                account_id=uuid.uuid4(),
                primary_instrument_id=stock_id,
                strategy_type="pmcc",
                status="open",
                opened_at=NOW,
                currency="USD",
            )
        )
        await session.commit()
        pos = (await session.execute(
            select(Position).where(Position.id == pos_id)
        )).scalar_one()
        with pytest.raises(ValueError, match="option instrument"):
            await validate_leap_instrument(session, pos, stock_id)


async def test_validate_leap_instrument_wrong_underlying_raises(db_session_maker) -> None:
    async with db_session_maker() as session:
        stock_a = uuid.uuid4()
        stock_b = uuid.uuid4()
        opt_id = uuid.uuid4()
        pos_id = uuid.uuid4()
        await session.execute(
            insert(Instrument).values(
                id=stock_a, kind="stock", symbol="AAPL", currency="USD"
            )
        )
        await session.execute(
            insert(Instrument).values(
                id=stock_b, kind="stock", symbol="MSFT", currency="USD"
            )
        )
        await session.execute(
            insert(Instrument).values(
                id=opt_id, kind="option", symbol="AAPL", currency="USD"
            )
        )
        await session.execute(
            insert(OptionContract).values(
                instrument_id=opt_id,
                underlying_id=stock_a,
                opt_type="call",
                strike=Decimal("150"),
                expiry=date(2028, 1, 21),
                multiplier=100,
                style="american",
            )
        )
        # Position's primary instrument is stock_b (MSFT), but the option
        # is on stock_a (AAPL) — underlying mismatch.
        await session.execute(
            insert(Position).values(
                id=pos_id,
                user_id=uuid.uuid4(),
                account_id=uuid.uuid4(),
                primary_instrument_id=stock_b,
                strategy_type="pmcc",
                status="open",
                opened_at=NOW,
                currency="USD",
            )
        )
        await session.commit()
        pos = (await session.execute(
            select(Position).where(Position.id == pos_id)
        )).scalar_one()
        with pytest.raises(ValueError, match="underlying"):
            await validate_leap_instrument(session, pos, opt_id)


# ---------------------------------------------------------------------------
# POST /positions/{pid}/wheel-meta
# ---------------------------------------------------------------------------


async def test_create_wheel_meta_201_min_payload(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["position_id"] == pos["id"]
    assert data["funding_source"] == "cash"
    assert data["loan_amount"] is None
    assert data["interest_rate_apr"] is None
    assert data["interest_accrued"] is None


async def test_create_wheel_meta_with_all_fields(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={
            "funding_source": "margin",
            "loan_amount": "10000.5000",
            "interest_rate_apr": "0.055",
            "interest_accrued": "250.50",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["funding_source"] == "margin"
    assert Decimal(data["loan_amount"]) == Decimal("10000.5000")
    assert Decimal(data["interest_rate_apr"]) == Decimal("0.055")
    assert Decimal(data["interest_accrued"]) == Decimal("250.50")


async def test_create_wheel_meta_rejects_position_id_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash", "position_id": pos["id"]},
    )
    assert resp.status_code == 422


async def test_create_wheel_meta_rejects_unknown_field_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash", "bogus": True},
    )
    assert resp.status_code == 422


async def test_create_wheel_meta_rejects_negative_loan_amount_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash", "loan_amount": "-1"},
    )
    assert resp.status_code == 422


async def test_create_wheel_meta_rejects_negative_interest_rate_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash", "interest_rate_apr": "-0.01"},
    )
    assert resp.status_code == 422


async def test_create_wheel_meta_rejects_negative_interest_accrued_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash", "interest_accrued": "-0.01"},
    )
    assert resp.status_code == 422


async def test_create_wheel_meta_allows_zero_loan_amount(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash", "loan_amount": "0"},
    )
    assert resp.status_code == 201
    assert Decimal(resp.json()["loan_amount"]) == Decimal("0")


async def test_create_wheel_meta_rejects_bad_funding_source_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "bitcoin"},
    )
    assert resp.status_code == 422


async def test_create_wheel_meta_rejects_missing_funding_source_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={},
    )
    assert resp.status_code == 422


async def test_create_wheel_meta_rejects_on_non_wheel_position_422(
    auth_client: AsyncClient,
) -> None:
    acct = await _seed_account(auth_client)
    stock = await _seed_stock(auth_client)
    # Iron-condor position — not wheel
    pos = await _seed_position(
        auth_client, acct["id"], stock["id"], strategy_type="iron_condor"
    )
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    assert resp.status_code == 422
    assert "strategy_type" in resp.json()["detail"]


async def test_create_wheel_meta_409_if_already_exists(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp1 = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    assert resp1.status_code == 201
    resp2 = await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "margin"},
    )
    assert resp2.status_code == 409
    assert "PATCH" in resp2.json()["detail"]


async def test_create_wheel_meta_404_unknown_position(
    auth_client: AsyncClient,
) -> None:
    resp = await auth_client.post(
        f"/api/positions/{uuid.uuid4()}/wheel-meta",
        json={"funding_source": "cash"},
    )
    assert resp.status_code == 404


async def test_create_wheel_meta_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, alice_pos = await _seed_wheel_fixtures(auth_client)
    resp = await second_user_client.post(
        f"/api/positions/{alice_pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /positions/{pid}/wheel-meta
# ---------------------------------------------------------------------------


async def test_get_wheel_meta_200(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    resp = await auth_client.get(f"/api/positions/{pos['id']}/wheel-meta")
    assert resp.status_code == 200
    assert resp.json()["funding_source"] == "cash"


async def test_get_wheel_meta_404_when_not_created(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.get(f"/api/positions/{pos['id']}/wheel-meta")
    assert resp.status_code == 404


async def test_get_wheel_meta_404_unknown_position(
    auth_client: AsyncClient,
) -> None:
    resp = await auth_client.get(f"/api/positions/{uuid.uuid4()}/wheel-meta")
    assert resp.status_code == 404


async def test_get_wheel_meta_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, alice_pos = await _seed_wheel_fixtures(auth_client)
    resp = await second_user_client.get(
        f"/api/positions/{alice_pos['id']}/wheel-meta"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /positions/{pid}/wheel-meta
# ---------------------------------------------------------------------------


async def test_patch_wheel_meta_partial_update(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"loan_amount": "5000"},
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["loan_amount"]) == Decimal("5000")
    assert resp.json()["funding_source"] == "cash"


async def test_patch_wheel_meta_multiple_fields(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={
            "funding_source": "margin",
            "loan_amount": "10000",
            "interest_rate_apr": "0.055",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["funding_source"] == "margin"
    assert Decimal(data["loan_amount"]) == Decimal("10000")
    assert Decimal(data["interest_rate_apr"]) == Decimal("0.055")


async def test_patch_wheel_meta_unset_means_no_change(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash", "loan_amount": "5000"},
    )
    # Patch only funding_source — loan_amount should remain 5000
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "margin"},
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["loan_amount"]) == Decimal("5000")


async def test_patch_wheel_meta_rejects_negative_value_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"loan_amount": "-10"},
    )
    assert resp.status_code == 422


async def test_patch_wheel_meta_rejects_position_id_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"position_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 422


async def test_patch_wheel_meta_404_when_meta_not_created(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "margin"},
    )
    assert resp.status_code == 404


async def test_patch_wheel_meta_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, alice_pos = await _seed_wheel_fixtures(auth_client)
    resp = await second_user_client.patch(
        f"/api/positions/{alice_pos['id']}/wheel-meta",
        json={"funding_source": "margin"},
    )
    assert resp.status_code == 404


async def test_patch_wheel_meta_allowed_on_closed_position(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    # Close the position
    await auth_client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-08-01T20:00:00Z"},
    )
    # PATCH meta on closed position → still 200
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"interest_accrued": "250.50"},
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["interest_accrued"]) == Decimal("250.50")


async def test_patch_wheel_meta_rejects_null_funding_source_422(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": None},
    )
    assert resp.status_code == 422
    assert "funding_source" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# DELETE /positions/{pid}/wheel-meta
# ---------------------------------------------------------------------------


async def test_delete_wheel_meta_204(auth_client: AsyncClient) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    resp = await auth_client.delete(f"/api/positions/{pos['id']}/wheel-meta")
    assert resp.status_code == 204

    # Meta is gone
    resp2 = await auth_client.get(f"/api/positions/{pos['id']}/wheel-meta")
    assert resp2.status_code == 404

    # Second delete → 404
    resp3 = await auth_client.delete(f"/api/positions/{pos['id']}/wheel-meta")
    assert resp3.status_code == 404


async def test_delete_wheel_meta_404_when_not_created(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    resp = await auth_client.delete(f"/api/positions/{pos['id']}/wheel-meta")
    assert resp.status_code == 404


async def test_delete_wheel_meta_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, alice_pos = await _seed_wheel_fixtures(auth_client)
    resp = await second_user_client.delete(
        f"/api/positions/{alice_pos['id']}/wheel-meta"
    )
    assert resp.status_code == 404


async def test_delete_wheel_meta_allowed_on_closed_position(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    # Close the position
    await auth_client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-08-01T20:00:00Z"},
    )
    resp = await auth_client.delete(f"/api/positions/{pos['id']}/wheel-meta")
    assert resp.status_code == 204


async def test_delete_wheel_meta_does_not_affect_position(
    auth_client: AsyncClient,
) -> None:
    _, _, pos = await _seed_wheel_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/wheel-meta",
        json={"funding_source": "cash"},
    )
    await auth_client.delete(f"/api/positions/{pos['id']}/wheel-meta")
    # Position still exists
    resp = await auth_client.get(f"/api/positions/{pos['id']}")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /positions/{pid}/pmcc-meta
# ---------------------------------------------------------------------------


async def test_create_pmcc_meta_201(auth_client: AsyncClient) -> None:
    _, _, leap, pos = await _seed_pmcc_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["position_id"] == pos["id"]
    assert data["leap_instrument_id"] == leap["id"]


async def test_create_pmcc_meta_rejects_on_non_pmcc_position_422(
    auth_client: AsyncClient,
) -> None:
    acct = await _seed_account(auth_client)
    stock = await _seed_stock(auth_client)
    # Wheel position — not PMCC
    pos = await _seed_position(
        auth_client, acct["id"], stock["id"], strategy_type="wheel"
    )
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 422
    assert "strategy_type" in resp.json()["detail"]


async def test_create_pmcc_meta_rejects_unknown_leap_422(
    auth_client: AsyncClient,
) -> None:
    _, _, _, pos = await _seed_pmcc_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 422
    assert "not found" in resp.json()["detail"]


async def test_create_pmcc_meta_rejects_non_option_leap_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, _, pos = await _seed_pmcc_fixtures(auth_client)
    # Use the stock instrument as the "LEAP" — wrong kind
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": stock["id"]},
    )
    assert resp.status_code == 422
    assert "option instrument" in resp.json()["detail"]


async def test_create_pmcc_meta_rejects_wrong_underlying_leap_422(
    auth_client: AsyncClient,
) -> None:
    acct = await _seed_account(auth_client)
    await _seed_stock(auth_client)
    msft = await _seed_stock(auth_client, symbol="MSFT")
    # LEAP option on AAPL, but position primary is MSFT
    leap = await _seed_option(auth_client)
    pos = await _seed_position(
        auth_client, acct["id"], msft["id"], strategy_type="pmcc"
    )
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    assert resp.status_code == 422
    assert "underlying" in resp.json()["detail"]


async def test_create_pmcc_meta_409_if_already_exists(
    auth_client: AsyncClient,
) -> None:
    _, _, leap, pos = await _seed_pmcc_fixtures(auth_client)
    resp1 = await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    assert resp1.status_code == 201
    resp2 = await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    assert resp2.status_code == 409


async def test_create_pmcc_meta_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, leap, alice_pos = await _seed_pmcc_fixtures(auth_client)
    resp = await second_user_client.post(
        f"/api/positions/{alice_pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    assert resp.status_code == 404


async def test_create_pmcc_meta_rejects_position_id_in_body_422(
    auth_client: AsyncClient,
) -> None:
    _, _, leap, pos = await _seed_pmcc_fixtures(auth_client)
    resp = await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"], "position_id": pos["id"]},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /positions/{pid}/pmcc-meta
# ---------------------------------------------------------------------------


async def test_get_pmcc_meta_200(auth_client: AsyncClient) -> None:
    _, _, leap, pos = await _seed_pmcc_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    resp = await auth_client.get(f"/api/positions/{pos['id']}/pmcc-meta")
    assert resp.status_code == 200
    assert resp.json()["leap_instrument_id"] == leap["id"]


async def test_get_pmcc_meta_404_when_not_created(
    auth_client: AsyncClient,
) -> None:
    _, _, _, pos = await _seed_pmcc_fixtures(auth_client)
    resp = await auth_client.get(f"/api/positions/{pos['id']}/pmcc-meta")
    assert resp.status_code == 404


async def test_get_pmcc_meta_404_cross_user(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    _, _, leap, alice_pos = await _seed_pmcc_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{alice_pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    resp = await second_user_client.get(
        f"/api/positions/{alice_pos['id']}/pmcc-meta"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /positions/{pid}/pmcc-meta
# ---------------------------------------------------------------------------


async def test_patch_pmcc_meta_changes_leap_retarget(
    auth_client: AsyncClient,
) -> None:
    """Retarget LEAP to another valid option on the same underlying."""
    acct = await _seed_account(auth_client)
    stock = await _seed_stock(auth_client)
    leap1 = await _seed_option(auth_client)
    # Second option on same underlying (different strike/expiry)
    leap2 = await _seed_option(
        auth_client,
        strike="200.00",
        expiry="2028-06-17",
    )
    pos = await _seed_position(
        auth_client, acct["id"], stock["id"], strategy_type="pmcc"
    )
    await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap1["id"]},
    )
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap2["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["leap_instrument_id"] == leap2["id"]


async def test_patch_pmcc_meta_rejects_wrong_underlying_leap_422(
    auth_client: AsyncClient,
) -> None:
    acct = await _seed_account(auth_client)
    stock_a = await _seed_stock(auth_client, symbol="AAPL")
    await _seed_stock(auth_client, symbol="MSFT")
    leap_a = await _seed_option(auth_client, underlying_symbol="AAPL")
    leap_b = await _seed_option(auth_client, underlying_symbol="MSFT")
    pos = await _seed_position(
        auth_client, acct["id"], stock_a["id"], strategy_type="pmcc"
    )
    await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap_a["id"]},
    )
    # Try to retarget to an option on MSFT — wrong underlying
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap_b["id"]},
    )
    assert resp.status_code == 422
    assert "underlying" in resp.json()["detail"]


async def test_patch_pmcc_meta_rejects_non_option_leap_422(
    auth_client: AsyncClient,
) -> None:
    _, stock, leap, pos = await _seed_pmcc_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    # Try to change LEAP to a stock instrument
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": stock["id"]},
    )
    assert resp.status_code == 422
    assert "option instrument" in resp.json()["detail"]


async def test_patch_pmcc_meta_404_when_meta_not_created(
    auth_client: AsyncClient,
) -> None:
    _, _, leap, pos = await _seed_pmcc_fixtures(auth_client)
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    assert resp.status_code == 404


async def test_patch_pmcc_meta_allowed_on_closed_position(
    auth_client: AsyncClient,
) -> None:
    _, _, leap, pos = await _seed_pmcc_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    # Close the position
    await auth_client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-08-01T20:00:00Z"},
    )
    # Create another valid LEAP to retarget to
    # (can reuse the same one — it's still valid)
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    assert resp.status_code == 200


async def test_patch_pmcc_meta_rejects_null_leap_instrument_id_422(
    auth_client: AsyncClient,
) -> None:
    _, _, leap, pos = await _seed_pmcc_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    resp = await auth_client.patch(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": None},
    )
    assert resp.status_code == 422
    assert "leap_instrument_id" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# DELETE /positions/{pid}/pmcc-meta
# ---------------------------------------------------------------------------


async def test_delete_pmcc_meta_204(auth_client: AsyncClient) -> None:
    _, _, leap, pos = await _seed_pmcc_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    resp = await auth_client.delete(f"/api/positions/{pos['id']}/pmcc-meta")
    assert resp.status_code == 204

    # Meta is gone
    resp2 = await auth_client.get(f"/api/positions/{pos['id']}/pmcc-meta")
    assert resp2.status_code == 404

    # Second delete → 404
    resp3 = await auth_client.delete(f"/api/positions/{pos['id']}/pmcc-meta")
    assert resp3.status_code == 404


async def test_delete_pmcc_meta_404_when_not_created(
    auth_client: AsyncClient,
) -> None:
    _, _, _, pos = await _seed_pmcc_fixtures(auth_client)
    resp = await auth_client.delete(f"/api/positions/{pos['id']}/pmcc-meta")
    assert resp.status_code == 404


async def test_delete_pmcc_meta_allowed_on_closed_position(
    auth_client: AsyncClient,
) -> None:
    _, _, leap, pos = await _seed_pmcc_fixtures(auth_client)
    await auth_client.post(
        f"/api/positions/{pos['id']}/pmcc-meta",
        json={"leap_instrument_id": leap["id"]},
    )
    # Close the position
    await auth_client.patch(
        f"/api/positions/{pos['id']}",
        json={"status": "closed", "closed_at": "2026-08-01T20:00:00Z"},
    )
    resp = await auth_client.delete(f"/api/positions/{pos['id']}/pmcc-meta")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_DUMMY_UUID = "00000000-0000-0000-0000-000000000000"

_AUTH_CASES = [
    ("POST", "/api/positions/{pid}/wheel-meta", {"funding_source": "cash"}),
    ("GET", "/api/positions/{pid}/wheel-meta", None),
    ("PATCH", "/api/positions/{pid}/wheel-meta", {"funding_source": "margin"}),
    ("DELETE", "/api/positions/{pid}/wheel-meta", None),
    ("POST", "/api/positions/{pid}/pmcc-meta", {"leap_instrument_id": _DUMMY_UUID}),
    ("GET", "/api/positions/{pid}/pmcc-meta", None),
    ("PATCH", "/api/positions/{pid}/pmcc-meta", {"leap_instrument_id": _DUMMY_UUID}),
    ("DELETE", "/api/positions/{pid}/pmcc-meta", None),
]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    _AUTH_CASES,
    ids=[f"{m}-{p.split('/')[-1]}" for m, p, _ in _AUTH_CASES],
)
async def test_requires_auth(
    client: AsyncClient, method: str, path: str, body: dict | None
) -> None:
    pid = "00000000-0000-0000-0000-000000000000"
    resp = await client.request(method, path.format(pid=pid), json=body)
    assert resp.status_code == 401
