import io
import pytest
from PIL import Image, ImageDraw

from app.services.ocr_preprocessor import preprocess_image_for_ocr
from app.services.ocr_processor import run_ocr_on_image, assess_ocr_quality
from app.services.ingestion_service import convert_images_to_pdf_bytes, ingest_document, ingest_multi_photo_batch, is_image_filename
from app.services.vision_ocr_provider import get_vision_ocr_provider, MockVisionOCRProvider


def create_sample_paper_image(text="Abstract — Test research paper contents.") -> bytes:
    img = Image.new("RGB", (1200, 1600), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((100, 100), text, fill=(0, 0, 0))
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def test_is_image_filename():
    assert is_image_filename("paper_page1.png") is True
    assert is_image_filename("scan.JPG") is True
    assert is_image_filename("paper.webp") is True
    assert is_image_filename("article.pdf") is False


def test_image_preprocessing():
    img_bytes = create_sample_paper_image()
    processed = preprocess_image_for_ocr(img_bytes)
    assert isinstance(processed, bytes)
    assert len(processed) > 0


def test_assess_ocr_quality():
    good_text = (
        "Abstract — This paper presents a novel deep learning architecture evaluated on standard benchmark datasets. "
        "The proposed methodology achieves state-of-the-art results across all performance metrics."
    )
    is_reliable, confidence = assess_ocr_quality(good_text)
    assert is_reliable is True
    assert confidence is not None
    assert confidence > 0.4

    bad_text = "abc 123"
    is_reliable_bad, conf_bad = assess_ocr_quality(bad_text)
    assert is_reliable_bad is False


def test_run_ocr_on_image():
    img_bytes = create_sample_paper_image()
    res = run_ocr_on_image(img_bytes, page_number=1)
    assert res.page_number == 1
    assert res.ocr_engine in ("tesseract", "vision_llm", "fallback")
    assert isinstance(res.text, str)


def test_convert_images_to_pdf_bytes():
    img1 = create_sample_paper_image("Page 1 Abstract")
    img2 = create_sample_paper_image("Page 2 Experiments")
    pdf_bytes = convert_images_to_pdf_bytes([img1, img2])
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


def test_ingest_single_photo():
    img_bytes = create_sample_paper_image("Single Photo Paper Title\nIntroduction text")
    res = ingest_document(img_bytes, filename="paper_photo.png", is_photo=True)
    assert res.source_type == "single_photo"
    assert res.extraction.total_pages == 1
    assert len(res.page_results) == 1
    assert res.page_results[0].page_number == 1


def test_ingest_multi_photo_batch():
    img1 = create_sample_paper_image("Page 1 Title and Abstract")
    img2 = create_sample_paper_image("Page 2 Methodology")
    photo_files = [(img1, "page1.png"), (img2, "page2.png")]

    res = ingest_multi_photo_batch(photo_files)
    assert res.source_type == "multi_photo"
    assert res.extraction.total_pages == 2
    assert res.page_results[0].page_number == 1
    assert res.page_results[1].page_number == 2


def test_vision_ocr_provider_fallback():
    provider = get_vision_ocr_provider()
    assert provider is not None
    img_bytes = create_sample_paper_image()
    txt, blocks = provider.extract_text_and_layout(img_bytes)
    assert isinstance(txt, str)
    assert isinstance(blocks, list)
