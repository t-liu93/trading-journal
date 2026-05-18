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
async def _override_session(
    db_session_maker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    """Bind the app's ``get_session`` dependency to the per-test DB.

    Shared between ``client`` and ``second_user_client`` so both AsyncClient
    instances hit the same test database.
    """

    async def _provider() -> AsyncIterator[AsyncSession]:
        async with db_session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = _provider
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)


def _new_async_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def client(_override_session: None) -> AsyncIterator[AsyncClient]:
    """``AsyncClient`` bound to the app with ``get_session`` pointed at the test DB."""
    async with _new_async_client() as ac:
        yield ac


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


@pytest.fixture
async def second_user_client(
    _override_session: None,
    second_credentials: dict[str, str],
) -> AsyncIterator[AsyncClient]:
    """A second logged-in user. Independent cookie jar from ``client`` / ``auth_client``.

    Used to verify cross-user isolation: Bob must not see or modify Alice's data.
    """
    async with _new_async_client() as ac:
        register = await ac.post("/auth/register", json=second_credentials)
        assert register.status_code == 201, register.text
        login = await ac.post(
            "/auth/login",
            data={
                "username": second_credentials["email"],
                "password": second_credentials["password"],
            },
        )
        assert login.status_code == 204, login.text
        yield ac
