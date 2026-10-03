"""Trajectory evaluation: did the Diagnosis agent call the right tool(s)?

"Trajectory evaluation for the agent (did it call the right tools, in the
right order?)" from the project brief. Diagnosis is the only agent with a
genuine tool-calling loop (see DECISIONS.md #10), so it's the only one with
a trajectory worth checking — Research and Escalation call their tools
directly in fixed code, not by model choice.

Manual eval, not part of the pytest suite: calls a real LLM, is
non-deterministic, and takes several seconds per case. Run directly:
    python -m evals.trajectory_eval
"""

from dataclasses import dataclass

from support_triage.graph import build_graph

_graph = build_graph()


@dataclass
class TrajectoryCase:
    ticket_text: str
    expected_tools: set[str]


CASES = [
    TrajectoryCase("What is the status of order 4821?", {"query_order_status"}),
    TrajectoryCase(
        "Order 4821 payments keep timing out, what's going on?", {"search_logs"}
    ),
    TrajectoryCase(
        "What's the status of order 55, and are there any related errors in the logs?",
        {"query_order_status", "search_logs"},
    ),
]


def run() -> None:
    passed = 0
    for case in CASES:
        result = _graph.invoke({"ticket_text": case.ticket_text})
        actual_tools = set(result.get("tool_trace", []))
        # Subset check, not exact match: a local model may reasonably make an
        # extra exploratory call. What matters is it didn't skip a tool it
        # clearly needed.
        ok = case.expected_tools.issubset(actual_tools)
        passed += ok

        print(f"[{'PASS' if ok else 'FAIL'}] {case.ticket_text!r}")
        print(f"         category:        {result.get('category')}")
        print(f"         expected subset: {sorted(case.expected_tools)}")
        print(f"         actual trace:    {result.get('tool_trace', [])}")
        print()

    print(f"{passed}/{len(CASES)} trajectory cases passed.")


if __name__ == "__main__":
    run()
