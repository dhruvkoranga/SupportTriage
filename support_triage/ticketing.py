"""Mock ticketing API for the Escalation agent.

Deliberately exposes only read (get_ticket) and a reversible write
(add_internal_note) — no close_ticket or refund tool exists yet. Those are
destructive/high-risk actions that Phase 4's human-approval gate is meant to
guard; adding them before that gate exists would leave a window where the
agent could act unsupervised (see DECISIONS.md #7).

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
