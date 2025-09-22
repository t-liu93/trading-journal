from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from trading_journal import db_migration

if TYPE_CHECKING:
    from collections.abc import Generator
    from sqlite3 import Connection as DBAPIConnection


class Database:
    def __init__(
        self,
        database_url: str | None = None,
        *,
        echo: bool = False,
        connect_args: dict | None = None,
    ) -> None:
        self._database_url = database_url or "sqlite:///:memory:"

        default_connect = {"check_same_thread": False, "timeout": 30} if self._database_url.startswith("sqlite") else {}
        merged_connect = {**default_connect, **(connect_args or {})}

        if self._database_url == "sqlite:///:memory:":
            logger = logging.getLogger(__name__)
            logger.warning(
                "Using in-memory SQLite database; all data will be lost when the application stops.",
            )
            self._engine = create_engine(
                self._database_url,
                echo=echo,
                connect_args=merged_connect,
                poolclass=StaticPool,
            )
        else:
            self._engine = create_engine(self._database_url, echo=echo, connect_args=merged_connect)

        if self._database_url.startswith("sqlite"):

            def _enable_sqlite_pragmas(dbapi_conn: DBAPIConnection, _connection_record: object) -> None:
                try:
                    cur = dbapi_conn.cursor()
                    cur.execute("PRAGMA journal_mode=WAL;")
                    cur.execute("PRAGMA synchronous=NORMAL;")
                    cur.execute("PRAGMA foreign_keys=ON;")
                    cur.execute("PRAGMA busy_timeout=30000;")
                    cur.close()
                except Exception:
                    logger = logging.getLogger(__name__)
                    logger.exception("Failed to set sqlite pragmas on new connection: ")

            event.listen(self._engine, "connect", _enable_sqlite_pragmas)

    def init_db(self) -> None:
        # db_migration.run_migrations(self._engine)
        pass

    def get_session(self) -> Generator[Session, None, None]:
        session = Session(self._engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self._engine.dispose()


def create_database(
    database_url: str | None = None,
    *,
    echo: bool = False,
    connect_args: dict | None = None,
) -> Database:
    return Database(database_url, echo=echo, connect_args=connect_args)
