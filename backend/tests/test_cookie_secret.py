"""The persisted cookie secret: generate-once, then reuse on every boot."""

from collections.abc import Iterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import trading_journal.auth.secret as secret_mod
from trading_journal.auth.secret import COOKIE_SECRET_KEY, ensure_cookie_secret, get_cookie_secret
from trading_journal.models.app_config import AppConfig


@pytest.fixture
def _reset_secret_cache() -> Iterator[None]:
    """Clear the in-process secret cache around each test (it's module global)."""
    secret_mod._cookie_secret = None
    secret_mod._ephemeral_fallback = None
    yield
    secret_mod._cookie_secret = None
    secret_mod._ephemeral_fallback = None


async def _count_rows(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(AppConfig)) or 0


async def test_generates_and_persists_once(
    db_session_maker: async_sessionmaker[AsyncSession], _reset_secret_cache: None
) -> None:
    async with db_session_maker() as session:
        value = await ensure_cookie_secret(session)

    assert value
    async with db_session_maker() as session:
        row = await session.get(AppConfig, COOKIE_SECRET_KEY)
        assert row is not None
        assert row.value == value
        assert await _count_rows(session) == 1


async def test_reused_across_reboots(
    db_session_maker: async_sessionmaker[AsyncSession], _reset_secret_cache: None
) -> None:
    async with db_session_maker() as session:
        first = await ensure_cookie_secret(session)

    # Simulate a fresh process against the same DB: clear the cache, re-run.
    secret_mod._cookie_secret = None
    async with db_session_maker() as session:
        second = await ensure_cookie_secret(session)
        assert await _count_rows(session) == 1

    assert second == first


async def test_get_falls_back_when_uninitialised(_reset_secret_cache: None) -> None:
    """Without startup (e.g. in tests), reads return a stable ephemeral secret."""
    value = get_cookie_secret()
    assert value
    assert get_cookie_secret() == value  # stable within the process
