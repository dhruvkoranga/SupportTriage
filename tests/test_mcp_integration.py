"""Exercises the real MCP server as a subprocess — slower than a unit test,
but this is the one place we prove the MCP round trip actually works end to
end, not just that the underlying function does (see DECISIONS.md #7).
"""

from support_triage.mcp_integration.client import search_logs_via_mcp


def test_search_logs_via_mcp_finds_matching_line():
    results = search_logs_via_mcp("timeout payment order 4821")
    assert any("timeout calling PaymentGateway" in r for r in results)


def test_search_logs_via_mcp_no_match():
    assert search_logs_via_mcp("xyzzy_nonexistent_term") == []
