from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_connection
from app.models.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    settings = get_settings()
    db_ok = await check_connection()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        embedding_model=settings.embedding_model_name,
        llm_provider=settings.llm_provider,
    )
