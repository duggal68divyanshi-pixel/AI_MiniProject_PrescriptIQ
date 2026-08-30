"""
LLM generation provider abstraction.

The rest of the app (rag.py) never talks to a vendor SDK directly — it
calls `generate()` on whichever provider is configured via LLM_PROVIDER.
This keeps embeddings, retrieval, and generation cleanly separated: this
file is the ONLY place that knows about Anthropic/OpenAI SDK specifics.

Supported providers:
  - "anthropic": Claude models via the Anthropic API
  - "openai":     GPT models via the OpenAI API
  - "mock":       deterministic offline stub for local dev without any
                   API key — every response it returns is clearly labeled
                   as a mock so it can never be mistaken for a real answer
"""
from __future__ import annotations

import abc
import logging

from app.core.config import get_settings
from app.core.exceptions import LLMGenerationError, MissingAPIKeyError

logger = logging.getLogger("research_nexus.llm")


class LLMProvider(abc.ABC):
    @abc.abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's plain-text completion."""
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, max_tokens: int):
        if not api_key:
            raise MissingAPIKeyError(
                "LLM_PROVIDER is 'anthropic' but LLM_API_KEY is not set."
            )
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()
        except Exception as exc:
            logger.error("Anthropic generation failed: %s", exc)
            raise LLMGenerationError(f"Anthropic API error: {exc}") from exc


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, max_tokens: int):
        if not api_key:
            raise MissingAPIKeyError(
                "LLM_PROVIDER is 'openai' but LLM_API_KEY is not set."
            )
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.error("OpenAI generation failed: %s", exc)
            raise LLMGenerationError(f"OpenAI API error: {exc}") from exc


class MockProvider(LLMProvider):
    """Offline stub. Never used unless LLM_PROVIDER=mock is explicitly set."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return (
            "[MOCK LLM RESPONSE — no real model was called because "
            "LLM_PROVIDER=mock. Set LLM_PROVIDER to 'anthropic' or 'openai' "
            "and provide LLM_API_KEY to get a real grounded answer.]\n\n"
            "The retrieved context above would normally be summarized here "
            "by the configured LLM."
        )


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        return AnthropicProvider(settings.llm_api_key, settings.llm_model, settings.llm_max_tokens)
    if provider == "openai":
        return OpenAIProvider(settings.llm_api_key, settings.llm_model, settings.llm_max_tokens)
    if provider == "mock":
        return MockProvider()
    raise LLMGenerationError(f"Unknown LLM_PROVIDER '{settings.llm_provider}'.")
