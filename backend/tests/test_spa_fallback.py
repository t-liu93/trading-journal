"""SPA static-serving fallback (production single-container mode).

In dev STATIC_DIR is unset, so create_app() skips the SPA mount entirely
(covered by test_health.test_unknown_route_404). Here we point STATIC_DIR at a
throwaway dist/ and assert the catch-all behaviour from
v1-implementation-plan-f6 §3.2: client-side routes get index.html, real files
are served, the API router still wins, and an unknown /api/* path is a real 404
(not the SPA shell).
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from trading_journal.config import get_settings
from trading_journal.main import create_app


@pytest.fixture
def spa_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>SPA shell</title>")
    (dist / "assets" / "app.js").write_text("console.log('hi')")
    monkeypatch.setenv("STATIC_DIR", str(dist))
    get_settings.cache_clear()
    try:
        yield create_app()
    finally:
        get_settings.cache_clear()


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_client_route_returns_index(spa_app: FastAPI) -> None:
    async with _client(spa_app) as client:
        response = await client.get("/positions/42")
    assert response.status_code == 200
    assert "SPA shell" in response.text


async def test_real_asset_is_served(spa_app: FastAPI) -> None:
    async with _client(spa_app) as client:
        response = await client.get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


async def test_unknown_api_path_is_404_not_shell(spa_app: FastAPI) -> None:
    async with _client(spa_app) as client:
        response = await client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert "SPA shell" not in response.text


async def test_real_api_route_still_wins(spa_app: FastAPI) -> None:
    async with _client(spa_app) as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
