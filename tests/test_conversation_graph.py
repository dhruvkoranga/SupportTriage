from types import SimpleNamespace

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

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


def test_conversation_graph_pauses_and_executes_only_after_approval(monkeypatch):
    proposed_action = {
        "sub_task": "close it",
        "tool": "close_ticket",
        "args": {"ticket_id": "T-1001", "reason": "resolved"},
        "reason": "resolved",
    }
    pipeline_calls = []

    def fake_invoke(_state):
        pipeline_calls.append(1)
        return {
            "final_summary": "Proposing to close the ticket.",
            "proposed_actions": [proposed_action],
        }

    monkeypatch.setattr(conversation_module, "_turn_graph", SimpleNamespace(invoke=fake_invoke))

    calls = []
    fake_tool = SimpleNamespace(invoke=lambda args: calls.append(args) or "Ticket closed.")
    monkeypatch.setattr(conversation_module, "DESTRUCTIVE_TOOLS", {"close_ticket": fake_tool})

    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_conversation_graph(checkpointer)
        config = {"configurable": {"thread_id": "t1"}}

        graph.invoke({"ticket_id": "T-1001", "messages": [("human", "close it")]}, config)
        snapshot = graph.get_state(config)
        assert snapshot.next  # paused, awaiting approval

        payload = snapshot.tasks[0].interrupts[0].value
        assert payload["proposed_actions"] == [proposed_action]
        assert calls == []  # not executed yet, just because a proposal exists

        # {"approved": True}, not a bare True — see conversation.py's run_turn_node
        # for why Command(resume=<bare bool>) doesn't work in this LangGraph version.
        result = graph.invoke(Command(resume={"approved": True}), config)

    # Regression test for a real bug: the first version had both the expensive
    # pipeline call and interrupt() in ONE node, so resuming re-ran the whole
    # pipeline again (extra LLM cost, and risked a different, non-deterministic
    # answer than what the human actually approved). Splitting into two nodes
    # means only the interrupted node re-executes on resume — the pipeline
    # runs exactly once, no matter how the human responds (see DECISIONS.md #14).
    assert len(pipeline_calls) == 1
    assert calls == [{"ticket_id": "T-1001", "reason": "resolved"}]
    assert "Ticket closed." in result["messages"][-1].content


def test_conversation_graph_skips_execution_when_rejected(monkeypatch):
    proposed_action = {
        "sub_task": "refund",
        "tool": "issue_refund",
        "args": {"order_id": "55", "amount_usd": 10.0, "reason": "duplicate charge"},
        "reason": "duplicate charge",
    }
    fake_turn_graph = SimpleNamespace(
        invoke=lambda _state: {
            "final_summary": "Proposing a refund.",
            "proposed_actions": [proposed_action],
        }
    )
    monkeypatch.setattr(conversation_module, "_turn_graph", fake_turn_graph)

    calls = []
    fake_tool = SimpleNamespace(invoke=lambda args: calls.append(args) or "should not happen")
    monkeypatch.setattr(conversation_module, "DESTRUCTIVE_TOOLS", {"issue_refund": fake_tool})

    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_conversation_graph(checkpointer)
        config = {"configurable": {"thread_id": "t2"}}

        graph.invoke({"ticket_id": "T-1002", "messages": [("human", "refund me")]}, config)
        result = graph.invoke(Command(resume={"approved": False}), config)

    assert calls == []
    assert "not approved" in result["messages"][-1].content.lower()


def test_command_resume_with_bare_false_is_a_known_langgraph_pitfall():
    """Not a bug in our code — documents a real finding: this LangGraph version's
    map_command checks `if cmd.resume:` (truthy), so Command(resume=False) is
    silently treated as no resume value at all (yields zero writes). This is
    why run_turn_node expects {"approved": bool}, never a bare bool. If this
    test ever fails, LangGraph fixed the upstream bug and the workaround in
    conversation.py/main.py can be simplified back to a bare bool."""
    from langgraph.pregel.io import map_command

    assert list(map_command(Command(resume=False))) == []
    assert list(map_command(Command(resume={"approved": False}))) != []
