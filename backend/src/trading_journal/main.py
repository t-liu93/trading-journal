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

from fastapi import APIRouter, FastAPI

from trading_journal.api import (
    accounts,
    health,
    instruments,
    positions,
    strategy_configs,
    strategy_meta,
    trades,
)
from trading_journal.auth.backend import auth_backend, fastapi_users
from trading_journal.schemas.user import UserCreate, UserRead, UserUpdate

API_PREFIX = "/api"


def create_app() -> FastAPI:
    """Build the FastAPI app. Factory style so tests can construct fresh instances."""
    app = FastAPI(title="Trading Journal", version="0.1.0")

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

    app.include_router(api)
    return app


app = create_app()
