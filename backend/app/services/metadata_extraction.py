"""
Structured paper metadata extraction.

Runs once, after a document finishes indexing (see document_processor.py).
Reads only the document's own leading chunks (title page / abstract) —
never invents a title, author list, year, or abstract that isn't
supported by that text. Anything the model can't find is returned as
null and stored as null; extraction_status records whether the call
itself succeeded, so the UI can distinguish "genuinely unknown" from
"extraction never ran / failed".

This is intentionally decoupled from the main RAG chat path — it's a
one-shot structured-output call, not a conversational answer, so it gets
its own small, strict system prompt.
"""
from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from app.services import document_repository as doc_repo
from app.services import metadata_repository as meta_repo
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger("research_nexus.metadata")

SYSTEM_PROMPT = """You extract bibliographic metadata from the opening text of a research paper.

Rules you MUST follow:
1. Use ONLY the text provided. Never invent a title, author, year, or abstract.
2. If a field is not clearly present in the text, set it to null. Do not guess.
3. "authors" must be a JSON array of individual author name strings, or null.
4. "publication_year" must be a 4-digit integer or null — never a range or approximation.
5. "keywords" must be a short JSON array of topical terms actually reflected in the
   text (e.g. from an explicit "Keywords:" line, or the paper's evident subject),
   or null if you cannot ground them in the text.
6. Respond with ONLY a single JSON object and nothing else — no markdown fences,
   no commentary, no preamble.

Output schema:
{"title": string|null, "authors": array|null, "publication_year": integer|null,
 "abstract": string|null, "keywords": array|null}
"""

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_response(raw: str) -> dict:
    match = _JSON_BLOCK_RE.search(raw)
    if not match:
        raise ValueError("No JSON object found in model output")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Model output was not a JSON object")
    return data


def _clean_year(value) -> int | None:
    if isinstance(value, int) and 1900 <= value <= 2100:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        year = int(value.strip())
        if 1900 <= year <= 2100:
            return year
    return None


def _clean_str_list(value) -> list[str] | None:
    if not isinstance(value, list):
        return None
    cleaned = [str(v).strip() for v in value if str(v).strip()]
    return cleaned or None


async def extract_and_store_metadata(document_id: UUID) -> None:
    """
    Best-effort — never raises. Any failure is recorded on the
    paper_metadata row as extraction_status='failed' so the document
    pipeline itself is never affected by this step.
    """
    try:
        chunks = await doc_repo.get_leading_chunks(document_id, limit=3)
        if not chunks:
            await meta_repo.save_failed(document_id, "No indexed chunks available to extract from.")
            return

        source_text = "\n\n".join(c["content"] for c in chunks)[:6000]
        provider = get_llm_provider()
        raw = provider.generate(
            SYSTEM_PROMPT,
            f"Opening text of the paper:\n\n{source_text}\n\nExtract the metadata now.",
        )
        data = _parse_response(raw)

        await meta_repo.save_extracted(
            document_id=document_id,
            title=(data.get("title") or None),
            authors=_clean_str_list(data.get("authors")),
            publication_year=_clean_year(data.get("publication_year")),
            abstract=(data.get("abstract") or None),
            keywords=_clean_str_list(data.get("keywords")),
        )
    except Exception as exc:  # metadata extraction is best-effort, never fatal
        logger.warning("Metadata extraction failed for %s: %s", document_id, exc)
        await meta_repo.save_failed(document_id, str(exc)[:500])
