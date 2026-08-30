"""
Orchestrates the Phase 3 pipeline for one already-indexed document:

    chunks (from Phase 1)
        -> section detection            (ml/section_classifier.py)
        -> entity extraction              (ml/entity_extraction.py)
        -> keyphrase extraction           (ml/keyphrase.py)
        -> claim candidate shortlisting + LLM normalization
        -> limitation candidate shortlisting + LLM normalization
        -> relationship derivation        (deterministic, from the above)
        -> persist                        (scientific_repository.py)

Mirrors the shape of document_processor.py (Phase 1's orchestrator):
runs as a FastAPI BackgroundTask (no Celery/Redis — item 25 of the
brief), updates a processing_jobs row at every stage so the frontend can
poll progress the same way it already polls document status, and never
lets one stage's failure crash the whole pipeline — a partial result
(e.g. sections + entities, but claim extraction failed because the LLM
provider isn't configured) is still persisted and surfaced.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app.core.exceptions import DocumentNotIndexedError
from app.models.schemas import DocumentStatus
from app.services import document_repository as doc_repo
from app.services import scientific_repository as sci_repo
from app.services.ml import claim_extraction, entity_extraction, keyphrase, section_classifier

logger = logging.getLogger("research_nexus.scientific_extraction")


@dataclass
class _ChunkView:
    """Adapter so ml/section_classifier.py (written against the Phase 1
    Chunk dataclass shape) can walk chunk rows fetched from the DB."""

    chunk_index: int
    text: str
    page_number: int | None
    id: UUID


def _section_for_chunk(spans: list[section_classifier.SectionSpan], chunk_index: int) -> section_classifier.SectionSpan | None:
    for span in spans:
        if span.start_chunk_index <= chunk_index <= span.end_chunk_index:
            return span
    return None


async def run_paper_intelligence(document_id: UUID, job_id: UUID | None = None) -> dict:
    """Runs the full Phase 3 pipeline for one document. Returns a summary
    dict of what was extracted. Raises DocumentNotIndexedError if Phase 1
    hasn't finished for this document yet."""

    async def _stage(name: str):
        if job_id is not None:
            await sci_repo.update_job(job_id, status="running", progress_stage=name)

    document = await doc_repo.get_document(document_id)
    if document["status"] != DocumentStatus.INDEXED.value:
        raise DocumentNotIndexedError(
            f"Document '{document['filename']}' has status '{document['status']}', "
            "not 'indexed' — Phase 1 must finish before Phase 3 extraction can run."
        )

    if job_id is not None:
        await sci_repo.update_job(job_id, status="running", started=True)

    chunk_rows = await doc_repo.get_all_chunks(document_id)
    if not chunk_rows:
        raise DocumentNotIndexedError(f"Document '{document['filename']}' has no chunks to analyze.")
    chunks = [
        _ChunkView(chunk_index=r["chunk_index"], text=r["content"], page_number=r["page_number"], id=r["id"])
        for r in chunk_rows
    ]

    # --- 1. Section detection ---
    await _stage("sections")
    spans = section_classifier.detect_sections(chunks)
    await sci_repo.replace_sections(
        document_id,
        [
            {
                "section_label": s.section_label,
                "heading_text": s.heading_text,
                "start_chunk_index": s.start_chunk_index,
                "end_chunk_index": s.end_chunk_index,
                "page_start": s.page_start,
                "page_end": s.page_end,
                "detection_method": s.detection_method,
                "confidence": s.confidence,
            }
            for s in spans
        ],
    )

    # --- 2. Entity extraction (per chunk, so provenance is exact) ---
    await _stage("entities")
    all_mentions: list[dict] = []
    chunk_section_labels: dict[int, str] = {}
    for chunk in chunks:
        span = _section_for_chunk(spans, chunk.chunk_index)
        section_label = span.section_label if span else "other"
        chunk_section_labels[chunk.chunk_index] = section_label
        for mention in entity_extraction.extract_entities(chunk.text):
            all_mentions.append(
                {
                    **mention,
                    "chunk_id": chunk.id,
                    "section_label": section_label,
                    "page_number": chunk.page_number,
                }
            )
    await sci_repo.replace_paper_entities(document_id, all_mentions)

    # --- 3. Keyphrase extraction (whole-document text, capped) ---
    await _stage("keyphrases")
    full_text = "\n".join(c.text for c in chunks)[:20000]  # cap so KeyBERT stays fast on long papers
    phrases = keyphrase.extract_keyphrases(full_text)
    await sci_repo.replace_keyphrases(document_id, phrases)

    # --- 4. Claim candidates + LLM normalization ---
    await _stage("claims")
    claim_candidates: list[dict] = []  # candidate sentence -> chunk/section/page provenance
    for chunk in chunks:
        section_label = chunk_section_labels[chunk.chunk_index]
        for sentence in claim_extraction.find_claim_candidates(chunk.text, section_label):
            claim_candidates.append(
                {"sentence": sentence, "chunk_id": chunk.id, "section_label": section_label, "page_number": chunk.page_number}
            )
    claims_to_save: list[dict] = []
    if claim_candidates:
        try:
            normalized = claim_extraction.normalize_claims([c["sentence"] for c in claim_candidates])
            by_sentence = {c["sentence"]: c for c in claim_candidates}
            for item in normalized:
                evidence = str(item.get("evidence_text") or "")
                source = next((c for s, c in by_sentence.items() if evidence in s or s in evidence), None)
                claims_to_save.append(
                    {
                        "claim_type": item.get("claim_type") or "finding",
                        "claim_text": str(item.get("claim_text") or "").strip(),
                        "evidence_text": evidence,
                        "chunk_id": source["chunk_id"] if source else None,
                        "section_label": source["section_label"] if source else None,
                        "page_number": source["page_number"] if source else None,
                    }
                )
        except Exception:
            logger.exception("Claim normalization failed for %s (LLM provider issue?)", document_id)
    await sci_repo.replace_claims(document_id, claims_to_save)

    # --- 5. Limitation candidates + LLM normalization ---
    await _stage("limitations")
    limitation_candidates: list[dict] = []
    for chunk in chunks:
        section_label = chunk_section_labels[chunk.chunk_index]
        for sentence in claim_extraction.find_limitation_candidates(chunk.text, section_label):
            limitation_candidates.append(
                {"sentence": sentence, "chunk_id": chunk.id, "section_label": section_label, "page_number": chunk.page_number}
            )
    limitations_to_save: list[dict] = []
    if limitation_candidates:
        try:
            normalized = claim_extraction.normalize_limitations([c["sentence"] for c in limitation_candidates])
            by_sentence = {c["sentence"]: c for c in limitation_candidates}
            for item in normalized:
                evidence = str(item.get("evidence_text") or "")
                source = next((c for s, c in by_sentence.items() if evidence in s or s in evidence), None)
                limitations_to_save.append(
                    {
                        "limitation_text": str(item.get("limitation_text") or "").strip(),
                        "category": item.get("category") or "other",
                        "evidence_text": evidence,
                        "chunk_id": source["chunk_id"] if source else None,
                        "section_label": source["section_label"] if source else None,
                        "page_number": source["page_number"] if source else None,
                    }
                )
        except Exception:
            logger.exception("Limitation normalization failed for %s (LLM provider issue?)", document_id)
    await sci_repo.replace_limitations(document_id, limitations_to_save)

    # --- 6. Relationship derivation (deterministic, from what we already have) ---
    await _stage("relationships")
    relationships = await _derive_relationships(document_id, all_mentions, claims_to_save, limitations_to_save)
    await sci_repo.replace_relationships(document_id, relationships)

    if job_id is not None:
        await sci_repo.update_job(job_id, status="completed", progress_stage="done", finished=True)

    return {
        "document_id": str(document_id),
        "sections": len(spans),
        "entity_mentions": len(all_mentions),
        "keyphrases": len(phrases),
        "claims": len(claims_to_save),
        "limitations": len(limitations_to_save),
        "relationships": len(relationships),
    }


