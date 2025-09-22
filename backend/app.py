from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

import settings
from trading_journal import db, service
from trading_journal.db import Database
from trading_journal.dto import SessionsBase, SessionsCreate, UserCreate, UserLogin, UserRead

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
async def register_user(request: Request, user_in: UserCreate) -> UserRead:
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
async def login(request: Request, user_in: UserLogin) -> SessionsBase:
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
# @app.post(f"{settings.settings.api_base}/exchanges")
# async def create_exchange(request: Request, name: str, notes: str | None) -> dict:


@app.get(f"{settings.settings.api_base}/trades")
async def get_trades(request: Request) -> list:
    db_factory: Database = request.app.state.db_factory
    with db_factory.get_session_ctx_manager() as db:
        return service.get_trades_service(db, request.state.user_id)
