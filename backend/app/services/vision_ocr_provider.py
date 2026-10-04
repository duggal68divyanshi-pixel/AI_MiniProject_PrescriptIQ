"""
Modular Vision-Language Model OCR Provider.

Provides Level 2 fallback OCR for blurry, handwritten, or complex multi-column paper photos.
Supports:
  - Anthropic Vision (Claude 3.5 Sonnet)
  - OpenAI Vision (GPT-4o / GPT-4-vision)
  - Mock Vision Provider (offline local dev fallback)
"""
from __future__ import annotations

import abc
import base64
import json
import logging

from app.core.config import get_settings

logger = logging.getLogger("research_nexus.vision_ocr")


class VisionOCRProvider(abc.ABC):
    @abc.abstractmethod
    def extract_text_and_layout(self, image_bytes: bytes) -> tuple[str, list[dict]]:
        """
        Extract page text and detected layout blocks from image bytes.
        Returns:
            (extracted_text, layout_blocks)
        """
        raise NotImplementedError


class AnthropicVisionOCRProvider(VisionOCRProvider):
    def __init__(self, api_key: str, model: str):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model or "claude-3-5-sonnet-20241022"

    def extract_text_and_layout(self, image_bytes: bytes) -> tuple[str, list[dict]]:
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "You are an expert scientific paper OCR engine. Extract ALL text from this paper page image.\n"
            "Maintain original reading order across multi-column layouts.\n"
            "Output JSON with keys: 'extracted_text' (string) and 'layout_blocks' (array of objects with 'type' and 'text').\n"
            "Allowed block types: title, heading, paragraph, table, figure_caption, list, footer, header."
        )
        try:
            res = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64_img,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            raw = "".join(b.text for b in res.content if b.type == "text").strip()
            # Attempt to parse JSON response
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(raw)
            return data.get("extracted_text", raw), data.get("layout_blocks", [])
        except Exception as exc:
            logger.error("Anthropic Vision OCR failed: %s", exc)
            return "", []


class OpenAIVisionOCRProvider(VisionOCRProvider):
    def __init__(self, api_key: str, model: str, base_url: str = ""):
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self._model = model or "gpt-4o"

    def extract_text_and_layout(self, image_bytes: bytes) -> tuple[str, list[dict]]:
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:image/png;base64,{b64_img}"
        system_prompt = (
            "You are an OCR and document layout engine for scientific research papers.\n"
            "Return JSON ONLY with schema:\n"
            "{\n"
            '  "extracted_text": "...",\n'
            '  "layout_blocks": [{"type": "paragraph|heading|title|table|list", "text": "..."}]\n'
            "}"
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Perform high-accuracy OCR on this paper page photo."},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                max_tokens=2048,
            )
            raw = response.choices[0].message.content or "{}"
            data = json.loads(raw)
            return data.get("extracted_text", raw), data.get("layout_blocks", [])
        except Exception as exc:
            logger.error("OpenAI Vision OCR failed: %s", exc)
            return "", []


class MockVisionOCRProvider(VisionOCRProvider):
    """Offline stub for vision OCR."""

    def extract_text_and_layout(self, image_bytes: bytes) -> tuple[str, list[dict]]:
        mock_text = (
            "Abstract — This research paper presents an advanced methodology evaluated on benchmark datasets. "
            "Our experimental findings demonstrate significant improvements over baseline models.\n\n"
            "1. Introduction\nRecent progress in machine learning has enabled state-of-the-art results."
        )
        blocks = [
            {"type": "heading", "text": "Abstract"},
            {"type": "paragraph", "text": "This research paper presents an advanced methodology evaluated on benchmark datasets."},
            {"type": "heading", "text": "1. Introduction"},
            {"type": "paragraph", "text": "Recent progress in machine learning has enabled state-of-the-art results."},
        ]
        return mock_text, blocks


def get_vision_ocr_provider() -> VisionOCRProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "anthropic" and settings.llm_api_key:
        return AnthropicVisionOCRProvider(settings.llm_api_key, settings.llm_model)
    if provider in ("openai", "grok", "xai", "groq") and settings.llm_api_key:
        base_url = settings.llm_base_url
        if provider in ("grok", "xai") and not base_url:
            base_url = "https://api.x.ai/v1"
        elif provider == "groq" and not base_url:
            base_url = "https://api.groq.com/openai/v1"
        return OpenAIVisionOCRProvider(settings.llm_api_key, settings.llm_model, base_url=base_url)
    return MockVisionOCRProvider()
