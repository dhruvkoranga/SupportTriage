"""Shared state schemas for the triage LangGraph pipelines."""

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages

Category = Literal["research", "diagnosis", "escalation"]


class ProposedAction(TypedDict):
    """A destructive tool call the Escalation agent wants to make, captured
    but never executed until a human approves it (see DECISIONS.md #14)."""

    sub_task: str
    tool: str
    args: dict
    reason: str


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
    proposed_actions: list[ProposedAction]
    tool_trace: list[str]


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
    proposed_actions: Annotated[list[ProposedAction], operator.add]
    final_summary: str


class ConversationState(TypedDict, total=False):
    """State for the outer, checkpointed graph — the real multi-turn memory.

    ``pending_summary``/``pending_actions`` are NOT reducer fields — each
    turn's run_pipeline_node plainly overwrites them, so unlike PlanningState
    (see its docstring), there's no accumulation-across-turns risk here.
    They exist to let the graph split into two nodes: run_pipeline_node
    (expensive, calls the LLM pipeline) and approve_and_finalize_node (calls
    interrupt()). On resume, LangGraph only re-runs the node that actually
    called interrupt() — if both steps lived in one node, resuming would
    silently re-run the entire expensive pipeline from scratch just to reach
    the interrupt() call again (found live — see DECISIONS.md #14).
    """

    ticket_id: str
    messages: Annotated[list, add_messages]
    pending_summary: str
    pending_actions: list[ProposedAction]
