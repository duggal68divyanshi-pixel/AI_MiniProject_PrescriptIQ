from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.schemas import LiteratureMatrixRow
from app.services import literature_matrix


@pytest.mark.asyncio
async def test_build_literature_matrix_reuses_cached_row(monkeypatch):
    project_id, doc_id = uuid4(), uuid4()

    async def fake_get_document(document_id):
        return {"id": doc_id, "filename": "paper_a.pdf"}

    cached_row = LiteratureMatrixRow(
        document_id=doc_id,
        filename="paper_a.pdf",
        title="A Study of Something",
        authors=["A. Author"],
        publication_year=2023,
        research_problem="X",
        methodology="Y",
        model_or_algorithm="CNN",
        dataset="ISIC",
        evaluation_metrics="Accuracy",
        key_results="91.2%",
        contributions="A new approach",
        limitations="Small dataset",
        sources=[],
    )

    async def fake_get_cached(project_id_, analysis_type, document_ids):
        assert document_ids == [doc_id]
        return {"id": uuid4(), "content": cached_row.model_dump(mode="json")}

    extraction_calls = []

    async def fake_extract(document):
        extraction_calls.append(document)
        raise AssertionError("Should not re-extract when a cached row exists")

    monkeypatch.setattr(literature_matrix.doc_repo, "get_document", fake_get_document)
    monkeypatch.setattr(literature_matrix, "get_cached", fake_get_cached)
    monkeypatch.setattr(literature_matrix, "_extract_row_for_document", fake_extract)

    rows, skipped, any_cached = await literature_matrix.build_literature_matrix(
        project_id, [doc_id]
    )

    assert len(rows) == 1
    assert rows[0].filename == "paper_a.pdf"
    assert any_cached is True
    assert skipped == []
    assert extraction_calls == []


@pytest.mark.asyncio
async def test_build_literature_matrix_skips_documents_that_fail(monkeypatch):
    project_id, doc_id = uuid4(), uuid4()

    async def fake_get_document(document_id):
        return {"id": doc_id, "filename": "corrupted.pdf"}

    async def fake_get_cached(*args, **kwargs):
        return None

    async def fake_extract(document):
        raise ValueError("No indexed chunks available for this document.")

    monkeypatch.setattr(literature_matrix.doc_repo, "get_document", fake_get_document)
    monkeypatch.setattr(literature_matrix, "get_cached", fake_get_cached)
    monkeypatch.setattr(literature_matrix, "_extract_row_for_document", fake_extract)

    rows, skipped, any_cached = await literature_matrix.build_literature_matrix(
        project_id, [doc_id]
    )

    assert rows == []
    assert len(skipped) == 1
    assert skipped[0]["document_id"] == str(doc_id)
    assert any_cached is False
