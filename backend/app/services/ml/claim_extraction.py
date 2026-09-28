"""
Scientific claim/finding extraction (Phase 3, item 8) and limitation
extraction (item 9).

APPROACH (matches the brief's explicit instruction: "Do not simply ask
the LLM to summarize the entire paper. First retrieve candidate
scientific statements using section classification / semantic methods,
then use the LLM only where appropriate for normalization or structured
extraction."):

1. CANDIDATE SHORTLISTING — deterministic, no model call. For each
   chunk, using the section label already produced by
   ml/section_classifier.py:
     - Claim candidates: sentences from RESULTS / DISCUSSION / CONCLUSION
       sections that contain a numeral, percentage, or a
       comparative/reporting cue word ("achieved", "outperform",
       "improve", "propose", "demonstrate", ...).
     - Limitation candidates: sentences from LIMITATIONS / FUTURE_WORK /
       DISCUSSION / CONCLUSION sections containing an explicit hedging or
       constraint cue word ("limitation", "however", "future work",
       "constrained by", "small dataset", "does not generalize", ...).
   This keeps the candidate list short (capped by
   Settings.max_claim_candidates_per_document /
   max_limitation_candidates_per_document) and already evidence-grounded
   BEFORE any LLM call — the LLM never sees or summarizes the raw paper.

2. LLM NORMALIZATION — the existing, already-configured `llm_provider`
   (Anthropic/OpenAI/mock — see services/llm_provider.py, unchanged) is
   given ONLY the shortlisted candidate sentences and asked to normalize
   each into one clean statement + classify its type. It is explicitly
   forbidden from inventing new claims beyond the candidates it was
   given, and every output row keeps the original candidate sentence as
   `evidence_text` for provenance.
"""
from __future__ import annotations

import json
import logging
import re

from app.core.config import get_settings
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger("research_nexus.ml.claims")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'\(])")
_NUMBER_RE = re.compile(r"\d")
_PERCENT_RE = re.compile(r"%|percent")

_CLAIM_CUE_WORDS = (
    "achieve", "achieved", "achieves", "outperform", "outperforms", "outperformed",
    "improve", "improved", "improves", "improvement", "propose", "proposes", "proposed",
    "demonstrate", "demonstrates", "demonstrated", "show that", "shows that", "showed that",
    "result", "results", "resulted", "we find", "we found", "we report", "our model",
    "our approach", "our method", "compared to", "compared with", "surpass", "state-of-the-art",
    "significant", "significantly",
)

_LIMITATION_CUE_WORDS = (
    "limitation", "limitations", "limited", "however", "does not generalize", "does not scale",
    "future work", "small dataset", "small sample", "not evaluated", "further work",
    "constrained by", "constraint", "drawback", "weakness", "fails to", "cannot", "could not",
    "lack of", "lacking", "remains a challenge", "remains challenging", "shortcoming",
    "computational cost", "computationally expensive", "may not", "might not",
)

_CLAIM_SECTIONS = {"results", "discussion", "conclusion", "experiments", "abstract", "other", "introduction", "background"}
_LIMITATION_SECTIONS = {"limitations", "future_work", "discussion", "conclusion", "abstract", "other"}


def _split_sentences(text: str) -> list[str]:
    sentences = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        for sent in _SENTENCE_SPLIT_RE.split(para):
            sent = sent.strip()
            if len(sent) >= 20:  # drop headings/fragments
                sentences.append(sent)
    return sentences


def find_claim_candidates(chunk_text: str, section_label: str) -> list[str]:
    if section_label not in _CLAIM_SECTIONS:
        return []
    candidates = []
    for sent in _split_sentences(chunk_text):
        lower = sent.lower()
        has_evidence = bool(_NUMBER_RE.search(sent)) or bool(_PERCENT_RE.search(lower))
        has_cue = any(cue in lower for cue in _CLAIM_CUE_WORDS)
        if has_evidence or has_cue:
            candidates.append(sent)
    return candidates


