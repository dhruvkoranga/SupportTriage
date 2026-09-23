"""Triage agent and the three specialist agents it routes to."""

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from support_triage.db import query_order_status
from support_triage.llm import get_chat_model
from support_triage.mcp_integration.client import search_logs_via_mcp
from support_triage.state import Category, TriageState
from support_triage.ticketing import add_internal_note, get_ticket
from support_triage.tool_loop import run_tool_loop
from support_triage.tools import search_knowledge_base

TRIAGE_SYSTEM_PROMPT = """You triage incoming support tickets for an e-commerce platform. \
Classify each ticket into exactly one category:
- research: a how-to or documentation question; nothing is broken
- diagnosis: something is broken or behaving unexpectedly and needs investigation
- escalation: a high-risk request (cancel, refund, delete) or anything urgent enough \
to need a human before acting"""

RESEARCH_SYSTEM_PROMPT = (
    "You are the Research agent. Answer the user's question using only the knowledge "
    "base excerpts below. If nothing relevant was found, say so plainly."
)

DIAGNOSIS_SYSTEM_PROMPT = (
    "You are the Diagnosis agent. You have two tools: search_logs (recent system logs) "
    "and query_order_status (the orders database). Use whichever are relevant to "
    "investigate the ticket — extract IDs like an order number from the ticket text "
    "yourself. Explain what you found in plain language. If nothing relevant turned up, "
    "say so; don't guess."
)

ESCALATION_SYSTEM_PROMPT = (
    "You are the Escalation agent. This ticket has been flagged as high-risk and "
    "requires human approval before any action is taken (e.g. cancelling an order or "
    "issuing a refund). Using the ticket system record below, write a concise summary "
    "for the human reviewer: what the customer wants, why it was escalated, and what "
    "decision they need to make. Do not claim the issue has been resolved — a human "
    "still has to act."
)


@tool
def search_logs(query: str) -> list[str]:
    """Search recent system log lines for entries matching the query."""
    return search_logs_via_mcp(query)


class TriageClassification(BaseModel):
    category: Category
    reasoning: str = Field(description="One sentence explaining the classification.")


def triage_node(state: TriageState) -> dict:
    llm = get_chat_model()
    structured_llm = llm.with_structured_output(TriageClassification)
    result: TriageClassification = structured_llm.invoke(
        [("system", TRIAGE_SYSTEM_PROMPT), ("human", state["ticket_text"])]
    )
    return {"category": result.category, "classification_reasoning": result.reasoning}


def route_after_triage(state: TriageState) -> Category:
    return state["category"]


def research_node(state: TriageState) -> dict:
    findings = search_knowledge_base(state["ticket_text"])
    context = "\n".join(findings) or "No matching knowledge base articles found."
    llm = get_chat_model()
    response = llm.invoke(
        [
            ("system", RESEARCH_SYSTEM_PROMPT),
            ("human", f"Ticket: {state['ticket_text']}\n\nKnowledge base excerpts:\n{context}"),
        ]
    )
    return {"agent_output": response.content}


def diagnosis_node(state: TriageState) -> dict:
    tools = [search_logs, query_order_status]
    llm_with_tools = get_chat_model().bind_tools(tools)
    messages = [
        ("system", DIAGNOSIS_SYSTEM_PROMPT),
        ("human", f"Ticket: {state['ticket_text']}"),
    ]
    answer = run_tool_loop(llm_with_tools, tools, messages)
    return {"agent_output": answer}


def escalation_node(state: TriageState) -> dict:
    ticket_id = state["ticket_id"]
    ticket_record = get_ticket.invoke({"ticket_id": ticket_id})
    reasoning = state.get("classification_reasoning", "")
    add_internal_note.invoke(
        {"ticket_id": ticket_id, "note": f"Escalated by Triage agent: {reasoning}"}
    )

    llm = get_chat_model()
    response = llm.invoke(
        [
            ("system", ESCALATION_SYSTEM_PROMPT),
            (
                "human",
                f"Ticket: {state['ticket_text']}\n\n"
                f"Ticket system record:\n{ticket_record}\n\n"
                f"Triage reasoning: {reasoning}",
            ),
        ]
    )
    return {"agent_output": response.content}
