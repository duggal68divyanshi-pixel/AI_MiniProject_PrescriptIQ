"""
Topic discovery (Phase 3, item 6).

MODEL: BERTopic (github.com/MaartenGr/BERTopic, MIT license, actively
maintained). Pipeline: embed documents -> UMAP dimensionality reduction
-> HDBSCAN density-based clustering -> c-TF-IDF to name each cluster's
representative keywords. This is the established open-source approach
the brief explicitly names in item 6/20 — no LLM is asked "what are the
topics", clusters are found by real unsupervised ML.

Like keyphrase.py, this reuses `embeddings.get_shared_model()` as
BERTopic's `embedding_model`, so no extra model download happens by
default (unless `Settings.topic_model_name` is overridden).

SMALL-CORPUS SAFETY: BERTopic/HDBSCAN need a minimum number of documents
to form any cluster at all, and the demo scenario (item 37) only expects
5-10 papers. `min_topic_size` defaults to a small value
(Settings.topic_min_topic_size) precisely so a 5-10 paper demo project
still produces topics instead of dumping everything into the -1 outlier
bucket. If BERTopic still can't form a meaningful clustering (e.g. only
2-3 papers, or all papers are near-duplicates), `discover_topics` returns
an empty list rather than fabricating topics — this is documented in the
API response (see api/intelligence.py) as "not enough distinct papers to
discover topics yet".
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from app.core.config import get_settings

logger = logging.getLogger("research_nexus.ml.topics")

_lock = threading.Lock()


@dataclass
class TopicResult:
    topic_index: int
    label: str
    keywords: list[str]
    document_indices: list[int]  # indices into the input `documents` list
    probabilities: list[float | None]


def discover_topics(documents: list[str]) -> list[TopicResult]:
    """
    Run BERTopic over a project's papers (one representative text per
    paper — typically abstract + top keyphrases, built by the caller in
    services/topic_service.py so this module stays a pure ML wrapper with
    no database knowledge).

    Returns [] if there isn't enough distinct text to form topics (BERTopic
    raises/produces only outliers below a handful of documents) — this is
    a real, honestly-reported outcome, not an error.
    """
    if len(documents) < 3:
        logger.info("Only %d document(s) provided — need at least 3 for topic discovery.", len(documents))
        return []

    try:
        from bertopic import BERTopic

        from app.services.embeddings import get_shared_model
    except ImportError:
        logger.warning("bertopic is not installed — topic discovery skipped. `pip install bertopic`.")
        return []

    settings = get_settings()
    with _lock:
        embedder = get_shared_model()
        if settings.resolved_topic_model_name != settings.embedding_model_name:
            from sentence_transformers import SentenceTransformer

            embedder = SentenceTransformer(settings.resolved_topic_model_name)

        try:
            # umap_model/hdbscan_model left as BERTopic defaults, but
            # min_topic_size is lowered for small demo-sized corpora, and
            # calculate_probabilities is on so the UI can show real
            # assignment confidence rather than a fabricated number.
            topic_model = BERTopic(
                embedding_model=embedder,
                min_topic_size=min(settings.topic_min_topic_size, max(2, len(documents) // 2)),
                calculate_probabilities=True,
                verbose=False,
            )
            topics, probabilities = topic_model.fit_transform(documents)
        except Exception as exc:
            logger.error("BERTopic fit_transform failed: %s", exc)
            return []

    topic_info = topic_model.get_topic_info()
    results: list[TopicResult] = []
    for _, row in topic_info.iterrows():
        topic_idx = int(row["Topic"])
        if topic_idx == -1:
            continue  # outlier bucket — not a real topic, never surfaced
        keywords = [word for word, _score in topic_model.get_topic(topic_idx)][:8]
        doc_indices = [i for i, t in enumerate(topics) if t == topic_idx]
        probs: list[float | None] = []
        for i in doc_indices:
            try:
                p = probabilities[i]
                probs.append(float(p) if p is not None else None)
            except (IndexError, TypeError):
                probs.append(None)
        label = ", ".join(keywords[:3]).title() if keywords else f"Topic {topic_idx}"
        results.append(
            TopicResult(
                topic_index=topic_idx,
                label=label,
                keywords=keywords,
                document_indices=doc_indices,
                probabilities=probs,
            )
        )
    return results
