"""Shared state schema for the triage LangGraph pipeline."""

from typing import Literal, TypedDict

Category = Literal["research", "diagnosis", "escalation"]


class TriageState(TypedDict, total=False):
    """State threaded through every node in the graph.

    ``total=False`` because each node returns only the keys it updates;
    LangGraph merges that partial dict into the running state.
    """

    ticket_text: str
    ticket_id: str
    category: Category
    classification_reasoning: str
    agent_output: str
