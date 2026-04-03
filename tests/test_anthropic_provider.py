"""Tests for Anthropic model (QALLM-12c)."""

from unittest.mock import MagicMock, patch

from qallm.llm.anthropic_provider import AnthropicModel
from qallm.llm.base import TokenTracker


def test_name_uses_model_id():
    assert AnthropicModel(model_id="claude-3-5-haiku-20241022").name() == "claude-3-5-haiku-20241022"


def test_not_configured_when_no_key(monkeypatch):
    monkeypatch.setattr("qallm.llm.anthropic_provider.settings.ANTHROPIC_API_KEY", None)
    assert not AnthropicModel().is_configured()


def test_configured_when_key_set(monkeypatch):
    monkeypatch.setattr("qallm.llm.anthropic_provider.settings.ANTHROPIC_API_KEY", "sk-ant-test")
    assert AnthropicModel().is_configured()


def test_chat_returns_error_when_not_configured(monkeypatch):
    monkeypatch.setattr("qallm.llm.anthropic_provider.settings.ANTHROPIC_API_KEY", None)
    resp = AnthropicModel().chat("sys", "user")
    assert "not configured" in resp.error
    assert resp.provider == "anthropic"


def test_chat_respects_budget(monkeypatch):
    monkeypatch.setattr("qallm.llm.anthropic_provider.settings.ANTHROPIC_API_KEY", "sk-ant-test")
    tracker = TokenTracker(budget=100)
    tracker.total_input = 100
    resp = AnthropicModel().chat("sys", "user", tracker)
    assert "exhausted" in resp.error


def test_chat_calls_anthropic_api(monkeypatch):
    monkeypatch.setattr("qallm.llm.anthropic_provider.settings.ANTHROPIC_API_KEY", "sk-ant-test")

    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "fixed code"

    mock_usage = MagicMock()
    mock_usage.input_tokens = 60
    mock_usage.output_tokens = 40

    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_response.usage = mock_usage
    mock_response.model = "claude-3-5-haiku-20241022"

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    mock_mod = MagicMock()
    mock_mod.Anthropic.return_value = mock_client

    with patch.dict("sys.modules", {"anthropic": mock_mod}):
        tracker = TokenTracker(budget=1000)
        resp = AnthropicModel().chat("sys", "fix", tracker)

    assert resp.content == "fixed code"
    assert resp.provider == "anthropic"
    assert tracker.total_tokens == 100
