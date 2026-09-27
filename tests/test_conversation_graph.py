from types import SimpleNamespace

from langgraph.checkpoint.sqlite import SqliteSaver

import support_triage.conversation as conversation_module
from support_triage.conversation_graph import build_conversation_graph


def test_conversation_graph_persists_messages_across_turns(monkeypatch):
    fake_turn_graph = SimpleNamespace(
        invoke=lambda state: {"final_summary": f"reply to: {state['messages'][-1].content}"}
    )
    monkeypatch.setattr(conversation_module, "_turn_graph", fake_turn_graph)

    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_conversation_graph(checkpointer)
        config = {"configurable": {"thread_id": "test-thread"}}

        r1 = graph.invoke({"ticket_id": "T-1001", "messages": [("human", "first")]}, config)
        assert r1["messages"][-1].content == "reply to: first"

        r2 = graph.invoke({"ticket_id": "T-1001", "messages": [("human", "second")]}, config)
        assert len(r2["messages"]) == 4
        assert r2["messages"][-1].content == "reply to: second"


def test_conversation_graph_does_not_leak_scratch_state_across_turns(monkeypatch):
    """Regression test for a real bug: subtask_results (per-turn scratch state)
    used to live in the checkpointed schema and silently accumulated across
    turns via its operator.add reducer, so turn 2's aggregation saw turn 1's
    leftover results too. Fixed by moving scratch state into an inner,
    uncheckpointed turn graph — see state.py's PlanningState docstring.
    """
    seen_message_counts = []

    def fake_invoke(state):
        seen_message_counts.append(len(state["messages"]))
        return {"final_summary": "ok"}

    monkeypatch.setattr(conversation_module, "_turn_graph", SimpleNamespace(invoke=fake_invoke))

    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_conversation_graph(checkpointer)
        config = {"configurable": {"thread_id": "test-thread"}}

        graph.invoke({"ticket_id": "T-1001", "messages": [("human", "first")]}, config)
        graph.invoke({"ticket_id": "T-1001", "messages": [("human", "second")]}, config)

    # Turn 1: just the human message (1). Turn 2: turn 1's human+ai plus the
    # new human message (3). Growing message history is correct and expected
    # — what matters is there's no separate scratch-state channel to leak.
    assert seen_message_counts == [1, 3]
