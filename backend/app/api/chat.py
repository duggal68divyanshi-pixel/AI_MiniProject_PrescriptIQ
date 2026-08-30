from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import ChatRequest, ChatResponse
from app.services.rag import answer_question

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await answer_question(
        question=request.question,
        document_id=request.document_id,
        top_k=request.top_k,
    )
