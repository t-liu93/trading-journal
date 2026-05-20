"""End-to-end tests for the Account CRUD vertical slice."""

import uuid

import pytest
from httpx import AsyncClient

VALID_BODY = {
    "name": "IBKR Margin",
    "broker": "IBKR",
    "account_type": "margin",
    "base_currency": "USD",
    "notes": "tracer-bullet account",
}


async def _create(client: AsyncClient, **overrides: object) -> dict[str, object]:
    body = {**VALID_BODY, **overrides}
    response = await client.post("/api/accounts", json=body)
    assert response.status_code == 201, response.text
    data: dict[str, object] = response.json()
    return data


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_create_account(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/api/accounts", json=VALID_BODY)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == VALID_BODY["name"]
    assert data["broker"] == VALID_BODY["broker"]
    assert data["account_type"] == "margin"
    assert data["base_currency"] == "USD"
    assert data["notes"] == VALID_BODY["notes"]
    assert data["archived_at"] is None
    assert data["created_at"] is not None
    uuid.UUID(data["id"])
    uuid.UUID(data["user_id"])  # derived from auth, not from body


async def test_list_accounts_empty(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/accounts")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_accounts_after_create(auth_client: AsyncClient) -> None:
    await _create(auth_client, name="A")
    await _create(auth_client, name="B")
    response = await auth_client.get("/api/accounts")
    assert response.status_code == 200
    # Order across rapid inserts isn't guaranteed (SQLite created_at is
    # second-precision); presence is what matters here.
    names = {acc["name"] for acc in response.json()}
    assert names == {"A", "B"}


async def test_get_account_by_id(auth_client: AsyncClient) -> None:
    created = await _create(auth_client)
    response = await auth_client.get(f"/api/accounts/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_update_account_partial(auth_client: AsyncClient) -> None:
    created = await _create(auth_client)
    response = await auth_client.patch(f"/api/accounts/{created['id']}", json={"notes": "edited"})
    assert response.status_code == 200
    body = response.json()
    assert body["notes"] == "edited"
    # untouched fields preserved
    assert body["name"] == created["name"]
    assert body["broker"] == created["broker"]


async def test_soft_delete_excludes_from_default_list(auth_client: AsyncClient) -> None:
    created = await _create(auth_client)
    delete = await auth_client.delete(f"/api/accounts/{created['id']}")
    assert delete.status_code == 204

    listed = await auth_client.get("/api/accounts")
    assert listed.status_code == 200
    assert listed.json() == []


async def test_include_archived_param(auth_client: AsyncClient) -> None:
    created = await _create(auth_client)
    await auth_client.delete(f"/api/accounts/{created['id']}")

    listed = await auth_client.get("/api/accounts", params={"include_archived": "true"})
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["id"] == created["id"]
    assert body[0]["archived_at"] is not None


# ---------------------------------------------------------------------------
# Auth — every endpoint demands a valid session cookie
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/accounts"),
        ("GET", "/api/accounts"),
        ("GET", "/api/accounts/00000000-0000-0000-0000-000000000000"),
        ("PATCH", "/api/accounts/00000000-0000-0000-0000-000000000000"),
        ("DELETE", "/api/accounts/00000000-0000-0000-0000-000000000000"),
    ],
)
async def test_requires_auth(client: AsyncClient, method: str, path: str) -> None:
    response = await client.request(
        method, path, json=VALID_BODY if method in {"POST", "PATCH"} else None
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


async def test_create_rejects_invalid_account_type(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/accounts", json={**VALID_BODY, "account_type": "checking"}
    )
    assert response.status_code == 422


async def test_create_rejects_missing_required_fields(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/accounts",
        json={"name": "X"},  # missing broker, account_type, base_currency
    )
    assert response.status_code == 422


@pytest.mark.parametrize("bad", ["usd", "US", "USDD", "U$D", "123"])
async def test_create_rejects_invalid_currency_code(auth_client: AsyncClient, bad: str) -> None:
    response = await auth_client.post("/api/accounts", json={**VALID_BODY, "base_currency": bad})
    assert response.status_code == 422


async def test_create_rejects_unknown_field(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/api/accounts", json={**VALID_BODY, "totally_unknown": "x"})
    assert response.status_code == 422


async def test_update_rejects_unknown_field(auth_client: AsyncClient) -> None:
    created = await _create(auth_client)
    response = await auth_client.patch(
        f"/api/accounts/{created['id']}", json={"totally_unknown": "x"}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Authorization — cross-user isolation
# ---------------------------------------------------------------------------


async def test_list_only_returns_own_accounts(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    await _create(auth_client, name="alice-acct")
    await _create(second_user_client, name="bob-acct")

    alice_list = (await auth_client.get("/api/accounts")).json()
    bob_list = (await second_user_client.get("/api/accounts")).json()

    assert {a["name"] for a in alice_list} == {"alice-acct"}
    assert {a["name"] for a in bob_list} == {"bob-acct"}


async def test_get_other_users_account_returns_404(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    alice_acct = await _create(auth_client)
    response = await second_user_client.get(f"/api/accounts/{alice_acct['id']}")
    assert response.status_code == 404


async def test_update_other_users_account_returns_404(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    alice_acct = await _create(auth_client)
    response = await second_user_client.patch(
        f"/api/accounts/{alice_acct['id']}", json={"notes": "hax"}
    )
    assert response.status_code == 404

    # Verify Alice's row was not touched.
    refetched = (await auth_client.get(f"/api/accounts/{alice_acct['id']}")).json()
    assert refetched["notes"] == alice_acct["notes"]


async def test_delete_other_users_account_returns_404(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    alice_acct = await _create(auth_client)
    response = await second_user_client.delete(f"/api/accounts/{alice_acct['id']}")
    assert response.status_code == 404

    # Alice's account is still visible to her.
    refetched = await auth_client.get(f"/api/accounts/{alice_acct['id']}")
    assert refetched.status_code == 200
    assert refetched.json()["archived_at"] is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_get_nonexistent_returns_404(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/accounts/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_get_archived_by_default_returns_404(auth_client: AsyncClient) -> None:
    created = await _create(auth_client)
    await auth_client.delete(f"/api/accounts/{created['id']}")
    response = await auth_client.get(f"/api/accounts/{created['id']}")
    assert response.status_code == 404


async def test_delete_already_archived_returns_404(auth_client: AsyncClient) -> None:
    created = await _create(auth_client)
    first = await auth_client.delete(f"/api/accounts/{created['id']}")
    assert first.status_code == 204
    second = await auth_client.delete(f"/api/accounts/{created['id']}")
    assert second.status_code == 404


async def test_user_id_in_body_is_ignored(auth_client: AsyncClient) -> None:
    """Schema forbids user_id; even if a malicious client sends it, 422."""
    response = await auth_client.post(
        "/api/accounts",
        json={**VALID_BODY, "user_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422
