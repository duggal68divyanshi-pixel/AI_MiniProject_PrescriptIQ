from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import AnalysisFailedError, InsufficientPapersError
from app.models.schemas import (
    AnalyticsResponse,
    CompareRequest,
    ComparisonResponse,
    GapAnalysisRequest,
    GapAnalysisResponse,
    LiteratureMatrixResponse,
    ProjectChatRequest,
    ProjectChatResponse,
    ResearchQuestionsRequest,
    ResearchQuestionsResponse,
)
from app.services import project_repository as proj_repo
from app.services.analytics import get_project_analytics
from app.services.comparison import compare_documents
from app.services.gap_analysis import analyze_gaps
from app.services.literature_matrix import build_literature_matrix
from app.services.project_chat import answer_project_question
from app.services.research_questions import generate_research_questions

router = APIRouter(prefix="/api/projects", tags=["research"])


@router.post("/{project_id}/chat", response_model=ProjectChatResponse)
async def project_chat(project_id: UUID, request: ProjectChatRequest):
    await proj_repo.get_project(project_id)
    return await answer_project_question(project_id, request.question, top_k=request.top_k)


@router.post("/{project_id}/compare", response_model=ComparisonResponse)
async def compare_papers(project_id: UUID, request: CompareRequest):
    await proj_repo.get_project(project_id)
    indexed_ids = set(await proj_repo.get_indexed_document_ids(project_id))
    not_indexed = [d for d in request.document_ids if d not in indexed_ids]
    if not_indexed:
        raise InsufficientPapersError(
            "All selected papers must be fully indexed before comparing. "
            f"Not yet indexed: {', '.join(str(d) for d in not_indexed)}"
        )
    try:
        return await compare_documents(project_id, request.document_ids)
    except InsufficientPapersError:
        raise
    except Exception as exc:
        raise AnalysisFailedError(f"Comparison failed: {exc}") from exc


@router.get("/{project_id}/literature-matrix", response_model=LiteratureMatrixResponse)
async def literature_matrix(project_id: UUID, force_refresh: bool = False):
    await proj_repo.get_project(project_id)
    indexed_ids = await proj_repo.get_indexed_document_ids(project_id)
    if not indexed_ids:
        return LiteratureMatrixResponse(project_id=project_id, rows=[], skipped=[], cached=False)
    rows, skipped, any_cached = await build_literature_matrix(
        project_id, indexed_ids, force_refresh=force_refresh
    )
    return LiteratureMatrixResponse(project_id=project_id, rows=rows, skipped=skipped, cached=any_cached)


@router.post("/{project_id}/gap-analysis", response_model=GapAnalysisResponse)
async def gap_analysis(project_id: UUID, request: GapAnalysisRequest):
    await proj_repo.get_project(project_id)
    indexed_ids = await proj_repo.get_indexed_document_ids(project_id)
    if len(indexed_ids) < 2:
        raise InsufficientPapersError(
            "Gap analysis needs at least 2 fully indexed papers in this project."
        )
    try:
        gaps, cached, analysis_id = await analyze_gaps(
            project_id, indexed_ids, force_refresh=request.force_refresh
        )
    except ValueError as exc:
        raise InsufficientPapersError(str(exc)) from exc
    except Exception as exc:
        raise AnalysisFailedError(f"Gap analysis failed: {exc}") from exc
    return GapAnalysisResponse(
        project_id=project_id,
        gaps=gaps,
        papers_analyzed=len(indexed_ids),
        cached=cached,
        analysis_id=analysis_id,
    )


@router.post("/{project_id}/research-questions", response_model=ResearchQuestionsResponse)
async def research_questions(project_id: UUID, request: ResearchQuestionsRequest):
    await proj_repo.get_project(project_id)
    indexed_ids = await proj_repo.get_indexed_document_ids(project_id)
    if len(indexed_ids) < 2:
        raise InsufficientPapersError(
            "Research question generation needs at least 2 fully indexed papers in this project."
        )
    try:
        question_sets, cached = await generate_research_questions(
            project_id, indexed_ids, force_refresh=request.force_refresh
        )
    except ValueError as exc:
        raise InsufficientPapersError(str(exc)) from exc
    except Exception as exc:
        raise AnalysisFailedError(f"Research question generation failed: {exc}") from exc
    return ResearchQuestionsResponse(project_id=project_id, question_sets=question_sets, cached=cached)


@router.get("/{project_id}/analytics", response_model=AnalyticsResponse)
async def project_analytics(project_id: UUID):
    await proj_repo.get_project(project_id)
    indexed_ids = await proj_repo.get_indexed_document_ids(project_id)
    return await get_project_analytics(project_id, indexed_ids)
