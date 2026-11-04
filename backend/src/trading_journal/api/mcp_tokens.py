"""Cookie-authenticated management of dedicated MCP credentials."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.auth.deps import current_active_user
from trading_journal.db import get_session
from trading_journal.models.mcp_token import McpToken
from trading_journal.models.user import User
from trading_journal.schemas.mcp_token import (
    McpTokenCreate,
    McpTokenIssued,
    McpTokenRead,
)
from trading_journal.services.mcp_tokens import issue_token, utc_now

router = APIRouter(prefix="/mcp-tokens", tags=["mcp-tokens"])


@router.get("", response_model=list[McpTokenRead])
async def list_mcp_tokens(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[McpToken]:
    result = await session.execute(
        select(McpToken).where(McpToken.user_id == user.id).order_by(McpToken.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=McpTokenIssued, status_code=status.HTTP_201_CREATED)
async def create_mcp_token(
    payload: McpTokenCreate,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> McpTokenIssued:
    row, token = await issue_token(
        session,
        user_id=user.id,
        name=payload.name,
        profile=payload.profile,
        expires_at=payload.expires_at,
        no_expiry="expires_at" in payload.model_fields_set and payload.expires_at is None,
    )
    metadata = McpTokenRead.model_validate(row, from_attributes=True)
    return McpTokenIssued(**metadata.model_dump(), token=token)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_mcp_token(
    token_id: uuid.UUID,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    row = await session.get(McpToken, token_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="MCP credential not found")
    if row.revoked_at is None:
        row.revoked_at = utc_now()
        await session.commit()
