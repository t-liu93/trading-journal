"""Bearer dependency for future MCP HTTP handlers."""

from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.db import get_session
from trading_journal.services.mcp_tokens import McpPrincipal, authenticate_token

bearer_scheme = HTTPBearer(auto_error=False)


async def authenticate_bearer_header(
    session: AsyncSession, authorization: str | None
) -> McpPrincipal:
    """Authenticate one request's explicit Bearer header without shared state."""
    scheme, separator, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not separator or not token:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid MCP bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await authenticate_token(session, token)


async def current_mcp_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> McpPrincipal:
    authorization = f"Bearer {credentials.credentials}" if credentials is not None else None
    return await authenticate_bearer_header(session, authorization)
