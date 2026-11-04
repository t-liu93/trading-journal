"""SDK registration and request-identity contracts for the MCP tool surface."""

from trading_journal.mcp.server import server


async def test_exact_d02_tools_and_raw_prepare_request_schema() -> None:
    tools = await server.list_tools()
    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == {
        "get_context",
        "list_accounts",
        "search_instruments",
        "list_positions",
        "get_position",
        "list_trades",
        "prepare_entry",
        "commit_entry",
    }
    prepare_schema = by_name["prepare_entry"].input_schema
    assert "request" in prepare_schema["required"]
    assert prepare_schema["properties"]["request"]["type"] == "object"
    description = by_name["prepare_entry"].description or ""
    for contract_field in (
        "request_id",
        "open_position",
        "add_trades",
        "position_id",
        "primary_instrument",
        "instrument_id",
        "underlying_symbol",
        "executed_at",
        "timezone",
    ):
        assert contract_field in description
    assert "unchanged" in description
    assert "draft_id" in by_name["commit_entry"].input_schema["properties"]
    assert "request" not in by_name["commit_entry"].input_schema["properties"]


async def test_sdk_argument_validation_uses_structured_invalid_fields() -> None:
    invalid_type = await server.call_tool("list_accounts", {"limit": "bad"})
    missing_required = await server.call_tool("get_position", {})

    invalid_content = invalid_type.structured_content
    assert invalid_content["ok"] is False
    assert invalid_content["error"]["code"] == "invalid_fields"
    assert invalid_content["error"]["fields"][0]["path"] == "limit"
    assert missing_required.structured_content["error"]["code"] == "invalid_fields"
    assert missing_required.structured_content["error"]["fields"][0]["path"] == "position_id"
