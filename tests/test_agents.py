from support_triage.agents import escalation_node, route_after_triage


def test_route_after_triage_returns_category():
    for category in ("research", "diagnosis", "escalation"):
        assert route_after_triage({"category": category}) == category


def test_escalation_node_drafts_summary_without_calling_llm():
    state = {
        "ticket_text": "Please cancel and refund order #123",
        "classification_reasoning": "refund request",
    }
    result = escalation_node(state)
    assert "ESCALATION REQUIRED" in result["agent_output"]
    assert "order #123" in result["agent_output"]
