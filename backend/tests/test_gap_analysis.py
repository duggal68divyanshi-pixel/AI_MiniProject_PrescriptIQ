from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.models.schemas import LiteratureMatrixRow, SourceReference
from app.services import gap_analysis


def _matrix_row(filename, limitations="Limited dataset diversity."):
    return LiteratureMatrixRow(
        document_id=uuid4(),
        filename=filename,
        title=None,
        authors=None,
        publication_year=None,
        research_problem="Classifying skin lesions",
        methodology="Supervised CNN",
        model_or_algorithm="ResNet-50",
        dataset="ISIC 2019",
        evaluation_metrics="Accuracy, F1",
        key_results="91% accuracy",
        contributions="A new augmentation technique",
        limitations=limitations,
        sources=[
            SourceReference(
                document=filename,
                document_id=uuid4(),
                page=3,
                chunk_id=uuid4(),
                similarity=0.8,
                excerpt="excerpt",
            )
        ],
    )


class FakeProvider:
    def __init__(self, payload):
        self._payload = payload

    def generate(self, system_prompt, user_prompt):
        return json.dumps(self._payload)


@pytest.mark.asyncio
async def test_analyze_gaps_computes_evidence_strength_from_paper_count(monkeypatch):
    project_id = uuid4()
    rows = [_matrix_row("paper_a.pdf"), _matrix_row("paper_b.pdf"), _matrix_row("paper_c.pdf")]
    doc_ids = [uuid4(), uuid4(), uuid4()]

    async def fake_build_matrix(project_id_, document_ids, force_refresh=False):
        return rows, [], False

    async def fake_get_cached(*args, **kwargs):
        return None

    saved = {}

    async def fake_save(project_id_, analysis_type, document_ids, content):
        saved["content"] = content
        return uuid4()

    payload = [
        {
            "gap": "Most studies rely on the same benchmark dataset.",
            "category": "dataset",
            "affected_papers": ["paper_a.pdf", "paper_b.pdf", "paper_c.pdf"],
            "why_it_matters": "Results may not generalize.",
            "potential_direction": "Evaluate on additional datasets.",
        },
        {
            "gap": "Only one paper evaluates real-world deployment latency.",
            "category": "evaluation",
            "affected_papers": ["paper_a.pdf"],
            "why_it_matters": "Deployment feasibility is unclear.",
            "potential_direction": "Benchmark inference latency across papers.",
        },
        {
            "gap": "A gap referencing a paper not in this project.",
            "category": "methodological",
            "affected_papers": ["not_a_real_paper.pdf"],
            "why_it_matters": "n/a",
            "potential_direction": "n/a",
        },
    ]

    monkeypatch.setattr(gap_analysis, "build_literature_matrix", fake_build_matrix)
    monkeypatch.setattr(gap_analysis, "get_cached", fake_get_cached)
    monkeypatch.setattr(gap_analysis, "save", fake_save)
    monkeypatch.setattr(gap_analysis, "get_llm_provider", lambda: FakeProvider(payload))

    gaps, cached, analysis_id = await gap_analysis.analyze_gaps(project_id, doc_ids)

    assert cached is False
    # the gap citing a nonexistent paper must be dropped entirely
    assert len(gaps) == 2
    assert gaps[0].evidence_strength == "High"  # 3 supporting papers
    assert gaps[1].evidence_strength == "Low"  # 1 supporting paper
    assert all(g.evidence for g in gaps)  # every kept gap carries real source references
    assert "content" in saved


@pytest.mark.asyncio
async def test_analyze_gaps_requires_at_least_two_papers(monkeypatch):
    async def fake_get_cached(*args, **kwargs):
        return None

    monkeypatch.setattr(gap_analysis, "get_cached", fake_get_cached)

    with pytest.raises(ValueError):
        await gap_analysis.analyze_gaps(uuid4(), [uuid4()])
