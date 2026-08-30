from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, UploadFile, File

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError
from app.models.schemas import DocumentOut, DocumentUploadResponse
from app.services import document_repository as repo
from app.services.document_processor import process_document

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _stored_path(document_id: UUID) -> Path:
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir / f"{document_id}.pdf"


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    settings = get_settings()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise InvalidFileTypeError(f"'{file.filename}' is not a PDF file.")
    if file.content_type not in ("application/pdf", "application/x-pdf", None):
        raise InvalidFileTypeError("Uploaded file is not a valid PDF (wrong content type).")

    file_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(
            f"File exceeds the {settings.max_upload_size_mb}MB limit."
        )
    if len(file_bytes) == 0:
        raise InvalidFileTypeError("Uploaded file is empty.")

    document_id = await repo.create_document(filename=file.filename, title=None)

    # Persist raw bytes so a failed/interrupted run can be retried via
    # POST /{id}/process without asking the user to re-upload.
    _stored_path(document_id).write_bytes(file_bytes)

    # Kick off the heavy pipeline in the background so the upload call
    # returns immediately; the frontend polls GET /api/documents/{id}.
    background_tasks.add_task(process_document, document_id, file_bytes, file.filename)

    return DocumentUploadResponse(
        id=document_id,
        filename=file.filename,
        status="uploaded",
        message="File received. Processing has started.",
    )


@router.get("", response_model=list[DocumentOut])
async def list_documents():
    rows = await repo.list_documents()
    return [DocumentOut(**row) for row in rows]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: UUID):
    row = await repo.get_document(document_id)
    return DocumentOut(**row)


@router.post("/{document_id}/process", response_model=DocumentOut)
async def reprocess_document(document_id: UUID, background_tasks: BackgroundTasks):
    """Re-run the pipeline for a document using its persisted file bytes."""
    row = await repo.get_document(document_id)
    stored = _stored_path(document_id)
    if not stored.exists():
        raise InvalidFileTypeError(
            "Original file bytes are no longer available on this server; please re-upload."
        )
    file_bytes = stored.read_bytes()
    background_tasks.add_task(process_document, document_id, file_bytes, row["filename"])
    return DocumentOut(**row)
