"""Builds the outer, checkpointed conversation graph — the real top-level
entry point as of Phase 3 (see main.py). Two nodes, not one — see
conversation.py's module docstring for why the split matters for resume.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from support_triage.conversation import approve_and_finalize_node, run_pipeline_node
from support_triage.state import ConversationState


def build_conversation_graph(checkpointer: BaseCheckpointSaver):
    graph = StateGraph(ConversationState)
    graph.add_node("run_pipeline", run_pipeline_node)
    graph.add_node("approve_and_finalize", approve_and_finalize_node)
    graph.add_edge(START, "run_pipeline")
    graph.add_edge("run_pipeline", "approve_and_finalize")
    graph.add_edge("approve_and_finalize", END)
    return graph.compile(checkpointer=checkpointer)
