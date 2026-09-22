"""Triage agent and the three specialist agents it routes to."""

from pydantic import BaseModel, Field

from support_triage.llm import get_chat_model
from support_triage.state import Category, TriageState
from support_triage.tools import draft_escalation_summary, search_knowledge_base, search_logs

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
    "You are the Diagnosis agent. Explain what the log evidence below suggests is wrong, "
    "in plain language a support engineer can act on. If no logs matched, say so."
)


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
    findings = search_logs(state["ticket_text"])
    context = "\n".join(findings) or "No matching log lines found."
    llm = get_chat_model()
    response = llm.invoke(
        [
            ("system", DIAGNOSIS_SYSTEM_PROMPT),
            ("human", f"Ticket: {state['ticket_text']}\n\nLog search results:\n{context}"),
        ]
    )
    return {"agent_output": response.content}


def escalation_node(state: TriageState) -> dict:
    summary = draft_escalation_summary(
        state["ticket_text"], state.get("classification_reasoning", "")
    )
    return {"agent_output": summary}
