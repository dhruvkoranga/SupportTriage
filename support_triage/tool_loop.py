"""A minimal ReAct-style tool-calling loop.

This is what LangGraph's prebuilt agent helpers do internally; written out
by hand here so the mechanics (call model -> execute requested tools ->
feed results back -> repeat) stay visible rather than hidden behind a
one-line prebuilt call. Used by the Diagnosis agent, which genuinely needs
the model to choose between tools; agents with a fixed procedure call their
tools directly instead (see DECISIONS.md #7).
"""

from langchain_core.messages import ToolMessage

_MAX_ITERATIONS = 4


def run_tool_loop(llm_with_tools, tools: list, messages: list) -> str:
    """Invoke llm_with_tools, executing any requested tools, until it gives a final answer."""
    tool_map = {t.name: t for t in tools}

    for _ in range(_MAX_ITERATIONS):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not getattr(response, "tool_calls", None):
            return response.content

        for call in response.tool_calls:
            result = tool_map[call["name"]].invoke(call["args"])
            messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    return "Reached the tool-call limit without a final answer."
