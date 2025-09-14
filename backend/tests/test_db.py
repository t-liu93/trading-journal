from collections.abc import Generator
from contextlib import contextmanager, suppress

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel

from trading_journal.db import Database, create_database


@contextmanager
def session_ctx(db: Database) -> Generator[Session, None, None]:
    """
    Drive Database.get_session() generator and correctly propagate exceptions
    into the generator so the generator's except/rollback path runs.
    """
    gen = db.get_session()
    session = next(gen)
    try:
        yield session
    except Exception as exc:
        # Propagate the exception into the dependency generator so it can rollback.
        with suppress(StopIteration):
            gen.throw(exc)
        raise
    else:
        # Normal completion: advance generator to let it commit/close.
        with suppress(StopIteration):
            next(gen)
    finally:
        # close the generator but DO NOT dispose the engine here
        gen.close()


@contextmanager
def database_ctx(db: Database) -> Generator[Database, None, None]:
    """
    Test-scoped context manager to ensure the Database (engine) is disposed at test end.
    Use this to wrap test logic that needs the same in-memory engine across multiple sessions.
    """
    try:
        yield db
    finally:
        db.dispose()


def test_select_one_executes() -> None:
    db = create_database(None)  # in-memory by default
    with database_ctx(db):
        with session_ctx(db) as session:
            val = session.exec(text("SELECT 1")).scalar_one()
    assert int(val) == 1


def test_in_memory_persists_across_sessions_when_using_staticpool() -> None:
    db = create_database(None)  # in-memory with StaticPool
    with database_ctx(db):
        with session_ctx(db) as s1:
            s1.exec(
                text("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, val TEXT);")
            )
            s1.exec(text("INSERT INTO t (val) VALUES (:v)").bindparams(v="hello"))
        with session_ctx(db) as s2:
            got = s2.exec(text("SELECT val FROM t")).scalar_one()
    assert got == "hello"


def test_sqlite_pragmas_applied() -> None:
    db = create_database(None)
    with database_ctx(db):
        # PRAGMA returns integer 1 when foreign_keys ON
        with session_ctx(db) as session:
            fk = session.exec(text("PRAGMA foreign_keys")).scalar_one()
    assert int(fk) == 1


def test_rollback_on_exception() -> None:
    db = create_database(None)
    SQLModel.metadata.clear()
    db.init_db()
    with database_ctx(db):
        # Create table then insert and raise inside the same session to force rollback
        with pytest.raises(RuntimeError):  # noqa: PT012, SIM117
            with session_ctx(db) as s:
                s.exec(
                    text(
                        "CREATE TABLE IF NOT EXISTS t_rb (id INTEGER PRIMARY KEY, val TEXT);"
                    )
                )
                s.exec(
                    text("INSERT INTO t_rb (val) VALUES (:v)").bindparams(
                        v="will_rollback"
                    )
                )
                # simulate handler error -> should trigger rollback in get_session
                raise RuntimeError("simulated failure")

        # New session should not see the inserted row
        with session_ctx(db) as s2:
            rows = list(s2.exec(text("SELECT val FROM t_rb")).scalars())
    assert rows == []
