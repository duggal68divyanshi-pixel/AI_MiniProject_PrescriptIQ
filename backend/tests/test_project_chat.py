from __future__ import annotations

from uuid import uuid4

import pytest

from app.services import project_chat
from app.services.retrieval import RetrievedChunk


def _chunk(document_id, filename, similarity, page=1, content="Some evidence text."):
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=document_id,
        document_filename=filename,
        content=content,
        page_number=page,
        similarity=similarity,
    )


@pytest.mark.asyncio
async def test_project_chat_retrieves_across_multiple_documents(monkeypatch):
    doc_a, doc_b = uuid4(), uuid4()
    chunks = [
        _chunk(doc_a, "paper_a.pdf", 0.81),
        _chunk(doc_b, "paper_c.pdf", 0.77),
        _chunk(doc_a, "paper_a.pdf", 0.5),  # below threshold, should be filtered
    ]

    async def fake_retrieve(query, project_id, top_k=None):
        return chunks

    def fake_generate(system_prompt, user_prompt):
        assert "paper_a.pdf" in user_prompt and "paper_c.pdf" in user_prompt
        return "Both papers use CNN-based methods. [Source 1][Source 2]"

    class FakeProvider:
        def generate(self, system_prompt, user_prompt):
            return fake_generate(system_prompt, user_prompt)

    monkeypatch.setattr(project_chat, "retrieve_relevant_chunks_for_project", fake_retrieve)
    monkeypatch.setattr(project_chat, "get_llm_provider", lambda: FakeProvider())

    response = await project_chat.answer_project_question(
        uuid4(), "Which methods are commonly used across these papers?"
    )

    assert response.grounded is True
    assert set(response.papers_cited) == {"paper_a.pdf", "paper_c.pdf"}
    # the weak (0.5-similarity) chunk must be filtered out by the similarity threshold
    assert all(s.similarity >= 0.2 for s in response.sources)


@pytest.mark.asyncio
async def test_project_chat_reports_no_grounding_when_nothing_relevant(monkeypatch):
    async def fake_retrieve(query, project_id, top_k=None):
        return []

    monkeypatch.setattr(project_chat, "retrieve_relevant_chunks_for_project", fake_retrieve)

    response = await project_chat.answer_project_question(uuid4(), "What about topic X?")

    assert response.grounded is False
    assert response.sources == []
    assert "couldn't find" in response.answer.lower()
