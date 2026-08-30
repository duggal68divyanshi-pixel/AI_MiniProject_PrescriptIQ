from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, documents, health, intelligence, projects, research, search
from app.core.config import get_settings
from app.core.database import close_pool, init_pool
from app.core.exceptions import ResearchNexusError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("research_nexus")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_pool()
    except Exception:
        logger.error(
            "Startup: could not connect to the database. Check DATABASE_URL "
            "in your .env file. The API will start but most endpoints will fail."
        )
    yield
    await close_pool()


app = FastAPI(
    title="Research Nexus — Research Intelligence Core",
    description="PDF ingestion, semantic search, and grounded RAG question answering.",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ResearchNexusError)
async def domain_error_handler(request: Request, exc: ResearchNexusError):
    logger.warning("%s: %s", exc.__class__.__name__, exc.message)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )


app.include_router(documents.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(research.router)
app.include_router(intelligence.document_router)
app.include_router(intelligence.project_router)
app.include_router(intelligence.system_router)
