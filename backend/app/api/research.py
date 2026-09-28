from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import AnalysisFailedError, InsufficientPapersError
from app.models.schemas import (
    AnalyticsResponse,
    AuthoringRequest,
    AuthoringResponse,
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
from app.services import document_repository as doc_repo
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


@router.get("/{project_id}/chat/history")
async def get_project_chat_history_endpoint(project_id: UUID):
    from app.services.project_chat import get_project_chat_history
    await proj_repo.get_project(project_id)
    return await get_project_chat_history(project_id)


@router.delete("/{project_id}/chat/history")
async def clear_project_chat_history_endpoint(project_id: UUID):
    from app.services.project_chat import clear_project_chat_history
    await proj_repo.get_project(project_id)
    success = await clear_project_chat_history(project_id)
    return {"cleared": success}



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


@router.get("/{project_id}/export/bibtex")
async def export_project_bibtex(project_id: UUID):
    from fastapi.responses import PlainTextResponse
    from app.services.citations import generate_bibtex
    from app.services.metadata_repository import get_metadata_for_documents

    project = await proj_repo.get_project(project_id)
    docs = await doc_repo.list_documents(project_id=project_id)
    indexed_ids = [d["id"] for d in docs if d["status"] == "indexed"]
    metadata_map = await get_metadata_for_documents(indexed_ids)

    entries = []
    for d in docs:
        if d["status"] != "indexed":
            continue
        meta = metadata_map.get(d["id"]) or {}
        paper_dict = {
            "title": meta.get("title") or d.get("title") or d.get("filename"),
            "authors": meta.get("authors") or [],
            "publication_year": meta.get("publication_year"),
            "venue": meta.get("venue"),
            "doi": meta.get("doi"),
        }
        entries.append(generate_bibtex(paper_dict))

    content = "\n\n".join(entries) if entries else "% No indexed papers in project."
    filename = f"{project['name'].lower().replace(' ', '_')}_bibliography.bib"
    return PlainTextResponse(
        content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{project_id}/export/ris")
async def export_project_ris(project_id: UUID):
    from fastapi.responses import PlainTextResponse
    from app.services.citations import generate_ris
    from app.services.metadata_repository import get_metadata_for_documents

    project = await proj_repo.get_project(project_id)
    docs = await doc_repo.list_documents(project_id=project_id)
    indexed_ids = [d["id"] for d in docs if d["status"] == "indexed"]
    metadata_map = await get_metadata_for_documents(indexed_ids)

    entries = []
    for d in docs:
        if d["status"] != "indexed":
            continue
        meta = metadata_map.get(d["id"]) or {}
        paper_dict = {
            "title": meta.get("title") or d.get("title") or d.get("filename"),
            "authors": meta.get("authors") or [],
            "publication_year": meta.get("publication_year"),
            "venue": meta.get("venue"),
            "doi": meta.get("doi"),
            "abstract": meta.get("abstract"),
        }
        entries.append(generate_ris(paper_dict))

    content = "\n\n".join(entries) if entries else "TY  - JOUR\nTI  - Empty\nER  - "
    filename = f"{project['name'].lower().replace(' ', '_')}_bibliography.ris"
    return PlainTextResponse(
        content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{project_id}/authoring/{section_type}", response_model=AuthoringResponse | None)
async def get_saved_authoring_section_endpoint(project_id: UUID, section_type: str):
    from app.services.authoring import get_saved_manuscript_section
    await proj_repo.get_project(project_id)
    res = await get_saved_manuscript_section(project_id, section_type=section_type)
    if res is None:
        return None
    return AuthoringResponse(**res)


@router.post("/{project_id}/authoring/generate", response_model=AuthoringResponse)
async def generate_authoring_section(project_id: UUID, request: AuthoringRequest):
    from app.services.authoring import generate_manuscript_section

    await proj_repo.get_project(project_id)
    indexed_ids = await proj_repo.get_indexed_document_ids(project_id)
    if not indexed_ids:
        raise InsufficientPapersError(
            "Paper authoring assistance requires at least 1 indexed paper in this project."
        )
    try:
        res = await generate_manuscript_section(
            project_id,
            section_type=request.section_type,
            custom_instructions=request.custom_instructions,
            force_refresh=request.force_refresh,
        )
        return AuthoringResponse(**res)
    except Exception as exc:
        raise AnalysisFailedError(f"Manuscript section drafting failed: {exc}") from exc
