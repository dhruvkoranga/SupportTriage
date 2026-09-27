"""The outer graph's single node: run one turn through the (uncheckpointed)
turn graph, then fold its final answer into the persisted conversation.
"""

from support_triage.planning_graph import build_turn_graph
from support_triage.state import ConversationState

_turn_graph = build_turn_graph()


def run_turn_node(state: ConversationState) -> dict:
    turn_result = _turn_graph.invoke(
        {"ticket_id": state["ticket_id"], "messages": state["messages"]}
    )
    return {"messages": [("ai", turn_result["final_summary"])]}
