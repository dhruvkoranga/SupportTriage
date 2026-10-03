"""Triage agent and the three specialist agents it routes to."""

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from support_triage.db import query_order_status
from support_triage.llm import get_chat_model
from support_triage.mcp_integration.client import search_logs_via_mcp
from support_triage.state import Category, TriageState
from support_triage.ticketing import add_internal_note, close_ticket, get_ticket, issue_refund
from support_triage.tool_loop import run_tool_loop
from support_triage.tools import search_knowledge_base

TRIAGE_SYSTEM_PROMPT = """You triage incoming support tickets for an e-commerce platform. \
Classify each ticket into exactly one category:
- research: a how-to or documentation question about how the platform works in general; \
no specific order or account is involved
- diagnosis: anything about a specific order, account, or transaction — including plain \
status lookups ("what's the status of order X"), not just things that are broken
- escalation: a high-risk request (cancel, refund, delete) or anything urgent enough \
to need a human before acting

Set confident=false if the ticket is ambiguous, could fit more than one category, or \
you otherwise aren't sure — an unconfident classification is automatically escalated to \
a human rather than acted on, so it is always safe to say you're not sure."""

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

ESCALATION_PROPOSAL_SYSTEM_PROMPT = (
    "You are the Escalation agent's action-proposal step. Decide whether this ticket "
    "clearly asks for a specific action you have a tool for (closing the ticket, issuing "
    "a refund). Call the matching tool ONLY if the request is explicit and you have the "
    "details you need (order ID, amount, etc.) from the ticket or ticket record below. If "
    "the ticket doesn't clearly ask for one of these two specific actions, don't call any "
    "tool. Calling a tool here only proposes it for human approval — it does not execute."
)

ESCALATION_SUMMARY_SYSTEM_PROMPT = (
    "You are the Escalation agent. This ticket needs human review before any action is "
    "taken. Write a concise plain-language summary for the human reviewer: what the "
    "customer wants, why this was escalated, and — if a specific action was proposed "
    "below — what they're being asked to approve. Do not claim the issue has been "
    "resolved; a human still has to act."
)


@tool
def search_logs(query: str) -> list[str]:
    """Search recent system log lines for entries matching the query."""
    return search_logs_via_mcp(query)


class TriageClassification(BaseModel):
    category: Category
    confident: bool = Field(
        description="False if the ticket is ambiguous or you're not sure which category fits."
    )
    reasoning: str = Field(description="One sentence explaining the classification.")


def triage_node(state: TriageState) -> dict:
    llm = get_chat_model()
    structured_llm = llm.with_structured_output(TriageClassification)
    result: TriageClassification = structured_llm.invoke(
        [("system", TRIAGE_SYSTEM_PROMPT), ("human", state["ticket_text"])]
    )
    category = result.category if result.confident else "escalation"
    return {"category": category, "classification_reasoning": result.reasoning}


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
    trace: list[str] = []
    answer = run_tool_loop(llm_with_tools, tools, messages, trace=trace)
    return {"agent_output": answer, "tool_trace": trace}


def escalation_node(state: TriageState) -> dict:
    ticket_id = state["ticket_id"]
    ticket_text = state["ticket_text"]
    ticket_record = get_ticket.invoke({"ticket_id": ticket_id})
    reasoning = state.get("classification_reasoning", "")
    add_internal_note.invoke(
        {"ticket_id": ticket_id, "note": f"Escalated by Triage agent: {reasoning}"}
    )

    # Never executes these — only captures what the model would propose.
    # The only code path that actually calls close_ticket/issue_refund lives
    # in conversation.py, after a human approves via interrupt() (DECISIONS.md #14).
    destructive_tools = [close_ticket, issue_refund]
    proposal_llm = get_chat_model().bind_tools(destructive_tools)
    proposal_response = proposal_llm.invoke(
        [
            ("system", ESCALATION_PROPOSAL_SYSTEM_PROMPT),
            ("human", f"Ticket: {ticket_text}\n\nTicket system record:\n{ticket_record}"),
        ]
    )
    proposed_actions = [
        {"sub_task": ticket_text, "tool": call["name"], "args": call["args"], "reason": reasoning}
        for call in (proposal_response.tool_calls or [])
    ]

    proposal_note = ""
    if proposed_actions:
        proposal_note = "\n\nProposed action(s) pending human approval:\n" + "\n".join(
            f"- {a['tool']}({a['args']})" for a in proposed_actions
        )

    llm = get_chat_model()
    response = llm.invoke(
        [
            ("system", ESCALATION_SUMMARY_SYSTEM_PROMPT),
            (
                "human",
                f"Ticket: {ticket_text}\n\nTicket system record:\n{ticket_record}\n\n"
                f"Triage reasoning: {reasoning}{proposal_note}",
            ),
        ]
    )
    return {"agent_output": response.content, "proposed_actions": proposed_actions}
