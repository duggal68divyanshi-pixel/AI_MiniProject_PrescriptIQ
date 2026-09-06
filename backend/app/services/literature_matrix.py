"""
Literature review matrix.

For each indexed paper in a project, extracts structured findings
(research problem, methodology, model/algorithm, dataset, evaluation
metrics, key results, contributions, limitations) grounded in chunks
retrieved specifically for each of those dimensions — not one giant
"summarize everything" prompt, so each field is backed by the passages
most relevant to it.

Each paper's row is cached independently (keyed on that single
document_id) so re-opening the matrix, or adding a new paper to the
project, only extracts the papers that don't already have a cached row.
"""
from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from app.models.schemas import DocumentOut, LiteratureMatrixRow, SourceReference
from app.services import document_repository as doc_repo
from app.services import metadata_repository as meta_repo
from app.services.analysis_cache import get_cached, save
from app.services.llm_provider import get_llm_provider
from app.services.project_knowledge import get_structured_knowledge_for_matrix
from app.services.project_retrieval import retrieve_per_document_chunks

logger = logging.getLogger("research_nexus.matrix")

ANALYSIS_TYPE = "literature_matrix_row"

# One retrieval query per matrix dimension keeps each field grounded in
# the passages most relevant to it, instead of hoping a single top-k pull
# happens to cover methodology AND dataset AND limitations equally well.
_DIMENSION_QUERIES = {
    "research_problem": "research problem, motivation, objective of this paper",
    "methodology": "methodology, approach, method used",
    "model_or_algorithm": "model architecture, algorithm used",
    "dataset": "dataset used for training and evaluation",
    "evaluation_metrics": "evaluation metrics used to measure performance",
    "key_results": "key results, findings, performance achieved",
    "contributions": "main contributions of this paper",
    "limitations": "limitations, weaknesses, future work",
}

SYSTEM_PROMPT = """You extract structured findings from research paper evidence for a literature review matrix.

Rules you MUST follow:
1. Use ONLY the evidence chunks provided. Never invent a method, dataset, metric,
   result, contribution, or limitation that isn't stated in the evidence.
2. Each field must be a short, specific string (1-2 sentences). If the evidence does
   not cover a field, set it to "Not reported in the indexed text" — never guess.
3. Respond with ONLY a single JSON object using exactly these keys: research_problem,
   methodology, model_or_algorithm, dataset, evaluation_metrics, key_results,
   contributions, limitations. No markdown fences, no commentary.
"""

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
_NOT_REPORTED = "Not reported in the indexed text"


