from __future__ import annotations

from uuid import uuid4

import pytest

from app.services import project_knowledge


@pytest.mark.asyncio
async def test_get_structured_knowledge_for_matrix_returns_empty_when_no_intelligence(monkeypatch):
    document_id = uuid4()

    async def fake_has_intelligence(_id):
        return False

    monkeypatch.setattr(project_knowledge.sci_repo, "has_intelligence", fake_has_intelligence)

    result = await project_knowledge.get_structured_knowledge_for_matrix(document_id)
    assert result == {}


@pytest.mark.asyncio
async def test_get_structured_knowledge_for_matrix_dedupes_and_sorts(monkeypatch):
    document_id = uuid4()

    async def fake_has_intelligence(_id):
        return True

    async def fake_get_paper_entities(_id):
        return [
            {"entity_type": "model", "canonical_name": "SciBERT"},
            {"entity_type": "model", "canonical_name": "BERT"},
            {"entity_type": "model", "canonical_name": "SciBERT"},  # duplicate mention
            {"entity_type": "dataset", "canonical_name": "PubMed"},
        ]

    async def fake_get_limitations(_id):
        return [{"limitation_text": "Small dataset size."}]

    async def fake_get_claims(_id):
        return [
            {"claim_type": "result", "claim_text": "94% accuracy achieved."},
            {"claim_type": "contribution", "claim_text": "A new architecture."},
        ]

    monkeypatch.setattr(project_knowledge.sci_repo, "has_intelligence", fake_has_intelligence)
    monkeypatch.setattr(project_knowledge.sci_repo, "get_paper_entities", fake_get_paper_entities)
    monkeypatch.setattr(project_knowledge.sci_repo, "get_limitations", fake_get_limitations)
    monkeypatch.setattr(project_knowledge.sci_repo, "get_claims", fake_get_claims)

    result = await project_knowledge.get_structured_knowledge_for_matrix(document_id)

    assert result["models"] == ["BERT", "SciBERT"]  # deduped + sorted
    assert result["datasets"] == ["PubMed"]
    assert result["limitations"] == ["Small dataset size."]
    assert result["results"] == ["94% accuracy achieved."]  # only claim_type == 'result'


@pytest.mark.asyncio
async def test_get_project_knowledge_aggregates_common_limitations(monkeypatch):
    project_id = uuid4()
    doc_ids = [uuid4(), uuid4()]

    async def fake_get_project_entities(_ids):
        return [{"entity_type": "model", "canonical_name": "ResNet"}]

    async def fake_get_project_topics(_pid):
        return []

    async def fake_get_project_limitations(_ids):
        return [
            {"limitation_text": "Small dataset size."},
            {"limitation_text": "small dataset size."},  # same limitation, different casing
            {"limitation_text": "No real-time evaluation."},
        ]

    async def fake_get_project_claims(_ids, claim_types=None):
        return []

    async def fake_get_project_top_concepts(_ids, limit=20):
        return []

    monkeypatch.setattr(project_knowledge.sci_repo, "get_project_entities", fake_get_project_entities)
    monkeypatch.setattr(project_knowledge.sci_repo, "get_project_topics", fake_get_project_topics)
    monkeypatch.setattr(project_knowledge.sci_repo, "get_project_limitations", fake_get_project_limitations)
    monkeypatch.setattr(project_knowledge.sci_repo, "get_project_claims", fake_get_project_claims)
    monkeypatch.setattr(project_knowledge.sci_repo, "get_project_top_concepts", fake_get_project_top_concepts)

    result = await project_knowledge.get_project_knowledge(project_id, doc_ids)

    assert result["top_models"][0]["canonical_name"] == "ResNet"
    common = {c["limitation"]: c["paper_count"] for c in result["common_limitations"]}
    assert common["small dataset size."] == 2
