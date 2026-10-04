"""
Unified Document Ingestion Abstraction for Research Nexus.

Converts Native PDFs, Scanned PDFs, Single Paper Photos, and Multi-Photo Batches
into a single unified ExtractionResult structure with preserved 1-indexed page provenance.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from uuid import UUID

import fitz  # PyMuPDF
from PIL import Image

from app.core.exceptions import CorruptedPDFError, ResearchNexusError
from app.services.ocr_processor import run_ocr_on_image, run_ocr_on_pdf_bytes, OCRPageResult
from app.services.pdf_processor import ExtractionResult, PageText, _clean_text, _guess_title

logger = logging.getLogger("research_nexus.ingestion")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def is_image_filename(filename: str) -> bool:
    import os
    ext = os.path.splitext(filename.lower())[1]
    return ext in IMAGE_EXTENSIONS


@dataclass
class IngestionResult:
    extraction: ExtractionResult
    source_type: str  # 'native_pdf' | 'scanned_pdf' | 'single_photo' | 'multi_photo'
    page_results: list[OCRPageResult]
    composite_pdf_bytes: bytes  # Stored so original bytes or synthesized PDF can be downloaded/viewed


def convert_images_to_pdf_bytes(images: list[bytes]) -> bytes:
    """Combines 1 or more image byte payloads into a single multi-page PDF."""
    pdf_doc = fitz.open()
    for img_bytes in images:
        try:
            # Open image with PIL to normalize format and handle EXIF rotation
            img = Image.open(io.BytesIO(img_bytes))
            img_byte_arr = io.BytesIO()
            img.convert("RGB").save(img_byte_arr, format="JPEG", quality=95)
            img_data = img_byte_arr.getvalue()

            img_doc = fitz.open(stream=img_data, filetype="jpeg")
            rect = img_doc[0].rect
            pdf_page = pdf_doc.new_page(width=rect.width, height=rect.height)
            pdf_page.show_pdf_page(rect, img_doc, 0)
            img_doc.close()
        except Exception as exc:
            logger.warning("Failed to add image page to PDF: %s", exc)

    if pdf_doc.page_count == 0:
        pdf_doc.close()
        raise ResearchNexusError("Failed to convert image files into a valid PDF document.")

    output_bytes = pdf_doc.tobytes()
    pdf_doc.close()
    return output_bytes


def ingest_document(
    file_bytes: bytes, filename: str, is_photo: bool = False
) -> IngestionResult:
    """
    Single unified entry point for Native PDF, Scanned PDF, or Single Photo.
    """
    if is_photo or is_image_filename(filename):
        # Single paper photo upload
        logger.info("Ingesting single paper photo: %s", filename)
        pdf_bytes = convert_images_to_pdf_bytes([file_bytes])
        ocr_res = run_ocr_on_image(file_bytes, page_number=1)
        
        pages = [PageText(page_number=1, text=ocr_res.text)]
        extraction = ExtractionResult(pages=pages, title=filename, total_pages=1)
        return IngestionResult(
            extraction=extraction,
            source_type="single_photo",
            page_results=[ocr_res],
            composite_pdf_bytes=pdf_bytes,
        )

    # Standard PDF processing
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise CorruptedPDFError(f"'{filename}' could not be opened as a valid PDF.") from exc

    if doc.page_count == 0:
        doc.close()
        raise CorruptedPDFError(f"'{filename}' contains 0 pages.")

    # 1. Try Native Text Extraction
    pages: list[PageText] = []
    for i in range(doc.page_count):
        raw_text = doc.load_page(i).get_text("text")
        cleaned = _clean_text(raw_text)
        if cleaned:
            pages.append(PageText(page_number=i + 1, text=cleaned))

    # Check if native extraction succeeded
    total_len = sum(len(p.text) for p in pages)
    if pages and total_len >= 50:
        title = _guess_title(doc, pages[0].text)
        doc.close()
        extraction = ExtractionResult(pages=pages, title=title, total_pages=len(pages))
        page_results = [
            OCRPageResult(
                page_number=p.page_number,
                text=p.text,
                ocr_engine="fitz_native",
                confidence=1.0,
                blocks=[{"type": "paragraph", "text": p.text}],
            )
            for p in pages
        ]
        return IngestionResult(
            extraction=extraction,
            source_type="native_pdf",
            page_results=page_results,
            composite_pdf_bytes=file_bytes,
        )

    doc.close()
    # 2. Native text failed or empty -> Scanned PDF with OCR
    logger.info("Scanned/Image-only PDF detected for '%s'. Running page-by-page OCR.", filename)
    ocr_results = run_ocr_on_pdf_bytes(file_bytes)
    ocr_pages = [PageText(page_number=r.page_number, text=r.text) for r in ocr_results]
    title = ocr_pages[0].text.splitlines()[0][:120] if ocr_pages and ocr_pages[0].text else filename

    extraction = ExtractionResult(
        pages=ocr_pages, title=title, total_pages=len(ocr_results)
    )
    return IngestionResult(
        extraction=extraction,
        source_type="scanned_pdf",
        page_results=ocr_results,
        composite_pdf_bytes=file_bytes,
    )


def ingest_multi_photo_batch(
    photo_files: list[tuple[bytes, str]]
) -> IngestionResult:
    """
    Ingests an ordered list of paper page photos and combines them into one unified document.
    """
    if not photo_files:
        raise ResearchNexusError("No image files provided for multi-photo batch upload.")

    image_bytes_list = [f[0] for f in photo_files]
    composite_pdf_bytes = convert_images_to_pdf_bytes(image_bytes_list)

    page_results: list[OCRPageResult] = []
    extraction_pages: list[PageText] = []

    for idx, (img_bytes, fname) in enumerate(photo_files, start=1):
        ocr_res = run_ocr_on_image(img_bytes, page_number=idx)
        page_results.append(ocr_res)
        extraction_pages.append(PageText(page_number=idx, text=ocr_res.text))

    title = photo_files[0][1] if photo_files else "Multi-Photo Paper"
    extraction = ExtractionResult(
        pages=extraction_pages, title=title, total_pages=len(photo_files)
    )

    return IngestionResult(
        extraction=extraction,
        source_type="multi_photo",
        page_results=page_results,
        composite_pdf_bytes=composite_pdf_bytes,
    )
