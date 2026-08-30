"""
Model registry (Phase 3, item 21/22/32/33).

A single place that documents every model/library Phase 3 can use, its
purpose, and whether it's actually importable in the current environment
— backs `GET /api/system/ml-info` so the frontend (and README) can show
real, live status instead of a static claim. Nothing here loads a model;
it only checks importability, which is cheap and safe to call on every
health check.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field

from app.core.config import get_settings


@dataclass
class ModelInfo:
    task: str
    library: str
    model_name: str
    repository: str
    license: str
    runs_locally: bool
    replaces_handcrafted: str
    available: bool = field(default=False)
    notes: str = ""


def _importable(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def get_model_registry() -> list[ModelInfo]:
    settings = get_settings()

    entries = [
        ModelInfo(
            task="Semantic embeddings (Phase 1 retrieval, reused by keyphrase/topic/section models)",
            library="sentence-transformers",
            model_name=settings.embedding_model_name,
            repository=f"https://huggingface.co/{settings.embedding_model_name}",
            license="Apache-2.0 (all-MiniLM-L6-v2)",
            runs_locally=True,
            replaces_handcrafted="n/a — already the Phase 1 embedding model",
        ),
        ModelInfo(
            task="Scientific section classification (fallback path)",
            library="sentence-transformers (embedding-similarity, no extra model)",
            model_name=settings.embedding_model_name,
            repository=f"https://huggingface.co/{settings.embedding_model_name}",
            license="Apache-2.0",
            runs_locally=True,
            replaces_handcrafted="n/a — heading-pattern detection is primary; this is the fallback",
        ),
        ModelInfo(
            task="Scientific entity extraction (models/datasets/methods/metrics)",
            library="rapidfuzz (fuzzy gazetteer matching) + spaCy (optional candidate noun-chunks)",
            model_name=f"gazetteer + {settings.spacy_model_name}" if settings.enable_spacy_candidates else "gazetteer only",
            repository="https://github.com/rapidfuzz/RapidFuzz ; https://github.com/explosion/spaCy",
            license="MIT (rapidfuzz) ; MIT (spaCy) ; MIT (en_core_web_sm)",
            runs_locally=True,
            replaces_handcrafted="Replaces a naive exact keyword-matching implementation",
        ),
        ModelInfo(
            task="Keyphrase extraction",
            library="KeyBERT",
            model_name=settings.resolved_keyphrase_model_name,
            repository="https://github.com/MaartenGr/KeyBERT",
            license="MIT",
            runs_locally=True,
            replaces_handcrafted="Replaces a TF-IDF/handwritten frequency-count keyword extractor",
        ),
        ModelInfo(
            task="Topic discovery",
            library="BERTopic (UMAP + HDBSCAN + c-TF-IDF)",
            model_name=settings.resolved_topic_model_name,
            repository="https://github.com/MaartenGr/BERTopic",
            license="MIT",
            runs_locally=True,
            replaces_handcrafted="Replaces asking the LLM 'what are the topics?'",
        ),
        ModelInfo(
            task="Claim / finding extraction (normalization only)",
            library="Configured LLM provider (Anthropic/OpenAI/mock) — unchanged from Phase 2",
            model_name=settings.llm_model,
            repository="n/a (hosted API)",
            license="Vendor terms of service",
            runs_locally=False,
            replaces_handcrafted="Used only to normalize an already-shortlisted candidate list, "
            "never to summarize the raw paper",
        ),
        ModelInfo(
            task="Limitation extraction (normalization only)",
            library="Configured LLM provider (Anthropic/OpenAI/mock) — unchanged from Phase 2",
            model_name=settings.llm_model,
            repository="n/a (hosted API)",
            license="Vendor terms of service",
            runs_locally=False,
            replaces_handcrafted="Used only to normalize an already-shortlisted candidate list",
        ),
    ]

    checks = {
        "sentence-transformers": "sentence_transformers",
        "rapidfuzz": "rapidfuzz",
        "spaCy": "spacy",
        "KeyBERT": "keybert",
        "BERTopic": "bertopic",
    }
    for entry in entries:
        for label, module in checks.items():
            if label.lower() in entry.library.lower():
                entry.available = _importable(module)
    # LLM-provider entries are "available" whenever an API key is configured.
    for entry in entries:
        if entry.library.startswith("Configured LLM"):
            entry.available = bool(settings.llm_api_key) or settings.llm_provider.lower() == "mock"

    return entries
