# Backend

[中文说明](./README_zh.md)

[Back to root](../README.md)

This directory now contains the Phase 1 backend scaffold.

Included in this phase:

- FastAPI app factory and entrypoint
- environment-based settings
- SQLAlchemy engine and session wiring
- Alembic scaffold with an empty baseline revision
- health endpoint at `/api/v1/health`
- minimal tests for happy flow and configuration errors

This phase does not add any business schema or domain models.

Runbook:

1. Create the repo root environment file: `cp .env.example .env`
2. Start the local PostgreSQL example from the repo root: `docker compose -f docker-compose-example.yaml up -d`
3. Create the backend virtual environment from the repo root: `cd backend && python3 -m venv .venv`
4. Install backend dependencies: `cd backend && .venv/bin/pip install -e ".[dev]"`
5. Run migrations: `cd backend && .venv/bin/alembic upgrade head`
6. Start the app with environment-based host and port: `cd backend && .venv/bin/python -m app.main`
7. Run tests: `cd backend && .venv/bin/pytest`

Notes:

- Backend settings are read from environment variables and also load the repo root `.env` file by default.
- `DATABASE_URL` is the only required backend database setting in this phase.
- The baseline Alembic revision is intentionally empty because schema design is deferred to the next phase.
- If you prefer running through Uvicorn directly, use `cd backend && .venv/bin/uvicorn app.asgi:app --host 0.0.0.0 --port 8000`.
