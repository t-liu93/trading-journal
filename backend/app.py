from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

import settings
from trading_journal import db, service
from trading_journal.dto import CycleBase, ExchangesBase, ExchangesRead, SessionsBase, SessionsCreate, UserCreate, UserLogin, UserRead

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from trading_journal.db import Database

_db = db.create_database(settings.settings.database_url)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    await asyncio.to_thread(_db.init_db)
    try:
        yield
    finally:
        await asyncio.to_thread(_db.dispose)


app = FastAPI(lifespan=lifespan)
app.add_middleware(service.AuthMiddleWare)
app.state.db_factory = _db


@app.get(f"{settings.settings.api_base}/status")
async def get_status() -> dict[str, str]:
    return {"status": "ok"}


@app.post(f"{settings.settings.api_base}/register")
async def register_user(request: Request, user_in: UserCreate) -> Response:
    db_factory: Database = request.app.state.db_factory

    def sync_work() -> UserRead:
        with db_factory.get_session_ctx_manager() as db:
            return service.register_user_service(db, user_in)

    try:
        user = await asyncio.to_thread(sync_work)
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=user.model_dump())
    except service.UserAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to register user: \n")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from e


@app.post(f"{settings.settings.api_base}/login")
async def login(request: Request, user_in: UserLogin) -> Response:
    db_factory: Database = request.app.state.db_factory

    def sync_work() -> tuple[SessionsCreate, str] | None:
        with db_factory.get_session_ctx_manager() as db:
            return service.authenticate_user_service(db, user_in)

    try:
        result = await asyncio.to_thread(sync_work)
        if result is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid username or password, or user doesn't exist"},
            )
        session, token = result
        session_return = SessionsBase(user_id=session.user_id)
        response = JSONResponse(status_code=status.HTTP_200_OK, content=session_return.model_dump())
        expires_sec = int((session.expires_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds())
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=expires_sec,
            path="/",
        )
    except Exception as e:
        logger.exception("Failed to login user: \n")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from e
    else:
        return response


# Exchange
@app.post(f"{settings.settings.api_base}/exchanges")
async def create_exchange(request: Request, exchange_data: ExchangesBase) -> Response:
    db_factory: Database = request.app.state.db_factory

    def sync_work() -> ExchangesBase:
        with db_factory.get_session_ctx_manager() as db:
            return service.create_exchange_service(db, request.state.user_id, exchange_data.name, exchange_data.notes)

    try:
        exchange = await asyncio.to_thread(sync_work)
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=exchange.model_dump())
    except service.ExchangeAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to create exchange: \n")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from e


@app.get(f"{settings.settings.api_base}/exchanges")
async def get_exchanges(request: Request) -> list[ExchangesRead]:
    db_factory: Database = request.app.state.db_factory

    def sync_work() -> list[ExchangesRead]:
        with db_factory.get_session_ctx_manager() as db:
            return service.get_exchanges_by_user_service(db, request.state.user_id)

    try:
        return await asyncio.to_thread(sync_work)
    except Exception as e:
        logger.exception("Failed to get exchanges: \n")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from e


@app.patch(f"{settings.settings.api_base}/exchanges/{{exchange_id}}")
async def update_exchange(request: Request, exchange_id: int, exchange_data: ExchangesBase) -> Response:
    db_factory: Database = request.app.state.db_factory

    def sync_work() -> ExchangesBase:
        with db_factory.get_session_ctx_manager() as db:
            return service.update_exchanges_service(db, request.state.user_id, exchange_id, exchange_data.name, exchange_data.notes)

    try:
        exchange = await asyncio.to_thread(sync_work)
        return JSONResponse(status_code=status.HTTP_200_OK, content=exchange.model_dump())
    except service.ExchangeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except service.ExchangeAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to update exchange: \n")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from e


# Cycle
@app.post(f"{settings.settings.api_base}/cycles")
async def create_cycle(request: Request, cycle_data: CycleBase) -> Response:
    return JSONResponse(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, content="Not supported.")
    db_factory: Database = request.app.state.db_factory

    def sync_work() -> CycleBase:
        with db_factory.get_session_ctx_manager() as db:
            return service.create_cycle_service(db, request.state.user_id, cycle_data)

    try:
        cycle = await asyncio.to_thread(sync_work)
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=jsonable_encoder(cycle))
    except Exception as e:
        logger.exception("Failed to create cycle: \n")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from e
