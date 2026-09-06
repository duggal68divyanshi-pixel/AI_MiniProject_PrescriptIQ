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
            from umap import UMAP
            from hdbscan import HDBSCAN

            n_samples = len(documents)
            n_neighbors = min(15, max(2, n_samples - 1))
            n_components = min(5, max(2, n_samples - 1))
            min_cluster = min(settings.topic_min_topic_size, max(2, n_samples // 2))

            umap_model = UMAP(
                n_neighbors=n_neighbors,
                n_components=n_components,
                min_dist=0.0,
                metric="cosine",
                init="random",  # 'random' prevents scipy.linalg.eigh k >= N sparse matrix errors on small corpora
                random_state=42,
            )

            hdbscan_model = HDBSCAN(
                min_cluster_size=min_cluster,
                min_samples=1,
                metric="euclidean",
                cluster_selection_method="eom",
            )

            topic_model = BERTopic(
                embedding_model=embedder,
                umap_model=umap_model,
                hdbscan_model=hdbscan_model,
                min_topic_size=min_cluster,
                calculate_probabilities=True,
                verbose=False,
            )
            topics, probabilities = topic_model.fit_transform(documents)
        except Exception as exc:
            logger.warning("BERTopic fit_transform failed: %s — falling back to TF-IDF NMF topic extraction.", exc)
            return _tfidf_fallback_topics(documents)

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


def _tfidf_fallback_topics(documents: list[str]) -> list[TopicResult]:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import NMF

        n_samples = len(documents)
        n_topics = min(3, max(1, n_samples))
        vectorizer = TfidfVectorizer(max_df=1.0, min_df=1, stop_words="english")
        tfidf = vectorizer.fit_transform(documents)
        nmf_model = NMF(n_components=n_topics, random_state=42)
        doc_topics = nmf_model.fit_transform(tfidf)
        feature_names = vectorizer.get_feature_names_out()

        results = []
        for topic_idx, topic in enumerate(nmf_model.components_):
            top_indices = topic.argsort()[:-9:-1]
            keywords = [feature_names[i] for i in top_indices if i < len(feature_names)]
            if not keywords:
                continue
            doc_indices = [i for i, row in enumerate(doc_topics) if row.argmax() == topic_idx]
            if not doc_indices:
                doc_indices = list(range(n_samples))
            probs = [float(doc_topics[i, topic_idx]) for i in doc_indices]
            label = ", ".join(keywords[:3]).title() if keywords else f"Topic {topic_idx + 1}"
            results.append(
                TopicResult(
                    topic_index=topic_idx + 1,
                    label=label,
                    keywords=keywords,
                    document_indices=doc_indices,
                    probabilities=probs,
                )
            )
        return results
    except Exception as exc:
        logger.warning("TF-IDF NMF fallback topic extraction failed: %s", exc)
        return []
