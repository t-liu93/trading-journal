from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, cast

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

import settings
from trading_journal import crud, security
from trading_journal.dto import (
    CycleBase,
    CycleCreate,
    ExchangesBase,
    ExchangesCreate,
    ExchangesRead,
    SessionsCreate,
    SessionsUpdate,
    UserCreate,
    UserLogin,
    UserRead,
)

SessionsCreate.model_rebuild()
CycleBase.model_rebuild()

if TYPE_CHECKING:
    from sqlmodel import Session

    from trading_journal.db import Database
    from trading_journal.models import Sessions


EXCEPT_PATHS = [
    f"{settings.settings.api_base}/status",
    f"{settings.settings.api_base}/register",
    f"{settings.settings.api_base}/login",
]

logger = logging.getLogger(__name__)


class AuthMiddleWare(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:  # noqa: PLR0911
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
                login_session: Sessions | None = crud.get_login_session_by_token_hash(request_session, hashed_token)
                if not login_session:
                    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Unauthorized"})
                session_expires_utc = login_session.expires_at.replace(tzinfo=timezone.utc)
                if session_expires_utc < datetime.now(timezone.utc):
                    crud.delete_login_session(request_session, login_session.session_token_hash)
                    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Unauthorized"})
                if login_session.user.is_active is False:
                    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Unauthorized"})
                if session_expires_utc - datetime.now(timezone.utc) < timedelta(seconds=3600):
                    updated_expiry = datetime.now(timezone.utc) + timedelta(seconds=settings.settings.session_expiry_seconds)
                else:
                    updated_expiry = session_expires_utc
                updated_session: SessionsUpdate = SessionsUpdate(
                    last_seen_at=datetime.now(timezone.utc),
                    last_used_ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("User-Agent"),
                    expires_at=updated_expiry,
                )
                user_id = login_session.user_id
                request.state.user_id = user_id
                crud.update_login_session(request_session, hashed_token, update_session=updated_session)
        except Exception:
            logger.exception("Failed to authenticate user: \n")
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error"})

        return await call_next(request)


class ServiceError(Exception):
    pass


class UserAlreadyExistsError(ServiceError):
    pass


class ExchangeAlreadyExistsError(ServiceError):
    pass


class ExchangeNotFoundError(ServiceError):
    pass


# User service
def register_user_service(db_session: Session, user_in: UserCreate) -> UserRead:
    if crud.get_user_by_username(db_session, user_in.username):
        raise UserAlreadyExistsError("username already exists")
    hashed = security.hash_password(user_in.password)
    user_data: dict = {
        "username": user_in.username,
        "password_hash": hashed,
    }
    try:
        user = crud.create_user(db_session, user_data=user_data)
        try:
            # prefer pydantic's from_orm if DTO supports orm_mode
            user = UserRead.model_validate(user)
        except Exception as e:
            logger.exception("Failed to convert user to UserRead: ")
            raise ServiceError("Failed to convert user to UserRead") from e
    except Exception as e:
        logger.exception("Failed to create user:")
        raise ServiceError("Failed to create user") from e
    return user


def authenticate_user_service(db_session: Session, user_in: UserLogin) -> tuple[SessionsCreate, str] | None:
    user = crud.get_user_by_username(db_session, user_in.username)
    if not user:
        return None
    user_id_val = cast("int", user.id)

    if not security.verify_password(user_in.password, user.password_hash):
        return None

    token = security.generate_session_token()
    token_hashed = security.hash_session_token_sha256(token)
    try:
        session = crud.create_login_session(
            session=db_session,
            user_id=user_id_val,
            session_token_hash=token_hashed,
            session_length_seconds=settings.settings.session_expiry_seconds,
        )
    except Exception as e:
        logger.exception("Failed to create login session: \n")
        raise ServiceError("Failed to create login session") from e
    return SessionsCreate.model_validate(session), token


# Exchanges service
def create_exchange_service(db_session: Session, user_id: int, name: str, notes: str | None) -> ExchangesCreate:
    existing_exchange = crud.get_exchange_by_name_and_user_id(db_session, name, user_id)
    if existing_exchange:
        raise ExchangeAlreadyExistsError("Exchange with the same name already exists for this user")
    exchange_data = ExchangesCreate(
        user_id=user_id,
        name=name,
        notes=notes,
    )
    try:
        exchange = crud.create_exchange(db_session, exchange_data=exchange_data)
        try:
            exchange_dto = ExchangesCreate.model_validate(exchange)
        except Exception as e:
            logger.exception("Failed to convert exchange to ExchangesCreate:")
            raise ServiceError("Failed to convert exchange to ExchangesCreate") from e
    except Exception as e:
        logger.exception("Failed to create exchange:")
        raise ServiceError("Failed to create exchange") from e
    return exchange_dto


def get_exchanges_by_user_service(db_session: Session, user_id: int) -> list[ExchangesRead]:
    exchanges = crud.get_all_exchanges_by_user_id(db_session, user_id)
    return [ExchangesRead.model_validate(exchange) for exchange in exchanges]


def update_exchanges_service(db_session: Session, user_id: int, exchange_id: int, name: str | None, notes: str | None) -> ExchangesBase:
    existing_exchange = crud.get_exchange_by_id(db_session, exchange_id)
    if not existing_exchange:
        raise ExchangeNotFoundError("Exchange not found")
    if existing_exchange.user_id != user_id:
        raise ExchangeNotFoundError("Exchange not found")

    if name:
        other_exchange = crud.get_exchange_by_name_and_user_id(db_session, name, user_id)
        if other_exchange and other_exchange.id != existing_exchange.id:
            raise ExchangeAlreadyExistsError("Another exchange with the same name already exists for this user")

    exchange_data = ExchangesBase(
        name=name or existing_exchange.name,
        notes=notes or existing_exchange.notes,
    )
    try:
        exchange = crud.update_exchange(db_session, cast("int", existing_exchange.id), update_data=exchange_data)
    except Exception as e:
        logger.exception("Failed to update exchange: \n")
        raise ServiceError("Failed to update exchange") from e
    return ExchangesBase.model_validate(exchange)


# Cycle Service
def create_cycle_service(db_session: Session, user_id: int, cycle_data: CycleBase) -> CycleBase:
    cycle_data_dict = cycle_data.model_dump()
    cycle_data_dict["user_id"] = user_id
    cycle_data_with_user_id: CycleCreate = CycleCreate.model_validate(cycle_data_dict)
    crud.create_cycle(db_session, cycle_data=cycle_data_with_user_id)
    return cycle_data


def get_trades_service(db_session: Session, user_id: int) -> list:
    return crud.get_trades_by_user_id(db_session, user_id)
