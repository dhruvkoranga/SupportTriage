"""Planning node, sub-task fan-out, and result aggregation for the outer graph.

The core Triage -> specialist pipeline (support_triage.graph) is reused
unchanged here as a black box, invoked once per sub-task (see DECISIONS.md
#11) — this module never touches TriageState's own nodes.
"""

from langgraph.types import Send
from pydantic import BaseModel, Field

from support_triage.graph import build_graph
from support_triage.llm import get_chat_model
from support_triage.state import PlanningState

PLAN_SYSTEM_PROMPT = (
    "You are the Planning agent for a support-ticket triage system. Break the customer's "
    "LATEST message into one or more independent sub-tasks that can each be triaged "
    "separately. Most messages are a single, atomic request — only split when the customer "
    "is clearly asking for more than one distinct thing. Use the earlier conversation (if "
    "any) to understand context for follow-ups, but only decompose the latest message. Each "
    "sub-task must be a self-contained sentence that makes sense on its own — restate "
    "specifics (order numbers, what's broken) rather than saying 'the other issue.' Preserve "
    "the original phrasing's mood: a question ('how do I reset a password?') must stay a "
    "question, not become a command ('reset a password') — rewording a question into an "
    "imperative changes how urgent or risky it sounds and can get it mis-triaged."
)

AGGREGATE_SYSTEM_PROMPT = (
    "You are combining the results of several sub-tasks handled separately for one support "
    "ticket into a single reply. Summarize what was found/done for each sub-task, clearly "
    "enough that the customer or reviewer understands the outcome of every part of their "
    "request."
)

_core_graph = build_graph()


class PlanningResult(BaseModel):
    sub_tasks: list[str] = Field(description="One or more self-contained sub-task descriptions.")


def plan_node(state: PlanningState) -> dict:
    llm = get_chat_model()
    structured_llm = llm.with_structured_output(PlanningResult)
    result: PlanningResult = structured_llm.invoke(
        [("system", PLAN_SYSTEM_PROMPT), *state["messages"]]
    )
    return {"sub_tasks": result.sub_tasks}


def route_subtasks(state: PlanningState) -> list[Send]:
    return [
        Send("run_subtask", {"ticket_text": sub_task, "ticket_id": state["ticket_id"]})
        for sub_task in state["sub_tasks"]
    ]


def run_subtask_node(state: dict) -> dict:
    """Runs the whole existing Triage -> specialist pipeline for one sub-task.

    Receives only the Send()-provided input (ticket_text, ticket_id), not the
    full PlanningState — this is a plain dict, not a PlanningState, by design.
    """
    core_result = _core_graph.invoke(
        {"ticket_text": state["ticket_text"], "ticket_id": state["ticket_id"]}
    )
    return {
        "subtask_results": [
            {
                "sub_task": state["ticket_text"],
                "category": core_result["category"],
                "agent_output": core_result["agent_output"],
            }
        ],
        "proposed_actions": core_result.get("proposed_actions") or [],
    }


def aggregate_node(state: PlanningState) -> dict:
    results = state["subtask_results"]

    if len(results) == 1:
        final_summary = results[0]["agent_output"]
    else:
        findings = "\n\n".join(
            f"Sub-task: {r['sub_task']}\nCategory: {r['category']}\nResult: {r['agent_output']}"
            for r in results
        )
        llm = get_chat_model()
        response = llm.invoke([("system", AGGREGATE_SYSTEM_PROMPT), ("human", findings)])
        final_summary = response.content

    return {"final_summary": final_summary}
