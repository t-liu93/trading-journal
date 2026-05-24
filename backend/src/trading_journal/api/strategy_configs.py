"""``StrategyConfig`` CRUD endpoints (data-model.md §4.7, P7).

Ownership rule: every endpoint scopes by ``current_active_user.id``. When a
user tries to access a config they don't own, we return 404 (not 403) — same
as Account.

Key design choices:
  - ``strategy_type`` (enum value) is the path key, not the UUID ``id``.
  - ``POST`` is get-or-create: existing ``(user_id, strategy_type)`` returns
    200 with the existing row unchanged; new rows return 201.
  - ``PATCH`` uses ``model_dump(exclude_unset=True)`` so ``{}`` is a no-op,
    ``{"max_exposure": null}`` explicitly clears, and
    ``{"max_exposure": "5000"}`` sets.
  - ``DELETE`` is a hard delete (no ``archived_at`` on the model).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status  # noqa: A005
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.deps import current_active_user
from trading_journal.db import get_session
from trading_journal.models._enums import StrategyType
from trading_journal.models.strategy_config import StrategyConfig
from trading_journal.models.user import User
from trading_journal.schemas.strategy_config import (
    StrategyConfigCreate,
    StrategyConfigRead,
    StrategyConfigUpdate,
)

router = APIRouter(prefix="/strategy-configs", tags=["strategy-configs"])


async def _get_config_by_user_id(
    session: AsyncSession,
    user_id: uuid.UUID,
    strategy_type: StrategyType,
) -> StrategyConfig | None:
    stmt = select(StrategyConfig).where(
        StrategyConfig.user_id == user_id,
        StrategyConfig.strategy_type == strategy_type,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _get_owned_config(
    session: AsyncSession,
    user: User,
    strategy_type: StrategyType,
) -> StrategyConfig:
    cfg = await _get_config_by_user_id(session, user.id, strategy_type)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy config not found",
        )
    return cfg


@router.post(
    "",
    response_model=StrategyConfigRead,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_200_OK: {"model": StrategyConfigRead}},
)
async def create_strategy_config(
    payload: StrategyConfigCreate,
    response: Response,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyConfig:
    # Capture pure values before any rollback can expire the user ORM object.
    user_id: uuid.UUID = user.id
    stype: StrategyType = payload.strategy_type

    existing = await _get_config_by_user_id(session, user_id, stype)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing

    cfg = StrategyConfig(
        user_id=user_id,
        strategy_type=stype,
        max_exposure=payload.max_exposure,
        exposure_currency=payload.exposure_currency,
        notes=payload.notes,
    )
    session.add(cfg)
    try:
        await session.commit()
    except IntegrityError:
        # Concurrent insert won the race on (user_id, strategy_type).
        # rollback() expires all ORM objects in the session (including
        # ``user``), so we must not access ``user.id`` afterwards —
        # hence the pure-value captures above.
        await session.rollback()
        winner = await _get_config_by_user_id(session, user_id, stype)
        if winner is None:
            raise
        response.status_code = status.HTTP_200_OK
        return winner
    await session.refresh(cfg)
    return cfg


@router.get("", response_model=list[StrategyConfigRead])
async def list_strategy_configs(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[StrategyConfig]:
    stmt = (
        select(StrategyConfig)
        .where(StrategyConfig.user_id == user.id)
        .order_by(StrategyConfig.strategy_type)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{strategy_type}", response_model=StrategyConfigRead)
async def get_strategy_config(
    strategy_type: StrategyType,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyConfig:
    return await _get_owned_config(session, user, strategy_type)


@router.patch("/{strategy_type}", response_model=StrategyConfigRead)
async def update_strategy_config(
    strategy_type: StrategyType,
    payload: StrategyConfigUpdate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StrategyConfig:
    cfg = await _get_owned_config(session, user, strategy_type)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(cfg, field, value)
    await session.commit()
    await session.refresh(cfg)
    return cfg


@router.delete("/{strategy_type}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy_config(
    strategy_type: StrategyType,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    cfg = await _get_owned_config(session, user, strategy_type)
    await session.delete(cfg)
    await session.commit()
