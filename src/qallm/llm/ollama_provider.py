"""Ollama local LLM model (QALLM-12c).

Uses the ``ollama`` Python SDK (lazy import — won't break if not installed).

Env vars:
  - OLLAMA_BASE_URL  (default: http://localhost:11434)
  - OLLAMA_MODEL     (default: llama3.1:8b)
"""

from __future__ import annotations

import logging

from qallm.llm.base import LLMModel, LLMResponse, TokenTracker
from qallm.repair.config import settings

logger = logging.getLogger(__name__)


class OllamaModel(LLMModel):
    """Local Ollama chat model."""

    def __init__(self, model_id: str | None = None, display_name: str | None = None) -> None:
        self._model_id = model_id or settings.OLLAMA_MODEL
        self._display_name = display_name or f"ollama/{self._model_id}"

    def name(self) -> str:
        return self._display_name

    def is_configured(self) -> bool:
        """
        Configured only if:
        - OLLAMA_BASE_URL is set
        - ollama SDK is installed
        - Ollama server is reachable
        """
        base_url = settings.OLLAMA_BASE_URL
        if not base_url:
            return False

        try:
            import httpx
        except ImportError:
            return False

        # Health check (fast, low overhead)
        try:
            # Use /api/tags which is lightweight
            with httpx.Client(timeout=2.0) as client:
                r = client.get(f"{base_url.rstrip('/')}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    def chat(
        self,
        system: str,
        user: str,
        tracker: TokenTracker | None = None,
    ) -> LLMResponse:
        if not self.is_configured():
            return LLMResponse(
                content="",
                provider="ollama",
                model=self._model_id,
                error="ollama SDK not installed or OLLAMA_BASE_URL not set",
            )

        if tracker and tracker.remaining <= 0:
            return LLMResponse(
                content="",
                provider="ollama",
                model=self._model_id,
                error=f"Token budget exhausted ({tracker.budget} tokens used)",
            )

        try:
            import ollama

            client = ollama.Client(host=settings.OLLAMA_BASE_URL)
            response = client.chat(
                model=self._model_id,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                options={"temperature": 0.1},
            )

            content = response.get("message", {}).get("content", "")
            prompt_tokens = response.get("prompt_eval_count", 0)
            completion_tokens = response.get("eval_count", 0)

            resp = LLMResponse(
                content=content,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                model=self._model_id,
                provider="ollama",
            )

        except Exception as e:
            logger.error("Ollama API error [%s]: %s", self._model_id, e)
            resp = LLMResponse(
                content="",
                provider="ollama",
                model=self._model_id,
                error=str(e),
            )

        if tracker:
            tracker.record(resp)

        return resp
