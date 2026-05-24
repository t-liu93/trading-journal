"""End-to-end tests for the Instrument CRUD (P6.1: stock, P6.2: option, P6.3: forex).

Instruments are **global** — no per-user isolation. The key extra test
is cross-user sharing (``test_instruments_are_global``).
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from trading_journal.main import app

STOCK_BODY = {
    "kind": "stock",
    "symbol": "AAPL",
    "exchange": "NASDAQ",
    "currency": "USD",
}

OPTION_BODY = {
    "kind": "option",
    "underlying_symbol": "AAPL",
    "underlying_exchange": "NASDAQ",
    "currency": "USD",
    "opt_type": "put",
    "strike": "220",
    "expiry": "2026-05-28",
}

FOREX_BODY = {
    "kind": "forex",
    "symbol": "EURUSD",
    "base_currency": "EUR",
    "quote_currency": "USD",
    "pip_size": "0.0001",
}


async def _create_stock(client: AsyncClient, **overrides: object) -> dict[str, object]:
    body = {**STOCK_BODY, **overrides}
    response = await client.post("/api/instruments", json=body)
    assert response.status_code == 201, response.text
    data: dict[str, object] = response.json()
    return data


async def _create_option(client: AsyncClient, **overrides: object) -> dict[str, object]:
    body = {**OPTION_BODY, **overrides}
    response = await client.post("/api/instruments", json=body)
    assert response.status_code in (200, 201), response.text
    data: dict[str, object] = response.json()
    return data


async def _create_forex(client: AsyncClient, **overrides: object) -> dict[str, object]:
    body = {**FOREX_BODY, **overrides}
    response = await client.post("/api/instruments", json=body)
    assert response.status_code in (200, 201), response.text
    data: dict[str, object] = response.json()
    return data


# ---------------------------------------------------------------------------
# P6.1 — Stock happy paths
# ---------------------------------------------------------------------------


async def test_create_stock_201(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/api/instruments", json=STOCK_BODY)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["kind"] == "stock"
    assert data["symbol"] == "AAPL"
    assert data["exchange"] == "NASDAQ"
    assert data["currency"] == "USD"
    assert data["created_at"] is not None
    uuid.UUID(data["id"])


async def test_create_stock_normalizes_symbol(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={"kind": "stock", "symbol": " aapl ", "currency": "USD"},
    )
    assert response.status_code == 201
    assert response.json()["symbol"] == "AAPL"


async def test_create_stock_idempotent_returns_200_same_id(
    auth_client: AsyncClient,
) -> None:
    first = await _create_stock(auth_client)
    # Same payload again
    response = await auth_client.post("/api/instruments", json=STOCK_BODY)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == first["id"]


async def test_create_stock_distinct_exchange_creates_new_row(
    auth_client: AsyncClient,
) -> None:
    first = await _create_stock(auth_client)
    # Same symbol+currency, different exchange
    response = await auth_client.post(
        "/api/instruments",
        json={"kind": "stock", "symbol": "AAPL", "exchange": "NYSE", "currency": "USD"},
    )
    assert response.status_code == 201
    assert response.json()["id"] != first["id"]


async def test_create_stock_no_exchange_vs_null_exchange(auth_client: AsyncClient) -> None:
    """Two creates with no exchange are the same instrument."""
    first = await auth_client.post(
        "/api/instruments",
        json={"kind": "stock", "symbol": "MSFT", "currency": "USD"},
    )
    assert first.status_code == 201
    second = await auth_client.post(
        "/api/instruments",
        json={"kind": "stock", "symbol": "MSFT", "currency": "USD"},
    )
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


# ---------------------------------------------------------------------------
# P6.1 — List / search
# ---------------------------------------------------------------------------


async def test_list_instruments_empty(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/instruments")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_instruments_ordered_by_symbol(auth_client: AsyncClient) -> None:
    await _create_stock(auth_client, symbol="MSFT", currency="USD")
    await _create_stock(auth_client, symbol="AAPL", currency="USD")
    await _create_stock(auth_client, symbol="GOOG", currency="USD")
    response = await auth_client.get("/api/instruments")
    assert response.status_code == 200
    symbols = [inst["symbol"] for inst in response.json()]
    assert symbols == sorted(symbols)


async def test_list_filters_by_kind(auth_client: AsyncClient) -> None:
    await _create_stock(auth_client, symbol="AAPL", currency="USD")
    response = await auth_client.get("/api/instruments", params={"kind": "stock"})
    assert response.status_code == 200
    assert len(response.json()) >= 1

    response = await auth_client.get("/api/instruments", params={"kind": "forex"})
    assert response.status_code == 200
    assert response.json() == []


async def test_list_filters_by_prefix_q(auth_client: AsyncClient) -> None:
    await _create_stock(auth_client, symbol="AAPL", currency="USD")
    await _create_stock(auth_client, symbol="MSFT", currency="USD")

    response = await auth_client.get("/api/instruments", params={"q": "aa"})
    assert response.status_code == 200
    symbols = {inst["symbol"] for inst in response.json()}
    assert symbols == {"AAPL"}

    response = await auth_client.get("/api/instruments", params={"q": "MS"})
    assert response.status_code == 200
    symbols = {inst["symbol"] for inst in response.json()}
    assert symbols == {"MSFT"}


# ---------------------------------------------------------------------------
# P6.1 — Get by ID
# ---------------------------------------------------------------------------


async def test_get_by_id_200(auth_client: AsyncClient) -> None:
    created = await _create_stock(auth_client)
    response = await auth_client.get(f"/api/instruments/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_unknown_404(auth_client: AsyncClient) -> None:
    response = await auth_client.get(
        "/api/instruments/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# P6.1 — Input validation
# ---------------------------------------------------------------------------


async def test_create_rejects_bad_currency_422(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={"kind": "stock", "symbol": "X", "currency": "usd"},
    )
    assert response.status_code == 422


async def test_create_rejects_empty_symbol_422(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={"kind": "stock", "symbol": "", "currency": "USD"},
    )
    assert response.status_code == 422


async def test_create_rejects_whitespace_only_symbol_422(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={"kind": "stock", "symbol": "   ", "currency": "USD"},
    )
    assert response.status_code == 422


async def test_create_rejects_unknown_field_422(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={**STOCK_BODY, "totally_unknown": "x"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# P6.1 — Auth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/instruments"),
        ("GET", "/api/instruments"),
        ("GET", "/api/instruments/00000000-0000-0000-0000-000000000000"),
    ],
)
async def test_requires_auth(client: AsyncClient, method: str, path: str) -> None:
    response = await client.request(
        method, path, json=STOCK_BODY if method == "POST" else None
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# P6.1 — Global sharing — instruments are visible across users
# ---------------------------------------------------------------------------


async def test_instruments_are_global(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    # User A creates AAPL
    aapl = await _create_stock(auth_client)

    # User B sees it in list
    bob_list = (await second_user_client.get("/api/instruments")).json()
    assert any(inst["id"] == aapl["id"] for inst in bob_list)

    # User B's identical POST returns 200 with A's row id
    response = await second_user_client.post("/api/instruments", json=STOCK_BODY)
    assert response.status_code == 200
    assert response.json()["id"] == aapl["id"]


# ---------------------------------------------------------------------------
# P6.1 — OpenAPI schema
# ---------------------------------------------------------------------------


def test_post_instrument_openapi_declares_200_and_201() -> None:
    """The POST endpoint must declare both 200 (existing) and 201 (created)."""
    sync_client = TestClient(app)
    spec = sync_client.get("/openapi.json").json()
    post_responses = spec["paths"]["/api/instruments"]["post"]["responses"]
    assert "200" in post_responses, "POST /instruments should declare 200"
    assert "201" in post_responses, "POST /instruments should declare 201"


# ===========================================================================
# P6.2 — Option create + nested read
# ===========================================================================


async def test_create_option_201_and_nested_read(auth_client: AsyncClient) -> None:
    data = await _create_option(auth_client)
    assert data["kind"] == "option"
    assert data["symbol"] == "AAPL"
    assert data["currency"] == "USD"
    assert data["option"] is not None
    opt = data["option"]
    assert opt["opt_type"] == "put"
    assert opt["strike"] == "220.000000"
    assert opt["expiry"] == "2026-05-28"
    assert opt["multiplier"] == 100
    assert opt["style"] == "american"


async def test_create_option_autocreates_underlying_stock(
    auth_client: AsyncClient,
) -> None:
    """Creating an option should auto-create the underlying stock instrument."""
    await _create_option(auth_client)
    stocks = (await auth_client.get("/api/instruments", params={"kind": "stock"})).json()
    assert any(
        s["symbol"] == "AAPL" and s["currency"] == "USD" for s in stocks
    ), "Underlying stock should have been auto-created"


async def test_create_option_reuses_existing_underlying(
    auth_client: AsyncClient,
) -> None:
    """Pre-create the AAPL stock; option creation should not duplicate it."""
    stock = await _create_stock(auth_client)
    await _create_option(auth_client)
    # Only one stock with symbol AAPL should exist
    stocks = (await auth_client.get("/api/instruments", params={"kind": "stock"})).json()
    aapl_stocks = [s for s in stocks if s["symbol"] == "AAPL"]
    assert len(aapl_stocks) == 1
    assert aapl_stocks[0]["id"] == stock["id"]


async def test_create_option_idempotent_returns_200(
    auth_client: AsyncClient,
) -> None:
    first = await _create_option(auth_client)
    assert first["id"]

    response = await auth_client.post("/api/instruments", json=OPTION_BODY)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == first["id"]


async def test_option_currency_matches_underlying(
    auth_client: AsyncClient,
) -> None:
    """Option instrument currency must equal its underlying stock currency."""
    data = await _create_option(auth_client)
    option_currency = data["currency"]

    # Find the auto-created underlying
    stocks = (await auth_client.get("/api/instruments", params={"kind": "stock"})).json()
    underlying = next(s for s in stocks if s["symbol"] == "AAPL")
    assert underlying["currency"] == option_currency


async def test_create_option_rejects_nonpositive_strike_422(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={**OPTION_BODY, "strike": "0"},
    )
    assert response.status_code == 422


async def test_create_option_rejects_bad_opt_type_422(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={**OPTION_BODY, "opt_type": "invalid"},
    )
    assert response.status_code == 422


async def test_create_option_rejects_unknown_field_422(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={**OPTION_BODY, "totally_unknown": "x"},
    )
    assert response.status_code == 422


async def test_option_get_by_id_has_nested_block(
    auth_client: AsyncClient,
) -> None:
    created = await _create_option(auth_client)
    response = await auth_client.get(f"/api/instruments/{created['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["option"] is not None
    assert data["option"]["opt_type"] == "put"


async def test_option_normalizes_underlying_symbol(
    auth_client: AsyncClient,
) -> None:
    data = await _create_option(auth_client, underlying_symbol=" aapl ")
    assert data["symbol"] == "AAPL"


# ===========================================================================
# P6.3 — Forex create + nested read
# ===========================================================================


async def test_create_forex_201_currency_equals_quote(
    auth_client: AsyncClient,
) -> None:
    data = await _create_forex(auth_client)
    assert data["kind"] == "forex"
    assert data["symbol"] == "EURUSD"
    assert data["currency"] == "USD", "instrument.currency must equal quote_currency"
    assert data["forex"] is not None
    forex = data["forex"]
    assert forex["base_currency"] == "EUR"
    assert forex["quote_currency"] == "USD"
    assert forex["pip_size"] == "0.00010000"
    assert forex["contract_size"] is None


async def test_create_forex_idempotent_returns_200(
    auth_client: AsyncClient,
) -> None:
    first = await _create_forex(auth_client)
    response = await auth_client.post("/api/instruments", json=FOREX_BODY)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == first["id"]


async def test_create_forex_rejects_bad_quote_currency_422(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={**FOREX_BODY, "quote_currency": "usd"},
    )
    assert response.status_code == 422


async def test_forex_nested_read_has_pip_size(
    auth_client: AsyncClient,
) -> None:
    data = await _create_forex(auth_client, pip_size="0.01")
    assert data["forex"] is not None
    assert data["forex"]["pip_size"] == "0.01000000"


async def test_forex_get_by_id_has_nested_block(
    auth_client: AsyncClient,
) -> None:
    created = await _create_forex(auth_client)
    response = await auth_client.get(f"/api/instruments/{created['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["forex"] is not None
    assert data["forex"]["base_currency"] == "EUR"


async def test_forex_with_contract_size(
    auth_client: AsyncClient,
) -> None:
    data = await _create_forex(auth_client, contract_size="100000")
    assert data["forex"]["contract_size"] == "100000.0000"


async def test_create_forex_rejects_bad_base_currency_422(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={**FOREX_BODY, "base_currency": "123"},
    )
    assert response.status_code == 422


async def test_create_forex_rejects_nonpositive_pip_size_422(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={**FOREX_BODY, "pip_size": "0"},
    )
    assert response.status_code == 422


async def test_create_forex_normalizes_symbol(
    auth_client: AsyncClient,
) -> None:
    data = await _create_forex(auth_client, symbol=" eurusd ")
    assert data["symbol"] == "EURUSD"


async def test_forex_has_no_exchange(
    auth_client: AsyncClient,
) -> None:
    data = await _create_forex(auth_client)
    assert data["exchange"] is None


async def test_create_forex_rejects_unknown_field_422(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post(
        "/api/instruments",
        json={**FOREX_BODY, "totally_unknown": "x"},
    )
    assert response.status_code == 422


# ===========================================================================
# Cross-kind — list filtering and search work across all kinds
# ===========================================================================


async def test_list_filters_option_by_kind(auth_client: AsyncClient) -> None:
    await _create_option(auth_client)
    response = await auth_client.get("/api/instruments", params={"kind": "option"})
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert all(i["kind"] == "option" for i in items)


async def test_list_filters_forex_by_kind(auth_client: AsyncClient) -> None:
    await _create_forex(auth_client)
    response = await auth_client.get("/api/instruments", params={"kind": "forex"})
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert all(i["kind"] == "forex" for i in items)


async def test_list_prefix_search_includes_option_and_stock(
    auth_client: AsyncClient,
) -> None:
    await _create_stock(auth_client)
    await _create_option(auth_client)
    response = await auth_client.get("/api/instruments", params={"q": "AAPL"})
    assert response.status_code == 200
    items = response.json()
    # Should include both the stock AAPL and the option (symbol = AAPL)
    assert len(items) >= 2


async def test_instruments_are_global_for_options(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    option = await _create_option(auth_client)
    bob_list = (await second_user_client.get("/api/instruments")).json()
    assert any(inst["id"] == option["id"] for inst in bob_list)
