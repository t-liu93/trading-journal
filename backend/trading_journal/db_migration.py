from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from sqlalchemy import text
from sqlmodel import SQLModel

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection, Engine

LATEST_VERSION = 1


def _mig_0_1(engine: Engine) -> None:
    """
    Initial schema: create all tables from SQLModel models.
    Safe to call on an empty DB; idempotent for missing tables.
    """
    # Ensure all models are imported before this is called (import side-effect registers tables)
    # e.g. trading_journal.models is imported in the caller / app startup.
    from trading_journal import models_v1

    SQLModel.metadata.create_all(
        bind=engine,
        tables=[
            models_v1.Trades.__table__,
            models_v1.Cycles.__table__,
            models_v1.Users.__table__,
            models_v1.Sessions.__table__,
        ],
    )


# map current_version -> function that migrates from current_version -> current_version+1
MIGRATIONS: dict[int, Callable[[Engine], None]] = {
    0: _mig_0_1,
}


def _get_sqlite_user_version(conn: Connection) -> int:
    row = conn.execute(text("PRAGMA user_version")).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _set_sqlite_user_version(conn: Connection, v: int) -> None:
    conn.execute(text(f"PRAGMA user_version = {int(v)}"))


def run_migrations(engine: Engine, target_version: int | None = None) -> int:
    """
    Run migrations up to target_version (or LATEST_VERSION).
    Returns final applied version.
    """
    target = target_version or LATEST_VERSION
    with engine.begin() as conn:
        driver = conn.engine.name.lower()
        if driver == "sqlite":
            cur_version = _get_sqlite_user_version(conn)
            while cur_version < target:
                fn = MIGRATIONS.get(cur_version)
                if fn is None:
                    raise RuntimeError(
                        f"No migration from {cur_version} -> {cur_version + 1}"
                    )
                # call migration with Engine (fn should use transactions)
                fn(engine)
                _set_sqlite_user_version(conn, cur_version + 1)
                cur_version += 1
            return cur_version
        return -1  # unknown / unsupported driver; no-op
