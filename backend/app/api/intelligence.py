from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks

from app.core.exceptions import AnalysisFailedError, InsufficientPapersError
from app.models.schemas import (
    AnalyzeDocumentResponse,
    ClaimOut,
    EntityDetailResponse,
    EntityMentionOut,
    KeyphraseOut,
    LimitationOut,
    MLModelInfoOut,
    PaperIntelligenceResponse,
    ProcessingJobOut,
    ProjectAnalyzeRequest,
    ProjectAnalyzeResponse,
    ProjectEntitySummary,
    ProjectKnowledgeResponse,
    ProjectTopicOut,
    RelationshipOut,
    SectionOut,
    TopicDetailResponse,
)
from app.services import document_repository as doc_repo
from app.services import project_repository as proj_repo
from app.services import scientific_extraction
from app.services import scientific_repository as sci_repo
from app.services.ml.model_registry import get_model_registry
from app.services.project_knowledge import get_project_knowledge

logger = logging.getLogger("research_nexus.api.intelligence")

document_router = APIRouter(prefix="/api/documents", tags=["intelligence"])
project_router = APIRouter(prefix="/api/projects", tags=["intelligence"])
system_router = APIRouter(prefix="/api/system", tags=["intelligence"])


async def _run_paper_intelligence_job(document_id: UUID, job_id: UUID) -> None:
    try:
        await scientific_extraction.run_paper_intelligence(document_id, job_id=job_id)
    except Exception as exc:
        logger.exception("Phase 3 extraction failed for %s", document_id)
        await sci_repo.update_job(job_id, status="failed", error_message=str(exc), finished=True)


async def _run_project_topics_job(project_id: UUID, document_ids: list[UUID], job_id: UUID) -> None:
    try:
        await scientific_extraction.run_project_topics(project_id, document_ids, job_id=job_id)
    except Exception as exc:
        logger.exception("Topic discovery failed for project %s", project_id)
        await sci_repo.update_job(job_id, status="failed", error_message=str(exc), finished=True)


# ---------------------------------------------------------------------
# Per-document endpoints
# ---------------------------------------------------------------------

@document_router.post("/{document_id}/analyze", response_model=AnalyzeDocumentResponse)
async def analyze_document(document_id: UUID, background_tasks: BackgroundTasks):
    """Trigger the Phase 3 scientific-extraction pipeline for one document."""
    await doc_repo.get_document(document_id)  # 404s if it doesn't exist
    job_id = await sci_repo.create_job("paper_intelligence", document_id=document_id)
    background_tasks.add_task(_run_paper_intelligence_job, document_id, job_id)
    return AnalyzeDocumentResponse(
        document_id=document_id,
        job_id=job_id,
        status="queued",
        message="Scientific extraction started. Poll GET /api/documents/{id}/jobs/{job_id}.",
    )


@document_router.get("/{document_id}/jobs/{job_id}", response_model=ProcessingJobOut)
async def get_job_status(document_id: UUID, job_id: UUID):
    return ProcessingJobOut(**await sci_repo.get_job(job_id))


@document_router.get("/{document_id}/intelligence", response_model=PaperIntelligenceResponse)
async def get_paper_intelligence(document_id: UUID):
    document = await doc_repo.get_document(document_id)
    has_intel = await sci_repo.has_intelligence(document_id)
    latest_job = await sci_repo.get_latest_job(document_id, "paper_intelligence")

    sections = await sci_repo.get_sections(document_id) if has_intel else []
    entities = await sci_repo.get_paper_entities(document_id) if has_intel else []
    keyphrases = await sci_repo.get_keyphrases(document_id) if has_intel else []
    claims = await sci_repo.get_claims(document_id) if has_intel else []
    limitations = await sci_repo.get_limitations(document_id) if has_intel else []
    relationships = await sci_repo.get_relationships(document_id) if has_intel else []
    topics = await sci_repo.get_paper_topics(document_id) if has_intel else []

    return PaperIntelligenceResponse(
        document_id=document_id,
        filename=document["filename"],
        analysis_available=has_intel,
        last_job_status=latest_job["status"] if latest_job else None,
        sections=[SectionOut(**s) for s in sections],
        entities=[EntityMentionOut(**e) for e in entities],
        keyphrases=[KeyphraseOut(**k) for k in keyphrases],
        claims=[ClaimOut(**c) for c in claims],
        limitations=[LimitationOut(**limitation) for limitation in limitations],
        relationships=[RelationshipOut(**r) for r in relationships],
        topics=[dict(t) for t in topics],
    )


@document_router.get("/{document_id}/entities", response_model=list[EntityMentionOut])
async def get_document_entities(document_id: UUID):
    await doc_repo.get_document(document_id)
    return [EntityMentionOut(**e) for e in await sci_repo.get_paper_entities(document_id)]


@document_router.get("/{document_id}/claims", response_model=list[ClaimOut])
async def get_document_claims(document_id: UUID):
    await doc_repo.get_document(document_id)
    return [ClaimOut(**c) for c in await sci_repo.get_claims(document_id)]


