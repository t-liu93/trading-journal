"""Credential lifecycle, bearer isolation and ownership tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trading_journal.main import app
from trading_journal.models.mcp_token import McpToken
from trading_journal.models.user import User


@pytest.mark.parametrize("profile", ["read", "entry"])
async def test_issue_list_revoke_and_bearer_auth(
    auth_client: AsyncClient,
    db_session_maker: async_sessionmaker[AsyncSession],
    profile: str,
) -> None:
    response = await auth_client.post(
        "/api/mcp-tokens", json={"name": "Codex", "profile": profile}
    )
    assert response.status_code == 201, response.text
    issued = response.json()
    assert issued["token"].startswith("tj_mcp_")
    assert issued["profile"] == profile
    assert "token_digest" not in issued

    async with db_session_maker() as session:
        row = await session.get(McpToken, UUID(issued["id"]))
        assert row is not None
        assert issued["token"] not in row.token_digest
        assert row.token_digest != issued["token"]
        assert row.expires_at is not None
        assert row.expires_at.replace(tzinfo=UTC) > datetime.now(UTC)

    listed = await auth_client.get("/api/mcp-tokens")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "token" not in listed.json()[0]
    assert "token_digest" not in listed.json()[0]

    # The bearer credential cannot substitute for the cookie session used by management APIs.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bearer_only = await client.get(
            "/api/mcp-tokens", headers={"Authorization": f"Bearer {issued['token']}"}
        )
    assert bearer_only.status_code == 401

    from trading_journal.services.mcp_tokens import authenticate_token

    async with db_session_maker() as session:
        principal = await authenticate_token(session, issued["token"])
        assert str(principal.credential_id) == issued["id"]
        assert principal.profile == profile

    revoked = await auth_client.delete(f"/api/mcp-tokens/{issued['id']}")
    assert revoked.status_code == 204
    async with db_session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await authenticate_token(session, issued["token"])
        assert exc_info.value.status_code == 401


async def test_expiry_no_expiry_and_invalid_expiry(
    auth_client: AsyncClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    permanent = await auth_client.post(
        "/api/mcp-tokens", json={"name": "Permanent", "profile": "read", "expires_at": None}
    )
    assert permanent.status_code == 201, permanent.text
    assert permanent.json()["expires_at"] is None

    naive = await auth_client.post(
        "/api/mcp-tokens",
        json={"name": "Naive", "profile": "read", "expires_at": "2030-01-01T00:00:00"},
    )
    assert naive.status_code == 422
    past = await auth_client.post(
        "/api/mcp-tokens",
        json={"name": "Past", "profile": "read", "expires_at": "2020-01-01T00:00:00Z"},
    )
    assert past.status_code == 422

    async with db_session_maker() as session:
        row = await session.get(McpToken, UUID(permanent.json()["id"]))
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    from trading_journal.services.mcp_tokens import authenticate_token

    async with db_session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await authenticate_token(session, permanent.json()["token"])
        assert exc_info.value.status_code == 401


async def test_cross_user_revoke_is_404(
    auth_client: AsyncClient,
    second_user_client: AsyncClient,
) -> None:
    issued = await auth_client.post("/api/mcp-tokens", json={"name": "A", "profile": "entry"})
    assert issued.status_code == 201
    response = await second_user_client.delete(f"/api/mcp-tokens/{issued.json()['id']}")
    assert response.status_code == 404


async def test_disabled_user_token_fails(
    auth_client: AsyncClient,
    db_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    issued = await auth_client.post("/api/mcp-tokens", json={"name": "A", "profile": "read"})
    assert issued.status_code == 201
    async with db_session_maker() as session:
        user = (await session.execute(select(User))).scalar_one()
        user.is_active = False
        await session.commit()
    from trading_journal.services.mcp_tokens import authenticate_token

    async with db_session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await authenticate_token(session, issued.json()["token"])
        assert exc_info.value.status_code == 401
