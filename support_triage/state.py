"""Shared state schemas for the triage LangGraph pipelines."""

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages

Category = Literal["research", "diagnosis", "escalation"]


class TriageState(TypedDict, total=False):
    """State for the core single-ticket pipeline (Triage -> one specialist).

    ``total=False`` because each node returns only the keys it updates;
    LangGraph merges that partial dict into the running state. Unchanged
    since Phase 1/2 — the Phase 3 planning graph reuses this pipeline as a
    black box, once per sub-task (see DECISIONS.md #11).
    """

    ticket_text: str
    ticket_id: str
    category: Category
    classification_reasoning: str
    agent_output: str


class SubtaskResult(TypedDict):
    sub_task: str
    category: Category
    agent_output: str


class PlanningState(TypedDict, total=False):
    """State for the inner, per-turn "turn graph": plan -> fan-out -> aggregate.

    This graph is compiled WITHOUT a checkpointer and invoked fresh on every
    conversation turn (see conversation_graph.py) — that's deliberate.
    ``subtask_results`` needs ``operator.add`` to merge concurrent fan-out
    branches within one turn, but a reducer field never resets on its own;
    if this state were checkpointed across turns, one turn's leftover
    subtask_results would silently bleed into the next turn's aggregation
    (found live — see DECISIONS.md #12). Keeping this graph stateless
    between calls sidesteps that entirely: there's nothing to leak because
    nothing persists.

    ``messages`` here is conversation history handed in as plain input by
    the outer conversation graph (read-only context for planning), not
    something this graph accumulates on its own.
    """

    ticket_id: str
    messages: Annotated[list, add_messages]
    sub_tasks: list[str]
    subtask_results: Annotated[list[SubtaskResult], operator.add]
    final_summary: str


class ConversationState(TypedDict, total=False):
    """State for the outer, checkpointed graph — the real multi-turn memory.

    Deliberately minimal: only what should actually persist for the life of
    a conversation. Per-turn scratch work (sub_tasks, subtask_results) stays
    out of this schema entirely — see PlanningState's docstring.
    """

    ticket_id: str
    messages: Annotated[list, add_messages]
