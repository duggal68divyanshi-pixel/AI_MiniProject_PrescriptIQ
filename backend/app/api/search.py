from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import SearchRequest, SearchResponse, SearchResultItem
from app.services.retrieval import retrieve_relevant_chunks

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def semantic_search(request: SearchRequest):
    chunks = await retrieve_relevant_chunks(
        request.query, top_k=request.top_k, document_id=request.document_id
    )
    results = [
        SearchResultItem(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            document_filename=c.document_filename,
            content=c.content,
            page_number=c.page_number,
            similarity=round(c.similarity, 4),
        )
        for c in chunks
    ]
    return SearchResponse(query=request.query, results=results)
