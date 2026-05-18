"""FastAPI application entrypoint.

Run during development with:

    uv run uvicorn trading_journal.main:app --reload --host 127.0.0.1 --port 8000
"""

from fastapi import FastAPI

from trading_journal.api import health


def create_app() -> FastAPI:
    """Build the FastAPI app. Factory style so tests can construct fresh instances."""
    app = FastAPI(title="Trading Journal", version="0.1.0")
    app.include_router(health.router)
    return app


app = create_app()
