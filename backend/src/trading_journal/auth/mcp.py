"""Bearer dependency for future MCP HTTP handlers."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.db import get_session
from trading_journal.services.mcp_tokens import McpPrincipal, authenticate_token

bearer_scheme = HTTPBearer(auto_error=False)


async def current_mcp_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> McpPrincipal:
    token = credentials.credentials if credentials is not None else None
    return await authenticate_token(session, token)
