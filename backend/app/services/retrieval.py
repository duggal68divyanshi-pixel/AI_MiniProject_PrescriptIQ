"""
Retrieval: embed a query and run real cosine-similarity search against
document_chunks.embedding using pgvector's `<=>` (cosine distance)
operator. Similarity returned to callers is `1 - cosine_distance`, i.e. a
genuine number in [-1, 1] computed by Postgres itself — never faked.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.database import get_connection, vector_literal
from app.core.config import get_settings
from app.services.embeddings import embed_query


@dataclass
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    document_filename: str
    content: str
    page_number: int | None
    similarity: float


async def retrieve_relevant_chunks(
    query: str,
    top_k: int | None = None,
    document_id: UUID | None = None,
) -> list[RetrievedChunk]:
    settings = get_settings()
    top_k = top_k or settings.retrieval_top_k

    query_embedding = embed_query(query)
    embedding_literal = vector_literal(query_embedding)

    where_clause = "WHERE d.status = 'indexed'"
    params: list = [embedding_literal, top_k]
    if document_id is not None:
        where_clause += " AND c.document_id = $3"
        params.append(document_id)

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
        {where_clause}
        ORDER BY c.embedding <=> $1::vector
        LIMIT $2
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