def find_limitation_candidates(chunk_text: str, section_label: str) -> list[str]:
    if section_label not in _LIMITATION_SECTIONS:
        return []
    candidates = []
    for sent in _split_sentences(chunk_text):
        lower = sent.lower()
        if any(cue in lower for cue in _LIMITATION_CUE_WORDS):
            candidates.append(sent)
    return candidates


_CLAIM_SYSTEM_PROMPT = """You normalize candidate sentences already extracted from a research paper's \
results/discussion/conclusion sections into structured scientific claims.

Rules you MUST follow:
1. Use ONLY the candidate sentences given. Never invent a claim that isn't backed by one of them.
2. Every output item must reference exactly one candidate sentence verbatim as "evidence_text".
3. "claim_text" is a normalized, single-sentence restatement (clear, concise, no hedging removed
   if it is part of the actual claim).
4. Classify "claim_type" as exactly one of: finding, contribution, result, observation, conclusion.
5. Skip candidate sentences that are not actually a scientific claim (e.g. pure narration).
6. Respond with ONLY a JSON array, each element shaped like:
   {"claim_text": "...", "claim_type": "...", "evidence_text": "<verbatim candidate sentence>"}
   No markdown fences, no commentary, no extra keys.
"""

_LIMITATION_SYSTEM_PROMPT = """You normalize candidate sentences already extracted from a research paper's \
limitations/future-work/discussion sections into structured limitation statements.

Rules you MUST follow:
1. Use ONLY the candidate sentences given. Never invent a limitation that isn't backed by one of them.
2. Every output item must reference exactly one candidate sentence verbatim as "evidence_text".
3. "limitation_text" is a normalized, single-sentence restatement of the limitation.
4. Classify "category" as exactly one of: dataset, computational, generalization, evaluation,
   methodological, future_work, other.
5. Skip candidate sentences that don't actually describe a limitation/constraint/future direction.
6. Respond with ONLY a JSON array, each element shaped like:
   {"limitation_text": "...", "category": "...", "evidence_text": "<verbatim candidate sentence>"}
   No markdown fences, no commentary, no extra keys.
"""

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _call_llm_for_normalization(system_prompt: str, candidates: list[str], cap: int) -> list[dict]:
    if not candidates:
        return []
    capped = candidates[:cap]
    provider = get_llm_provider()
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(capped))
    try:
        raw = provider.generate(
            system_prompt,
            f"Candidate sentences:\n{numbered}\n\nNormalize them now, as a JSON array.",
        )
        match = _JSON_ARRAY_RE.search(raw)
        if match:
            items = json.loads(match.group(0))
            if isinstance(items, list):
                valid: list[dict] = []
                for item in items:
                    evidence = str(item.get("evidence_text") or "").strip()
                    if not evidence:
                        continue
                    if any(evidence in c or c in evidence for c in capped):
                        valid.append(item)
                if valid:
                    return valid
    except Exception as exc:
        logger.warning("LLM normalization call failed: %s", exc)

    return []


def normalize_claims(candidates: list[str]) -> list[dict]:
    settings = get_settings()
    items = _call_llm_for_normalization(
        _CLAIM_SYSTEM_PROMPT, candidates, settings.max_claim_candidates_per_document
    )
    if not items and candidates:
        for sentence in candidates[:settings.max_claim_candidates_per_document]:
            items.append({
                "claim_text": sentence,
                "claim_type": "finding",
                "evidence_text": sentence
            })
    return items


def normalize_limitations(candidates: list[str]) -> list[dict]:
    settings = get_settings()
    items = _call_llm_for_normalization(
        _LIMITATION_SYSTEM_PROMPT, candidates, settings.max_limitation_candidates_per_document
    )
    if not items and candidates:
        for sentence in candidates[:settings.max_limitation_candidates_per_document]:
            items.append({
                "limitation_text": sentence,
                "category": "other",
                "evidence_text": sentence
            })
    return items
