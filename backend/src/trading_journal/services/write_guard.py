"""Database-level coordination for instrument natural-key writes."""

from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.app_config import AppConfig

INSTRUMENT_WRITE_GUARD_KEY = "instrument_write_guard"


async def acquire_instrument_write_guard(session: AsyncSession) -> None:
    """Take the shared coordination row's database write lock until commit.

    SQLite serializes this UPDATE across independent connections. The value is
    unchanged and the caller owns the transaction and its eventual commit.
    """
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(AppConfig)
            .where(AppConfig.key == INSTRUMENT_WRITE_GUARD_KEY)
            .values(value=AppConfig.value)
        ),
    )
    if result.rowcount != 1:
        raise RuntimeError("instrument write coordination row is missing")
