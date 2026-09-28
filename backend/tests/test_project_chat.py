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


@pytest.mark.asyncio
async def test_project_chat_includes_history_context(monkeypatch):
    doc_id = uuid4()
    chunks = [_chunk(doc_id, "paper1.pdf", 0.85)]
    history_turns = [
        {"question": "What model did paper 1 use?", "answer": "Paper 1 used ResNet-50.", "sources": []}
    ]

    async def fake_retrieve(query, project_id, top_k=None):
        return chunks

    async def fake_get_history(project_id):
        return history_turns

    async def fake_save_message(project_id, q, a, sources):
        pass

    prompt_captured = {}

    class FakeProvider:
        def generate(self, system_prompt, user_prompt):
            prompt_captured["user_prompt"] = user_prompt
            return "ResNet-50 was compared to Transformer models. [Source 1]"

    monkeypatch.setattr(project_chat, "retrieve_relevant_chunks_for_project", fake_retrieve)
    monkeypatch.setattr(project_chat, "get_project_chat_history", fake_get_history)
    monkeypatch.setattr(project_chat, "save_chat_message", fake_save_message)
    monkeypatch.setattr(project_chat, "get_llm_provider", lambda: FakeProvider())

    response = await project_chat.answer_project_question(uuid4(), "Expand on ResNet-50 performance.")

    assert response.grounded is True
    assert "Recent Conversation History:" in prompt_captured["user_prompt"]
    assert "User: What model did paper 1 use?" in prompt_captured["user_prompt"]
    assert "Assistant: Paper 1 used ResNet-50." in prompt_captured["user_prompt"]


@pytest.mark.asyncio
async def test_clear_project_chat_history(monkeypatch):
    project_id = uuid4()

    async def fake_clear(p_id):
        assert p_id == project_id
        return True

    monkeypatch.setattr(project_chat, "clear_project_chat_history", fake_clear)

    result = await project_chat.clear_project_chat_history(project_id)
    assert result is True

