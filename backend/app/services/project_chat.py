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


import json
from app.core.database import get_connection

async def save_chat_message(project_id: UUID, question: str, answer: str, sources: list[dict]):
    try:
        async with get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO project_chat_history (project_id, question, answer, sources)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                project_id, question, answer, json.dumps(sources, default=str)
            )
    except Exception as exc:
        logger.warning("Failed to auto-save project chat history: %s", exc)


async def get_project_chat_history(project_id: UUID) -> list[dict]:
    try:
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT question, answer, sources, created_at
                FROM project_chat_history
                WHERE project_id = $1
                ORDER BY created_at ASC
                """,
                project_id
            )
            res = []
            for r in rows:
                s_data = r["sources"]
                if isinstance(s_data, str):
                    s_data = json.loads(s_data)
                res.append({
                    "question": r["question"],
                    "answer": r["answer"],
                    "sources": s_data or [],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else ""
                })
            return res
    except Exception as exc:
        logger.warning("Failed to fetch project chat history: %s", exc)
        return []


async def clear_project_chat_history(project_id: UUID) -> bool:
    try:
        async with get_connection() as conn:
            await conn.execute(
                """
                DELETE FROM project_chat_history
                WHERE project_id = $1
                """,
                project_id,
            )
            return True
    except Exception as exc:
        logger.warning("Failed to clear project chat history: %s", exc)
        return False


async def answer_project_question(
    project_id: UUID,
    question: str,
    top_k: int | None = None,
) -> ProjectChatResponse:
    settings = get_settings()
    chunks = await retrieve_relevant_chunks_for_project(question, project_id, top_k=top_k)
    relevant = [c for c in chunks if c.similarity >= settings.similarity_threshold]

    if not relevant:
        resp = ProjectChatResponse(
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
        await save_chat_message(project_id, question, resp.answer, [])
        return resp

    context_block = _build_context_block(relevant)

    # Multi-turn memory: include recent conversation turns (up to 5)
    history_turns = await get_project_chat_history(project_id)
    history_block = ""
    if history_turns:
        recent = history_turns[-5:]
        formatted_history = []
        for turn in recent:
            q = turn.get("question", "").strip()
            a = turn.get("answer", "").strip()
            if q and a:
                short_a = (a[:400] + "…") if len(a) > 400 else a
                formatted_history.append(f"User: {q}\nAssistant: {short_a}")
        if formatted_history:
            history_block = "Recent Conversation History:\n" + "\n\n".join(formatted_history) + "\n\n"

    # Graph-aware research context synthesis
    graph_context_block = ""
    try:
        from collections import defaultdict
        from app.services.knowledge_graph import build_project_knowledge_graph
        graph_data = await build_project_knowledge_graph(project_id)
        if graph_data and graph_data.get("nodes"):
            g_by_type = defaultdict(list)
            for gn in graph_data["nodes"]:
                g_by_type[gn["type"]].append(gn["label"])
            g_lines = []
            if g_by_type.get("model"):
                g_lines.append(f"- Models / Architectures: {', '.join(g_by_type['model'][:8])}")
            if g_by_type.get("dataset"):
                g_lines.append(f"- Benchmarks / Datasets: {', '.join(g_by_type['dataset'][:8])}")
            if g_by_type.get("method"):
                g_lines.append(f"- Methodologies / Techniques: {', '.join(g_by_type['method'][:8])}")
            if g_by_type.get("topic"):
                g_lines.append(f"- Research Topics: {', '.join(g_by_type['topic'][:6])}")
            if g_by_type.get("gap"):
                g_lines.append(f"- Open Research Gaps ({len(g_by_type['gap'])} identified): {', '.join(g_by_type['gap'][:4])}")
            if g_lines:
                graph_context_block = "Structured Project Knowledge Graph Context:\n" + "\n".join(g_lines) + "\n\n"
    except Exception as exc:
        logger.debug("Optional graph context injection omitted: %s", exc)

    user_prompt = (
        f"{graph_context_block}"
        f"Evidence retrieved from the project's papers:\n\n{context_block}\n\n"
        f"{history_block}"
        f"Question: {question}\n\n"
        "Answer using only the evidence and knowledge graph context above, citing sources as [Source N] and "
        "naming which paper(s) support each claim."
    )

    provider = get_llm_provider()
    try:
        answer_text = provider.generate(SYSTEM_PROMPT, user_prompt)
    except Exception as err:
        logger.warning("LLM provider generate failed in project chat: %s", err)
        answer_text = (
            f"**Retrieved Evidence from Project Literature**:\n\n{context_block}\n\n"
            "*(Note: LLM synthesis unavailable; displaying direct literature citations above.)*"
        )

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

    resp = ProjectChatResponse(
        question=question,
        answer=answer_text,
        sources=sources,
        papers_cited=papers_cited,
        grounded=True,
    )
    await save_chat_message(project_id, question, answer_text, [s.model_dump() for s in sources])
    return resp
