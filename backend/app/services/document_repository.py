"""Data access for documents and document_chunks."""
from __future__ import annotations

from uuid import UUID

from app.core.database import get_connection, vector_literal
from app.core.exceptions import DocumentNotFoundError
from app.models.schemas import DocumentStatus


async def create_document(
    filename: str, title: str | None, project_id: UUID | None = None
) -> UUID:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO documents (filename, title, status, project_id)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            filename,
            title,
            DocumentStatus.UPLOADED.value,
            project_id,
        )
        return row["id"]


async def update_status(
    document_id: UUID,
    status: DocumentStatus,
    error_message: str | None = None,
    page_count: int | None = None,
) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE documents
            SET status = $2,
                error_message = $3,
                page_count = COALESCE($4, page_count),
                updated_at = now()
            WHERE id = $1
            """,
            document_id,
            status.value,
            error_message,
            page_count,
        )


async def insert_chunks(document_id: UUID, chunks, embeddings: list[list[float]]) -> int:
    """Bulk-insert chunks with their embeddings. Returns number inserted."""
    async with get_connection() as conn:
        async with conn.transaction():
            for chunk, embedding in zip(chunks, embeddings):
                await conn.execute(
                    """
                    INSERT INTO document_chunks
                        (document_id, chunk_index, page_number, content, embedding)
                    VALUES ($1, $2, $3, $4, $5::vector)
                    """,
                    document_id,
                    chunk.chunk_index,
                    chunk.page_number,
                    chunk.text,
                    vector_literal(embedding),
                )
    return len(chunks)


async def set_document_project(document_id: UUID, project_id: UUID | None) -> None:
    """Attach (or detach, when project_id=None) a document to a project."""
    async with get_connection() as conn:
        result = await conn.execute(
            "UPDATE documents SET project_id = $2, updated_at = now() WHERE id = $1",
            document_id,
            project_id,
        )
    if result == "UPDATE 0":
        raise DocumentNotFoundError(f"No document with id {document_id}")


async def get_document(document_id: UUID) -> dict:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT d.*,
                   (SELECT COUNT(*) FROM document_chunks c WHERE c.document_id = d.id) AS chunk_count
            FROM documents d
            WHERE d.id = $1
            """,
            document_id,
        )
    if row is None:
        raise DocumentNotFoundError(f"No document with id {document_id}")
    return dict(row)


async def get_leading_chunks(document_id: UUID, limit: int = 3) -> list[dict]:
    """First N chunks in document order — where title/authors/abstract live."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT chunk_index, page_number, content
            FROM document_chunks
            WHERE document_id = $1
            ORDER BY chunk_index ASC
            LIMIT $2
            """,
            document_id,
            limit,
        )
    return [dict(r) for r in rows]


async def get_all_chunks(document_id: UUID) -> list[dict]:
    """All chunks for a document, in order. Used by Phase 3 scientific
    extraction, which needs every chunk (not just the leading ones)."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, chunk_index, page_number, content
            FROM document_chunks
            WHERE document_id = $1
            ORDER BY chunk_index ASC
            """,
            document_id,
        )
    return [dict(r) for r in rows]


async def list_documents(project_id: UUID | None = None) -> list[dict]:
    async with get_connection() as conn:
        if project_id is not None:
            rows = await conn.fetch(
                """
                SELECT d.*,
                       (SELECT COUNT(*) FROM document_chunks c WHERE c.document_id = d.id) AS chunk_count
                FROM documents d
                WHERE d.project_id = $1
                ORDER BY d.created_at DESC
                """,
                project_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT d.*,
                       (SELECT COUNT(*) FROM document_chunks c WHERE c.document_id = d.id) AS chunk_count
                FROM documents d
                ORDER BY d.created_at DESC
                """
            )
    return [dict(r) for r in rows]
