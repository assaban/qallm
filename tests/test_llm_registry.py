"""Tests for LLM model registry (QALLM-12c)."""

import pytest

from qallm.llm.base import LLMModel, LLMResponse
from qallm.llm.registry import LLMModelRegistry


class FakeModel(LLMModel):
    def __init__(self, name: str = "fake", configured: bool = True):
        self._name = name
        self._configured = configured

    def name(self) -> str:
        return self._name

    def is_configured(self) -> bool:
        return self._configured

    def chat(self, system, user, tracker=None):
        return LLMResponse(content="fake reply", provider=self._name)


def test_register_and_list():
    reg = LLMModelRegistry()
    reg.register(FakeModel("a"))
    reg.register(FakeModel("b"))
    assert reg.list() == ["a", "b"]


def test_get_existing():
    reg = LLMModelRegistry()
    reg.register(FakeModel("gpt-4o-mini"))
    assert reg.get("gpt-4o-mini") is not None


def test_get_missing_returns_none():
    reg = LLMModelRegistry()
    assert reg.get("nonexistent") is None


def test_pick_raises_on_unknown():
    reg = LLMModelRegistry()
    reg.register(FakeModel("gpt-4o-mini"))
    with pytest.raises(ValueError, match="Unknown LLM model"):
        reg.pick("nonexistent")


def test_pick_raises_on_unconfigured():
    reg = LLMModelRegistry()
    reg.register(FakeModel("gpt-4o-mini", configured=False))
    with pytest.raises(ValueError, match="not configured"):
        reg.pick("gpt-4o-mini")


def test_list_configured():
    reg = LLMModelRegistry()
    reg.register(FakeModel("a", configured=True))
    reg.register(FakeModel("b", configured=False))
    reg.register(FakeModel("c", configured=True))
    assert reg.list_configured() == ["a", "c"]


def test_get_default_returns_first_configured():
    reg = LLMModelRegistry()
    reg.register(FakeModel("a", configured=False))
    reg.register(FakeModel("b", configured=True))
    assert reg.get_default().name() == "b"


def test_get_default_none_if_nothing_configured():
    reg = LLMModelRegistry()
    reg.register(FakeModel("a", configured=False))
    assert reg.get_default() is None


def test_models_endpoint(client):
    """GET /api/llm/providers returns model list."""
    r = client.get("/api/llm/providers")
    assert r.status_code == 200
    data = r.json()
    assert "available" in data
    assert "configured" in data
    assert "default" in data
    assert "gpt-4o-mini" in data["available"]
    assert "gpt-5-mini" in data["available"]
