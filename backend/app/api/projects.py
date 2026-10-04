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
    await proj_repo.get_project(project_id)
    settings = get_settings()
    filename = file.filename or "paper.pdf"

    from app.services.ingestion_service import is_image_filename
    is_photo = is_image_filename(filename)

    file_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(f"File exceeds the {settings.max_upload_size_mb}MB limit.")
    if len(file_bytes) == 0:
        raise InvalidFileTypeError("Uploaded file is empty.")

    source_type = "single_photo" if is_photo else "native_pdf"
    document_id = await doc_repo.create_document(
        filename=filename, title=None, project_id=project_id, source_type=source_type
    )
    _stored_path(document_id).write_bytes(file_bytes)
    background_tasks.add_task(process_document, document_id, file_bytes, filename, is_photo=is_photo)

    return DocumentUploadResponse(
        id=document_id,
        filename=filename,
        status="uploaded",
        message="Paper received. Processing has started.",
    )


@router.post("/{project_id}/documents/upload-photos", response_model=DocumentUploadResponse)
async def upload_multi_photos_to_project(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    await proj_repo.get_project(project_id)
    settings = get_settings()
    if not files:
        raise InvalidFileTypeError("No image files provided for batch upload.")

    from app.services.ingestion_service import is_image_filename
    photo_files: list[tuple[bytes, str]] = []
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    for f in files:
        fname = f.filename or "paper_page.jpg"
        if not is_image_filename(fname):
            raise InvalidFileTypeError(f"'{fname}' is not a valid image format.")
        b = await f.read()
        if len(b) > max_bytes:
            raise FileTooLargeError(f"File '{fname}' exceeds size limit.")
        photo_files.append((b, fname))

    first_filename = photo_files[0][1]
    batch_filename = f"Batch Paper ({len(files)} pages) - {first_filename}"

    document_id = await doc_repo.create_document(
        filename=batch_filename, title=None, project_id=project_id, source_type="multi_photo"
    )
    background_tasks.add_task(
        process_document, document_id, b"", batch_filename, is_photo=True, multi_photos=photo_files
    )

    return DocumentUploadResponse(
        id=document_id,
        filename=batch_filename,
        status="uploaded",
        message=f"{len(files)} paper page photos added to project. Multi-page OCR pipeline started.",
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
