"""
Project-level knowledge aggregation (Phase 3, item 16).

Pure aggregation over already-extracted, already-persisted structured
data — no new model calls happen here. This is what powers the "Project
Knowledge" tab and is also reused (item 17/18) to give the existing
Phase 2 gap-analysis and literature-matrix LLM prompts real structured
evidence instead of relying on the LLM alone.
"""
from __future__ import annotations

from collections import Counter
from uuid import UUID

from app.services import scientific_repository as sci_repo


async def get_project_knowledge(project_id: UUID, document_ids: list[UUID]) -> dict:
    entities = await sci_repo.get_project_entities(document_ids)
    topics = await sci_repo.get_project_topics(project_id)
    limitations = await sci_repo.get_project_limitations(document_ids)
    claims = await sci_repo.get_project_claims(document_ids, claim_types=["finding", "contribution", "result"])
    top_concepts = await sci_repo.get_project_top_concepts(document_ids)

    by_type: dict[str, list[dict]] = {}
    for e in entities:
        by_type.setdefault(e["entity_type"], []).append(e)

    limitation_counter = Counter(lim["limitation_text"].strip().lower() for lim in limitations)
    common_limitations = [
        {"limitation": text, "paper_count": count}
        for text, count in limitation_counter.most_common(10)
        if count >= 1
    ]

    return {
        "project_id": str(project_id),
        "paper_count": len(document_ids),
        "top_models": by_type.get("model", [])[:10],
        "top_datasets": by_type.get("dataset", [])[:10],
        "top_methods": by_type.get("method", [])[:10],
        "top_metrics": by_type.get("metric", [])[:10],
        "top_domains": by_type.get("domain", [])[:10],
        "top_tasks": by_type.get("task", [])[:10],
        "top_concepts": top_concepts,
        "topics": topics,
        "common_limitations": common_limitations,
        "key_findings": claims[:15],
    }


async def get_structured_knowledge_for_matrix(document_id: UUID) -> dict:
    """
    Best-effort structured fields for one paper, used to pre-seed the
    Phase 2 literature-matrix extraction prompt (item 18) so the LLM only
    has to fill genuinely missing fields instead of re-deriving
    everything from raw chunks. Returns {} if Phase 3 hasn't run for this
    document yet — the caller falls back to pure LLM extraction exactly
    as before, so this is a strict enhancement, never a regression.
    """
    if not await sci_repo.has_intelligence(document_id):
        return {}

    entities = await sci_repo.get_paper_entities(document_id)
    limitations = await sci_repo.get_limitations(document_id)
    claims = await sci_repo.get_claims(document_id)

    by_type: dict[str, list[str]] = {}
    for e in entities:
        by_type.setdefault(e["entity_type"], []).append(e["canonical_name"])

    return {
        "models": sorted(set(by_type.get("model", []))),
        "datasets": sorted(set(by_type.get("dataset", []))),
        "methods": sorted(set(by_type.get("method", []))),
        "metrics": sorted(set(by_type.get("metric", []))),
        "limitations": [lim["limitation_text"] for lim in limitations],
        "results": [c["claim_text"] for c in claims if c["claim_type"] == "result"],
    }
