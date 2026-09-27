from types import SimpleNamespace

import support_triage.agents as agents_module
import support_triage.planning as planning_module
from support_triage.agents import TriageClassification
from support_triage.planning import (
    PlanningResult,
    aggregate_node,
    plan_node,
    route_subtasks,
    run_subtask_node,
)


def test_route_subtasks_sends_one_task_per_subtask():
    state = {"sub_tasks": ["task one", "task two"], "ticket_id": "T-1001"}
    sends = route_subtasks(state)

    assert len(sends) == 2
    assert all(send.node == "run_subtask" for send in sends)
    assert [send.arg["ticket_text"] for send in sends] == ["task one", "task two"]
    assert all(send.arg["ticket_id"] == "T-1001" for send in sends)


def test_plan_node_uses_structured_output(monkeypatch):
    fake_llm = SimpleNamespace(
        with_structured_output=lambda _schema: SimpleNamespace(
            invoke=lambda _messages: PlanningResult(sub_tasks=["a", "b"])
        )
    )
    monkeypatch.setattr(planning_module, "get_chat_model", lambda: fake_llm)

    result = plan_node({"messages": [("human", "do two things")]})

    assert result["sub_tasks"] == ["a", "b"]


def test_run_subtask_node_wraps_core_graph_result(monkeypatch):
    fake_llm = SimpleNamespace(
        with_structured_output=lambda _schema: SimpleNamespace(
            invoke=lambda _messages: TriageClassification(category="research", reasoning="how-to")
        ),
        invoke=lambda _messages: SimpleNamespace(content="Here's how."),
    )
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_llm)

    result = run_subtask_node({"ticket_text": "How do I do X?", "ticket_id": "T-1001"})

    assert result["subtask_results"] == [
        {"sub_task": "How do I do X?", "category": "research", "agent_output": "Here's how."}
    ]


def test_aggregate_node_single_result_skips_llm_call():
    state = {
        "subtask_results": [{"sub_task": "a", "category": "research", "agent_output": "the answer"}]
    }
    result = aggregate_node(state)
    assert result["final_summary"] == "the answer"


def test_aggregate_node_multiple_results_synthesizes_via_llm(monkeypatch):
    fake_llm = SimpleNamespace(invoke=lambda _messages: SimpleNamespace(content="combined reply"))
    monkeypatch.setattr(planning_module, "get_chat_model", lambda: fake_llm)

    state = {
        "subtask_results": [
            {"sub_task": "a", "category": "research", "agent_output": "answer a"},
            {"sub_task": "b", "category": "diagnosis", "agent_output": "answer b"},
        ]
    }
    result = aggregate_node(state)
    assert result["final_summary"] == "combined reply"
