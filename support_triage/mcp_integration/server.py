"""MCP server exposing the log-search tool.

Run standalone (spawned as a subprocess by client.py) via:
    python -m support_triage.mcp_integration.server
"""

from mcp.server.mcpserver import MCPServer

from support_triage.tools import search_logs as _search_logs

server = MCPServer(name="log-search")


@server.tool()
def search_logs(query: str) -> list[str]:
    """Keyword-match the query against recent system log lines."""
    return _search_logs(query)


if __name__ == "__main__":
    server.run(transport="stdio")
