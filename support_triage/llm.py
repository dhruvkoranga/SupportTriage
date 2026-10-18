"""LLM client factory.

This is the one seam agents depend on. Swapping providers (free local Ollama
by default, Anthropic for quality comparisons, Snowflake Cortex from Phase 6
on) means changing LLM_PROVIDER, not editing agent code — see DECISIONS.md #2.
"""

import os

from langchain_core.language_models.chat_models import BaseChatModel


def get_chat_model(provider: str | None = None, **kwargs) -> BaseChatModel:
    """Return a chat model for `provider`, or the LLM_PROVIDER env var if not given (default: ollama).

    The explicit `provider` override exists for callers that need a
    *different* model than the app's default — e.g. an eval judge using a
    stronger model than the agent it's grading, a well-established
    LLM-as-judge practice (see DECISIONS.md #18).
    """
    provider = provider or os.getenv("LLM_PROVIDER", "ollama")

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        return ChatOllama(model=model, **kwargs)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model="claude-sonnet-5", **kwargs)

    if provider == "snowflake_cortex":
        return _build_snowflake_cortex_chat_model(**kwargs)

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")


def _build_snowflake_cortex_chat_model(**kwargs) -> BaseChatModel:
    """ChatSnowflakeCortex's own env-var-reading validator (a pydantic v1-style
    @pre_init root_validator) does not fire under this project's installed
    pydantic/langchain-core versions — verified directly: it's registered in
    __pydantic_decorators__.root_validators but never runs at construction
    time, leaving _sp_session as None until the first .invoke() crashes. Not
    a credentials problem (confirmed live against a real account) — a real
    upstream compatibility bug. Worked around by building the Snowpark
    Session ourselves and injecting it directly, bypassing the broken
    validator entirely. See DECISIONS.md #20 for the full story, including
    why the default model below is llama3.1-8b, not the class's own default
    (snowflake-arctic isn't available in every Cortex region).
    """
    from langchain_community.chat_models import ChatSnowflakeCortex
    from snowflake.snowpark import Session

    model = os.getenv("SNOWFLAKE_CORTEX_MODEL", "llama3.1-8b")
    chat_model = ChatSnowflakeCortex(model=model, **kwargs)

    session = Session.builder.configs(
        {
            "account": os.environ["SNOWFLAKE_ACCOUNT"],
            "user": os.environ["SNOWFLAKE_USERNAME"],
            "password": os.environ["SNOWFLAKE_PASSWORD"],
            "database": os.environ["SNOWFLAKE_DATABASE"],
            "schema": os.environ["SNOWFLAKE_SCHEMA"],
            "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
            "role": os.environ["SNOWFLAKE_ROLE"],
        }
    ).create()
    chat_model._sp_session = session
    return chat_model


_MAX_STRUCTURED_ATTEMPTS = 3


def invoke_structured(llm: BaseChatModel, schema, messages, max_attempts: int = _MAX_STRUCTURED_ATTEMPTS):
    """Calls llm.with_structured_output(schema).invoke(messages), retrying on None.

    The local model occasionally fails to parse its own output as valid JSON,
    and with_structured_output() returns None in that case instead of
    raising — seen independently in Triage, Planning, and the eval judges
    (three separate call sites), which is what makes this worth a shared,
    centrally-fixed helper rather than a one-off patch (see DECISIONS.md #18).
    """
    structured_llm = llm.with_structured_output(schema)
    for _ in range(max_attempts):
        result = structured_llm.invoke(messages)
        if result is not None:
            return result
    raise RuntimeError(f"with_structured_output() returned None after {max_attempts} attempts.")
