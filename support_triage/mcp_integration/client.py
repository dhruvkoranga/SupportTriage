"""Synchronous client for the log-search MCP server.

Spawns server.py as a subprocess and talks to it over stdio — a genuine MCP
round trip, not a plain function call (see DECISIONS.md #7). LangGraph nodes
are synchronous, so this wraps the async MCP client in asyncio.run().
"""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "support_triage.mcp_integration.server"],
)


async def _search_logs_async(query: str) -> list[str]:
    async with stdio_client(_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("search_logs", {"query": query})
            if result.is_error:
                raise RuntimeError(f"log-search MCP server returned an error: {result.content}")
            return result.structured_content["result"]


def search_logs_via_mcp(query: str) -> list[str]:
    """Search logs by calling the log-search MCP server over stdio."""
    return asyncio.run(_search_logs_async(query))
