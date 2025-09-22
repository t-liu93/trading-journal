from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware

import settings
from trading_journal import crud, security
from trading_journal.db import Database
from trading_journal.dto import UserCreate, UserRead
from trading_journal.models import Sessions

EXCEPT_PATHS = [
    f"{settings.settings.api_base}/status",
    f"{settings.settings.api_base}/register",
]


class AuthMiddleWare(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        if request.url.path in EXCEPT_PATHS:
            return await call_next(request)

        token = request.cookies.get("session_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[len("Bearer ") :]

        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized"},
            )

        db_factory: Database | None = getattr(request.app.state, "db_factory", None)
        if db_factory is None:
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "db factory not configured"})
        try:
            with db_factory.get_session_ctx_manager() as request_session:
                hashed_token = security.hash_session_token_sha256(token)
                request.state.db_session = request_session
                login_session: Sessions | None = crud.get_login_session_by_token_hash(request.state.db_session, hashed_token)
        except Exception:  # noqa: BLE001
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "db error"})

        return None


class ServiceError(Exception):
    pass


class UserAlreadyExistsError(ServiceError):
    pass


def register_user_service(db_session: Session, user_in: UserCreate) -> UserRead:
    if crud.get_user_by_username(db_session, user_in.username):
        raise UserAlreadyExistsError("username already exists")
    hashed = security.hash_password(user_in.password)
    try:
        user = crud.create_user(db_session, username=user_in.username, hashed_password=hashed)
        try:
            # prefer pydantic's from_orm if DTO supports orm_mode
            user = UserRead.model_validate(user)
        except Exception as e:
            raise ServiceError("Failed to convert user to UserRead") from e
    except Exception as e:
        raise ServiceError("Failed to create user") from e
    return user
