"""Protocol boundary behavior: failures stay on MCP/API paths, never the SPA."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from trading_journal.config import get_settings
from trading_journal.main import create_app


@pytest.fixture
def mcp_spa_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<title>SPA</title>")
    monkeypatch.setenv("STATIC_DIR", str(dist))
    get_settings.cache_clear()
    try:
        yield create_app()
    finally:
        get_settings.cache_clear()


async def test_mcp_boundary_rejects_missing_bearer_and_path_suffix(
    mcp_spa_app: FastAPI,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=mcp_spa_app), base_url="http://localhost"
    ) as client:
        missing = await client.post("/api/mcp", json={"jsonrpc": "2.0"})
        suffix = await client.get("/api/mcp/anything")
        deep_link = await client.get("/positions/123")
    assert missing.status_code == 401
    assert "SPA" not in missing.text
    assert suffix.status_code == 404
    assert "SPA" not in suffix.text
    assert deep_link.status_code == 200
    assert "SPA" in deep_link.text


async def test_mcp_boundary_rejects_disallowed_host_and_origin(mcp_spa_app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=mcp_spa_app), base_url="http://localhost"
    ) as client:
        bad_host = await client.post(
            "/api/mcp",
            json={},
            headers={"Authorization": "Bearer invalid", "Host": "evil.example"},
        )
        bad_origin = await client.post(
            "/api/mcp",
            json={},
            headers={"Authorization": "Bearer invalid", "Origin": "https://evil.example"},
        )
    assert bad_host.status_code == 421
    assert bad_origin.status_code == 403
