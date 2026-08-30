from __future__ import annotations

from app.services.ml import entity_extraction


def test_extract_entities_finds_exact_gazetteer_matches_with_full_confidence():
    text = "We fine-tuned SciBERT on the PubMed dataset and evaluated using F1-score."
    results = entity_extraction.extract_entities(text)

    by_name = {r["canonical_name"]: r for r in results}
    assert "SciBERT" in by_name
    assert by_name["SciBERT"]["entity_type"] == "model"
    assert by_name["SciBERT"]["confidence"] == 1.0
    assert by_name["SciBERT"]["extraction_method"] == "gazetteer_match"

    assert "PubMed" in by_name
    assert by_name["PubMed"]["entity_type"] == "dataset"

    assert "F1-score" in by_name
    assert by_name["F1-score"]["entity_type"] == "metric"


def test_extract_entities_does_not_false_positive_on_substrings():
    # "bert" should not match inside "Robert" (word-boundary check).
    text = "Robert Smith led the study on classical statistical methods."
    results = entity_extraction.extract_entities(text)
    names = {r["canonical_name"] for r in results}
    assert "BERT" not in names


def test_extract_entities_provenance_includes_excerpt():
    text = "The proposed ResNet-50 backbone achieved strong results on ImageNet."
    results = entity_extraction.extract_entities(text)
    resnet_hits = [r for r in results if r["canonical_name"] == "ResNet"]
    assert resnet_hits
    assert "ResNet" in resnet_hits[0]["source_excerpt"] or "Res" in resnet_hits[0]["source_excerpt"]
