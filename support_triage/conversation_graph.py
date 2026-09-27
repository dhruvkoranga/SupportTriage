"""Builds the outer, checkpointed conversation graph — the real top-level
entry point as of Phase 3 (see main.py). This is intentionally a single
node wrapping the inner turn graph; the only thing this graph itself
persists is conversation-level memory (see ConversationState in state.py).
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from support_triage.conversation import run_turn_node
from support_triage.state import ConversationState


def build_conversation_graph(checkpointer: BaseCheckpointSaver):
    graph = StateGraph(ConversationState)
    graph.add_node("run_turn", run_turn_node)
    graph.add_edge(START, "run_turn")
    graph.add_edge("run_turn", END)
    return graph.compile(checkpointer=checkpointer)