@document_router.get("/{document_id}/limitations", response_model=list[LimitationOut])
async def get_document_limitations(document_id: UUID):
    await doc_repo.get_document(document_id)
    return [LimitationOut(**limitation) for limitation in await sci_repo.get_limitations(document_id)]


@document_router.get("/{document_id}/sections", response_model=list[SectionOut])
async def get_document_sections(document_id: UUID):
    await doc_repo.get_document(document_id)
    return [SectionOut(**s) for s in await sci_repo.get_sections(document_id)]


# ---------------------------------------------------------------------
# Project-level endpoints
# ---------------------------------------------------------------------

@project_router.post("/{project_id}/analyze", response_model=ProjectAnalyzeResponse)
async def analyze_project(project_id: UUID, request: ProjectAnalyzeRequest, background_tasks: BackgroundTasks):
    """Trigger Phase 3 extraction for every indexed paper in a project,
    plus (optionally) project-level topic discovery once entity/keyphrase
    extraction has a chance to complete for each paper."""
    await proj_repo.get_project(project_id)
    indexed_ids = await proj_repo.get_indexed_document_ids(project_id)
    if not indexed_ids:
        raise InsufficientPapersError("This project has no indexed papers to analyze yet.")

    jobs: list[dict] = []
    for document_id in indexed_ids:
        job_id = await sci_repo.create_job("paper_intelligence", document_id=document_id)
        background_tasks.add_task(_run_paper_intelligence_job, document_id, job_id)
        jobs.append(await sci_repo.get_job(job_id))

    topics_job_id = None
    if request.include_topics and len(indexed_ids) >= 3:
        topics_job_id = await sci_repo.create_job("project_topics", project_id=project_id)
        background_tasks.add_task(_run_project_topics_job, project_id, indexed_ids, topics_job_id)

    return ProjectAnalyzeResponse(
        project_id=project_id,
        jobs=[ProcessingJobOut(**j) for j in jobs],
        topics_job_id=topics_job_id,
        message=f"Scientific extraction started for {len(indexed_ids)} paper(s)."
        + (" Topic discovery queued." if topics_job_id else ""),
    )


@project_router.get("/{project_id}/knowledge", response_model=ProjectKnowledgeResponse)
async def get_project_knowledge_view(project_id: UUID):
    await proj_repo.get_project(project_id)
    indexed_ids = await proj_repo.get_indexed_document_ids(project_id)
    knowledge = await get_project_knowledge(project_id, indexed_ids)
    # Count how many indexed papers have already been through AI Analysis
    analyzed_count = 0
    for doc_id in indexed_ids:
        if await sci_repo.has_intelligence(doc_id):
            analyzed_count += 1
    return ProjectKnowledgeResponse(**knowledge, analyzed_count=analyzed_count)


@project_router.get("/{project_id}/entities", response_model=list[ProjectEntitySummary])
async def get_project_entities(project_id: UUID):
    await proj_repo.get_project(project_id)
    indexed_ids = await proj_repo.get_indexed_document_ids(project_id)
    rows = await sci_repo.get_project_entities(indexed_ids)
    return [ProjectEntitySummary(**r) for r in rows]


@project_router.get("/{project_id}/entities/{entity_id}", response_model=EntityDetailResponse)
async def get_project_entity_detail(project_id: UUID, entity_id: UUID):
    await proj_repo.get_project(project_id)
    indexed_ids = await proj_repo.get_indexed_document_ids(project_id)
    detail = await sci_repo.get_entity_detail(entity_id, document_ids=indexed_ids)
    if detail is None:
        raise AnalysisFailedError("Entity not found.")
    return EntityDetailResponse(**detail)


@project_router.get("/{project_id}/topics", response_model=list[ProjectTopicOut])
async def get_project_topics(project_id: UUID):
    await proj_repo.get_project(project_id)
    return [ProjectTopicOut(**t) for t in await sci_repo.get_project_topics(project_id)]


@project_router.get("/{project_id}/topics/{topic_id}", response_model=TopicDetailResponse)
async def get_project_topic_detail(project_id: UUID, topic_id: UUID):
    await proj_repo.get_project(project_id)
    detail = await sci_repo.get_topic_detail(topic_id)
    if detail is None:
        raise AnalysisFailedError("Topic not found.")
    return TopicDetailResponse(**detail)


@project_router.get("/{project_id}/jobs/{job_id}", response_model=ProcessingJobOut)
async def get_project_job_status(project_id: UUID, job_id: UUID):
    return ProcessingJobOut(**await sci_repo.get_job(job_id))


# ---------------------------------------------------------------------
# System / model registry
# ---------------------------------------------------------------------

@system_router.get("/ml-info", response_model=list[MLModelInfoOut])
async def get_ml_info():
    """Live status of every model/library Phase 3 can use — backs the
    README's model table and can be shown in the UI (item 32/33)."""
    return [MLModelInfoOut(**vars(m)) for m in get_model_registry()]
