from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError, DocumentNotFoundError
from app.models.schemas import (
    DocumentOut,
    DocumentPageOut,
    DocumentUploadResponse,
    OcrEvaluationResponse,
    OcrReprocessRequest,
    PageTextUpdate,
)
from app.services import document_repository as repo
from app.services.document_processor import process_document
from app.services.ingestion_service import is_image_filename
from app.services.ocr_processor import run_ocr_on_image

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
    filename = file.filename or "uploaded_paper.pdf"

    if is_image_filename(filename):
        return await upload_single_photo(background_tasks=background_tasks, file=file)

    if not filename.lower().endswith(".pdf"):
        raise InvalidFileTypeError(f"'{filename}' is not a PDF or accepted image file (.png, .jpg, .webp).")

    file_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(f"File exceeds the {settings.max_upload_size_mb}MB limit.")
    if len(file_bytes) == 0:
        raise InvalidFileTypeError("Uploaded file is empty.")

    document_id = await repo.create_document(filename=filename, title=None, source_type="native_pdf")
    _stored_path(document_id).write_bytes(file_bytes)
    background_tasks.add_task(process_document, document_id, file_bytes, filename)

    return DocumentUploadResponse(
        id=document_id,
        filename=filename,
        status="uploaded",
        message="PDF file received. Processing and OCR pipeline started.",
    )


@router.post("/upload-photo", response_model=DocumentUploadResponse)
async def upload_single_photo(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    settings = get_settings()
    filename = file.filename or "paper_photo.jpg"

    if not is_image_filename(filename):
        raise InvalidFileTypeError(f"'{filename}' is not an accepted image format (.jpg, .jpeg, .png, .webp).")

    file_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(f"File exceeds the {settings.max_upload_size_mb}MB limit.")
    if len(file_bytes) == 0:
        raise InvalidFileTypeError("Uploaded image file is empty.")

    document_id = await repo.create_document(filename=filename, title=None, source_type="single_photo")
    background_tasks.add_task(process_document, document_id, file_bytes, filename, is_photo=True)

    return DocumentUploadResponse(
        id=document_id,
        filename=filename,
        status="uploaded",
        message="Paper photo received. OCR & ingestion pipeline started.",
    )


@router.post("/upload-photos", response_model=DocumentUploadResponse)
async def upload_multi_photo_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    settings = get_settings()
    if not files:
        raise InvalidFileTypeError("No image files provided for batch upload.")

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

    document_id = await repo.create_document(filename=batch_filename, title=None, source_type="multi_photo")
    background_tasks.add_task(
        process_document, document_id, b"", batch_filename, is_photo=True, multi_photos=photo_files
    )

    return DocumentUploadResponse(
        id=document_id,
        filename=batch_filename,
        status="uploaded",
        message=f"{len(files)} paper page photos received. Multi-page OCR pipeline started.",
    )


@router.get("", response_model=list[DocumentOut])
async def list_documents():
    rows = await repo.list_documents()
    return [DocumentOut(**row) for row in rows]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: UUID):
    row = await repo.get_document(document_id)
    return DocumentOut(**row)


@router.get("/{document_id}/pages", response_model=list[DocumentPageOut])
async def get_document_pages(document_id: UUID):
    await repo.get_document(document_id)
    rows = await repo.get_document_pages(document_id)
    out = []
    for r in rows:
        conf = r.get("ocr_confidence")
        conf_label = f"{int(conf * 100)}%" if conf is not None else "OCR confidence unavailable"
        out.append(DocumentPageOut(**r, ocr_confidence_label=conf_label))
    return out


@router.get("/{document_id}/pages/{page_number}/image")
async def get_document_page_image(document_id: UUID, page_number: int):
    page = await repo.get_document_page(document_id, page_number)
    if not page or not page.get("image_path") or not Path(page["image_path"]).exists():
        raise HTTPException(status_code=404, detail=f"Image for page {page_number} not found.")
    return FileResponse(page["image_path"], media_type="image/png")


@router.put("/{document_id}/pages/{page_number}/text")
async def update_page_text_verification(
    document_id: UUID, page_number: int, payload: PageTextUpdate
):
    """User verifies and edits extracted OCR text for a page."""
    page = await repo.get_document_page(document_id, page_number)
    if not page:
        raise DocumentNotFoundError(f"Page {page_number} not found for document {document_id}")

    await repo.update_page_text(document_id, page_number, payload.text, user_edited=True)
    return {"message": f"Page {page_number} text updated successfully.", "page_number": page_number}


@router.post("/{document_id}/pages/{page_number}/reprocess-ocr")
async def reprocess_page_ocr(
    document_id: UUID, page_number: int, payload: OcrReprocessRequest
):
    """Reprocess page OCR using selected engine (tesseract | vision_llm)."""
    page = await repo.get_document_page(document_id, page_number)
    if not page or not page.get("image_path") or not Path(page["image_path"]).exists():
        raise HTTPException(status_code=404, detail="Page image unavailable for reprocessing.")

    img_bytes = Path(page["image_path"]).read_bytes()
    ocr_res = run_ocr_on_image(img_bytes, page_number=page_number, force_engine=payload.engine)

    await repo.upsert_document_page(
        document_id=document_id,
        page_number=page_number,
        image_path=page["image_path"],
        extracted_text=ocr_res.text,
        ocr_engine=ocr_res.ocr_engine,
        ocr_confidence=ocr_res.confidence,
        ocr_status="completed",
        layout_blocks=ocr_res.blocks,
    )
    return {"message": f"Page {page_number} reprocessed via {ocr_res.ocr_engine}.", "extracted_text": ocr_res.text}


@router.get("/{document_id}/ocr-eval", response_model=OcrEvaluationResponse)
async def get_ocr_evaluation(document_id: UUID):
    """Evaluation metrics framework for OCR quality."""
    await repo.get_document(document_id)
    return OcrEvaluationResponse(
        document_id=document_id,
        status="success",
        ground_truth_available=False,
        character_error_rate=None,
        word_error_rate=None,
        message="Evaluation dataset not yet available. Upload ground-truth text to calculate exact CER/WER metrics.",
    )


@router.post("/{document_id}/process", response_model=DocumentOut)
async def reprocess_document(document_id: UUID, background_tasks: BackgroundTasks):
    row = await repo.get_document(document_id)
    stored = _stored_path(document_id)
    if not stored.exists():
        raise InvalidFileTypeError("Original file bytes are no longer available; please re-upload.")
    file_bytes = stored.read_bytes()
    background_tasks.add_task(process_document, document_id, file_bytes, row["filename"])
    return DocumentOut(**row)


@router.get("/{document_id}/citation")
async def get_document_citation(document_id: UUID):
    from app.services.citations import get_all_citations
    from app.services.metadata_repository import get_metadata

    doc = await repo.get_document(document_id)
    meta = await get_metadata(document_id) or {}
    paper_dict = {
        "title": meta.get("title") or doc.get("title") or doc.get("filename"),
        "authors": meta.get("authors") or [],
        "publication_year": meta.get("publication_year"),
        "venue": meta.get("venue"),
        "doi": meta.get("doi"),
        "abstract": meta.get("abstract"),
    }
    return get_all_citations(paper_dict)
