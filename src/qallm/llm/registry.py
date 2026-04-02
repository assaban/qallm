"""LLM Model Registry — each entry is one callable model (QALLM-12c).

Usage::

    registry = LLMModelRegistry()
    registry.register(OpenAIModel("gpt-4o-mini", ...))
    registry.register(OpenAIModel("gpt-5-mini", ...))
    registry.register(AnthropicModel())
    registry.register(OllamaModel())

    model    = registry.pick("gpt-5-mini")    # raises if missing/unconfigured
    names    = registry.list()                 # all registered names
    ready    = registry.list_configured()      # only those with API keys
"""

from __future__ import annotations

from qallm.llm.base import LLMModel


class LLMModelRegistry:
    """Registry of available LLM models."""

    def __init__(self) -> None:
        self._models: dict[str, LLMModel] = {}

    def register(self, model: LLMModel) -> None:
        self._models[model.name()] = model

    def get(self, name: str) -> LLMModel | None:
        return self._models.get(name)

    def pick(self, name: str) -> LLMModel:
        m = self.get(name)
        if m is None:
            available = ", ".join(self.list())
            raise ValueError(f"Unknown LLM model '{name}'. Available: {available}")
        if not m.is_configured():
            raise ValueError(f"LLM model '{name}' is not configured. Set the required API key in your .env file.")
        return m

    def list(self) -> list[str]:
        """All registered model names."""
        return list(self._models.keys())

    def list_configured(self) -> list[str]:
        """Only models whose API keys are set."""
        return [n for n, m in self._models.items() if m.is_configured()]

    def get_default(self) -> LLMModel | None:
        """Return the first configured model, or None."""
        for m in self._models.values():
            if m.is_configured():
                return m
        return None


# Backward compatibility alias
# LLMProviderRegistry = LLMModelRegistry
