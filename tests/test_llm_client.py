"""Tests for OpenAI model instances (QALLM-12c)."""

from unittest.mock import MagicMock, patch

from qallm.llm.base import LLMResponse, TokenTracker
from qallm.llm.openai_provider import OpenAIModel


def test_gpt4o_mini_name():
    assert OpenAIModel(model_id="gpt-4o-mini").name() == "gpt-4o-mini"


def test_gpt5_mini_name():
    assert OpenAIModel(model_id="gpt-5-mini").name() == "gpt-5-mini"


def test_custom_display_name():
    m = OpenAIModel(model_id="gpt-4o-mini", display_name="fast")
    assert m.name() == "fast"


def test_token_tracker_accumulates():
    t = TokenTracker(budget=1000)
    t.record(LLMResponse(content="x", input_tokens=100, output_tokens=50, model="m"))
    t.record(LLMResponse(content="y", input_tokens=200, output_tokens=80, model="m"))
    assert t.total_tokens == 430
    assert t.remaining == 570


def test_token_tracker_to_dict():
    t = TokenTracker(budget=500)
    t.record(LLMResponse(content="x", input_tokens=100, output_tokens=50, model="m"))
    d = t.to_dict()
    assert d["budget"] == 500
    assert d["total_tokens"] == 150


def test_not_configured_when_no_key(monkeypatch):
    monkeypatch.setattr("qallm.llm.openai_provider.settings.OPENAI_API_KEY", None)
    assert not OpenAIModel().is_configured()


def test_chat_returns_error_when_not_configured(monkeypatch):
    monkeypatch.setattr("qallm.llm.openai_provider.settings.OPENAI_API_KEY", None)
    resp = OpenAIModel().chat("sys", "user")
    assert resp.error is not None
    assert "not configured" in resp.error


def test_chat_respects_budget(monkeypatch):
    monkeypatch.setattr("qallm.llm.openai_provider.settings.OPENAI_API_KEY", "sk-test")
    tracker = TokenTracker(budget=100)
    tracker.total_input = 100
    resp = OpenAIModel().chat("sys", "user", tracker)
    assert "exhausted" in resp.error


def test_gpt5_uses_max_completion_tokens(monkeypatch):
    """GPT-5 family should use max_completion_tokens, not max_tokens."""
    monkeypatch.setattr("qallm.llm.openai_provider.settings.OPENAI_API_KEY", "sk-test")

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 50
    mock_usage.completion_tokens = 30

    mock_choice = MagicMock()
    mock_choice.message.content = '{"corrected_code": "x = 1"}'

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    mock_response.model = "gpt-5-mini"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    mock_openai = MagicMock()
    mock_openai.OpenAI.return_value = mock_client

    with patch.dict("sys.modules", {"openai": mock_openai}):
        model = OpenAIModel(model_id="gpt-5-mini", use_structured=True)
        resp = model.chat("sys", "fix this")

    # Check the call kwargs
    call_kwargs = mock_client.chat.completions.create.call_args
    assert "max_completion_tokens" in call_kwargs.kwargs
    assert "max_tokens" not in call_kwargs.kwargs
    assert "temperature" not in call_kwargs.kwargs
    assert "response_format" in call_kwargs.kwargs
    # Structured output should parse corrected_code
    assert resp.content == "x = 1"


def test_gpt4o_uses_max_tokens(monkeypatch):
    """GPT-4o family should use max_tokens, not max_completion_tokens."""
    monkeypatch.setattr("qallm.llm.openai_provider.settings.OPENAI_API_KEY", "sk-test")

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 50
    mock_usage.completion_tokens = 30

    mock_choice = MagicMock()
    mock_choice.message.content = "x = 1"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    mock_response.model = "gpt-4o-mini"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    mock_openai = MagicMock()
    mock_openai.OpenAI.return_value = mock_client

    with patch.dict("sys.modules", {"openai": mock_openai}):
        model = OpenAIModel(model_id="gpt-4o-mini")
        resp = model.chat("sys", "fix this")

    call_kwargs = mock_client.chat.completions.create.call_args
    assert "max_tokens" in call_kwargs.kwargs
    assert "max_completion_tokens" not in call_kwargs.kwargs
    assert "response_format" not in call_kwargs.kwargs
    assert call_kwargs.kwargs["temperature"] == 0.1
    assert resp.content == "x = 1"



