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
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
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

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
        tokens = max_tokens or self._max_tokens
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=tokens,
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
    def __init__(self, api_key: str, model: str, max_tokens: int, base_url: str = ""):
        if not api_key:
            raise MissingAPIKeyError(
                "LLM_PROVIDER is configured but LLM_API_KEY is not set."
            )
        from openai import OpenAI

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
        tokens = max_tokens or self._max_tokens
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            raise LLMGenerationError(f"LLM API error: {exc}") from exc


class MockProvider(LLMProvider):
    """Offline deterministic provider for local testing without a live API key.
    Returns structurally valid but domain-neutral placeholder responses so it
    can never be mistaken for real LLM output from the user's actual papers.
    """

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
        import json
        import re
        sys_lower = system_prompt.lower()

        # 1. Comparison Schema — keyed by document UUIDs found in the prompt
        if "comparison" in sys_lower or "compare" in sys_lower:
            uuids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", user_prompt, re.I)
            comp_obj = {}
            for u in (uuids if uuids else ["doc1", "doc2"]):
                comp_obj[u] = {
                    "Problem": "Not reported in the indexed text (offline mock — index papers and use a live LLM key).",
                    "Methodology": "Not reported in the indexed text.",
                    "Model/Architecture": "Not reported in the indexed text.",
                    "Dataset": "Not reported in the indexed text.",
                    "Evaluation Metrics": "Not reported in the indexed text.",
                    "Results": "Not reported in the indexed text.",
                    "Contributions": "Not reported in the indexed text.",
                    "Limitations": "Not reported in the indexed text.",
                }
            return json.dumps(comp_obj)

        # 2. Claims & Limitations extraction (chunkless metadata pass)
        if "claims" in sys_lower and "limitations" in sys_lower and "json" in sys_lower:
            return json.dumps({
                "claims": [
                    {"claim_text": "[MOCK] No live LLM available — configure LLM_API_KEY to extract real claims.", "claim_type": "contribution", "evidence_text": ""},
                ],
                "limitations": [
                    {"limitation_text": "[MOCK] No live LLM available — configure LLM_API_KEY to extract real limitations.", "category": "other", "evidence_text": ""},
                ]
            })

        # 3. Claim normalization (JSON array)
        if "claim" in sys_lower and "normalize" in sys_lower and "json array" in sys_lower:
            candidates = [line.strip().lstrip("0123456789. ") for line in user_prompt.splitlines() if line.strip() and len(line.strip()) > 20]
            return json.dumps([{"claim_text": c, "claim_type": "finding", "evidence_text": c} for c in candidates[:6]]) or "[]"

        # 4. Limitation normalization (JSON array)
        if "limitation" in sys_lower and "normalize" in sys_lower and "json array" in sys_lower:
            candidates = [line.strip().lstrip("0123456789. ") for line in user_prompt.splitlines() if line.strip() and len(line.strip()) > 20]
            return json.dumps([{"limitation_text": c, "category": "other", "evidence_text": c} for c in candidates[:6]]) or "[]"

        # 5. Research Gap Analysis Schema
        if "gap" in sys_lower:
            filenames = []
            for line in user_prompt.splitlines():
                if ".pdf" in line.lower():
                    clean_f = line.strip().split(":")[0].strip().strip("-*• ")
                    if clean_f and clean_f not in filenames:
                        filenames.append(clean_f)
            affected = filenames if filenames else ["paper_1.pdf", "paper_2.pdf"]
            return json.dumps([
                {
                    "gap": "[MOCK] No live LLM available — configure LLM_API_KEY to detect real research gaps from your papers.",
                    "category": "underexplored_area",
                    "affected_papers": affected,
                    "why_it_matters": "A live LLM is required to perform evidence-grounded gap analysis.",
                    "potential_direction": "Set LLM_PROVIDER and LLM_API_KEY in your .env file."
                }
            ])

        # 6. Research Questions Generation (JSON array of strings)
        if "question" in sys_lower and "json" in sys_lower:
            return json.dumps([
                "[MOCK] No live LLM available — configure LLM_API_KEY to generate real research questions."
            ])

        # 7. Literature Matrix (JSON object)
        if "matrix" in sys_lower or "literature review" in sys_lower:
            return json.dumps({
                "research_problem": "[MOCK] Not extracted — configure LLM_API_KEY for real extraction.",
                "methodology": "Not reported in the indexed text.",
                "model_or_algorithm": "Not reported in the indexed text.",
                "dataset": "Not reported in the indexed text.",
                "evaluation_metrics": "Not reported in the indexed text.",
                "key_results": "Not reported in the indexed text.",
                "contributions": "Not reported in the indexed text.",
                "limitations": "Not reported in the indexed text."
            })

        # 8. Metadata Extraction Schema
        if "metadata" in sys_lower or ("json" in sys_lower and "title" in sys_lower):
            lines = [ln.strip() for ln in user_prompt.splitlines() if ln.strip()]
            first_line = lines[0] if lines else "Unknown Paper"
            return json.dumps({
                "title": first_line[:120],
                "authors": [],
                "publication_year": None,
                "abstract": "[MOCK] Configure LLM_API_KEY to extract real metadata.",
                "keywords": [],
                "claims": [],
                "limitations": [],
            })

        # Default: plain-text notice
        return (
            "[MOCK RESPONSE — No live LLM configured]\n\n"
            "To get real answers grounded in your papers, set LLM_PROVIDER and LLM_API_KEY "
            "in your .env file and restart the backend."
        )




def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        return AnthropicProvider(settings.llm_api_key, settings.llm_model, settings.llm_max_tokens)
    if provider in ("openai", "grok", "xai", "groq"):
        base_url = settings.llm_base_url
        if provider in ("grok", "xai") and not base_url:
            base_url = "https://api.x.ai/v1"
        elif provider == "groq" and not base_url:
            base_url = "https://api.groq.com/openai/v1"
        return OpenAIProvider(settings.llm_api_key, settings.llm_model, settings.llm_max_tokens, base_url=base_url)
    if provider == "mock":
        return MockProvider()
    raise LLMGenerationError(f"Unknown LLM_PROVIDER '{settings.llm_provider}'.")

