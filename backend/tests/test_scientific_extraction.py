from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.exceptions import DocumentNotIndexedError
from app.services import scientific_extraction
from app.services.ml import section_classifier


@pytest.mark.asyncio
async def test_run_paper_intelligence_rejects_non_indexed_documents(monkeypatch):
    document_id = uuid4()

    async def fake_get_document(_id):
        return {"id": document_id, "filename": "paper.pdf", "status": "extracting"}

    monkeypatch.setattr(scientific_extraction.doc_repo, "get_document", fake_get_document)

    with pytest.raises(DocumentNotIndexedError):
        await scientific_extraction.run_paper_intelligence(document_id)


@pytest.mark.asyncio
async def test_run_paper_intelligence_persists_every_stage_with_provenance(monkeypatch):
    document_id = uuid4()
    chunk_id_1, chunk_id_2 = uuid4(), uuid4()

    async def fake_get_document(_id):
        return {"id": document_id, "filename": "paper.pdf", "status": "indexed"}

    async def fake_get_all_chunks(_id):
        return [
            {"id": chunk_id_1, "chunk_index": 0, "page_number": 1, "content": "Methodology\nWe use SciBERT."},
            {
                "id": chunk_id_2,
                "chunk_index": 1,
                "page_number": 4,
                "content": "Results\nOur model achieved 92% accuracy, outperforming the baseline.",
            },
        ]

    saved = {}

    async def fake_replace_sections(doc_id, spans):
        saved["sections"] = spans

    async def fake_replace_paper_entities(doc_id, mentions):
        saved["entities"] = mentions

    async def fake_replace_keyphrases(doc_id, phrases):
        saved["keyphrases"] = phrases

    async def fake_replace_claims(doc_id, claims):
        saved["claims"] = claims

    async def fake_replace_limitations(doc_id, limitations):
        saved["limitations"] = limitations

    async def fake_replace_relationships(doc_id, relationships):
        saved["relationships"] = relationships

    async def fake_get_or_create_entity(entity_type, canonical_name):
        return uuid4()

    def fake_extract_entities(text):
        if "SciBERT" in text:
            return [
                {
                    "entity_type": "model",
                    "canonical_name": "SciBERT",
                    "mention_text": "SciBERT",
                    "source_excerpt": text,
                    "confidence": 1.0,
                    "extraction_method": "gazetteer_match",
                }
            ]
        return []

    def fake_extract_keyphrases(text, top_n=None):
        return [("scientific NLP", 0.8)]

    def fake_normalize_claims(candidates):
        return [
            {
                "claim_text": "The model achieved 92% accuracy.",
                "claim_type": "result",
                "evidence_text": candidates[0] if candidates else "",
            }
        ]

    def fake_normalize_limitations(candidates):
        return []

    monkeypatch.setattr(scientific_extraction.doc_repo, "get_document", fake_get_document)
    monkeypatch.setattr(scientific_extraction.doc_repo, "get_all_chunks", fake_get_all_chunks)
    monkeypatch.setattr(scientific_extraction.sci_repo, "replace_sections", fake_replace_sections)
    monkeypatch.setattr(scientific_extraction.sci_repo, "replace_paper_entities", fake_replace_paper_entities)
    monkeypatch.setattr(scientific_extraction.sci_repo, "replace_keyphrases", fake_replace_keyphrases)
    monkeypatch.setattr(scientific_extraction.sci_repo, "replace_claims", fake_replace_claims)
    monkeypatch.setattr(scientific_extraction.sci_repo, "replace_limitations", fake_replace_limitations)
    monkeypatch.setattr(scientific_extraction.sci_repo, "replace_relationships", fake_replace_relationships)
    monkeypatch.setattr(scientific_extraction.sci_repo, "get_or_create_entity", fake_get_or_create_entity)
    monkeypatch.setattr(scientific_extraction.entity_extraction, "extract_entities", fake_extract_entities)
    monkeypatch.setattr(scientific_extraction.keyphrase, "extract_keyphrases", fake_extract_keyphrases)
    monkeypatch.setattr(scientific_extraction.claim_extraction, "normalize_claims", fake_normalize_claims)
    monkeypatch.setattr(scientific_extraction.claim_extraction, "normalize_limitations", fake_normalize_limitations)

    summary = await scientific_extraction.run_paper_intelligence(document_id)

    assert summary["sections"] >= 1
    assert summary["entity_mentions"] == 1
    assert saved["entities"][0]["canonical_name"] == "SciBERT"
    assert saved["entities"][0]["chunk_id"] == chunk_id_1  # provenance preserved
    assert saved["entities"][0]["section_label"] == "methodology"
    assert saved["claims"][0]["claim_text"] == "The model achieved 92% accuracy."
    assert saved["claims"][0]["chunk_id"] == chunk_id_2
    assert saved["limitations"] == []
    # A model mention in the Methodology section should be derived into a
    # "proposes" relationship (deterministic, from section context).
    predicates = {r["predicate"] for r in saved["relationships"]}
    assert "proposes" in predicates
