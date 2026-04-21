from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


@lru_cache
def _get_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def get_engine(settings: Settings | None = None) -> Engine:
    app_settings = settings or get_settings()
    return _get_engine(app_settings.database_url)


@lru_cache
def _get_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_get_engine(database_url),
    )


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    app_settings = settings or get_settings()
    return _get_session_factory(app_settings.database_url)


def get_db_session(settings: Settings | None = None) -> Generator[Session, None, None]:
    session_factory = get_session_factory(settings)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