# Section -> predicate mapping: which section a mention was found in tells
# us what kind of relationship it likely is. Deterministic, no ML call.
_SECTION_TO_PREDICATE = {
    "dataset": "evaluates_on",
    "methodology": "proposes",
    "experiments": "uses",
    "results": "reports",
}


async def _derive_relationships(
    document_id: UUID, mentions: list[dict], claims: list[dict], limitations: list[dict]
) -> list[dict]:
    relationships: list[dict] = []

    # Paper -> uses/proposes/evaluates_on -> Entity, based on the section
    # the mention was found in (a MODEL mentioned in Methodology is
    # "proposes"/"uses"; a DATASET mentioned in Dataset/Experiments is
    # "evaluates_on"; anything in Results is "uses" the entity that
    # produced that result).
    seen_entity_predicates: set[tuple[str, str]] = set()
    for m in mentions:
        section = m.get("section_label") or "other"
        entity_type = m["entity_type"]
        if entity_type == "dataset":
            predicate = "evaluates_on"
        elif entity_type == "model" and section == "methodology":
            predicate = "proposes"
        else:
            predicate = _SECTION_TO_PREDICATE.get(section, "uses")

        entity_id = await sci_repo.get_or_create_entity(entity_type, m["canonical_name"])
        key = (str(entity_id), predicate)
        if key in seen_entity_predicates:
            continue
        seen_entity_predicates.add(key)
        relationships.append(
            {
                "predicate": predicate,
                "object_type": "entity",
                "object_entity_id": entity_id,
                "confidence": m.get("confidence"),
            }
        )

    # Paper -> reports -> Result (claim_type == 'result')
    for c in claims:
        if c["claim_type"] == "result":
            relationships.append(
                {"predicate": "reports", "object_type": "text", "object_text": c["claim_text"], "confidence": None}
            )

    return relationships


async def run_project_topics(project_id: UUID, document_ids: list[UUID], job_id: UUID | None = None) -> dict:
    """Delegates to topic_service.py — kept here as the single public
    entrypoint next to run_paper_intelligence for API symmetry."""
    from app.services.topic_service import discover_project_topics

    return await discover_project_topics(project_id, document_ids, job_id=job_id)
