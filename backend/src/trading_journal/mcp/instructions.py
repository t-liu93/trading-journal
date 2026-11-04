"""Workflow guidance shared with every MCP client during initialization."""

INSTRUCTIONS = """You are connected to a single-user trading journal. Start each entry workflow
with get_context.
Resolve missing information by asking the user; use list/search tools and ask them to choose when
there are no matches or multiple candidates. Never infer an account, contract, quantity, price,
execution time, or option open/close intent. In particular, option buy/sell does not determine
BTO, STO, BTC, or STC. Prepare one complete batch, show the server-generated preview and defaults,
and obtain explicit confirmation in chat before committing. Commit only the returned draft_id. If
a response is lost or a retry is needed, call commit_entry again with that same draft_id; do not
prepare a replacement batch."""
