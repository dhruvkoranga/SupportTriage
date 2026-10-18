"""Shared turn/approval logic for the conversation graph.

Used by both the CLI (main.py) and the FastAPI backend (api.py) so there's
exactly one place that knows how to detect a pending interrupt and resume
it — previously duplicated between the two, this is the single source of
truth for "how do you drive this graph."
"""

from dataclasses import dataclass
from typing import Literal

from langgraph.types import Command


@dataclass
class TurnOutcome:
    status: Literal["completed", "pending_approval"]
    reply: str | None = None
    draft_summary: str | None = None
    proposed_actions: list[dict] | None = None


def _outcome_from_state(graph, config: dict, result: dict) -> TurnOutcome:
    snapshot = graph.get_state(config)
    if snapshot.next:
        payload = snapshot.tasks[0].interrupts[0].value
        return TurnOutcome(
            status="pending_approval",
            draft_summary=payload["draft_summary"],
            proposed_actions=payload["proposed_actions"],
        )
    return TurnOutcome(status="completed", reply=result["messages"][-1].content)


def send_message(graph, config: dict, ticket_id: str, text: str) -> TurnOutcome:
    result = graph.invoke({"ticket_id": ticket_id, "messages": [("human", text)]}, config)
    return _outcome_from_state(graph, config, result)


def submit_approval(graph, config: dict, approved: bool) -> TurnOutcome:
    # {"approved": bool}, not a bare bool — Command(resume=False) is silently
    # dropped by this LangGraph version (see DECISIONS.md #16).
    result = graph.invoke(Command(resume={"approved": approved}), config)
    return _outcome_from_state(graph, config, result)
