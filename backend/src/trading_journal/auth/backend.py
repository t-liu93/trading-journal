"""Cookie transport + DB-backed access token strategy.

We persist sessions as rows in ``access_tokens`` (one row per login). The
cookie carries an opaque random token that maps to a row.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.users import get_user_manager
from trading_journal.config import get_settings
from trading_journal.db import get_session
from trading_journal.models.user import AccessToken, User


async def get_access_token_db(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncIterator[SQLAlchemyAccessTokenDatabase[AccessToken]]:
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


def get_database_strategy(
    access_token_db: Annotated[
        SQLAlchemyAccessTokenDatabase[AccessToken], Depends(get_access_token_db)
    ],
) -> DatabaseStrategy[User, uuid.UUID, AccessToken]:
    return DatabaseStrategy(
        access_token_db, lifetime_seconds=get_settings().session_lifetime_seconds
    )


def _build_cookie_transport() -> CookieTransport:
    settings = get_settings()
    return CookieTransport(
        cookie_name=settings.cookie_name,
        cookie_max_age=settings.session_lifetime_seconds,
        cookie_secure=settings.cookie_secure,
        cookie_httponly=True,
        cookie_samesite="lax",
    )


cookie_transport = _build_cookie_transport()

auth_backend: AuthenticationBackend[User, uuid.UUID] = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_database_strategy,
)


fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
