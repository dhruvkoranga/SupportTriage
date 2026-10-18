from types import SimpleNamespace

import pytest
from pydantic import BaseModel
from snowflake.snowpark import Session

from support_triage.llm import get_chat_model, invoke_structured


def test_get_chat_model_defaults_to_ollama(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    model = get_chat_model()
    assert model.__class__.__name__ == "ChatOllama"


def test_get_chat_model_anthropic_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    model = get_chat_model()
    assert model.__class__.__name__ == "ChatAnthropic"


def test_get_chat_model_explicit_provider_overrides_env_var(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    model = get_chat_model(provider="anthropic")
    assert model.__class__.__name__ == "ChatAnthropic"


def test_get_chat_model_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "made_up_provider")
    with pytest.raises(ValueError):
        get_chat_model()


def test_get_chat_model_snowflake_cortex_provider(monkeypatch):
    """Verified live against a real account (see DECISIONS.md #20) — this
    particular test still mocks Session.builder.configs(...).create() so it
    stays fast/offline; it exercises our own session-building code (the
    workaround for ChatSnowflakeCortex's validator not firing), not a live
    connection."""
    for name, value in {
        "SNOWFLAKE_USERNAME": "test-user",
        "SNOWFLAKE_PASSWORD": "test-pass",
        "SNOWFLAKE_ACCOUNT": "test-account",
        "SNOWFLAKE_DATABASE": "test-db",
        "SNOWFLAKE_SCHEMA": "test-schema",
        "SNOWFLAKE_WAREHOUSE": "test-wh",
        "SNOWFLAKE_ROLE": "test-role",
    }.items():
        monkeypatch.setenv(name, value)
    # Explicitly unset rather than assume it's absent — api.py's module-level
    # load_dotenv() leaks the developer's real .env into os.environ for the
    # whole pytest process once anything imports it, which this test was
    # actually bitten by (SNOWFLAKE_CORTEX_MODEL carried over from a live
    # Snowflake Cortex session in this same conversation).
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL", raising=False)

    fake_session = SimpleNamespace(close=lambda: None)
    fake_builder = SimpleNamespace(
        configs=lambda _opts: SimpleNamespace(create=lambda: fake_session)
    )
    monkeypatch.setattr(Session, "builder", fake_builder)

    model = get_chat_model(provider="snowflake_cortex")

    assert model.__class__.__name__ == "ChatSnowflakeCortex"
    assert model.model == "llama3.1-8b"
    # Proves our workaround actually ran: the class's own broken validator
    # never sets _sp_session, so this would be None without it.
    assert model._sp_session is fake_session


class _Schema(BaseModel):
    value: str


class _FlakyThenOkLLM:
    """Returns None a fixed number of times before succeeding — stands in for
    the real local model's occasional with_structured_output() JSON-parse miss."""

    def __init__(self, none_count: int, result):
        self._none_count = none_count
        self._result = result
        self.calls = 0

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        self.calls += 1
        if self.calls <= self._none_count:
            return None
        return self._result


def test_invoke_structured_returns_result_on_first_success():
    llm = _FlakyThenOkLLM(none_count=0, result=_Schema(value="ok"))
    result = invoke_structured(llm, _Schema, [])
    assert result.value == "ok"
    assert llm.calls == 1


def test_invoke_structured_retries_past_none_results():
    llm = _FlakyThenOkLLM(none_count=2, result=_Schema(value="ok"))
    result = invoke_structured(llm, _Schema, [])
    assert result.value == "ok"
    assert llm.calls == 3


def test_invoke_structured_raises_after_exhausting_attempts():
    llm = _FlakyThenOkLLM(none_count=5, result=_Schema(value="ok"))
    with pytest.raises(RuntimeError):
        invoke_structured(llm, _Schema, [], max_attempts=3)
    assert llm.calls == 3
