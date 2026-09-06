from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query

from app.core.exceptions import ResearchNexusError
from app.models.schemas import (
    DiscoverySearchResponse,
    DocumentUploadResponse,
    ImportDiscoveredPaperRequest,
)
from app.services import document_repository as doc_repo
from app.services import project_repository as proj_repo
from app.services.discovery import (
    import_discovered_paper,
    search_scholarly_literature,
)

router = APIRouter(prefix="/api", tags=["discovery"])


@router.get("/discovery/search", response_model=DiscoverySearchResponse)
async def search_literature(
    query: str = Query(..., min_length=1, max_length=1000, description="Keywords, title, author, or research question"),
    source: str = Query("all", description="Source: 'all', 'arxiv', or 'semantic_scholar'"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
):
    papers = await search_scholarly_literature(query=query, source=source, limit=limit)
    return DiscoverySearchResponse(
        query=query,
        source=source,
        total_results=len(papers),
        papers=papers,
    )


@router.post("/projects/{project_id}/discovery/import", response_model=DocumentUploadResponse)
async def import_paper_to_project(
    project_id: UUID,
    payload: ImportDiscoveredPaperRequest,
    background_tasks: BackgroundTasks,
):
    await proj_repo.get_project(project_id)
    document_id = await import_discovered_paper(project_id, payload)
    return DocumentUploadResponse(
        id=document_id,
        filename=f"{payload.title[:50]}.pdf",
        status="uploaded",
        message=f"Discovered paper '{payload.title}' imported and indexing started.",
    )


@router.post("/documents/discovery/import", response_model=DocumentUploadResponse)
async def import_paper_standalone(
    payload: ImportDiscoveredPaperRequest,
    background_tasks: BackgroundTasks,
):
    document_id = await import_discovered_paper(None, payload)
    return DocumentUploadResponse(
        id=document_id,
        filename=f"{payload.title[:50]}.pdf",
        status="uploaded",
        message=f"Discovered paper '{payload.title}' imported and indexing started.",
    )
