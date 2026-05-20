"""End-to-end migration tests.

Run Alembic in a subprocess against a per-test tempfile SQLite. Subprocess
isolation avoids clashing with pytest-asyncio's running event loop (env.py
calls ``asyncio.run``).
"""

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parent.parent

EXPECTED_DOMAIN_TABLES = {
    "users",
    "access_tokens",
    "accounts",
    "instruments",
    "option_contracts",
    "forex_pairs",
    "positions",
    "trades",
    "trade_plans",
    "strategy_configs",
    "wheel_cycle_metas",
    "pmcc_cycle_metas",
}


@pytest.fixture
def temp_db(tmp_path: Path) -> Iterator[tuple[str, str]]:
    """Yield (async_url, sync_url) for a fresh per-test sqlite file."""
    db_path = tmp_path / "test.db"
    async_url = f"sqlite+aiosqlite:///{db_path}"
    sync_url = f"sqlite:///{db_path}"
    yield async_url, sync_url


def _alembic(*args: str, url: str) -> None:
    """Invoke ``alembic`` from the project venv against the given async URL."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"url={url}", *args],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _table_names(sync_url: str) -> set[str]:
    engine = create_engine(sync_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _columns(sync_url: str, table: str) -> dict[str, dict[str, object]]:
    engine = create_engine(sync_url)
    try:
        return {c["name"]: c for c in inspect(engine).get_columns(table)}
    finally:
        engine.dispose()


# Column sets verified against the ORM models in src/trading_journal/models/.
# These three are the stable auth/account tables; Position/Trade columns are
# still in flux so they're deliberately left out (see fix plan Fix 5).
EXPECTED_COLUMNS = {
    "accounts": {
        "id",
        "user_id",
        "name",
        "broker",
        "account_type",
        "base_currency",
        "notes",
        "created_at",
        "archived_at",
    },
    "users": {
        "id",
        "email",
        "hashed_password",
        "is_active",
        "is_superuser",
        "is_verified",
        "last_login_at",
        "created_at",
    },
    "access_tokens": {"token", "user_id", "created_at"},
}


def test_alembic_upgrade_creates_all_tables(temp_db: tuple[str, str]) -> None:
    async_url, sync_url = temp_db
    _alembic("upgrade", "head", url=async_url)

    tables = _table_names(sync_url)
    assert "alembic_version" in tables
    missing = EXPECTED_DOMAIN_TABLES - tables
    assert not missing, f"missing tables after upgrade: {sorted(missing)}"


def test_alembic_upgrade_creates_expected_columns(temp_db: tuple[str, str]) -> None:
    """Migrations build the same columns the ORM declares for the stable tables.

    The API-test fixture builds schema from ``Base.metadata.create_all`` (ORM),
    not from migrations, so a migration that drifts from the ORM would slip
    through. This pins the column set for the auth/account tables.
    """
    async_url, sync_url = temp_db
    _alembic("upgrade", "head", url=async_url)

    for table, expected in EXPECTED_COLUMNS.items():
        actual = set(_columns(sync_url, table))
        missing = expected - actual
        assert not missing, f"{table}: missing columns after upgrade: {sorted(missing)}"


def test_alembic_downgrade_roundtrip(temp_db: tuple[str, str]) -> None:
    async_url, sync_url = temp_db

    _alembic("upgrade", "head", url=async_url)
    assert EXPECTED_DOMAIN_TABLES.issubset(_table_names(sync_url))

    _alembic("downgrade", "base", url=async_url)
    remaining = _table_names(sync_url)
    # After downgrade, only Alembic's bookkeeping table should remain.
    assert remaining <= {"alembic_version"}, f"leaked tables: {sorted(remaining)}"

    _alembic("upgrade", "head", url=async_url)
    assert EXPECTED_DOMAIN_TABLES.issubset(_table_names(sync_url))
