"""
Keyphrase / keyword extraction (Phase 3, item 5).

MODEL: KeyBERT (github.com/MaartenGr/KeyBERT, MIT license, actively
maintained). KeyBERT is not itself a neural network — it's an embedding-
based extraction ALGORITHM: it embeds candidate n-grams from the
document and ranks them by cosine similarity to the whole document's
embedding, using Maximal Marginal Relevance (MMR) to keep the top
results diverse rather than near-duplicates of each other.

Crucially, KeyBERT takes any sentence-transformers model as its backend.
This module passes it `embeddings.get_shared_model()` — the EXACT model
instance already loaded for Phase 1 retrieval — so keyphrase extraction
adds zero extra model downloads and zero extra resident memory beyond
KeyBERT's own (tiny) bookkeeping. This is a direct instance of the
brief's item 20/26: prefer semantic, embedding-based extraction over
generic keyword matching, without loading a second large model.

INPUT:  raw document text (or a large representative excerpt).
OUTPUT: list of (phrase, score) where score is KeyBERT's real cosine
        similarity in [0, 1] to the document embedding — never faked.
"""
from __future__ import annotations

import logging
import threading

from app.core.config import get_settings

logger = logging.getLogger("research_nexus.ml.keyphrase")

_keybert_model = None
_lock = threading.Lock()


def _get_keybert():
    global _keybert_model
    if _keybert_model is None:
        with _lock:
            if _keybert_model is None:
                from keybert import KeyBERT

                from app.services.embeddings import get_shared_model

                settings = get_settings()
                backend = get_shared_model()
                if settings.resolved_keyphrase_model_name != settings.embedding_model_name:
                    # An explicit override was configured — load that
                    # model instead of reusing the retrieval embedder.
                    from sentence_transformers import SentenceTransformer

                    backend = SentenceTransformer(settings.resolved_keyphrase_model_name)
                logger.info("Initializing KeyBERT (backend=%s)", settings.resolved_keyphrase_model_name)
                _keybert_model = KeyBERT(model=backend)
    return _keybert_model


def extract_keyphrases(text: str, top_n: int | None = None) -> list[tuple[str, float]]:
    """Extract top-N keyphrases (1-3 word n-grams) ranked by relevance."""
    if not text or not text.strip():
        return []
    settings = get_settings()
    top_n = top_n or settings.keyphrase_top_n
    try:
        model = _get_keybert()
        results = model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 3),
            stop_words="english",
            use_mmr=True,
            diversity=0.6,
            top_n=top_n,
        )
        return [(phrase, round(float(score), 4)) for phrase, score in results]
    except ImportError:
        logger.warning("keybert is not installed — keyphrase extraction skipped. `pip install keybert`.")
        return []
    except Exception as exc:
        logger.error("Keyphrase extraction failed: %s", exc)
        return []
