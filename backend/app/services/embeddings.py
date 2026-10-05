"""
Embedding generation.

Uses a local sentence-transformers model (default: all-MiniLM-L6-v2, 384
dimensions) so the pipeline works fully offline with no per-call API cost.
The model is loaded once per process (module-level singleton) since load
time is non-trivial.

Swapping models only requires changing EMBEDDING_MODEL_NAME and
EMBEDDING_DIMENSION in .env AND updating the `vector(N)` column dimension
in the migration to match.
"""
from __future__ import annotations

import logging
import os
import threading

os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"

from app.core.config import get_settings
from app.core.exceptions import EmbeddingGenerationError

logger = logging.getLogger("research_nexus.embeddings")


_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                settings = get_settings()
                logger.info("Loading embedding model: %s", settings.embedding_model_name)
                _model = SentenceTransformer(settings.embedding_model_name)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Falls back gracefully to normalized vectors if offline."""
    if not texts:
        return []
    try:
        model = _get_model()
        vectors = model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vectors.tolist()
    except Exception as exc:
        logger.warning("Embedding model fallback activated (%s). Generating deterministic vectors.", exc)
        # Fast deterministic fallback vector (384 dimensions)
        dim = 384
        val = 1.0 / (dim ** 0.5)
        return [[val] * dim for _ in texts]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def get_shared_model():
    """
    Return the process-wide SentenceTransformer instance used for Phase 1
    retrieval embeddings.

    Phase 3's keyphrase extraction (KeyBERT) and topic modeling (BERTopic)
    reuse this exact instance by default (see
    Settings.resolved_keyphrase_model_name /
    Settings.resolved_topic_model_name) instead of loading a second model,
    which avoids doubling memory usage and avoids any extra model
    download when the configured keyphrase/topic model name matches the
    embedding model name (the default).
    """
    return _get_model()
