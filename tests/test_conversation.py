from types import SimpleNamespace

import support_triage.conversation as conversation_module


def test_run_pipeline_node_stages_summary_and_actions(monkeypatch):
    fake_turn_graph = SimpleNamespace(
        invoke=lambda _input: {"final_summary": "the answer", "proposed_actions": []}
    )
    monkeypatch.setattr(conversation_module, "_turn_graph", fake_turn_graph)

    result = conversation_module.run_pipeline_node(
        {"ticket_id": "T-1001", "messages": [("human", "hello")]}
    )

    assert result == {"pending_summary": "the answer", "pending_actions": []}


def test_approve_and_finalize_node_skips_interrupt_when_no_actions_pending():
    result = conversation_module.approve_and_finalize_node(
        {"pending_summary": "the answer", "pending_actions": []}
    )

    assert result == {"messages": [("ai", "the answer")]}
