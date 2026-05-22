"""End-to-end tests for the Instrument CRUD (P6.1: stock only).

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


async def _create_stock(client: AsyncClient, **overrides: object) -> dict[str, object]:
    body = {**STOCK_BODY, **overrides}
    response = await client.post("/api/instruments", json=body)
    assert response.status_code == 201, response.text
    data: dict[str, object] = response.json()
    return data


# ---------------------------------------------------------------------------
# Happy paths
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
# List / search
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
# Get by ID
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
# Input validation
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
# Auth
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
# Global sharing — instruments are visible across users
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
# OpenAPI schema
# ---------------------------------------------------------------------------


def test_post_instrument_openapi_declares_200_and_201() -> None:
    """The POST endpoint must declare both 200 (existing) and 201 (created)."""
    sync_client = TestClient(app)
    spec = sync_client.get("/openapi.json").json()
    post_responses = spec["paths"]["/api/instruments"]["post"]["responses"]
    assert "200" in post_responses, "POST /instruments should declare 200"
    assert "201" in post_responses, "POST /instruments should declare 201"
