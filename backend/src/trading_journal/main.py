"""FastAPI application entrypoint.

Run during development with:

    uv run uvicorn trading_journal.main:app --reload --host 127.0.0.1 --port 8000
"""

from fastapi import FastAPI

from trading_journal.api import accounts, health
from trading_journal.auth.backend import auth_backend, fastapi_users
from trading_journal.schemas.user import UserCreate, UserRead, UserUpdate


def create_app() -> FastAPI:
    """Build the FastAPI app. Factory style so tests can construct fresh instances."""
    app = FastAPI(title="Trading Journal", version="0.1.0")
    app.include_router(health.router)

    # Auth: POST /auth/register, POST /auth/login, POST /auth/logout.
    # Email-verify and password-reset routers are intentionally not mounted —
    # they require an outbound email channel we don't have in MVP.
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth",
        tags=["auth"],
    )
    # User self-service + superuser admin: GET/PATCH /users/me, GET/PATCH/DELETE /users/{id}.
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )
    # Domain: Account CRUD.
    app.include_router(accounts.router)
    return app


app = create_app()
