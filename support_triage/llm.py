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
        raise NotImplementedError(
            "Snowflake Cortex support lands in Phase 6. Set LLM_PROVIDER=ollama or "
            "LLM_PROVIDER=anthropic for now."
        )

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")
