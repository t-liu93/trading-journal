import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from trading_journal import db_migration


def _base_type_of(compiled: str) -> str:
    """Return base type name (e.g. VARCHAR from VARCHAR(13)), upper-cased."""
    return compiled.split("(")[0].strip().upper()


def test_run_migrations_0_to_1(monkeypatch: pytest.MonkeyPatch) -> None:
    # in-memory engine that preserves the same connection (StaticPool)
    SQLModel.metadata.clear()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        monkeypatch.setattr(db_migration, "LATEST_VERSION", 1)
        final_version = db_migration.run_migrations(engine)
        assert final_version == 1

        expected_schema = {
            "users": {
                "id": ("INTEGER", 1, 1),
                "username": ("TEXT", 1, 0),
                "password_hash": ("TEXT", 1, 0),
                "is_active": ("BOOLEAN", 1, 0),
            },
            "cycles": {
                "id": ("INTEGER", 1, 1),
                "user_id": ("INTEGER", 1, 0),
                "friendly_name": ("TEXT", 0, 0),
                "symbol": ("TEXT", 1, 0),
                "underlying_currency": ("TEXT", 1, 0),
                "status": ("TEXT", 1, 0),
                "funding_source": ("TEXT", 0, 0),
                "capital_exposure_cents": ("INTEGER", 0, 0),
                "loan_amount_cents": ("INTEGER", 0, 0),
                "loan_interest_rate_bps": ("INTEGER", 0, 0),
                "start_date": ("DATE", 1, 0),
                "end_date": ("DATE", 0, 0),
            },
            "trades": {
                "id": ("INTEGER", 1, 1),
                "user_id": ("INTEGER", 1, 0),
                "friendly_name": ("TEXT", 0, 0),
                "symbol": ("TEXT", 1, 0),
                "underlying_currency": ("TEXT", 1, 0),
                "trade_type": ("TEXT", 1, 0),
                "trade_strategy": ("TEXT", 1, 0),
                "trade_time_utc": ("DATETIME", 1, 0),
                "expiry_date": ("DATE", 0, 0),
                "strike_price_cents": ("INTEGER", 0, 0),
                "quantity": ("INTEGER", 1, 0),
                "price_cents": ("INTEGER", 1, 0),
                "gross_cash_flow_cents": ("INTEGER", 1, 0),
                "commission_cents": ("INTEGER", 1, 0),
                "net_cash_flow_cents": ("INTEGER", 1, 0),
                "cycle_id": ("INTEGER", 0, 0),
            },
            "sessions": {
                "id": ("INTEGER", 1, 1),
                "user_id": ("INTEGER", 1, 0),
                "session_token_hash": ("TEXT", 1, 0),
                "created_at": ("DATETIME", 1, 0),
                "expires_at": ("DATETIME", 1, 0),
                "last_seen_at": ("DATETIME", 0, 0),
                "last_used_ip": ("TEXT", 0, 0),
                "user_agent": ("TEXT", 0, 0),
                "device_name": ("TEXT", 0, 0),
            },
        }

        expected_fks = {
            "trades": [
                {"table": "cycles", "from": "cycle_id", "to": "id"},
                {"table": "users", "from": "user_id", "to": "id"},
            ],
            "cycles": [
                {"table": "users", "from": "user_id", "to": "id"},
            ],
        }

        with engine.connect() as conn:
            # check tables exist
            rows = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'"),
            ).fetchall()
            found_tables = {r[0] for r in rows}
            assert set(expected_schema.keys()).issubset(found_tables), f"missing tables: {set(expected_schema.keys()) - found_tables}"

            # check user_version
            uv = conn.execute(text("PRAGMA user_version")).fetchone()
            assert uv is not None
            assert int(uv[0]) == 1

            # validate each table columns
            for tbl_name, cols in expected_schema.items():
                info_rows = conn.execute(text(f"PRAGMA table_info({tbl_name})")).fetchall()
                # map: name -> (type, notnull, pk)
                actual = {r[1]: ((r[2] or "").upper(), int(r[3]), int(r[5])) for r in info_rows}
                for colname, (exp_type, exp_notnull, exp_pk) in cols.items():
                    assert colname in actual, f"{tbl_name}: missing column {colname}"
                    act_type, act_notnull, act_pk = actual[colname]
                    # compare base type (e.g. VARCHAR(13) -> VARCHAR)
                    if act_type:
                        act_base = _base_type_of(act_type)
                    else:
                        act_base = ""
                    assert exp_type in act_base or act_base in exp_type, (
                        f"type mismatch {tbl_name}.{colname}: expected {exp_type}, got {act_base}"
                    )
                    assert act_notnull == exp_notnull, f"notnull mismatch {tbl_name}.{colname}: expected {exp_notnull}, got {act_notnull}"
                    assert act_pk == exp_pk, f"pk mismatch {tbl_name}.{colname}: expected {exp_pk}, got {act_pk}"
            for tbl_name, fks in expected_fks.items():
                fk_rows = conn.execute(text(f"PRAGMA foreign_key_list('{tbl_name}')")).fetchall()
                # fk_rows columns: (id, seq, table, from, to, on_update, on_delete, match)
                actual_fk_list = [{"table": r[2], "from": r[3], "to": r[4]} for r in fk_rows]
                for efk in fks:
                    assert efk in actual_fk_list, f"missing FK on {tbl_name}: {efk}"
    finally:
        engine.dispose()
        SQLModel.metadata.clear()
