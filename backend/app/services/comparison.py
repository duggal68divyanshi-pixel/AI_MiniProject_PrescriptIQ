"""
Paper comparison: select 2-6 papers from a project and generate a
structured, dimension-by-dimension comparison table, grounded in evidence
retrieved independently from each paper (so a shorter/sparser paper isn't
crowded out of the context by a longer one).

Cached per exact set of compared document ids.
"""
from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from app.models.schemas import ComparisonDimension, ComparisonResponse, DocumentOut, SourceReference
from app.services import document_repository as doc_repo
from app.services.analysis_cache import get_cached, save
from app.services.llm_provider import get_llm_provider
from app.services.project_retrieval import retrieve_per_document_chunks

logger = logging.getLogger("research_nexus.comparison")

ANALYSIS_TYPE = "comparison"

_COMPARISON_QUERY = (
    "research problem, methodology, model architecture, dataset, "
    "evaluation metrics, results, contributions, limitations"
)

DIMENSIONS = [
    "Problem",
    "Methodology",
    "Model/Architecture",
    "Dataset",
    "Evaluation Metrics",
    "Results",
    "Contributions",
    "Limitations",
]

SYSTEM_PROMPT = """You compare multiple research papers side by side for a literature review.

Rules you MUST follow:
1. Use ONLY the evidence provided for each paper. Never invent a value.
2. If a paper's evidence doesn't cover a dimension, use "Not reported in the indexed text".
3. Keep every value short (1-2 sentences) and specific — no generic filler.
4. Respond with ONLY a single JSON object shaped like:
   {"<document_id>": {"Problem": "...", "Methodology": "...", "Model/Architecture": "...",
     "Dataset": "...", "Evaluation Metrics": "...", "Results": "...",
     "Contributions": "...", "Limitations": "..."}, ...}
   with one top-level key per document_id given below. No markdown fences, no commentary.
"""

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


async def compare_documents(
    project_id: UUID, document_ids: list[UUID], force_refresh: bool = False
) -> ComparisonResponse:
    documents = []
    for document_id in document_ids:
        documents.append(await doc_repo.get_document(document_id))

    if not force_refresh:
        cached = await get_cached(project_id, ANALYSIS_TYPE, document_ids)
        if cached is not None:
            content = cached["content"]
            return ComparisonResponse(
                documents=[DocumentOut(**d) for d in documents],
                dimensions=[ComparisonDimension(**dim) for dim in content["dimensions"]],
                sources=[SourceReference(**s) for s in content["sources"]],
                cached=True,
            )

    per_doc_chunks = await retrieve_per_document_chunks(
        _COMPARISON_QUERY, document_ids, top_k_per_document=6
    )

    context_parts = []
    all_sources: list[SourceReference] = []
    for document in documents:
        doc_id = document["id"]
        chunks = per_doc_chunks.get(doc_id, [])
        if not chunks:
            context_parts.append(f"=== Paper {doc_id} ({document['filename']}) ===\nNo indexed evidence available.")
            continue
        block = "\n\n".join(f"(page {c.page_number}) {c.content}" for c in chunks)
        context_parts.append(f"=== Paper {doc_id} ({document['filename']}) ===\n{block}")
        all_sources.extend(
            SourceReference(
                document=c.document_filename,
                document_id=c.document_id,
                page=c.page_number,
                chunk_id=c.chunk_id,
                similarity=round(c.similarity, 4),
                excerpt=(c.content[:200] + "…") if len(c.content) > 200 else c.content,
            )
            for c in chunks
        )

    full_context = "\n\n".join(context_parts)
    doc_id_list = ", ".join(str(d["id"]) for d in documents)
    provider = get_llm_provider()
    raw = provider.generate(
        SYSTEM_PROMPT,
        f"Document ids to compare: {doc_id_list}\n\n{full_context}\n\n"
        "Produce the comparison JSON now.",
    )
    match = _JSON_BLOCK_RE.search(raw)
    if not match:
        raise ValueError("Model did not return a JSON object for the comparison.")
    per_doc_values = json.loads(match.group(0))

    dimensions = []
    for dim in DIMENSIONS:
        values = {}
        for document in documents:
            doc_id_str = str(document["id"])
            doc_values = per_doc_values.get(doc_id_str, {})
            values[doc_id_str] = str(doc_values.get(dim, "Not reported in the indexed text"))
        dimensions.append(ComparisonDimension(dimension=dim, values=values))

    await save(
        project_id,
        ANALYSIS_TYPE,
        document_ids,
        {
            "dimensions": [d.model_dump() for d in dimensions],
            "sources": [s.model_dump(mode="json") for s in all_sources],
        },
    )

    return ComparisonResponse(
        documents=[DocumentOut(**d) for d in documents],
        dimensions=dimensions,
        sources=all_sources,
        cached=False,
    )