async def _extract_row_for_document(document: dict) -> LiteratureMatrixRow:
    document_id = document["id"]

    # Pull dimension-specific chunks so every field has grounded evidence,
    # deduplicating chunks that satisfy more than one dimension query.
    all_chunks = []
    seen_chunk_ids = set()
    for query in _DIMENSION_QUERIES.values():
        results = await retrieve_per_document_chunks(query, [document_id], top_k_per_document=2)
        for c in results.get(document_id, []):
            if c.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(c.chunk_id)
                all_chunks.append(c)

    if not all_chunks:
        raise ValueError("No indexed chunks available for this document.")

    context_block = "\n\n".join(
        f"[Source {i}] (page {c.page_number})\n{c.content}" for i, c in enumerate(all_chunks, start=1)
    )

    # Phase 3 enrichment (item 18): if scientific extraction has already
    # run for this paper, hand the LLM the already-verified structured
    # entities/limitations/results as a starting point so it only has to
    # fill in genuinely missing fields (research_problem, methodology
    # narrative, contributions) instead of re-deriving everything from
    # raw chunks alone. Falls back to pure LLM extraction (unchanged
    # Phase 2 behavior) whenever Phase 3 hasn't run yet — this call never
    # raises past this point.
    structured_block = ""
    try:
        structured = await get_structured_knowledge_for_matrix(document_id)
    except Exception:
        structured = {}
    if structured:
        structured_block = (
            "\n\nStructured knowledge already extracted for this paper by upstream ML models "
            "(prefer these over re-deriving from the raw evidence, but you may still fill gaps):\n"
            f"Models/algorithms detected: {', '.join(structured['models']) or 'none detected'}\n"
            f"Datasets detected: {', '.join(structured['datasets']) or 'none detected'}\n"
            f"Methods detected: {', '.join(structured['methods']) or 'none detected'}\n"
            f"Metrics detected: {', '.join(structured['metrics']) or 'none detected'}\n"
            f"Extracted limitations: {'; '.join(structured['limitations']) or 'none detected'}\n"
            f"Extracted result claims: {'; '.join(structured['results']) or 'none detected'}\n"
        )

    provider = get_llm_provider()
    raw = "{}"
    try:
        raw = provider.generate(
            SYSTEM_PROMPT,
            f"Evidence from '{document['filename']}':\n\n{context_block}{structured_block}\n\n"
            "Extract the structured findings now, as a single JSON object.",
        )
    except Exception as err:
        logger.warning("LLM provider error in literature matrix row extraction: %s", err)
        raw = "{}"
    data = {}
    try:
        match = _JSON_BLOCK_RE.search(raw)
        if match:
            data = json.loads(match.group(0))
        else:
            data = json.loads(raw)
    except Exception:
        data = {}


    metadata = await meta_repo.get_metadata(document_id)

    sources = [
        SourceReference(
            document=c.document_filename,
            document_id=c.document_id,
            page=c.page_number,
            chunk_id=c.chunk_id,
            similarity=round(c.similarity, 4),
            excerpt=(c.content[:200] + "…") if len(c.content) > 200 else c.content,
        )
        for c in all_chunks
    ]

    return LiteratureMatrixRow(
        document_id=document_id,
        filename=document["filename"],
        title=(metadata or {}).get("title") or document.get("title"),
        authors=(metadata or {}).get("authors"),
        publication_year=(metadata or {}).get("publication_year"),
        research_problem=str(data.get("research_problem") or _NOT_REPORTED),
        methodology=str(data.get("methodology") or _NOT_REPORTED),
        model_or_algorithm=str(data.get("model_or_algorithm") or _NOT_REPORTED),
        dataset=str(data.get("dataset") or _NOT_REPORTED),
        evaluation_metrics=str(data.get("evaluation_metrics") or _NOT_REPORTED),
        key_results=str(data.get("key_results") or _NOT_REPORTED),
        contributions=str(data.get("contributions") or _NOT_REPORTED),
        limitations=str(data.get("limitations") or _NOT_REPORTED),
        sources=sources,
    )


async def build_literature_matrix(
    project_id: UUID, document_ids: list[UUID], force_refresh: bool = False
) -> tuple[list[LiteratureMatrixRow], list[dict], bool]:
    """Returns (rows, skipped, any_cache_hit)."""
    rows: list[LiteratureMatrixRow] = []
    skipped: list[dict] = []
    any_cached = False

    for document_id in document_ids:
        try:
            document = await doc_repo.get_document(document_id)
        except Exception as exc:
            skipped.append({"document_id": str(document_id), "reason": str(exc)})
            continue

        if not force_refresh:
            cached = await get_cached(project_id, ANALYSIS_TYPE, [document_id])
            if cached is not None:
                rows.append(LiteratureMatrixRow(**cached["content"]))
                any_cached = True
                continue

        try:
            row = await _extract_row_for_document(document)
            await save(project_id, ANALYSIS_TYPE, [document_id], row.model_dump(mode="json"))
            rows.append(row)
        except Exception as exc:
            logger.warning("Literature matrix extraction failed for %s: %s", document_id, exc)
            skipped.append({"document_id": str(document_id), "reason": str(exc)})

    return rows, skipped, any_cached
