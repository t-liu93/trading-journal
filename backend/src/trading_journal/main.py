"""FastAPI application entrypoint.

Run during development with:

    uv run uvicorn trading_journal.main:app --reload --host 127.0.0.1 --port 8000

URL convention: every domain / auth route lives under the ``/api`` prefix.
This is deliberate — it leaves the unprefixed namespace free for the SPA
(at deployment time FastAPI will mount the Vite-built ``dist/`` at ``/``).
Without the prefix, a route like ``/accounts`` would collide between the
API and the frontend's client-side router. ``/openapi.json`` and ``/docs``
stay at the root (FastAPI manages them; consumers expect them there).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse

from trading_journal.api import (
    accounts,
    dashboard,
    health,
    instruments,
    positions,
    strategy_configs,
    strategy_meta,
    trade_plans,
    trades,
)
from trading_journal.auth.backend import auth_backend, fastapi_users
from trading_journal.auth.secret import ensure_cookie_secret
from trading_journal.config import get_settings
from trading_journal.db import get_session_maker
from trading_journal.schemas.user import UserCreate, UserRead, UserUpdate

API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: generate-or-load the persisted cookie secret before serving.

    The ``app_config`` table is guaranteed present — migrations run (and must
    succeed) first: the single-container entrypoint and the compose ``migrate``
    service both gate startup on ``alembic upgrade head``. Tests don't run this
    lifespan (ASGITransport skips it); ``get_cookie_secret`` falls back to a
    process-ephemeral value there.
    """
    async with get_session_maker()() as session:
        await ensure_cookie_secret(session)
    yield


def create_app() -> FastAPI:
    """Build the FastAPI app. Factory style so tests can construct fresh instances."""
    app = FastAPI(title="Trading Journal", version="0.1.0", lifespan=lifespan)

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(health.router)

    # Auth: POST /api/auth/register, POST /api/auth/login, POST /api/auth/logout.
    # Email-verify and password-reset routers are intentionally not mounted —
    # they require an outbound email channel we don't have in MVP.
    api.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
    )
    api.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth",
        tags=["auth"],
    )
    # User self-service + superuser admin: GET/PATCH /api/users/me,
    # GET/PATCH/DELETE /api/users/{id}.
    api.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )
    # Domain: Account CRUD under /api/accounts.
    api.include_router(accounts.router)
    # Domain: Instrument dictionary under /api/instruments.
    api.include_router(instruments.router)
    # Domain: per-user StrategyConfig under /api/strategy-configs.
    api.include_router(strategy_configs.router)
    # Domain: Position CRUD under /api/positions (P8).
    api.include_router(positions.router)
    # Domain: Trade CRUD under /api/trades (P9).
    api.include_router(trades.router)
    # Domain: strategy-meta extensions under /api/positions/{pid}/wheel-meta
    # and /api/positions/{pid}/pmcc-meta (P10).
    api.include_router(strategy_meta.router)
    # Domain: TradePlan event stream under /api/positions/{pid}/trade-plans (P11).
    api.include_router(trade_plans.router)
    # Domain: Dashboard summary under /api/dashboard/summary (P12).
    api.include_router(dashboard.router)

    app.include_router(api)

    # Production single-container: also serve the built frontend SPA from
    # STATIC_DIR. In dev this is unset (Vite serves the SPA on :5173 and proxies
    # /api), so the block is skipped. Registered last — after the API router and
    # FastAPI's own /docs + /openapi.json — so those routes always win.
    static_dir = get_settings().static_dir
    if static_dir and Path(static_dir).is_dir():
        dist = Path(static_dir).resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            # An unmatched /api/* path is a real 404, not the SPA shell.
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404)
            # Serve a real file only if it exists AND stays inside dist/ (guards
            # against ../ traversal); otherwise hand back the SPA shell.
            candidate = (dist / full_path).resolve()
            if candidate.is_relative_to(dist) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
