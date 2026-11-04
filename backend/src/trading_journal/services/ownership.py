"""Reusable ownership checks shared by REST and MCP query/entry handlers."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.account import Account
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade


async def resolve_owned_account(
    session: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
) -> Account:
    result = await session.execute(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == user_id,
            Account.archived_at.is_(None),
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=422, detail="Account not found or archived")
    return account


async def resolve_owned_position(
    session: AsyncSession, user_id: uuid.UUID, position_id: uuid.UUID
) -> Position:
    result = await session.execute(
        select(Position).where(
            Position.id == position_id, Position.user_id == user_id
        )
    )
    position = result.scalar_one_or_none()
    if position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    return position


async def resolve_owned_trade(
    session: AsyncSession, user_id: uuid.UUID, trade_id: uuid.UUID
) -> Trade:
    result = await session.execute(
        select(Trade)
        .join(Position, Trade.position_id == Position.id)
        .where(Trade.id == trade_id, Position.user_id == user_id)
    )
    trade = result.scalar_one_or_none()
    if trade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    return trade
