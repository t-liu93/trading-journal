"""Shared pytest fixtures.

Per-test isolation via a fresh sqlite file under ``tmp_path``. Schema is built
from ``Base.metadata.create_all`` (the migration round-trip is exercised
separately in ``tests/test_migrations.py``), and the app's ``get_session``
dependency is overridden to bind every request inside the test to that DB.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from trading_journal import models  # noqa: F401  (populates Base.metadata)
from trading_journal.db import Base, get_session
from trading_journal.main import app

CREDENTIALS_DEFAULT = {"email": "alice@example.com", "password": "correct horse battery"}
CREDENTIALS_SECOND = {"email": "bob@example.com", "password": "another good passphrase"}


@pytest.fixture
async def db_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """Fresh per-test sqlite DB with the full schema pre-created."""
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session_maker(
    db_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def client(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """``AsyncClient`` bound to the app with ``get_session`` pointed at the test DB.

    The default ``follow_redirects=False`` matches real browser behaviour for
    POST/login and lets us assert on the actual status codes FastAPI Users
    returns rather than chasing redirects.
    """

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with db_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def credentials() -> dict[str, str]:
    return dict(CREDENTIALS_DEFAULT)


@pytest.fixture
def second_credentials() -> dict[str, str]:
    return dict(CREDENTIALS_SECOND)


@pytest.fixture
async def registered_user(client: AsyncClient, credentials: dict[str, str]) -> dict[str, str]:
    response = await client.post("/auth/register", json=credentials)
    assert response.status_code == 201, response.text
    return credentials


@pytest.fixture
async def auth_client(client: AsyncClient, registered_user: dict[str, str]) -> AsyncClient:
    """``client`` after a successful login. Subsequent calls carry the session cookie."""
    response = await client.post(
        "/auth/login",
        data={
            "username": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert response.status_code == 204, response.text
    return client
