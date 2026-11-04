"""Credential generation and verification for MCP clients."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.mcp_token import McpToken
from trading_journal.models.user import User

Profile = Literal["read", "entry"]
DEFAULT_TOKEN_LIFETIME = timedelta(days=90)


@dataclass(frozen=True)
class McpPrincipal:
    """Authenticated MCP identity; plaintext credentials are never retained."""

    user_id: uuid.UUID
    credential_id: uuid.UUID
    profile: Profile


def utc_now() -> datetime:
    return datetime.now(UTC)


async def issue_token(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    name: str,
    profile: Profile,
    expires_at: datetime | None,
    no_expiry: bool = False,
) -> tuple[McpToken, str]:
    now = utc_now()
    if expires_at is None and not no_expiry:
        expires_at = now + DEFAULT_TOKEN_LIFETIME
    elif expires_at is not None and expires_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="expires_at must include a timezone")
    elif expires_at is not None:
        expires_at = expires_at.astimezone(UTC)
        if expires_at <= now:
            raise HTTPException(status_code=422, detail="expires_at must be in the future")

    secret = secrets.token_urlsafe(32)
    token = f"tj_mcp_{secret}"
    prefix = token[:20]
    row = McpToken(
        user_id=user_id,
        name=name,
        profile=profile,
        token_prefix=prefix,
        token_digest=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=expires_at,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row, token


async def authenticate_token(session: AsyncSession, token: str | None) -> McpPrincipal:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid MCP bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    prefix = token[:20]
    result = await session.execute(select(McpToken).where(McpToken.token_prefix == prefix))
    row = result.scalar_one_or_none()
    digest = hashlib.sha256(token.encode()).hexdigest()
    if row is None or not secrets.compare_digest(row.token_digest, digest):
        raise _unauthorized()
    now = utc_now()
    expiry = row.expires_at
    if expiry is not None:
        expiry = expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry.astimezone(UTC)
    if expiry is not None and expiry <= now:
        raise _unauthorized()
    if row.revoked_at is not None:
        raise _unauthorized()
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return McpPrincipal(user_id=row.user_id, credential_id=row.id, profile=row.profile)  # type: ignore[arg-type]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid MCP bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )
