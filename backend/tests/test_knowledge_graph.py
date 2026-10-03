from __future__ import annotations

from uuid import uuid4
import pytest
from app.services import knowledge_graph


@pytest.mark.asyncio
async def test_build_project_knowledge_graph_empty_project(monkeypatch):
    project_id = uuid4()

    async def fake_get_project(_id):
        return {"id": project_id, "name": "Empty Project"}

    async def fake_list_documents(project_id=None):
        return []

    monkeypatch.setattr(knowledge_graph.proj_repo, "get_project", fake_get_project)
    monkeypatch.setattr(knowledge_graph.doc_repo, "list_documents", fake_list_documents)

    res = await knowledge_graph.build_project_knowledge_graph(project_id)
    assert res["project_id"] == str(project_id)
    assert res["nodes"] == []
    assert res["edges"] == []
    assert res["stats"]["total_nodes"] == 0


@pytest.mark.asyncio
async def test_build_project_knowledge_graph_with_data(monkeypatch):
    project_id = uuid4()
    doc1_id = uuid4()
    doc2_id = uuid4()

    async def fake_get_project(_id):
        return {"id": project_id, "name": "NLP Project"}

    async def fake_list_documents(project_id=None):
        return [
            {"id": doc1_id, "filename": "transformer.pdf", "status": "indexed"},
            {"id": doc2_id, "filename": "bert.pdf", "status": "indexed"},
        ]

    async def fake_get_metadata_for_documents(_ids):
        return {
            doc1_id: {
                "title": "Attention Is All You Need",
                "authors": ["Vaswani", "Shazeer"],
                "publication_year": 2017,
                "abstract": "The Transformer model."
            },
            doc2_id: {
                "title": "BERT Pre-training",
                "authors": ["Devlin", "Chang"],
                "publication_year": 2018,
                "abstract": "Pre-training deep bidirectional representations."
            }
        }

    async def fake_get_project_entities(_ids):
        return [
            {"entity_type": "model", "canonical_name": "Transformer", "paper_count": 2},
            {"entity_type": "dataset", "canonical_name": "WMT 2014", "paper_count": 1},
        ]

    async def fake_get_project_topics(_id):
        return [{"id": uuid4(), "label": "Attention Mechanisms", "keywords": ["attention", "transformer"], "document_count": 2}]

    async def fake_get_project_claims(_ids):
        return [{"id": uuid4(), "document_id": doc1_id, "claim_text": "Transformer achieves 28.4 BLEU.", "claim_type": "finding"}]

    async def fake_get_project_limitations(_ids):
        return [{"id": uuid4(), "document_id": doc1_id, "limitation_text": "High memory consumption on long sequences.", "category": "computational"}]

    async def fake_get_project_relationships(_ids, limit=150):
        return [
            {"document_id": doc1_id, "predicate": "proposes", "entity_type": "model", "entity_name": "Transformer"},
            {"document_id": doc2_id, "predicate": "uses", "entity_type": "model", "entity_name": "Transformer"},
            {"document_id": doc1_id, "predicate": "evaluates_on", "entity_type": "dataset", "entity_name": "WMT 2014"},
        ]

    async def fake_get_project_top_concepts(_ids, limit=25):
        return [{"phrase": "self-attention mechanism", "paper_count": 2, "avg_score": 0.88}]

    async def fake_get_paper_topic_assignments(_ids):
        return []

    async def fake_get_project_research_questions(_id):
        return []

    async def fake_get_project_keyphrases_top_n(_ids, top_n=5):
        return [{"document_id": doc1_id, "phrase": "self-attention mechanism", "score": 0.88, "rank": 1}]

    monkeypatch.setattr(knowledge_graph.proj_repo, "get_project", fake_get_project)
    monkeypatch.setattr(knowledge_graph.doc_repo, "list_documents", fake_list_documents)
    monkeypatch.setattr(knowledge_graph.meta_repo, "get_metadata_for_documents", fake_get_metadata_for_documents)
    monkeypatch.setattr(knowledge_graph.sci_repo, "get_project_entities", fake_get_project_entities)
    monkeypatch.setattr(knowledge_graph.sci_repo, "get_project_topics", fake_get_project_topics)
    monkeypatch.setattr(knowledge_graph.sci_repo, "get_project_claims", fake_get_project_claims)
    monkeypatch.setattr(knowledge_graph.sci_repo, "get_project_limitations", fake_get_project_limitations)
    monkeypatch.setattr(knowledge_graph.sci_repo, "get_project_relationships", fake_get_project_relationships)
    monkeypatch.setattr(knowledge_graph.sci_repo, "get_project_top_concepts", fake_get_project_top_concepts)
    monkeypatch.setattr(knowledge_graph.sci_repo, "get_paper_topic_assignments", fake_get_paper_topic_assignments)
    monkeypatch.setattr(knowledge_graph.sci_repo, "get_project_research_questions", fake_get_project_research_questions)
    monkeypatch.setattr(knowledge_graph.sci_repo, "get_project_keyphrases_top_n", fake_get_project_keyphrases_top_n)

    res = await knowledge_graph.build_project_knowledge_graph(project_id)
    assert res["project_id"] == str(project_id)
    assert res["stats"]["total_nodes"] > 0
    assert res["stats"]["total_edges"] > 0

    node_types = {n["type"] for n in res["nodes"]}
    assert "paper" in node_types
    assert "author" in node_types
    assert "topic" in node_types
    assert "model" in node_types
    assert "dataset" in node_types
    assert "finding" in node_types
    assert "gap" in node_types
    assert "concept" in node_types

    edge_predicates = {e["predicate"] for e in res["edges"]}
    assert "written_by" in edge_predicates
    assert "proposes" in edge_predicates
    assert "uses" in edge_predicates
    assert "evaluates_on" in edge_predicates
    assert "reports" in edge_predicates
    assert "has_limitation" in edge_predicates

    # Verify enriched metadata on Paper nodes
    paper_node = next(n for n in res["nodes"] if n["id"] == f"paper-{doc1_id}")
    assert "Transformer" in paper_node["data"]["models"]
    assert "WMT 2014" in paper_node["data"]["datasets"]
    assert len(paper_node["data"]["findings"]) > 0
    assert len(paper_node["data"]["gaps"]) > 0

    # Verify enriched metadata on Dataset nodes
    dataset_node = next(n for n in res["nodes"] if n["type"] == "dataset")
    assert "Transformer" in dataset_node["data"]["associated_models"]

    # Verify edge data has labels and descriptions
    first_edge = res["edges"][0]
    assert "source_label" in first_edge["data"]
    assert "target_label" in first_edge["data"]
    assert "description" in first_edge["data"]


@pytest.mark.asyncio
async def test_query_knowledge_graph(monkeypatch):
    project_id = uuid4()

    async def fake_build_graph(_pid):
        return {
            "project_id": str(project_id),
            "nodes": [
                {"id": "paper-1", "type": "paper", "label": "Attention Is All You Need"},
                {"id": "model-1", "type": "model", "label": "Transformer"},
                {"id": "dataset-1", "type": "dataset", "label": "WMT 2014"},
            ],
            "edges": [
                {"id": "e1", "source": "paper-1", "target": "model-1", "predicate": "proposes", "label": "proposes"},
                {"id": "e2", "source": "paper-1", "target": "dataset-1", "predicate": "evaluates_on", "label": "evaluates on"},
            ],
            "stats": {"total_nodes": 3, "total_edges": 2, "node_types": {"paper": 1, "model": 1, "dataset": 1}},
        }

    class FakeLLM:
        def generate(self, system_prompt, user_prompt):
            return "The Transformer model is evaluated on the WMT 2014 dataset."

    monkeypatch.setattr(knowledge_graph, "build_project_knowledge_graph", fake_build_graph)
    monkeypatch.setattr(knowledge_graph, "get_llm_provider", lambda: FakeLLM())

    ans = await knowledge_graph.query_knowledge_graph(project_id, "What models are used?")
    assert "Transformer" in ans["answer"]
    assert "model-1" in ans["relevant_nodes"]
    assert ans["stats"]["total_nodes"] == 3


