# Backend

> **English** · [中文](README.zh.md)

FastAPI, async SQLAlchemy, Alembic and SQLite; package `trading_journal`. Current CI uses Python 3.12 and uv.

See the [development guide](../docs/development.md) for an isolated local database, startup commands, architecture, domain contracts and checks. Run commands from this directory; never migrate or reset an existing database just to verify a change.

- Install: `uv sync --frozen`.
- Check: `uv run ruff check .`, `uv run mypy --strict src`, `uv run pytest`.
- API types: start the development backend on port 8000, then run `npm run codegen` from `frontend/`. OpenAPI is `/openapi.json`; business endpoints use `/api`.
- Tests use isolated databases built from real Alembic migrations.
- HTTP development requires `COOKIE_SECURE=false`. Sessions use database tokens; the signing secret is persisted automatically.

Implementation scope and acceptance live in the [current roadmap](../docs/plan/roadmap.md) and task cards, not the historical P/F plans.
