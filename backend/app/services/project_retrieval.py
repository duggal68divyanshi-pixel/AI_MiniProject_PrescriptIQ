"""
Project-scoped retrieval: the same real pgvector cosine search as
retrieval.py, but restricted to the papers that belong to one research
project instead of one document or the whole corpus. This is the
foundation every Phase 2 feature (project chat, comparison, literature
matrix, gap analysis) is built on.
"""
from __future__ import annotations

from uuid import UUID

from app.core.config import get_settings
from app.core.database import get_connection, vector_literal
from app.services.embeddings import embed_query
from app.services.retrieval import RetrievedChunk


async def retrieve_relevant_chunks_for_project(
    query: str,
    project_id: UUID,
    top_k: int | None = None,
    document_ids: list[UUID] | None = None,
) -> list[RetrievedChunk]:
    """
    Retrieve the top-k chunks across every indexed paper in a project
    (or, if document_ids is given, restricted further to that subset —
    used by comparison/matrix generation to target specific papers).
    """
    settings = get_settings()
    top_k = top_k or settings.retrieval_top_k

    query_embedding = embed_query(query)
    embedding_literal = vector_literal(query_embedding)

    params: list = [embedding_literal, project_id, top_k]
    doc_filter = ""
    if document_ids:
        doc_filter = "AND c.document_id = ANY($4::uuid[])"
        params.append(document_ids)

    sql = f"""
        SELECT
            c.id AS chunk_id,
            c.document_id AS document_id,
            d.filename AS document_filename,
            c.content AS content,
            c.page_number AS page_number,
            1 - (c.embedding <=> $1::vector) AS similarity
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.project_id = $2 AND d.status = 'indexed' {doc_filter}
        ORDER BY c.embedding <=> $1::vector
        LIMIT $3
    """

    async with get_connection() as conn:
        rows = await conn.fetch(sql, *params)

    return [
        RetrievedChunk(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            document_filename=row["document_filename"],
            content=row["content"],
            page_number=row["page_number"],
            similarity=float(row["similarity"]),
        )
        for row in rows
    ]


async def retrieve_per_document_chunks(
    query: str,
    document_ids: list[UUID],
    top_k_per_document: int = 4,
) -> dict[UUID, list[RetrievedChunk]]:
    """
    Run the same query against each document independently and return the
    top_k_per_document best chunks per paper. Used where every paper MUST
    be represented in the LLM context (comparison, literature matrix) —
    a single pooled top-k search would let one long/dense paper crowd out
    the others.
    """
    settings = get_settings()
    query_embedding = embed_query(query)
    embedding_literal = vector_literal(query_embedding)

    results: dict[UUID, list[RetrievedChunk]] = {}
    async with get_connection() as conn:
        for document_id in document_ids:
            rows = await conn.fetch(
                """
                SELECT
                    c.id AS chunk_id,
                    c.document_id AS document_id,
                    d.filename AS document_filename,
                    c.content AS content,
                    c.page_number AS page_number,
                    1 - (c.embedding <=> $1::vector) AS similarity
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.document_id = $2 AND d.status = 'indexed'
                ORDER BY c.embedding <=> $1::vector
                LIMIT $3
                """,
                embedding_literal,
                document_id,
                top_k_per_document,
            )
            results[document_id] = [
                RetrievedChunk(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    document_filename=row["document_filename"],
                    content=row["content"],
                    page_number=row["page_number"],
                    similarity=float(row["similarity"]),
                )
                for row in rows
            ]
    _ = settings  # settings reserved for future per-document thresholds
    return results
