"""End-to-end tests for the StrategyConfig CRUD vertical slice (P7)."""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

VALID_BODY = {
    "strategy_type": "wheel",
    "max_exposure": "50000",
    "exposure_currency": "USD",
    "notes": "Bull market only",
}


async def _create(client: AsyncClient, **overrides: object) -> dict[str, object]:
    body = {**VALID_BODY, **overrides}
    response = await client.post("/api/strategy-configs", json=body)
    assert response.status_code == 201, response.text
    data: dict[str, object] = response.json()
    return data


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_create_strategy_config_201(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/api/strategy-configs", json=VALID_BODY)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["strategy_type"] == "wheel"
    assert Decimal(data["max_exposure"]) == Decimal("50000")
    assert data["exposure_currency"] == "USD"
    assert data["notes"] == "Bull market only"
    assert data["updated_at"] is not None
    uuid.UUID(data["id"])
    uuid.UUID(data["user_id"])


async def test_create_returns_200_when_existing(auth_client: AsyncClient) -> None:
    first = await _create(auth_client)
    # Second POST with same strategy_type → 200, same id, original values preserved.
    response = await auth_client.post(
        "/api/strategy-configs",
        json={
            "strategy_type": "wheel",
            "max_exposure": "99999",
            "exposure_currency": "EUR",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == first["id"]
    assert Decimal(data["max_exposure"]) == Decimal("50000")
    assert data["exposure_currency"] == "USD"


async def test_list_returns_empty(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/strategy-configs")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_after_create(auth_client: AsyncClient) -> None:
    await _create(auth_client, strategy_type="wheel")
    await _create(auth_client, strategy_type="iron_condor", max_exposure="3000")
    response = await auth_client.get("/api/strategy-configs")
    assert response.status_code == 200
    types = [cfg["strategy_type"] for cfg in response.json()]
    # Ordered by strategy_type (iron_condor < wheel alphabetically).
    assert types == ["iron_condor", "wheel"]


async def test_get_by_strategy_type_200(auth_client: AsyncClient) -> None:
    await _create(auth_client)
    response = await auth_client.get("/api/strategy-configs/wheel")
    assert response.status_code == 200
    assert response.json()["strategy_type"] == "wheel"


async def test_patch_updates_only_provided_fields(auth_client: AsyncClient) -> None:
    await _create(auth_client)
    response = await auth_client.patch(
        "/api/strategy-configs/wheel", json={"notes": "Updated notes"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == "Updated notes"
    # max_exposure and exposure_currency unchanged.
    assert Decimal(data["max_exposure"]) == Decimal("50000")
    assert data["exposure_currency"] == "USD"


async def test_patch_clears_max_exposure_with_explicit_null(auth_client: AsyncClient) -> None:
    await _create(auth_client)
    response = await auth_client.patch(
        "/api/strategy-configs/wheel", json={"max_exposure": None}
    )
    assert response.status_code == 200
    assert response.json()["max_exposure"] is None


async def test_delete_strategy_config_204(auth_client: AsyncClient) -> None:
    await _create(auth_client)
    response = await auth_client.delete("/api/strategy-configs/wheel")
    assert response.status_code == 204

    # Row is gone — subsequent GET returns 404.
    get_response = await auth_client.get("/api/strategy-configs/wheel")
    assert get_response.status_code == 404


# ---------------------------------------------------------------------------
# Auth — every endpoint demands a valid session cookie
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/strategy-configs"),
        ("GET", "/api/strategy-configs"),
        ("GET", "/api/strategy-configs/wheel"),
        ("PATCH", "/api/strategy-configs/wheel"),
        ("DELETE", "/api/strategy-configs/wheel"),
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


async def test_create_rejects_unknown_strategy_type_422(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/strategy-configs",
        json={**VALID_BODY, "strategy_type": "cowabunga"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("bad", ["usd", "US", "USDD", "U$D", "123"])
async def test_create_rejects_bad_currency_422(auth_client: AsyncClient, bad: str) -> None:
    response = await auth_client.post(
        "/api/strategy-configs",
        json={**VALID_BODY, "exposure_currency": bad},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("bad", ["-1", "0"])
async def test_create_rejects_nonpositive_max_exposure_422(
    auth_client: AsyncClient, bad: str
) -> None:
    response = await auth_client.post(
        "/api/strategy-configs",
        json={**VALID_BODY, "max_exposure": bad},
    )
    assert response.status_code == 422


async def test_create_accepts_null_max_exposure(auth_client: AsyncClient) -> None:
    # Omit max_exposure entirely.
    response = await auth_client.post(
        "/api/strategy-configs",
        json={"strategy_type": "wheel", "exposure_currency": "USD"},
    )
    assert response.status_code == 201
    assert response.json()["max_exposure"] is None


async def test_create_accepts_explicit_null_max_exposure(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/strategy-configs",
        json={"strategy_type": "wheel", "max_exposure": None, "exposure_currency": "USD"},
    )
    assert response.status_code == 201
    assert response.json()["max_exposure"] is None


async def test_create_rejects_unknown_field_422(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/strategy-configs", json={**VALID_BODY, "totally_unknown": "x"}
    )
    assert response.status_code == 422


async def test_patch_rejects_strategy_type_in_body_422(auth_client: AsyncClient) -> None:
    await _create(auth_client)
    response = await auth_client.patch(
        "/api/strategy-configs/wheel",
        json={"strategy_type": "iron_condor"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 404s
# ---------------------------------------------------------------------------


async def test_get_unknown_strategy_type_404(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/strategy-configs/pmcc")
    assert response.status_code == 404


async def test_patch_unknown_strategy_type_404(auth_client: AsyncClient) -> None:
    response = await auth_client.patch(
        "/api/strategy-configs/pmcc", json={"notes": "test"}
    )
    assert response.status_code == 404


async def test_delete_unknown_strategy_type_404(auth_client: AsyncClient) -> None:
    response = await auth_client.delete("/api/strategy-configs/pmcc")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# updated_at semantics
# ---------------------------------------------------------------------------


async def test_patch_advances_updated_at(auth_client: AsyncClient) -> None:
    created = await _create(auth_client)
    original_updated_at = created["updated_at"]

    # Small sleep to ensure updated_at ticks forward (SQLite second-precision).
    import asyncio

    await asyncio.sleep(1.1)

    response = await auth_client.patch(
        "/api/strategy-configs/wheel", json={"notes": "tick"}
    )
    assert response.status_code == 200
    assert response.json()["updated_at"] > original_updated_at


# ---------------------------------------------------------------------------
# Authorization — cross-user isolation
# ---------------------------------------------------------------------------


async def test_list_returns_only_current_user_rows(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    await _create(auth_client)

    bob_list = (await second_user_client.get("/api/strategy-configs")).json()
    assert bob_list == []


async def test_same_strategy_isolated_across_users(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    # Both users create iron_condor config.
    alice = await _create(auth_client, strategy_type="iron_condor", max_exposure="3000")
    bob = await _create(
        second_user_client, strategy_type="iron_condor", max_exposure="9999"
    )

    # Distinct rows.
    assert alice["id"] != bob["id"]

    # Each user only sees their own.
    alice_list = (await auth_client.get("/api/strategy-configs")).json()
    bob_list = (await second_user_client.get("/api/strategy-configs")).json()
    assert len(alice_list) == 1
    assert len(bob_list) == 1
    assert alice_list[0]["id"] == alice["id"]
    assert bob_list[0]["id"] == bob["id"]


async def test_get_other_users_config_returns_404(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    await _create(auth_client, strategy_type="wheel")
    response = await second_user_client.get("/api/strategy-configs/wheel")
    assert response.status_code == 404


async def test_patch_other_users_config_returns_404(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    await _create(auth_client, strategy_type="wheel")
    response = await second_user_client.patch(
        "/api/strategy-configs/wheel", json={"notes": "hax"}
    )
    assert response.status_code == 404


async def test_delete_other_users_config_returns_404(
    auth_client: AsyncClient, second_user_client: AsyncClient
) -> None:
    await _create(auth_client, strategy_type="wheel")
    response = await second_user_client.delete("/api/strategy-configs/wheel")
    assert response.status_code == 404

    # Alice's config still exists.
    refetched = await auth_client.get("/api/strategy-configs/wheel")
    assert refetched.status_code == 200


# ---------------------------------------------------------------------------
# Concurrency — get-or-create under race
# ---------------------------------------------------------------------------


async def test_concurrent_same_key_post_get_or_create(auth_client: AsyncClient) -> None:
    """Concurrent POSTs with same (user, strategy_type) must not raise.

    All must return 200 or 201, and every response must reference the same
    row id. With aiosqlite only ~2-3 requests truly race, but the test
    validates that the IntegrityError catch + re-read path works end-to-end.
    """
    import asyncio

    payload = {"strategy_type": "wheel", "max_exposure": "1000", "exposure_currency": "USD"}
    tasks = [auth_client.post("/api/strategy-configs", json=payload) for _ in range(5)]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # No unhandled exceptions — the IntegrityError + rollback path must
    # not leak MissingGreenlet or any other error.
    exceptions = [r for r in responses if isinstance(r, BaseException)]
    assert exceptions == [], (
        f"Concurrent POSTs raised {len(exceptions)} unhandled exception(s): "
        f"{exceptions[0]!r}"
    )

    http_responses = list(responses)
    for r in http_responses:
        assert r.status_code in (200, 201), f"Unexpected status {r.status_code}: {r.text}"

    # Exactly one 201 (the creator); rest 200.
    assert [r.status_code for r in http_responses].count(201) == 1

    # All responses point to the same row.
    ids = {r.json()["id"] for r in http_responses}
    assert len(ids) == 1
