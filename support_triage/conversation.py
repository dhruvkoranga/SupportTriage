"""The outer graph's two nodes for one turn: run the (uncheckpointed) turn
graph, then — separately — pause for human approval if it proposed a
destructive action.

Split into two nodes deliberately, not combined into one (see
ConversationState's docstring in state.py): interrupt()/resume only
re-executes the node that actually called interrupt(), so keeping the
expensive pipeline call in its own earlier node means resuming after a
human decision doesn't silently re-run the whole multi-agent pipeline
again — found live, the first version paid for a second full pipeline run
(and risked a different, non-deterministic answer) on every approval
(see DECISIONS.md #14). interrupt() itself is still called directly in a
node of the checkpointed graph, not nested inside a black-box .invoke() —
that placement is unrelated and still required (see DECISIONS.md #14).
"""

from langgraph.types import interrupt

from support_triage.planning_graph import build_turn_graph
from support_triage.state import ConversationState
from support_triage.ticketing import DESTRUCTIVE_TOOLS

_turn_graph = build_turn_graph()


def _execute_approved_actions(proposed_actions: list[dict]) -> str:
    results = [DESTRUCTIVE_TOOLS[a["tool"]].invoke(a["args"]) for a in proposed_actions]
    return "\n".join(results)


def run_pipeline_node(state: ConversationState) -> dict:
    turn_result = _turn_graph.invoke(
        {"ticket_id": state["ticket_id"], "messages": state["messages"]}
    )
    return {
        "pending_summary": turn_result["final_summary"],
        "pending_actions": turn_result.get("proposed_actions") or [],
    }


def approve_and_finalize_node(state: ConversationState) -> dict:
    final_summary = state["pending_summary"]
    proposed_actions = state.get("pending_actions") or []

    if not proposed_actions:
        return {"messages": [("ai", final_summary)]}

    # resume must be a truthy value in this LangGraph version — Command(resume=False)
    # is silently dropped (map_command checks `if cmd.resume:`, not `is not None`),
    # so the caller resumes with {"approved": bool} rather than a bare bool.
    decision = interrupt({"draft_summary": final_summary, "proposed_actions": proposed_actions})
    approved = decision["approved"]

    if approved:
        outcome = _execute_approved_actions(proposed_actions)
        final_summary = f"{final_summary}\n\n{outcome}"
    else:
        final_summary = f"{final_summary}\n\nProposed action(s) were not approved — no changes were made."

    return {"messages": [("ai", final_summary)]}
