"""Demo script: one plain-text call to Snowflake Cortex — satisfies the
project brief's "one cloud AI platform for at least one model call"
requirement for Phase 6.

Verified live against a real Snowflake trial account (see DECISIONS.md #20
for the full story — a real upstream bug in ChatSnowflakeCortex's
credential-loading validator was found and worked around along the way).

Run with real credentials in .env (see .env.example's SNOWFLAKE_* vars):
    python -m evals.snowflake_cortex_demo

ChatSnowflakeCortex is completion-only — verified by reading its source:
_generate() builds a plain message string and never inspects a `tools`
kwarg at all. So this is a plain .invoke() call, not a run through the full
multi-agent pipeline, which needs bind_tools()/with_structured_output() to
actually work for Diagnosis/Escalation/Triage (see DECISIONS.md #20).
"""

from dotenv import load_dotenv

from support_triage.llm import get_chat_model


def run() -> None:
    load_dotenv()
    llm = get_chat_model(provider="snowflake_cortex")
    response = llm.invoke("In one sentence, what is a support-ticket triage system?")
    print(response.content)


if __name__ == "__main__":
    run()
