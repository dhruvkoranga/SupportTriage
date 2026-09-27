from types import SimpleNamespace

import support_triage.agents as agents_module
from support_triage.agents import diagnosis_node, escalation_node, route_after_triage
from support_triage.ticketing import _TICKETS


def test_route_after_triage_returns_category():
    for category in ("research", "diagnosis", "escalation"):
        assert route_after_triage({"category": category}) == category


def test_escalation_node_uses_ticket_record_and_logs_a_note(monkeypatch):
    no_proposal = SimpleNamespace(content="", tool_calls=[])
    summary = SimpleNamespace(content="Human review needed.")
    fake_llm = _ScriptedToolLLM([no_proposal, summary])
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_llm)

    notes_before = len(_TICKETS["T-1001"]["notes"])
    result = escalation_node(
        {
            "ticket_text": "Please cancel and refund order #123",
            "ticket_id": "T-1001",
            "classification_reasoning": "refund request",
        }
    )

    assert result["agent_output"] == "Human review needed."
    assert result["proposed_actions"] == []
    assert len(_TICKETS["T-1001"]["notes"]) == notes_before + 1
    assert "refund request" in _TICKETS["T-1001"]["notes"][-1]


def test_escalation_node_captures_proposed_action_without_executing_it(monkeypatch):
    proposal = SimpleNamespace(
        content="",
        tool_calls=[
            {
                "name": "issue_refund",
                "args": {"order_id": "55", "amount_usd": 20.0, "reason": "duplicate charge"},
                "id": "c1",
            }
        ],
    )
    summary = SimpleNamespace(content="Refund proposed, awaiting approval.")
    fake_llm = _ScriptedToolLLM([proposal, summary])
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_llm)

    result = escalation_node(
        {
            "ticket_text": "Please refund order #55, I was double charged",
            "ticket_id": "T-1002",
            "classification_reasoning": "refund request",
        }
    )

    assert result["proposed_actions"] == [
        {
            "sub_task": "Please refund order #55, I was double charged",
            "tool": "issue_refund",
            "args": {"order_id": "55", "amount_usd": 20.0, "reason": "duplicate charge"},
            "reason": "refund request",
        }
    ]


def test_escalation_node_never_directly_invokes_destructive_tools(monkeypatch):
    """The actual guardrail claim, tested rather than just asserted in a comment:
    escalation_node captures a requested tool call as data — it never calls
    .invoke() on the real tool. Only conversation.run_turn_node does that,
    after a human approves (see DECISIONS.md #14). Verified via the tool's
    real side effect (ticket status), since a LangChain StructuredTool is a
    Pydantic model and can't have .invoke monkeypatched directly."""
    proposal = SimpleNamespace(
        content="",
        tool_calls=[
            {"name": "close_ticket", "args": {"ticket_id": "T-1001", "reason": "resolved"}, "id": "c1"}
        ],
    )
    summary = SimpleNamespace(content="Closing proposed.")
    fake_llm = _ScriptedToolLLM([proposal, summary])
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_llm)

    escalation_node(
        {
            "ticket_text": "Please close this ticket",
            "ticket_id": "T-1001",
            "classification_reasoning": "resolved",
        }
    )

    assert _TICKETS["T-1001"]["status"] == "open"


class _ScriptedToolLLM:
    """Fakes both .bind_tools() (returns self) and scripted .invoke() responses."""

    def __init__(self, responses):
        self._responses = list(responses)

    def bind_tools(self, _tools):
        return self

    def invoke(self, _messages):
        return self._responses.pop(0)


def test_diagnosis_node_executes_requested_tool_and_returns_final_answer(monkeypatch):
    tool_call = SimpleNamespace(
        content="", tool_calls=[{"name": "query_order_status", "args": {"order_id": "4821"}, "id": "c1"}]
    )
    final = SimpleNamespace(content="Order 4821 is stuck in PROCESSING.", tool_calls=[])
    fake_llm = _ScriptedToolLLM([tool_call, final])
    monkeypatch.setattr(agents_module, "get_chat_model", lambda: fake_llm)

    result = diagnosis_node({"ticket_text": "What's happening with order 4821?"})

    assert result["agent_output"] == "Order 4821 is stuck in PROCESSING."
