"""OpenAI LLM models (QALLM-12c).

Registers as individual models (gpt-4o-mini, gpt-5-mini, etc.).
Each instance knows its own API quirks:
  - gpt-5 family: uses max_completion_tokens, supports structured outputs
  - gpt-4o family: uses max_tokens

Env vars:
  - OPENAI_API_KEY  (required)
"""

from __future__ import annotations

import json
import logging

from qallm.llm.base import LLMModel, LLMResponse, TokenTracker
from qallm.repair.config import settings

logger = logging.getLogger(__name__)

# Structured output schema for repair responses
REPAIR_SCHEMA = {
    "name": "code_repair",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "corrected_code": {
                "type": "string",
                "description": "The corrected code block, raw Python, no markdown.",
            },
        },
        "required": ["corrected_code"],
        "additionalProperties": False,
    },
}


class OpenAIModel(LLMModel):
    """One OpenAI chat model.

    Parameters
    ----------
    model_id : str
        OpenAI model name (e.g. "gpt-4o-mini", "gpt-5-mini").
    display_name : str | None
        Name shown in the dropdown. Defaults to *model_id*.
    use_structured : bool
        If True, use JSON-schema structured outputs for repair.
    """

    def __init__(
        self,
        model_id: str = "gpt-4o-mini",
        display_name: str | None = None,
        use_structured: bool = False,
    ) -> None:
        self._model_id = model_id
        self._display_name = display_name or model_id
        self._use_structured = use_structured
        self._is_gpt5 = model_id.startswith("gpt-5")

    def name(self) -> str:
        return self._display_name

    def is_configured(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    def chat(
        self,
        system: str,
        user: str,
        tracker: TokenTracker | None = None,
    ) -> LLMResponse:
        if not self.is_configured():
            return LLMResponse(
                content="",
                provider="openai",
                model=self._model_id,
                error="OPENAI_API_KEY not configured",
            )

        if tracker and tracker.remaining <= 0:
            return LLMResponse(
                content="",
                provider="openai",
                model=self._model_id,
                error=f"Token budget exhausted ({tracker.budget} tokens used)",
            )

        try:
            import openai

            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

            kwargs: dict = {
                "model": self._model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }

            # GPT-5 family: no temperature support, uses max_completion_tokens
            if self._is_gpt5:
                kwargs["max_completion_tokens"] = 4096
            else:
                kwargs["temperature"] = 0.1
                kwargs["max_tokens"] = 4096

            # Structured outputs (GPT-5 / supported models)
            if self._use_structured:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": REPAIR_SCHEMA,
                }

            logger.debug(
                "OpenAI call model=%s, prompt_len=%d, structured=%s",
                self._model_id,
                len(user),
                self._use_structured,
            )

            response = client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            usage = response.usage
            raw_content = choice.message.content or ""

            # Parse structured output
            if self._use_structured and raw_content:
                try:
                    parsed = json.loads(raw_content)
                    content = parsed.get("corrected_code", raw_content)
                except (json.JSONDecodeError, KeyError):
                    content = raw_content
            else:
                content = raw_content

            resp = LLMResponse(
                content=content,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                model=response.model,
                provider="openai",
            )

        except Exception as e:
            logger.error("OpenAI API error [%s]: %s", self._model_id, e)
            resp = LLMResponse(
                content="",
                provider="openai",
                model=self._model_id,
                error=str(e),
            )

        if tracker:
            tracker.record(resp)

        return resp


# Backward compatibility
class OpenAIProvider(OpenAIModel):
    """Legacy alias — use OpenAIModel instead."""

    def __init__(self) -> None:
        super().__init__(model_id=settings.OPENAI_MODEL)
