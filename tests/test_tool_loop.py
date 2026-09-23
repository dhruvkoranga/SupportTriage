from types import SimpleNamespace

from langchain_core.tools import tool

from support_triage.tool_loop import run_tool_loop


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


class _ScriptedLLM:
    """Returns pre-scripted responses in order — stands in for a real chat model."""

    def __init__(self, responses):
        self._responses = list(responses)

    def invoke(self, _messages):
        return self._responses.pop(0)


def test_run_tool_loop_executes_requested_tool_then_returns_final_answer():
    tool_call_response = SimpleNamespace(
        content="", tool_calls=[{"name": "add", "args": {"a": 2, "b": 3}, "id": "call_1"}]
    )
    final_response = SimpleNamespace(content="The answer is 5.", tool_calls=[])
    llm = _ScriptedLLM([tool_call_response, final_response])

    result = run_tool_loop(llm, [add], messages=[])

    assert result == "The answer is 5."


def test_run_tool_loop_returns_immediately_if_no_tool_call_requested():
    final_response = SimpleNamespace(content="No tool needed.", tool_calls=[])
    llm = _ScriptedLLM([final_response])

    result = run_tool_loop(llm, [add], messages=[])

    assert result == "No tool needed."


def test_run_tool_loop_gives_up_after_max_iterations():
    tool_call_response = SimpleNamespace(
        content="", tool_calls=[{"name": "add", "args": {"a": 1, "b": 1}, "id": "call_x"}]
    )
    llm = _ScriptedLLM([tool_call_response] * 4)

    result = run_tool_loop(llm, [add], messages=[])

    assert "tool-call limit" in result.lower()
