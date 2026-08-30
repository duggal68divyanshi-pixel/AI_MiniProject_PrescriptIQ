from __future__ import annotations

from dataclasses import dataclass

from app.services.ml import section_classifier


@dataclass
class FakeChunk:
    chunk_index: int
    text: str
    page_number: int | None


def test_detect_headings_maps_synonyms_to_canonical_label():
    assert section_classifier.detect_headings_in_chunk("Methodology\nWe propose...") == "methodology"
    assert section_classifier.detect_headings_in_chunk("Experimental Setup\nWe use...") == "experiments"
    assert section_classifier.detect_headings_in_chunk("Proposed Method\nOur approach...") == "methodology"
    assert section_classifier.detect_headings_in_chunk("3.1 Related Work\nPrior work...") == "related_work"
    assert section_classifier.detect_headings_in_chunk("Limitations\nOur method fails...") == "limitations"


def test_detect_headings_returns_none_for_prose():
    long_sentence = (
        "This is a normal sentence that is far too long and descriptive to plausibly be a heading line."
    )
    assert section_classifier.detect_headings_in_chunk(long_sentence) is None


def test_detect_sections_builds_contiguous_spans_from_headings():
    chunks = [
        FakeChunk(0, "Introduction\nThis paper studies X.", 1),
        FakeChunk(1, "Continuing the introduction with more detail about X.", 1),
        FakeChunk(2, "Methodology\nWe propose a new CNN architecture.", 2),
        FakeChunk(3, "Results\nOur model achieves 91% accuracy on the test set.", 5),
    ]
    spans = section_classifier.detect_sections(chunks)

    labels = [s.section_label for s in spans]
    assert labels == ["introduction", "methodology", "results"]
    assert spans[0].start_chunk_index == 0
    assert spans[0].end_chunk_index == 1
    assert spans[0].detection_method == "heading_pattern"
    assert spans[1].start_chunk_index == 2
    assert spans[2].start_chunk_index == 3
    assert spans[2].end_chunk_index == 3
