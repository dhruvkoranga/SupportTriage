"""Builds the compiled LangGraph pipeline: Triage -> {Research, Diagnosis, Escalation}."""

from langgraph.graph import END, START, StateGraph

from support_triage.agents import (
    diagnosis_node,
    escalation_node,
    research_node,
    route_after_triage,
    triage_node,
)
from support_triage.state import TriageState


def build_graph():
    graph = StateGraph(TriageState)

    graph.add_node("triage", triage_node)
    graph.add_node("research", research_node)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("escalation", escalation_node)

    graph.add_edge(START, "triage")
    graph.add_conditional_edges(
        "triage",
        route_after_triage,
        {"research": "research", "diagnosis": "diagnosis", "escalation": "escalation"},
    )
    graph.add_edge("research", END)
    graph.add_edge("diagnosis", END)
    graph.add_edge("escalation", END)

    return graph.compile()
