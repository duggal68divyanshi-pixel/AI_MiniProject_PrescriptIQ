"""
Scientific entity extraction (Phase 3, items 3 & 4).

Two extraction passes, run per chunk:

1. GAZETTEER MATCH (primary, always runs). Uses `rapidfuzz` — a mature,
   MIT-licensed, actively maintained fuzzy-string-matching library (pure
   C++ core, no model download, negligible CPU cost) — to match paper
   text against the curated entity list in gazetteer.py. This is the
   "structured extraction layer" the brief asks for: canonical name,
   type, and a real confidence score (the fuzzy match ratio, 0-1) for
   every hit, never fabricated.

2. SPACY CANDIDATE PASS (optional, `Settings.enable_spacy_candidates`).
   spaCy's small English pipeline (en_core_web_sm — Apache 2.0 licensed,
   ~13MB, CPU-only, distributed as a pip-installable wheel from spaCy's
   own GitHub releases so it doesn't need a Hugging Face download) is
   used ONLY for noun-chunk extraction, to surface method-like phrases
   ("multi-head self-attention with relative position encoding") that
   aren't in the curated gazetteer. These are tagged with
   extraction_method='spacy_candidate' and a lower default confidence,
   clearly distinguished from gazetteer hits so downstream consumers
   (Knowledge Explorer) can treat them as lower-precision candidates
   rather than confirmed entities. If spaCy / the model isn't installed,
   this pass is skipped entirely and gazetteer matching still works.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.core.config import get_settings
from app.services.ml.gazetteer import iter_gazetteer_entries

logger = logging.getLogger("research_nexus.ml.entities")

_WORD_BOUNDARY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-\.]*")


@dataclass
class EntityMention:
    entity_type: str
    canonical_name: str
    mention_text: str
    start: int
    end: int
    confidence: float
    extraction_method: str  # 'gazetteer_match' | 'spacy_candidate'


def _sentence_context(text: str, start: int, end: int, window: int = 120) -> str:
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    excerpt = text[lo:hi].strip()
    return excerpt


def _gazetteer_matches(text: str) -> list[EntityMention]:
    """
    Exact + fuzzy alias matching over sliding n-grams of the text.

    Runs exact (case-insensitive) matching first (fast, confidence 1.0),
    then a fuzzy pass with rapidfuzz for near-misses (hyphenation,
    spacing, OCR noise), only over candidate tokens/phrases that didn't
    already match exactly — keeps this fast enough to run per-chunk over
    a whole paper.
    """
    settings = get_settings()
    lower_text = text.lower()
    mentions: list[EntityMention] = []
    matched_spans: set[tuple[int, int]] = set()

    # --- exact alias matching ---
    for entity_type, canonical_name, alias in iter_gazetteer_entries():
        alias_lower = alias.lower()
        start_search = 0
        while True:
            idx = lower_text.find(alias_lower, start_search)
            if idx == -1:
                break
            end = idx + len(alias_lower)
            # word-boundary check so "bert" doesn't match inside "robert"
            before_ok = idx == 0 or not lower_text[idx - 1].isalnum()
            after_ok = end == len(lower_text) or not lower_text[end].isalnum()
            if before_ok and after_ok:
                mentions.append(
                    EntityMention(
                        entity_type=entity_type,
                        canonical_name=canonical_name,
                        mention_text=text[idx:end],
                        start=idx,
                        end=end,
                        confidence=1.0,
                        extraction_method="gazetteer_match",
                    )
                )
                matched_spans.add((idx, end))
            start_search = idx + 1

    # --- fuzzy fallback over candidate word/phrase spans ---
    try:
        from rapidfuzz import fuzz
    except ImportError:
        logger.warning("rapidfuzz not installed — skipping fuzzy entity matching (exact matches still apply).")
        return mentions

    # Candidate spans: runs of 1-3 "word-like" tokens (covers hyphenated
    # model names / multi-word phrases) that weren't already exact-matched.
    tokens = list(_WORD_BOUNDARY_RE.finditer(text))
    all_aliases = list(iter_gazetteer_entries())
    for n in (1, 2, 3):
        for i in range(len(tokens) - n + 1):
            start, end = tokens[i].start(), tokens[i + n - 1].end()
            if any(s <= start and end <= e for s, e in matched_spans):
                continue
            span_text = text[start:end]
            if len(span_text) < 3:
                continue
            span_lower = span_text.lower()
            best_ratio, best_type, best_name = 0.0, None, None
            for entity_type, canonical_name, alias in all_aliases:
                ratio = fuzz.ratio(span_lower, alias.lower()) / 100.0
                if ratio > best_ratio:
                    best_ratio, best_type, best_name = ratio, entity_type, canonical_name
            if best_ratio >= settings.entity_fuzzy_match_threshold and best_type is not None:
                mentions.append(
                    EntityMention(
                        entity_type=best_type,
                        canonical_name=best_name,
                        mention_text=span_text,
                        start=start,
                        end=end,
                        confidence=round(best_ratio, 3),
                        extraction_method="gazetteer_match",
                    )
                )
                matched_spans.add((start, end))

    return mentions


_spacy_nlp = None
_spacy_load_failed = False


def _get_spacy_pipeline():
    global _spacy_nlp, _spacy_load_failed
    if _spacy_load_failed:
        return None
    if _spacy_nlp is None:
        try:
            import spacy

            settings = get_settings()
            _spacy_nlp = spacy.load(settings.spacy_model_name, disable=["ner", "lemmatizer"])
        except Exception as exc:  # model or library not installed
            logger.info(
                "spaCy candidate pass disabled (%s). Gazetteer matching still runs. "
                "See README.md for how to install en_core_web_sm.",
                exc,
            )
            _spacy_load_failed = True
            return None
    return _spacy_nlp


_METHOD_HEAD_WORDS = {
    "learning", "network", "networks", "model", "algorithm", "approach", "method",
    "architecture", "encoder", "decoder", "attention", "regularization", "loss",
    "embedding", "embeddings", "classifier", "optimization", "training", "layer",
}


def _spacy_candidates(text: str, existing_spans: set[tuple[int, int]]) -> list[EntityMention]:
    settings = get_settings()
    if not settings.enable_spacy_candidates:
        return []
    nlp = _get_spacy_pipeline()
    if nlp is None:
        return []

    mentions: list[EntityMention] = []
    doc = nlp(text[:5000])  # cap per-chunk cost; chunks are already ~400 words
    for chunk in doc.noun_chunks:
        # Only surface phrases that look like method/technique names, to
        # keep candidate noise low (2-5 words, ending in a method-y head
        # noun) rather than dumping every noun phrase in the paper.
        words = chunk.text.split()
        if not (2 <= len(words) <= 5):
            continue
        if words[-1].lower().strip(".,") not in _METHOD_HEAD_WORDS:
            continue
        start, end = chunk.start_char, chunk.end_char
        if any(s <= start and end <= e for s, e in existing_spans):
            continue
        mentions.append(
            EntityMention(
                entity_type="method",
                canonical_name=chunk.text.strip(),
                mention_text=chunk.text.strip(),
                start=start,
                end=end,
                confidence=0.5,  # candidate, not a confirmed gazetteer hit — never overstated
                extraction_method="spacy_candidate",
            )
        )
    return mentions


def extract_entities(text: str) -> list[dict]:
    """
    Extract entity mentions from a chunk of text.

    Returns a list of dicts (not the EntityMention dataclass directly) so
    callers can persist/serialize without importing this module's
    internals — the public contract of the ML service layer.
    """
    gazetteer_hits = _gazetteer_matches(text)
    existing_spans = {(m.start, m.end) for m in gazetteer_hits}
    candidate_hits = _spacy_candidates(text, existing_spans)

    results = []
    for m in gazetteer_hits + candidate_hits:
        results.append(
            {
                "entity_type": m.entity_type,
                "canonical_name": m.canonical_name,
                "mention_text": m.mention_text,
                "source_excerpt": _sentence_context(text, m.start, m.end),
                "confidence": m.confidence,
                "extraction_method": m.extraction_method,
            }
        )
    return results
