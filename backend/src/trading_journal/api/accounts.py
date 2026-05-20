"""``Account`` CRUD endpoints (data-model.md §4.2, mvp-implementation-plan §5 Phase 4).

Ownership rule: every endpoint scopes by ``current_active_user.id``. When a
user tries to access an account they don't own, we return 404 (not 403) to
avoid leaking the fact that the account exists.

Archival rule: ``DELETE`` is a soft-delete that stamps ``archived_at``. Archived
accounts are invisible by default (404 on GET / PATCH / DELETE; absent from
the list). ``GET /accounts?include_archived=true`` brings them back.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.deps import current_active_user
from trading_journal.db import get_session
from trading_journal.models.account import Account
from trading_journal.models.user import User
from trading_journal.schemas.account import AccountCreate, AccountRead, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


async def _get_owned_account(
    session: AsyncSession,
    user: User,
    account_id: uuid.UUID,
    *,
    allow_archived: bool = False,
) -> Account:
    stmt = select(Account).where(Account.id == account_id, Account.user_id == user.id)
    if not allow_archived:
        stmt = stmt.where(Account.archived_at.is_(None))
    account = (await session.execute(stmt)).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.post(
    "",
    response_model=AccountRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    payload: AccountCreate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Account:
    account = Account(
        user_id=user.id,
        name=payload.name,
        broker=payload.broker,
        account_type=payload.account_type,
        base_currency=payload.base_currency,
        notes=payload.notes,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    include_archived: bool = False,
) -> list[Account]:
    stmt = (
        select(Account)
        .where(Account.user_id == user.id)
        .order_by(Account.created_at.desc(), Account.id.desc())
    )
    if not include_archived:
        stmt = stmt.where(Account.archived_at.is_(None))
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Account:
    return await _get_owned_account(session, user, account_id)


@router.patch("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Account:
    account = await _get_owned_account(session, user, account_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(account, field, value)
    await session.commit()
    await session.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_account(
    account_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    account = await _get_owned_account(session, user, account_id)
    account.archived_at = datetime.now(UTC)
    await session.commit()
