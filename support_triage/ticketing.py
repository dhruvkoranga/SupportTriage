"""Mock ticketing API for the Escalation agent.

get_ticket (read) and add_internal_note (append-only) can be called freely —
neither has a side effect a human would need to approve. close_ticket and
issue_refund are destructive, and the Escalation agent NEVER calls them
directly: it only captures the model's requested tool call as a proposal.
The only code that actually invokes these two functions lives in
conversation.py, after a human approves via a LangGraph interrupt() —
see DECISIONS.md #14 for why that's a real code-level guardrail rather than
a prompt-level one, and #13 for why they didn't exist at all before Phase 4.

State lives only for the lifetime of one process — each CLI invocation
starts fresh. Fine for a demo; Phase 6 is where this would move to real
persistence if this were more than a learning project.
"""

from langchain_core.tools import tool

_TICKETS: dict[str, dict] = {
    "T-1001": {"subject": "Order #4821 payment failing", "status": "open", "notes": []},
    "T-1002": {"subject": "Refund request for order #55", "status": "open", "notes": []},
}


@tool
def get_ticket(ticket_id: str) -> str:
    """Fetch a ticket's subject, status, and internal notes by ticket ID."""
    ticket = _TICKETS.get(ticket_id)
    if ticket is None:
        return f"No ticket found with ID {ticket_id!r}."
    notes = "; ".join(ticket["notes"]) or "none"
    return f"Ticket {ticket_id}: subject={ticket['subject']!r}, status={ticket['status']}, notes={notes}"


@tool
def add_internal_note(ticket_id: str, note: str) -> str:
    """Append an internal note to a ticket. Does not change status or notify the customer."""
    ticket = _TICKETS.get(ticket_id)
    if ticket is None:
        return f"No ticket found with ID {ticket_id!r}."
    ticket["notes"].append(note)
    return f"Note added to ticket {ticket_id}."


@tool
def close_ticket(ticket_id: str, reason: str) -> str:
    """Mark a ticket as closed. DESTRUCTIVE — requires human approval before this runs."""
    ticket = _TICKETS.get(ticket_id)
    if ticket is None:
        return f"No ticket found with ID {ticket_id!r}."
    ticket["status"] = "closed"
    return f"Ticket {ticket_id} closed. Reason: {reason}"


@tool
def issue_refund(order_id: int | str, amount_usd: float, reason: str) -> str:
    """Issue a refund for an order. DESTRUCTIVE — requires human approval before this runs."""
    order_id = str(order_id)
    return f"Refund of ${amount_usd:.2f} issued for order {order_id}. Reason: {reason}"


DESTRUCTIVE_TOOLS = {"close_ticket": close_ticket, "issue_refund": issue_refund}
