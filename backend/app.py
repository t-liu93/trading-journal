import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

import settings
from trading_journal import db, service
from trading_journal.db import Database
from trading_journal.dto import UserCreate, UserRead

_db = db.create_database(settings.settings.database_url)


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
        return await asyncio.to_thread(sync_work)
    except service.UserAlreadyExistsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error" + str(e)) from e


@app.get(f"{settings.settings.api_base}/trades")
async def get_trades() -> dict[str, str]:
    return {"trades": []}
