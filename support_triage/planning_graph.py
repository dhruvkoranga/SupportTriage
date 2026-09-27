"""Builds the inner, per-turn "turn graph": Plan -> fan-out -> Aggregate.

Deliberately uncompiled with no checkpointer — see PlanningState's docstring
in state.py for why. conversation_graph.py wraps this as a single node in
the outer, checkpointed graph that owns actual multi-turn memory.
"""

from langgraph.graph import END, START, StateGraph

from support_triage.planning import aggregate_node, plan_node, route_subtasks, run_subtask_node
from support_triage.state import PlanningState


def build_turn_graph():
    graph = StateGraph(PlanningState)

    graph.add_node("plan", plan_node)
    graph.add_node("run_subtask", run_subtask_node)
    graph.add_node("aggregate", aggregate_node)

    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", route_subtasks)
    graph.add_edge("run_subtask", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()
