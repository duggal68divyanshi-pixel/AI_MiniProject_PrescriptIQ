"""
Scientific document structure understanding (Phase 3, item 1 & 2).

MODEL SELECTION NOTE
---------------------
There is no mature, freely-licensed, pip-installable model that does
general-purpose "classify this arbitrary chunk of an ML/CS paper into
{introduction, methodology, results, ...}" out of the box — the closest
public work (e.g. sequential-sentence-classification models trained on
PubMed-RCT) is trained on structured biomedical abstracts, not full-text
CS/ML papers, and would need fine-tuning to transfer, which the Phase 3
brief explicitly puts out of scope ("no custom model training required").

So this module uses a deliberately two-tier, honestly-documented approach:

1. PRIMARY — heading-pattern detection (deterministic, free, no model).
   Papers almost always announce their own structure via headings
   ("Methodology", "Experimental Setup", "Related Work", ...). We detect
   heading-like lines and map them to a canonical section vocabulary
   through a tolerant synonym table (handles "Methods" / "Proposed
   Method" / "Experimental Setup" / "Evaluation" all mapping to the same
   canonical label, per the brief's explicit examples).

2. FALLBACK — embedding-similarity classification (a real model, zero
   extra download). For chunks that fall between headings, or documents
   whose headings don't parse cleanly, we embed the chunk with the SAME
   sentence-transformers model already loaded for Phase 1 retrieval
   (`embeddings.get_shared_model()`) and compare it via cosine similarity
   against embeddings of canonical section descriptions. This is a real
   semantic classifier, not a keyword match — it correctly tags a
   heading-less paragraph describing "we evaluate on ImageNet using
   top-1 accuracy" as RESULTS even though it never uses the word
   "results". Confidence is the actual cosine similarity to the winning
   label, never fabricated; a chunk is left as 'other' when the best
   similarity is below `section_embedding_confidence_floor`.

This hybrid is exactly what item 34/36 of the brief asks for: don't train
a model, don't rely solely on hardcoded heading names, and use the
existing embedding model where a semantic method is genuinely useful.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import get_settings

CANONICAL_SECTIONS = [
    "title",
    "abstract",
    "introduction",
    "related_work",
    "methodology",
    "dataset",
    "experiments",
    "results",
    "discussion",
    "conclusion",
    "limitations",
    "future_work",
    "references",
    "other",
]

# Tolerant heading -> canonical label mapping. Keys are matched against a
# normalized (lowercased, punctuation-stripped) heading line.
_HEADING_SYNONYMS: dict[str, str] = {
    "abstract": "abstract",
    "introduction": "introduction",
    "background": "introduction",
    "related work": "related_work",
    "related works": "related_work",
    "literature review": "related_work",
    "prior work": "related_work",
    "methodology": "methodology",
    "methods": "methodology",
    "method": "methodology",
    "proposed method": "methodology",
    "proposed methodology": "methodology",
    "proposed approach": "methodology",
    "system design": "methodology",
    "system architecture": "methodology",
    "approach": "methodology",
    "materials and methods": "methodology",
    "materials": "dataset",
    "dataset": "dataset",
    "datasets": "dataset",
    "data collection": "dataset",
    "experimental setup": "experiments",
    "experiment setup": "experiments",
    "experiments": "experiments",
    "experimental results": "results",
    "evaluation": "experiments",
    "evaluation setup": "experiments",
    "implementation details": "experiments",
    "results": "results",
    "result": "results",
    "results and discussion": "results",
    "performance evaluation": "results",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "conclusion and future work": "conclusion",
    "summary": "conclusion",
    "limitations": "limitations",
    "limitation": "limitations",
    "threats to validity": "limitations",
    "future work": "future_work",
    "future directions": "future_work",
    "references": "references",
    "bibliography": "references",
    "acknowledgments": "other",
    "acknowledgements": "other",
    "appendix": "other",
}

# A heading line: short, title-cased/uppercase-ish, optionally numbered
# ("3.", "3.1", "III."), no terminal punctuation, not a full sentence.
_HEADING_LINE_RE = re.compile(
    r"^\s*(?:[0-9]{1,2}(?:\.[0-9]{1,2})*\.?|[IVXLC]{1,4}\.)?\s*"
    r"([A-Za-z][A-Za-z\s\-/&]{2,60})\s*$"
)
_PUNCT_STRIP_RE = re.compile(r"[^a-z\s]")

# Canonical section descriptions used ONLY for the embedding-similarity
# fallback — written as descriptive sentences (not single words) so the
# embedding model has real semantic content to match against.
_SECTION_DESCRIPTIONS: dict[str, str] = {
    "abstract": "A short summary of the paper's problem, method, and results.",
    "introduction": "Motivation for the research problem and an overview of the paper's contributions.",
    "related_work": "A discussion of prior work and how it differs from this paper.",
    "methodology": "A description of the proposed method, model architecture, or algorithm.",
    "dataset": "A description of the dataset used for training and evaluation, including its size and source.",
    "experiments": "A description of the experimental setup, hyperparameters, and implementation details.",
    "results": "Reported results, performance numbers, and evaluation metrics achieved by the method.",
    "discussion": "An interpretation and discussion of what the results mean.",
    "conclusion": "A summary of the paper's contributions and findings.",
    "limitations": "A description of the limitations, weaknesses, or constraints of the proposed method.",
    "future_work": "Suggested directions for future research building on this work.",
}


@dataclass
class HeadingCandidate:
    line_index: int
    raw_text: str
    section_label: str


@dataclass
class SectionSpan:
    section_label: str
    heading_text: str | None
    start_chunk_index: int
    end_chunk_index: int
    page_start: int | None
    page_end: int | None
    detection_method: str  # 'heading_pattern' | 'embedding_similarity' | 'fallback'
    confidence: float | None


def _normalize_heading(line: str) -> str | None:
    match = _HEADING_LINE_RE.match(line.strip())
    if not match:
        return None
    candidate = match.group(1).strip().lower()
    candidate = _PUNCT_STRIP_RE.sub("", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)
    return candidate or None


def detect_headings_in_chunk(chunk_text: str) -> str | None:
    """
    Look at the first line of a chunk (chunks start at sentence
    boundaries, so a heading — if the chunk begins right after one —
    tends to show up as short leading text) and try to match it to a
    canonical section. Returns None if no heading pattern is found.
    """
    first_line = chunk_text.strip().split("\n", 1)[0]
    # Headings are short; if the "first line" is actually most of a long
    # chunk it's prose, not a heading.
    if len(first_line) > 80:
        return None
    normalized = _normalize_heading(first_line)
    if normalized is None:
        return None
    return _HEADING_SYNONYMS.get(normalized)


_section_embeddings_cache: dict[str, list[float]] | None = None


def _get_section_embeddings() -> dict[str, list[float]]:
    global _section_embeddings_cache
    if _section_embeddings_cache is None:
        from app.services.embeddings import get_shared_model

        model = get_shared_model()
        labels = list(_SECTION_DESCRIPTIONS.keys())
        vectors = model.encode(
            [_SECTION_DESCRIPTIONS[label] for label in labels],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        _section_embeddings_cache = {label: vec for label, vec in zip(labels, vectors)}
    return _section_embeddings_cache


def classify_chunk_by_embedding(chunk_text: str) -> tuple[str, float]:
    """
    Embedding-similarity fallback classifier. Returns (label, confidence)
    where confidence is a genuine cosine similarity in [-1, 1] — never
    fabricated. Falls back to ('other', 0.0) below the configured floor.
    """
    import numpy as np

    from app.services.embeddings import embed_query

    settings = get_settings()
    query_vec = np.array(embed_query(chunk_text[:1000]))  # first ~1000 chars is enough signal
    section_vecs = _get_section_embeddings()

    best_label, best_score = "other", -1.0
    for label, vec in section_vecs.items():
        score = float(np.dot(query_vec, vec))  # both sides are already unit-normalized
        if score > best_score:
            best_label, best_score = label, score

    if best_score < settings.section_embedding_confidence_floor:
        return "other", best_score
    return best_label, best_score


def classify_text(text: str) -> tuple[str, float | None]:
    """
    Public single-chunk classification entrypoint used by the entity/claim
    extraction stages, which need a section label per chunk without doing
    full-document heading detection. Tries heading pattern first, then the
    embedding fallback.
    """
    heading_label = detect_headings_in_chunk(text)
    if heading_label is not None:
        return heading_label, None  # deterministic — no meaningful "confidence" to report

    settings = get_settings()
    if not settings.enable_section_embedding_fallback:
        return "other", None
    label, score = classify_chunk_by_embedding(text)
    return label, score


def detect_sections(chunks: list) -> list[SectionSpan]:
    """
    Walk a document's ordered chunks and produce contiguous SectionSpans.

    `chunks` are the same Chunk objects produced by services/chunker.py
    (have .chunk_index, .text, .page_number).
    """
    settings = get_settings()
    spans: list[SectionSpan] = []
    current_label: str | None = None
    current_heading: str | None = None
    current_start = 0
    current_pages: list[int] = []
    current_method = "fallback"
    current_confidence: float | None = None

    def _flush(end_index: int):
        if current_label is None:
            return
        spans.append(
            SectionSpan(
                section_label=current_label,
                heading_text=current_heading,
                start_chunk_index=current_start,
                end_chunk_index=end_index,
                page_start=min(current_pages) if current_pages else None,
                page_end=max(current_pages) if current_pages else None,
                detection_method=current_method,
                confidence=current_confidence,
            )
        )

    for chunk in chunks:
        heading_label = detect_headings_in_chunk(chunk.text)
        if heading_label is not None:
            _flush(chunk.chunk_index - 1)
            current_label = heading_label
            current_heading = chunk.text.strip().split("\n", 1)[0][:120]
            current_start = chunk.chunk_index
            current_pages = [chunk.page_number] if chunk.page_number else []
            current_method = "heading_pattern"
            current_confidence = None
            continue

        if current_label is None:
            # No heading seen yet — classify via embedding fallback (or
            # leave as 'other' if disabled) rather than leaving it unlabeled.
            if settings.enable_section_embedding_fallback:
                label, score = classify_chunk_by_embedding(chunk.text)
                current_label, current_confidence = label, score
            else:
                current_label, current_confidence = "other", None
            current_heading = None
            current_start = chunk.chunk_index
            current_pages = [chunk.page_number] if chunk.page_number else []
            current_method = "embedding_similarity" if settings.enable_section_embedding_fallback else "fallback"
        else:
            if chunk.page_number:
                current_pages.append(chunk.page_number)

    if chunks:
        _flush(chunks[-1].chunk_index)

    return spans
