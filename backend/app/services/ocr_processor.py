"""
Core OCR Processing Engine for Research Nexus.

Combines image preprocessing, Level 1 local OCR (Tesseract / PyMuPDF),
heuristic quality & confidence evaluation, Level 2 Vision LLM fallback,
and structured layout block extraction.
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from PIL import Image

import fitz  # PyMuPDF

from app.services.ocr_preprocessor import preprocess_image_for_ocr
from app.services.vision_ocr_provider import get_vision_ocr_provider

logger = logging.getLogger("research_nexus.ocr_processor")

# Common English research vocabulary check for confidence heuristic
COMMON_PAPER_WORDS = {
    "abstract", "introduction", "method", "results", "discussion", "conclusion",
    "table", "figure", "references", "proposed", "model", "data", "dataset",
    "performance", "accuracy", "analysis", "study", "approach", "learning", "system"
}


@dataclass
class OCRPageResult:
    page_number: int
    text: str
    ocr_engine: str  # 'tesseract' | 'fitz_native' | 'vision_llm' | 'mock'
    confidence: float | None  # None = "OCR confidence unavailable"
    blocks: list[dict] = field(default_factory=list)


def assess_ocr_quality(text: str) -> tuple[bool, float | None]:
    """
    Evaluates extracted OCR text using empirical quality heuristics.
    
    Returns:
        (is_reliable: bool, confidence: float | None)
        confidence is None if a reliable statistical percentage cannot be calculated.
    """
    cleaned = text.strip()
    if not cleaned or len(cleaned) < 40:
        return False, None

    words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", cleaned)]
    if not words:
        return False, None

    # Calculate ratio of recognized research words
    matching = sum(1 for w in words if w in COMMON_PAPER_WORDS)
    paper_word_ratio = matching / len(words)

    # Check non-printable / garbage symbol density
    unusual_symbols = len(re.findall(r"[^\w\s\.,;\(\)\-\–\/\:\%\+\=\<\>\[\]]", cleaned))
    symbol_ratio = unusual_symbols / float(len(cleaned))

    if symbol_ratio > 0.15:
        return False, None

    # Heuristic confidence score (0.0 to 1.0)
    score = min(1.0, max(0.2, (len(words) / 100.0) * 0.4 + paper_word_ratio * 3.0))

    is_reliable = (len(words) >= 15 and symbol_ratio < 0.10)
    return is_reliable, round(score, 2)


def run_ocr_on_image(
    image_bytes: bytes, page_number: int = 1, force_engine: str | None = None
) -> OCRPageResult:
    """
    Runs full OCR processing on a single page image.
    
    Tries:
    1. Preprocessing image
    2. Level 1 Local OCR (Tesseract / PIL)
    3. Quality assessment
    4. Level 2 Vision LLM fallback if Level 1 is unreliable
    """
    preprocessed_bytes = preprocess_image_for_ocr(image_bytes)

    if force_engine == "vision_llm":
        vision_provider = get_vision_ocr_provider()
        txt, blocks = vision_provider.extract_text_and_layout(preprocessed_bytes)
        return OCRPageResult(
            page_number=page_number,
            text=txt,
            ocr_engine="vision_llm",
            confidence=None,
            blocks=blocks,
        )

    # 1. Try PyTesseract if available
    extracted_text = ""
    engine_used = "tesseract"
    try:
        import pytesseract
        pil_img = Image.open(io.BytesIO(preprocessed_bytes))
        extracted_text = pytesseract.image_to_string(pil_img)
    except Exception as exc:
        logger.debug("Tesseract OCR unavailable or failed: %s", exc)
        extracted_text = ""

    # 2. Quality check
    is_reliable, confidence = assess_ocr_quality(extracted_text)

    if is_reliable and extracted_text:
        # Build basic layout blocks
        blocks = [
            {"type": "paragraph", "text": paragraph.strip()}
            for paragraph in extracted_text.split("\n\n")
            if paragraph.strip()
        ]
        return OCRPageResult(
            page_number=page_number,
            text=extracted_text.strip(),
            ocr_engine=engine_used,
            confidence=confidence,
            blocks=blocks,
        )

    # 3. Fallback to Level 2 Vision OCR
    logger.info("Level 1 OCR unreliable for page %d; invoking Level 2 Vision OCR", page_number)
    vision_provider = get_vision_ocr_provider()
    txt, blocks = vision_provider.extract_text_and_layout(preprocessed_bytes)
    
    if txt:
        return OCRPageResult(
            page_number=page_number,
            text=txt,
            ocr_engine="vision_llm",
            confidence=None,  # "OCR confidence unavailable" for LLM vision
            blocks=blocks,
        )

    # 4. Final Fallback if vision provider returns empty
    return OCRPageResult(
        page_number=page_number,
        text=extracted_text.strip() or "[OCR warning: No text could be extracted from this page image]",
        ocr_engine="fallback",
        confidence=None,
        blocks=[],
    )


def run_ocr_on_pdf_bytes(pdf_bytes: bytes) -> list[OCRPageResult]:
    """
    Renders each PDF page into high-res pixmaps and runs OCR per page.
    """
    results: list[OCRPageResult] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for i in range(doc.page_count):
            page = doc.load_page(i)
            # Render page to 300 DPI image
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            page_res = run_ocr_on_image(img_bytes, page_number=i + 1)
            results.append(page_res)
    finally:
        doc.close()
    return results
