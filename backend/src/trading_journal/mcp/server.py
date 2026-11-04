"""Official MCP Python SDK server mounted into the existing FastAPI app."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.context import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import ValidationError
from starlette.types import ASGIApp, Receive, Scope, Send

from trading_journal.config import get_settings
from trading_journal.mcp.instructions import INSTRUCTIONS
from trading_journal.mcp.tools import register_tools


class JournalMCPServer(MCPServer):
    """Keep SDK argument validation failures inside the structured tool contract."""

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: Context[Any, Any] | None = None,
    ) -> Any:
        try:
            return await super().call_tool(name, arguments, context)
        except ToolError as exc:
            cause = exc.__cause__
            if not isinstance(cause, ValidationError):
                raise
            problems = [
                {
                    "path": ".".join(str(part) for part in item["loc"]),
                    "message": item["msg"],
                }
                for item in cause.errors()
            ]
            tool = self._tool_manager.get_tool(name)
            if tool is None:
                raise
            return tool.fn_metadata.convert_result(
                {"ok": False, "error": {"code": "invalid_fields", "fields": problems}}
            )


server = JournalMCPServer(name="Trading Journal", instructions=INSTRUCTIONS, version="1.0.0")
register_tools(server)

settings = get_settings()
sdk_transport = server.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=settings.mcp_allowed_hosts,
        allowed_origins=settings.mcp_allowed_origins,
    ),
)


class ExactMountRoot:
    """Adapt the exact external endpoint path to the SDK's `/` route."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            mounted_scope = dict(scope)
            mounted_scope["path"] = "/"
            mounted_scope["root_path"] = ""
            await self.app(mounted_scope, receive, send)
            return
        await self.app(scope, receive, send)


@asynccontextmanager
async def session_manager_lifespan() -> AsyncIterator[None]:
    """The top-level FastAPI lifespan owns the SDK session manager."""
    async with server.session_manager.run():
        yield
