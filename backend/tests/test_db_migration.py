import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from trading_journal import db_migration


def _base_type_of(compiled: str) -> str:
    """Return base type name (e.g. VARCHAR from VARCHAR(13)), upper-cased."""
    return compiled.split("(")[0].strip().upper()


def test_run_migrations_0_to_1(monkeypatch: pytest.MonkeyPatch) -> None:
    # in-memory engine that preserves the same connection (StaticPool)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # ensure target is the LATEST_VERSION we expect for the test
    monkeypatch.setattr(db_migration, "LATEST_VERSION", 1)

    # run real migrations (will import trading_journal.models_v1 inside _mig_0_1)
    final_version = db_migration.run_migrations(engine)
    assert final_version == 1

    # import snapshot models to validate schema
    from trading_journal import models_v1

    expected_tables = {
        "trades": models_v1.Trades.__table__,
        "cycles": models_v1.Cycles.__table__,
    }

    with engine.connect() as conn:
        # check tables exist
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        found_tables = {r[0] for r in rows}
        assert set(expected_tables.keys()).issubset(found_tables), (
            f"missing tables: {set(expected_tables.keys()) - found_tables}"
        )

        # check user_version
        uv = conn.execute(text("PRAGMA user_version")).fetchone()
        assert uv is not None
        assert int(uv[0]) == 1

        # validate columns and (base) types for each expected table
        dialect = conn.dialect
        for tbl_name, table in expected_tables.items():
            info_rows = conn.execute(text(f"PRAGMA table_info({tbl_name})")).fetchall()
            # build mapping: column name -> declared type (upper)
            actual_cols = {r[1]: (r[2] or "").upper() for r in info_rows}
            for col in table.columns:
                assert col.name in actual_cols, (
                    f"column {col.name} missing in table {tbl_name}"
                )
                # compile expected type against this dialect
                try:
                    compiled = col.type.compile(
                        dialect=dialect
                    )  # e.g. VARCHAR(13), DATETIME
                except Exception:
                    compiled = str(col.type)
                expected_base = _base_type_of(compiled)
                actual_type = actual_cols[col.name]
                actual_base = _base_type_of(actual_type) if actual_type else ""
                # accept either direction (some dialect vs sqlite naming differences)
                assert (expected_base in actual_base) or (
                    actual_base in expected_base
                ), (
                    f"type mismatch for {tbl_name}.{col.name}: expected {expected_base}, got {actual_base}"
                )
