from types import SimpleNamespace

import support_triage.conversation as conversation_module


def test_run_turn_node_wraps_final_summary_into_messages(monkeypatch):
    fake_turn_graph = SimpleNamespace(invoke=lambda _input: {"final_summary": "the answer"})
    monkeypatch.setattr(conversation_module, "_turn_graph", fake_turn_graph)

    result = conversation_module.run_turn_node(
        {"ticket_id": "T-1001", "messages": [("human", "hello")]}
    )

    assert result == {"messages": [("ai", "the answer")]}
