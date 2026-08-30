"""
Multi-document research chat: the Phase 1 rag.py pattern (retrieve ->
grounded context -> generate -> cite), scoped to every indexed paper in a
project instead of one document, with a system prompt that additionally
asks the model to distinguish common findings, paper-specific findings,
and conflicts across the retrieved evidence.
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.core.config import get_settings
from app.models.schemas import ProjectChatResponse, SourceReference
from app.services.llm_provider import get_llm_provider
from app.services.project_retrieval import retrieve_relevant_chunks_for_project

logger = logging.getLogger("research_nexus.project_chat")

SYSTEM_PROMPT = """You are Research Nexus, a multi-paper literature intelligence assistant.

You are given evidence chunks retrieved from MULTIPLE research papers in one
project. Rules you MUST follow:
1. Answer using ONLY the supplied evidence. Never add outside knowledge.
2. Every chunk is labeled with the paper it came from, e.g. "(document: X)".
   Always be explicit about which paper(s) support each claim.
3. Cite sources by number, e.g. "[Source 2]", so every claim is traceable.
4. When evidence from multiple papers agrees, say so explicitly (e.g.
   "Papers A and C both report..."). When papers disagree, say so explicitly
   rather than picking a side or averaging the claims away.
5. If the evidence does not contain enough information to answer, say:
   "The indexed papers do not contain enough information to answer this question."
6. Do not fabricate a consensus that isn't actually present in the evidence.
"""


def _build_context_block(chunks) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        page_info = f", page {c.page_number}" if c.page_number else ""
        parts.append(
            f"[Source {i}] (document: {c.document_filename}{page_info}, "
            f"similarity: {c.similarity:.2f})\n{c.content}"
        )
    return "\n\n".join(parts)


async def answer_project_question(
    project_id: UUID,
    question: str,
    top_k: int | None = None,
) -> ProjectChatResponse:
    settings = get_settings()
    chunks = await retrieve_relevant_chunks_for_project(question, project_id, top_k=top_k)
    relevant = [c for c in chunks if c.similarity >= settings.similarity_threshold]

    if not relevant:
        return ProjectChatResponse(
            question=question,
            answer=(
                "I couldn't find any relevant content across this project's indexed "
                "papers to answer this question. Try rephrasing, or confirm papers "
                "have finished indexing."
            ),
            sources=[],
            papers_cited=[],
            grounded=False,
        )

    context_block = _build_context_block(relevant)
    user_prompt = (
        f"Evidence retrieved from the project's papers:\n\n{context_block}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the evidence above, citing sources as [Source N] and "
        "naming which paper(s) support each claim."
    )

    provider = get_llm_provider()
    answer_text = provider.generate(SYSTEM_PROMPT, user_prompt)

    sources = [
        SourceReference(
            document=c.document_filename,
            document_id=c.document_id,
            page=c.page_number,
            chunk_id=c.chunk_id,
            similarity=round(c.similarity, 4),
            excerpt=(c.content[:280] + "…") if len(c.content) > 280 else c.content,
        )
        for c in relevant
    ]
    papers_cited = sorted({c.document_filename for c in relevant})

    return ProjectChatResponse(
        question=question,
        answer=answer_text,
        sources=sources,
        papers_cited=papers_cited,
        grounded=True,
    )
