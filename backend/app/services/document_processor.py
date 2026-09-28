"""
Orchestrates the full pipeline for one document:
extract -> clean -> chunk -> embed -> persist -> mark indexed.

Each stage updates the document's status row so the frontend can poll and
show live progress (Extracting -> Chunking -> Embedding -> Indexed).
Any failure is caught, logged, and recorded as a FAILED status with a
human-readable error_message instead of raising past the caller.
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.core.config import get_settings
from app.core.exceptions import ResearchNexusError
from app.models.schemas import DocumentStatus
from app.services import document_repository as repo
from app.services.chunker import chunk_document
from app.services.embeddings import embed_texts
from app.services import metadata_repository as meta_repo
from app.services.metadata_extraction import extract_and_store_metadata
from app.services.pdf_processor import extract_pdf

logger = logging.getLogger("research_nexus.pipeline")


async def process_document(document_id: UUID, file_bytes: bytes, filename: str) -> None:
    settings = get_settings()
    try:
        # 1. EXTRACT
        await repo.update_status(document_id, DocumentStatus.EXTRACTING)
        extraction = extract_pdf(file_bytes, filename)
        await repo.update_status(
            document_id, DocumentStatus.EXTRACTING, page_count=extraction.total_pages
        )

        # 2. CHUNK
        await repo.update_status(document_id, DocumentStatus.CHUNKING)
        chunks = chunk_document(
            extraction.pages,
            chunk_size_tokens=settings.chunk_size_tokens,
            chunk_overlap_tokens=settings.chunk_overlap_tokens,
        )
        if not chunks:
            raise ResearchNexusError("Chunking produced zero chunks — document may be empty.")

        # 3. EMBED
        await repo.update_status(document_id, DocumentStatus.EMBEDDING)
        embeddings = embed_texts([c.text for c in chunks])

        # 4. PERSIST + INDEX
        await repo.insert_chunks(document_id, chunks, embeddings)
        await repo.update_status(document_id, DocumentStatus.INDEXED)
        logger.info(
            "Document %s indexed: %d pages, %d chunks", document_id, extraction.total_pages, len(chunks)
        )

        # 5. Phase 2: best-effort structured metadata extraction (title,
        # authors, year, abstract, keywords). Never allowed to affect the
        # document's own status — a paper is "indexed" regardless of
        # whether this succeeds, since retrieval/chat don't depend on it.
        try:
            await meta_repo.upsert_pending(document_id)  # ensure row always exists
            await extract_and_store_metadata(document_id)
        except Exception:
            logger.exception("Metadata extraction step raised unexpectedly for %s", document_id)

    except ResearchNexusError as exc:
        logger.warning("Processing failed for %s: %s", document_id, exc.message)
        await repo.update_status(document_id, DocumentStatus.FAILED, error_message=exc.message)
    except Exception as exc:  # unexpected — still never crash the background task
        logger.exception("Unexpected error processing %s", document_id)
        await repo.update_status(
            document_id, DocumentStatus.FAILED, error_message=f"Unexpected error: {exc}"
        )
