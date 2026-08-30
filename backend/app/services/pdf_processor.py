"""
PDF text extraction.

Uses PyMuPDF (fitz) which gives reliable, fast text extraction with page
boundaries and works without any external system dependency (unlike
poppler-based tools). Extraction noise (repeated headers/footers, excess
whitespace, form-feed/control characters) is cleaned before chunking.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import fitz  # PyMuPDF

from app.core.exceptions import CorruptedPDFError, EmptyPDFError

logger = logging.getLogger("research_nexus.pdf")


@dataclass
class PageText:
    page_number: int  # 1-indexed
    text: str


@dataclass
class ExtractionResult:
    pages: list[PageText]
    title: str | None
    total_pages: int

    @property
    def full_text_length(self) -> int:
        return sum(len(p.text) for p in self.pages)


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\n(\w)")


def _clean_text(raw: str) -> str:
    """Remove common PDF extraction noise while preserving paragraph structure."""
    text = _CONTROL_CHARS_RE.sub("", raw)
    # Rejoin words that were hyphen-broken across a line wrap: "infor-\nmation" -> "information"
    text = _HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def _guess_title(doc: "fitz.Document", first_page_text: str) -> str | None:
    meta_title = (doc.metadata or {}).get("title", "").strip()
    if meta_title and meta_title.lower() not in {"untitled", ""}:
        return meta_title
    # Fallback: first non-trivial line of the first page (common for papers,
    # where the title is the largest text block at the top).
    for line in first_page_text.splitlines():
        candidate = line.strip()
        if 8 <= len(candidate) <= 200:
            return candidate
    return None


def extract_pdf(file_bytes: bytes, filename: str) -> ExtractionResult:
    """
    Extract cleaned text per page from raw PDF bytes.

    Raises:
        CorruptedPDFError: file cannot be opened as a PDF at all.
        EmptyPDFError: file opens but contains no extractable text
            (e.g. a scanned/image-only PDF with no OCR layer).
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        logger.warning("Failed to open PDF '%s': %s", filename, exc)
        raise CorruptedPDFError(
            f"'{filename}' could not be opened — it may be corrupted or not a valid PDF."
        ) from exc

    if doc.page_count == 0:
        doc.close()
        raise CorruptedPDFError(f"'{filename}' contains zero pages.")

    pages: list[PageText] = []
    try:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            raw_text = page.get_text("text")
            cleaned = _clean_text(raw_text)
            if cleaned:
                pages.append(PageText(page_number=page_index + 1, text=cleaned))
    except Exception as exc:
        doc.close()
        raise CorruptedPDFError(
            f"An error occurred while reading pages of '{filename}': {exc}"
        ) from exc

    if not pages:
        doc.close()
        raise EmptyPDFError(
            f"'{filename}' has no extractable text. It is likely a scanned "
            "image PDF with no text layer — OCR is not part of this MVP."
        )

    title = _guess_title(doc, pages[0].text)
    total_pages = doc.page_count
    doc.close()

    return ExtractionResult(pages=pages, title=title, total_pages=total_pages)
