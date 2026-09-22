import pytest

from support_triage.llm import get_chat_model


def test_get_chat_model_defaults_to_ollama(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    model = get_chat_model()
    assert model.__class__.__name__ == "ChatOllama"


def test_get_chat_model_anthropic_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    model = get_chat_model()
    assert model.__class__.__name__ == "ChatAnthropic"


def test_get_chat_model_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "made_up_provider")
    with pytest.raises(ValueError):
        get_chat_model()


def test_get_chat_model_snowflake_not_yet_implemented(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "snowflake_cortex")
    with pytest.raises(NotImplementedError):
        get_chat_model()
