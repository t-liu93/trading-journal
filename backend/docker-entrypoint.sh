#!/bin/sh
set -e

# Bring the (bind-mounted) SQLite DB up to the latest schema, then hand off to
# CMD (uvicorn). `exec` keeps uvicorn as PID 1 for clean signal handling.
# alembic reads DATABASE_URL via trading_journal.config (see alembic/env.py),
# so the same env var drives both migrations and the app.
#
# `set -e` makes this fail-closed: if the migration fails, we exit non-zero and
# uvicorn never starts on a bad schema.
#
# RUN_MIGRATIONS=false skips this step. The compose `app` service sets it so the
# dedicated one-shot `migrate` service owns the migration (and `app` only starts
# once it has succeeded) — the schema is never migrated twice.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    alembic upgrade head
fi

exec "$@"
