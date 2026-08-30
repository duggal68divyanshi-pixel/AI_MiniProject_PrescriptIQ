from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, UploadFile

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError
from app.models.schemas import (
    DocumentOut,
    DocumentUploadResponse,
    PaperMetadataOut,
    ProjectCreate,
    ProjectDocumentOut,
    ProjectOut,
    ProjectUpdate,
)
from app.services import document_repository as doc_repo
from app.services import metadata_repository as meta_repo
from app.services import project_repository as proj_repo
from app.services.document_processor import process_document

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _stored_path(document_id: UUID) -> Path:
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir / f"{document_id}.pdf"


@router.post("", response_model=ProjectOut)
async def create_project(payload: ProjectCreate):
    project_id = await proj_repo.create_project(payload.name, payload.description)
    return ProjectOut(**await proj_repo.get_project(project_id))


@router.get("", response_model=list[ProjectOut])
async def list_projects():
    rows = await proj_repo.list_projects()
    return [ProjectOut(**row) for row in rows]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: UUID):
    return ProjectOut(**await proj_repo.get_project(project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: UUID, payload: ProjectUpdate):
    return ProjectOut(**await proj_repo.update_project(project_id, payload.name, payload.description))


@router.delete("/{project_id}")
async def delete_project(project_id: UUID):
    await proj_repo.delete_project(project_id)
    return {"deleted": True}


@router.post("/{project_id}/documents", response_model=DocumentUploadResponse)
async def upload_paper_to_project(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    # Validates the project exists before accepting the upload.
    await proj_repo.get_project(project_id)

    settings = get_settings()
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise InvalidFileTypeError(f"'{file.filename}' is not a PDF file.")
    if file.content_type not in ("application/pdf", "application/x-pdf", None):
        raise InvalidFileTypeError("Uploaded file is not a valid PDF (wrong content type).")

    file_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(f"File exceeds the {settings.max_upload_size_mb}MB limit.")
    if len(file_bytes) == 0:
        raise InvalidFileTypeError("Uploaded file is empty.")

    document_id = await doc_repo.create_document(
        filename=file.filename, title=None, project_id=project_id
    )
    _stored_path(document_id).write_bytes(file_bytes)
    background_tasks.add_task(process_document, document_id, file_bytes, file.filename)

    return DocumentUploadResponse(
        id=document_id,
        filename=file.filename,
        status="uploaded",
        message="File received. Processing has started.",
    )


@router.get("/{project_id}/documents", response_model=list[ProjectDocumentOut])
async def list_project_documents(project_id: UUID):
    await proj_repo.get_project(project_id)
    rows = await doc_repo.list_documents(project_id=project_id)
    metadata_map = await meta_repo.get_metadata_for_documents([r["id"] for r in rows])
    out = []
    for row in rows:
        meta = metadata_map.get(row["id"])
        out.append(
            ProjectDocumentOut(
                **row, metadata=PaperMetadataOut(**meta) if meta else None
            )
        )
    return out


@router.delete("/{project_id}/documents/{document_id}")
async def remove_paper_from_project(project_id: UUID, document_id: UUID):
    """Removes the paper FROM this project (per spec item 1). The document
    itself is not deleted — it just becomes a standalone Phase 1 document
    again, same as a project that gets deleted."""
    await proj_repo.get_project(project_id)
    await doc_repo.set_document_project(document_id, None)
    return {"removed": True}
