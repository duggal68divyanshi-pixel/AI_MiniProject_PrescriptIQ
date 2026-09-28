from __future__ import annotations

from uuid import uuid4
import pytest

from app.services import authoring
from app.models.schemas import LiteratureMatrixRow, SourceReference


class FakeLLMProvider:
    def generate(self, system_prompt, user_prompt):
        return "# Related Work\n\nThis section synthesizes prior work in medical image classification."


@pytest.mark.asyncio
async def test_generate_manuscript_section(monkeypatch):
    project_id = uuid4()
    doc_id = uuid4()

    async def fake_get_project(p_id):
        return {"id": p_id, "name": "Medical AI Research"}

    async def fake_get_indexed(p_id):
        return [doc_id]

    async def fake_build_matrix(p_id, ids, force_refresh=False):
        row = LiteratureMatrixRow(
            document_id=doc_id,
            filename="paper1.pdf",
            title="CNNs for Medical Imaging",
            authors=["Alice Smith"],
            publication_year=2023,
            research_problem="Skin cancer classification",
            methodology="Supervised CNN",
            model_or_algorithm="ResNet-50",
            dataset="ISIC 2019",
            evaluation_metrics="Accuracy",
            key_results="92% accuracy",
            contributions="New transfer learning strategy",
            limitations="Dataset domain shift",
            sources=[
                SourceReference(
                    document="paper1.pdf",
                    document_id=doc_id,
                    page=1,
                    chunk_id=uuid4(),
                    similarity=0.85,
                    excerpt="excerpt",
                )
            ],
        )
        return [row], [], False

    async def fake_get_knowledge(p_id, ids):
        return {"common_methods": ["ResNet-50"], "common_datasets": ["ISIC 2019"]}

    monkeypatch.setattr(authoring, "get_project", fake_get_project)
    monkeypatch.setattr(authoring, "get_indexed_document_ids", fake_get_indexed)
    monkeypatch.setattr(authoring, "build_literature_matrix", fake_build_matrix)
    monkeypatch.setattr(authoring, "get_project_knowledge", fake_get_knowledge)
    monkeypatch.setattr(authoring, "get_llm_provider", lambda: FakeLLMProvider())

    res = await authoring.generate_manuscript_section(project_id, section_type="related_work")

    assert res["project_id"] == str(project_id)
    assert res["section_type"] == "related_work"
    assert "Related Work" in res["content"]
    assert res["papers_analyzed"] == 1


@pytest.mark.asyncio
async def test_generate_manuscript_section_passes_max_tokens(monkeypatch):
    project_id = uuid4()
    doc_id = uuid4()

    captured_kwargs = {}

    class TrackingProvider:
        def generate(self, system_prompt, user_prompt, max_tokens=None):
            captured_kwargs["max_tokens"] = max_tokens
            return "# Introduction\n\nDraft content..."

    async def fake_get_project(p_id):
        return {"id": p_id, "name": "Test Project"}

    async def fake_get_indexed(p_id):
        return [doc_id]

    async def fake_build_matrix(p_id, ids, force_refresh=False):
        return [], [], False

    async def fake_get_knowledge(p_id, ids):
        return {}

    monkeypatch.setattr(authoring, "get_project", fake_get_project)
    monkeypatch.setattr(authoring, "get_indexed_document_ids", fake_get_indexed)
    monkeypatch.setattr(authoring, "build_literature_matrix", fake_build_matrix)
    monkeypatch.setattr(authoring, "get_project_knowledge", fake_get_knowledge)
    monkeypatch.setattr(authoring, "get_llm_provider", lambda: TrackingProvider())

    res = await authoring.generate_manuscript_section(project_id, section_type="introduction")

    assert captured_kwargs.get("max_tokens") == 4096
    assert "Introduction" in res["content"]

