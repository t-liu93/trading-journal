"""``UserManager`` and the DI hooks FastAPI Users needs to find it.

The manager is the single place that:
  - hashes passwords on register (delegated to BaseUserManager)
  - validates password strength (we enforce ``min_password_length``)
  - emits side-effects after register / login (logging + ``last_login_at``)
"""

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi_users import BaseUserManager, InvalidPasswordException, UUIDIDMixin, schemas
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.secret import get_cookie_secret
from trading_journal.config import get_settings
from trading_journal.db import get_session
from trading_journal.models.user import User

logger = logging.getLogger(__name__)


async def get_user_db(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AsyncIterator[SQLAlchemyUserDatabase[User, uuid.UUID]]:
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """App-specific user manager. Cookie secret doubles as the token signing key."""

    def __init__(self, user_db: SQLAlchemyUserDatabase[User, uuid.UUID]) -> None:
        super().__init__(user_db)
        # The cookie secret is persisted in the DB (generated on first boot) and
        # loaded at startup — not an operator-supplied env var. It only signs the
        # reset-password / verify flows, which we don't expose yet, but the
        # attributes must exist on the class.
        secret = get_cookie_secret()
        self.reset_password_token_secret = secret
        self.verification_token_secret = secret
        self._min_password_length = get_settings().min_password_length

    async def validate_password(
        self,
        password: str,
        user: schemas.UC | User,
    ) -> None:
        if len(password) < self._min_password_length:
            raise InvalidPasswordException(
                reason=f"Password must be at least {self._min_password_length} characters."
            )

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        logger.info("user.registered id=%s email=%s", user.id, user.email)

    async def on_after_login(
        self,
        user: User,
        request: Request | None = None,
        response: Response | None = None,
    ) -> None:
        await self.user_db.update(user, {"last_login_at": datetime.now(UTC)})
        logger.info("user.login id=%s email=%s", user.id, user.email)


async def get_user_manager(
    user_db: Annotated[SQLAlchemyUserDatabase[User, uuid.UUID], Depends(get_user_db)],
) -> AsyncIterator[UserManager]:
    yield UserManager(user_db)
