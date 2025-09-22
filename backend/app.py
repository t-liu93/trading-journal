import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status

import settings
from trading_journal import db
from trading_journal.dto import TradeCreate, TradeRead

API_BASE = "/api/v1"

_db = db.create_database(settings.settings.database_url)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    await asyncio.to_thread(_db.init_db)
    try:
        yield
    finally:
        await asyncio.to_thread(_db.dispose)


app = FastAPI(lifespan=lifespan)


@app.get(f"{API_BASE}/status")
async def get_status() -> dict[str, str]:
    return {"status": "ok"}
