from types import SimpleNamespace

import support_triage.agents as agents_module
import support_triage.planning as planning_module
from support_triage.agents import TriageClassification
from support_triage.planning import PlanningResult
from support_triage.planning_graph import build_turn_graph


def test_turn_graph_single_subtask_skips_aggregate_llm_call(monkeypatch):
    fake_plan_llm = SimpleNamespace(
        with_structured_output=lambda _schema: SimpleNamespace(
            invoke=lambda _messages: PlanningResult(sub_tasks=["a single question"])
        ),
    )
    monkeypatch.setattr(planning_module, "get_chat_model", lambda: fake_plan_llm)

    fake_agent_llm = SimpleNamespace(
        with_structured_output=lambda _schema: SimpleNamespace(
            invoke=lambda _messages: TriageClassification(category="research", reasoning="how-to")
        ),
        invoke=lambda _messages: SimpleNamespace(content="the answer"),
    )
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_agent_llm)

    graph = build_turn_graph()
    result = graph.invoke({"ticket_id": "T-1001", "messages": [("human", "one question")]})

    assert len(result["subtask_results"]) == 1
    assert result["final_summary"] == "the answer"


def test_turn_graph_fans_out_over_multiple_subtasks(monkeypatch):
    fake_plan_llm = SimpleNamespace(
        with_structured_output=lambda _schema: SimpleNamespace(
            invoke=lambda _messages: PlanningResult(sub_tasks=["question one", "question two"])
        ),
        invoke=lambda _messages: SimpleNamespace(content="combined answer"),
    )
    monkeypatch.setattr(planning_module, "get_chat_model", lambda: fake_plan_llm)

    fake_agent_llm = SimpleNamespace(
        with_structured_output=lambda _schema: SimpleNamespace(
            invoke=lambda _messages: TriageClassification(category="research", reasoning="how-to")
        ),
        invoke=lambda _messages: SimpleNamespace(content="an answer"),
    )
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_agent_llm)

    graph = build_turn_graph()
    result = graph.invoke({"ticket_id": "T-1001", "messages": [("human", "two things")]})

    assert len(result["subtask_results"]) == 2
    assert result["final_summary"] == "combined answer"
