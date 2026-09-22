"""Phase 1 tool stubs for the specialist agents.

Deliberately simple in-memory lookups. Phase 2 replaces these with real
systems: a mock ticketing API, real log search, a DB query tool, and one
tool exposed over MCP (see DECISIONS.md #7).
"""

import string

# Short/common words excluded from matching — without this, "a" or "do" match
# almost every article and every query returns the whole knowledge base.
_STOPWORDS = {
    "a", "an", "the", "is", "are", "do", "does", "did", "i", "to", "of",
    "in", "on", "for", "my", "how", "and", "or", "it", "this", "that",
}

_KNOWLEDGE_BASE = [
    {
        "title": "Resetting a user's password",
        "content": "Go to Admin > Users > select the user > Reset Password. "
        "The user receives a reset email valid for 24 hours.",
    },
    {
        "title": "Configuring tax rates by region",
        "content": "Tax rates are set under Catalog > Tax Rules. Each region "
        "can have its own rate; changes take effect after the next catalog sync.",
    },
    {
        "title": "Understanding order status codes",
        "content": "PENDING -> PROCESSING -> SHIPPED -> DELIVERED. CANCELLED "
        "can only occur from PENDING or PROCESSING.",
    },
]

_LOGS = [
    "2026-09-20 10:12:03 ERROR OrderService: timeout calling PaymentGateway for order #4821",
    "2026-09-20 10:12:04 WARN  OrderService: retrying payment for order #4821 (attempt 2/3)",
    "2026-09-20 10:12:09 ERROR OrderService: timeout calling PaymentGateway for order #4821 (attempt 3/3, giving up)",
    "2026-09-21 08:45:17 INFO  InventoryService: stock sync completed for catalog EU-WEST",
    "2026-09-21 09:03:22 ERROR AuthService: invalid token for user_id=9911, session expired",
]


def _extract_terms(query: str) -> list[str]:
    words = (w.strip(string.punctuation) for w in query.lower().split())
    return [w for w in words if w and w not in _STOPWORDS]


def search_knowledge_base(query: str) -> list[str]:
    """Keyword-match the query against KB article titles and content."""
    terms = _extract_terms(query)
    return [
        f"{doc['title']}: {doc['content']}"
        for doc in _KNOWLEDGE_BASE
        if any(term in doc["title"].lower() or term in doc["content"].lower() for term in terms)
    ]


def search_logs(query: str) -> list[str]:
    """Keyword-match the query against recent log lines."""
    terms = _extract_terms(query)
    return [line for line in _LOGS if any(term in line.lower() for term in terms)]


def draft_escalation_summary(ticket_text: str, reasoning: str) -> str:
    """Build a human-readable summary for a ticket routed to escalation."""
    return (
        "ESCALATION REQUIRED\n"
        f"Ticket: {ticket_text}\n"
        f"Triage reasoning: {reasoning}\n"
        "Action: awaiting human review before anything is done."
    )
