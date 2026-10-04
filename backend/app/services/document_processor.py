"""
Orchestrates the full pipeline for one document (PDF or Paper Photo):
extract/OCR -> clean -> chunk -> embed -> persist -> mark indexed.

Saves page images and OCR metadata to document_pages for human verification UI.
"""
from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.core.exceptions import ResearchNexusError
from app.models.schemas import DocumentStatus
from app.services import document_repository as repo
from app.services.chunker import chunk_document
from app.services.embeddings import embed_texts
from app.services import metadata_repository as meta_repo
from app.services.metadata_extraction import extract_and_store_metadata
from app.services.ingestion_service import ingest_document, ingest_multi_photo_batch, IngestionResult

logger = logging.getLogger("research_nexus.pipeline")


async def process_document(
    document_id: UUID,
    file_bytes: bytes,
    filename: str,
    is_photo: bool = False,
    multi_photos: list[tuple[bytes, str]] | None = None,
) -> None:
    settings = get_settings()
    try:
        # 1. EXTRACT / OCR
        await repo.update_status(document_id, DocumentStatus.EXTRACTING)

        if multi_photos:
            ingestion: IngestionResult = ingest_multi_photo_batch(multi_photos)
        else:
            ingestion = ingest_document(file_bytes, filename, is_photo=is_photo)

        extraction = ingestion.extraction
        await repo.update_status(
            document_id, DocumentStatus.EXTRACTING, page_count=extraction.total_pages
        )

        # Persist page images and OCR metadata
        page_dir = Path(settings.upload_dir) / "pages" / str(document_id)
        page_dir.mkdir(parents=True, exist_ok=True)

        for page_res in ingestion.page_results:
            page_num = page_res.page_number
            img_file = page_dir / f"page_{page_num}.png"

            await repo.upsert_document_page(
                document_id=document_id,
                page_number=page_num,
                image_path=str(img_file),
                extracted_text=page_res.text,
                ocr_engine=page_res.ocr_engine,
                ocr_confidence=page_res.confidence,
                ocr_status="completed",
                layout_blocks=page_res.blocks,
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

        # 5. Metadata extraction pass
        try:
            await meta_repo.upsert_pending(document_id)
            await extract_and_store_metadata(document_id)
        except Exception:
            logger.exception("Metadata extraction step raised unexpectedly for %s", document_id)

    except ResearchNexusError as exc:
        logger.warning("Processing failed for %s: %s", document_id, exc.message)
        await repo.update_status(document_id, DocumentStatus.FAILED, error_message=exc.message)
    except Exception as exc:
        logger.exception("Unexpected error processing %s", document_id)
        await repo.update_status(
            document_id, DocumentStatus.FAILED, error_message=f"Unexpected error: {exc}"
        )
