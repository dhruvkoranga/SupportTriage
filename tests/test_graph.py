from types import SimpleNamespace

import support_triage.agents as agents_module
from support_triage.agents import TriageClassification
from support_triage.graph import build_graph


class _FakeChatModel:
    """Stands in for a real chat model so graph tests don't hit the network."""

    def __init__(self, structured_result, text_content):
        self._structured_result = structured_result
        self._text_content = text_content

    def with_structured_output(self, _schema):
        return SimpleNamespace(invoke=lambda _messages: self._structured_result)

    def invoke(self, _messages):
        return SimpleNamespace(content=self._text_content)


def test_graph_routes_research_ticket_to_research_node(monkeypatch):
    fake_llm = _FakeChatModel(
        structured_result=TriageClassification(category="research", reasoning="how-to question"),
        text_content="Here is how you do it.",
    )
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_llm)

    graph = build_graph()
    result = graph.invoke({"ticket_text": "How do I reset a password?"})

    assert result["category"] == "research"
    assert result["agent_output"] == "Here is how you do it."


def test_graph_routes_escalation_ticket_without_llm_draft(monkeypatch):
    fake_llm = _FakeChatModel(
        structured_result=TriageClassification(category="escalation", reasoning="refund request"),
        text_content="unused",
    )
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_llm)

    graph = build_graph()
    result = graph.invoke({"ticket_text": "Please refund and cancel order #55"})

    assert result["category"] == "escalation"
    assert "ESCALATION REQUIRED" in result["agent_output"]
