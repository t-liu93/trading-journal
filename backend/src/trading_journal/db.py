"""Async SQLAlchemy engine, session factory, and declarative Base.

Module-level state is intentionally lazy: the engine is built the first time a
session is requested. Tests substitute the dependency via
``app.dependency_overrides[get_session]`` rather than poking these globals.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from trading_journal.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base. All ORM models must subclass this."""


_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, future=True)
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_maker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an ``AsyncSession`` bound to the app engine."""
    async with get_session_maker()() as session:
        yield session
