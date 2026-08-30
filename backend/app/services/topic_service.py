"""
Project-level topic discovery orchestration (Phase 3, items 6/7/16/30).

Builds one representative text per paper — abstract if Phase 2 metadata
extraction succeeded, otherwise falls back to the paper's leading chunks
(title/abstract area) — plus its top keyphrases if already extracted, so
BERTopic (ml/topic_model.py) has a compact, high-signal document per
paper rather than the entire raw PDF text (which would be slow and would
let boilerplate/references dominate the clustering).
"""
from __future__ import annotations

import logging
from uuid import UUID, uuid4

from app.services import document_repository as doc_repo
from app.services import metadata_repository as meta_repo
from app.services import scientific_repository as sci_repo
from app.services.ml import topic_model

logger = logging.getLogger("research_nexus.topic_service")


async def _representative_text(document_id: UUID) -> str:
    metadata = await meta_repo.get_metadata(document_id)
    parts = []
    if metadata and metadata.get("abstract"):
        parts.append(metadata["abstract"])
    if metadata and metadata.get("title"):
        parts.append(metadata["title"])
    if not parts:
        leading = await doc_repo.get_leading_chunks(document_id, limit=3)
        parts.extend(c["content"] for c in leading)

    keyphrases = await sci_repo.get_keyphrases(document_id)
    if keyphrases:
        parts.append(" ".join(k["phrase"] for k in keyphrases[:10]))

    return "\n".join(parts).strip()


async def discover_project_topics(project_id: UUID, document_ids: list[UUID], job_id: UUID | None = None) -> dict:
    if job_id is not None:
        await sci_repo.update_job(job_id, status="running", progress_stage="building_corpus", started=True)

    texts: list[str] = []
    valid_document_ids: list[UUID] = []
    for document_id in document_ids:
        text = await _representative_text(document_id)
        if text:
            texts.append(text)
            valid_document_ids.append(document_id)

    if job_id is not None:
        await sci_repo.update_job(job_id, status="running", progress_stage="clustering")

    topics = topic_model.discover_topics(texts)

    if not topics:
        if job_id is not None:
            await sci_repo.update_job(job_id, status="completed", progress_stage="done", finished=True)
        return {"project_id": str(project_id), "topics": 0, "message": "Not enough distinct papers to discover topics yet."}

    model_run_id = uuid4()
    topic_dicts = [
        {
            "topic_index": t.topic_index,
            "label": t.label,
            "keywords": t.keywords,
            "document_indices": t.document_indices,
        }
        for t in topics
    ]
    topic_ids = await sci_repo.replace_project_topics(project_id, model_run_id, topic_dicts, valid_document_ids)

    assignments = []
    for t in topics:
        topic_row_id = topic_ids[t.topic_index]
        for idx, prob in zip(t.document_indices, t.probabilities):
            assignments.append(
                {"document_id": valid_document_ids[idx], "topic_id": topic_row_id, "probability": prob}
            )
    await sci_repo.insert_topic_assignments(assignments)

    if job_id is not None:
        await sci_repo.update_job(job_id, status="completed", progress_stage="done", finished=True)

    return {"project_id": str(project_id), "topics": len(topics), "papers_assigned": len(assignments)}
