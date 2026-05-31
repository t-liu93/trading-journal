#!/bin/sh
set -e

# Bring the (bind-mounted) SQLite DB up to the latest schema, then hand off to
# CMD (uvicorn). `exec` keeps uvicorn as PID 1 for clean signal handling.
# alembic reads DATABASE_URL via trading_journal.config (see alembic/env.py),
# so the same env var drives both migrations and the app.
alembic upgrade head

exec "$@"
