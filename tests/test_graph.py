from types import SimpleNamespace

import support_triage.agents as agents_module
from support_triage.agents import TriageClassification
from support_triage.graph import build_graph


class _FakeChatModel:
    """Stands in for a real chat model so graph tests don't hit the network."""

    def __init__(self, structured_result, text_content=None, tool_loop_responses=None):
        self._structured_result = structured_result
        self._text_content = text_content
        self._tool_loop_responses = list(tool_loop_responses or [])

    def with_structured_output(self, _schema):
        return SimpleNamespace(invoke=lambda _messages: self._structured_result)

    def invoke(self, _messages):
        return SimpleNamespace(content=self._text_content)

    def bind_tools(self, _tools):
        return SimpleNamespace(invoke=lambda _messages: self._tool_loop_responses.pop(0))


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


def test_graph_routes_escalation_ticket_and_uses_ticketing_tool(monkeypatch):
    fake_llm = _FakeChatModel(
        structured_result=TriageClassification(category="escalation", reasoning="refund request"),
        text_content="Human review needed before this refund proceeds.",
    )
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_llm)

    graph = build_graph()
    result = graph.invoke(
        {"ticket_text": "Please refund and cancel order #55", "ticket_id": "T-1001"}
    )

    assert result["category"] == "escalation"
    assert result["agent_output"] == "Human review needed before this refund proceeds."


def test_graph_routes_diagnosis_ticket_through_tool_loop(monkeypatch):
    tool_call = SimpleNamespace(
        content="",
        tool_calls=[{"name": "query_order_status", "args": {"order_id": "4821"}, "id": "c1"}],
    )
    final = SimpleNamespace(content="Order 4821 is stuck in PROCESSING.", tool_calls=[])
    fake_llm = _FakeChatModel(
        structured_result=TriageClassification(category="diagnosis", reasoning="bug report"),
        tool_loop_responses=[tool_call, final],
    )
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_llm)

    graph = build_graph()
    result = graph.invoke({"ticket_text": "Order 4821 seems stuck, what's wrong?"})

    assert result["category"] == "diagnosis"
    assert result["agent_output"] == "Order 4821 is stuck in PROCESSING."
