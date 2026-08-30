"""
RAG orchestration: retrieve -> build grounded context -> generate ->
attach sources. This is the only file that combines retrieval and
generation; each remains independently testable/swappable.
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.core.config import get_settings
from app.models.schemas import ChatResponse, SourceReference
from app.services.llm_provider import get_llm_provider
from app.services.retrieval import retrieve_relevant_chunks

logger = logging.getLogger("research_nexus.rag")

SYSTEM_PROMPT = """You are Research Nexus, an academic research assistant.

Rules you MUST follow:
1. Answer the user's question using ONLY the research context provided below.
2. Do not invent, assume, or add information that is not present in the context.
3. If the context does not contain enough information to answer, say clearly:
   "The provided document(s) do not contain enough information to answer this question."
4. When you use information from the context, refer to it by its source number,
   e.g. "[Source 2]", so the user can trace every claim back to a passage.
5. Be precise and concise. Do not pad the answer with generic commentary.
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


async def answer_question(
    question: str,
    document_id: UUID | None = None,
    top_k: int | None = None,
) -> ChatResponse:
    settings = get_settings()
    chunks = await retrieve_relevant_chunks(question, top_k=top_k, document_id=document_id)

    # Filter out weak matches so irrelevant chunks don't pollute the prompt.
    relevant = [c for c in chunks if c.similarity >= settings.similarity_threshold]

    if not relevant:
        return ChatResponse(
            question=question,
            answer=(
                "I couldn't find any relevant content in the indexed document(s) "
                "to answer this question. Try rephrasing, or confirm the paper "
                "covering this topic has finished indexing."
            ),
            sources=[],
            grounded=False,
        )

    context_block = _build_context_block(relevant)
    user_prompt = (
        f"Research context:\n\n{context_block}\n\n"
        f"Question: {question}\n\n"
        "Answer the question using only the context above, citing sources as [Source N]."
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

    return ChatResponse(question=question, answer=answer_text, sources=sources, grounded=True)
