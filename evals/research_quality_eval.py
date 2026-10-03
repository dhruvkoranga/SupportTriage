"""LLM-as-judge evaluation for the Research agent: faithfulness (does the
answer stick to the retrieved context, with no invented specifics?) and
correctness (does it match a reference answer?).

"RAGAS or LLM-as-judge for the retrieval sub-component" — from the project
brief. This is the LLM-as-judge half of that choice; see DECISIONS.md #8 for
why RAGAS itself isn't used (its dependency tree no longer has a release
compatible with this project's pinned LangChain/LangGraph generation).

Manual eval, not part of the pytest suite: calls a real LLM three times per
case (the agent, then two judges), is non-deterministic. Run directly:
    python -m evals.research_quality_eval

The judge uses JUDGE_LLM_PROVIDER if set, falling back to LLM_PROVIDER
(same default as everything else: free local Ollama). A judge no stronger
than the agent it's grading can be unreliable — see DECISIONS.md #18 for a
concrete example caught live. Set JUDGE_LLM_PROVIDER=anthropic (with
ANTHROPIC_API_KEY in .env) for a stronger, independent judge; costs a small
amount per run, so it's opt-in, not the default.
"""

import os
from dataclasses import dataclass

from pydantic import BaseModel, Field

from support_triage.agents import research_node
from support_triage.llm import get_chat_model
from support_triage.tools import search_knowledge_base

_JUDGE_PROVIDER = os.getenv("JUDGE_LLM_PROVIDER") or None


@dataclass
class ResearchCase:
    question: str
    reference_answer: str


CASES = [
    ResearchCase(
        "How do I reset a user's password?",
        "Go to Admin > Users, select the user, then Reset Password. "
        "The reset email is valid for 24 hours.",
    ),
    ResearchCase(
        "How are tax rates configured?",
        "Tax rates are set under Catalog > Tax Rules, per region, and take "
        "effect after the next catalog sync.",
    ),
    ResearchCase(
        "What are the possible order status codes?",
        "PENDING, PROCESSING, SHIPPED, DELIVERED, and CANCELLED "
        "(CANCELLED only from PENDING or PROCESSING).",
    ),
]

_FAITHFULNESS_JUDGE_PROMPT = (
    "You are grading an AI support agent's answer for faithfulness to its source material. "
    "Given the retrieved context and the agent's answer, decide whether every factual claim in "
    "the answer is actually supported by the context. An answer that adds unsupported specifics "
    "is not faithful, even if those specifics happen to be true."
)

_CORRECTNESS_JUDGE_PROMPT = (
    "You are grading an AI support agent's answer against a reference answer. Decide whether the "
    "agent's answer conveys the same key information as the reference, even if worded "
    "differently. Missing or contradicting key information means not correct."
)


class FaithfulnessJudgment(BaseModel):
    faithful: bool = Field(
        description="True only if every claim in the answer is supported by the given context."
    )
    reasoning: str = Field(description="One sentence explaining the verdict.")


class CorrectnessJudgment(BaseModel):
    correct: bool = Field(
        description="True if the answer conveys the same key information as the reference answer."
    )
    reasoning: str = Field(description="One sentence explaining the verdict.")


_MAX_JUDGE_ATTEMPTS = 3


def _invoke_judge(schema, messages):
    """Retries on None — with_structured_output() occasionally returns None
    on this local model when it fails to parse its own output as JSON (also
    seen in planning.py's plan_node; see DECISIONS.md #18). A judge call
    isn't worth failing an entire eval run over a transient parse miss."""
    llm = get_chat_model(provider=_JUDGE_PROVIDER).with_structured_output(schema)
    for attempt in range(_MAX_JUDGE_ATTEMPTS):
        result = llm.invoke(messages)
        if result is not None:
            return result
    raise RuntimeError(f"Judge returned None after {_MAX_JUDGE_ATTEMPTS} attempts.")


def _judge_faithfulness(context: str, answer: str) -> FaithfulnessJudgment:
    return _invoke_judge(
        FaithfulnessJudgment,
        [
            ("system", _FAITHFULNESS_JUDGE_PROMPT),
            ("human", f"Context:\n{context}\n\nAnswer:\n{answer}"),
        ],
    )


def _judge_correctness(reference: str, answer: str) -> CorrectnessJudgment:
    return _invoke_judge(
        CorrectnessJudgment,
        [
            ("system", _CORRECTNESS_JUDGE_PROMPT),
            ("human", f"Reference answer:\n{reference}\n\nAgent's answer:\n{answer}"),
        ],
    )


def run() -> None:
    faithful_count = 0
    correct_count = 0

    for case in CASES:
        answer = research_node({"ticket_text": case.question})["agent_output"]
        context = "\n".join(search_knowledge_base(case.question)) or "No matching articles found."

        faithfulness = _judge_faithfulness(context, answer)
        correctness = _judge_correctness(case.reference_answer, answer)
        faithful_count += faithfulness.faithful
        correct_count += correctness.correct

        print(f"Q: {case.question}")
        print(f"A: {answer}")
        print(f"   faithful={faithfulness.faithful}  ({faithfulness.reasoning})")
        print(f"   correct={correctness.correct}  ({correctness.reasoning})")
        print()

    n = len(CASES)
    print(f"Faithfulness: {faithful_count}/{n}")
    print(f"Correctness:  {correct_count}/{n}")


if __name__ == "__main__":
    run()
