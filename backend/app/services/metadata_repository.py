"""Data access for paper_metadata (structured bibliographic fields)."""
from __future__ import annotations

from uuid import UUID

from app.core.database import get_connection


async def upsert_pending(document_id: UUID) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO paper_metadata (document_id, extraction_status)
            VALUES ($1, 'pending')
            ON CONFLICT (document_id) DO NOTHING
            """,
            document_id,
        )


async def save_extracted(
    document_id: UUID,
    title: str | None,
    authors: list[str] | None,
    publication_year: int | None,
    abstract: str | None,
    keywords: list[str] | None,
) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO paper_metadata
                (document_id, title, authors, publication_year, abstract, keywords,
                 extraction_status, extracted_at)
            VALUES ($1, $2, $3, $4, $5, $6, 'extracted', now())
            ON CONFLICT (document_id) DO UPDATE SET
                title = EXCLUDED.title,
                authors = EXCLUDED.authors,
                publication_year = EXCLUDED.publication_year,
                abstract = EXCLUDED.abstract,
                keywords = EXCLUDED.keywords,
                extraction_status = 'extracted',
                extraction_error = NULL,
                extracted_at = now()
            """,
            document_id,
            title,
            authors,
            publication_year,
            abstract,
            keywords,
        )


async def save_failed(document_id: UUID, error: str) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO paper_metadata (document_id, extraction_status, extraction_error, extracted_at)
            VALUES ($1, 'failed', $2, now())
            ON CONFLICT (document_id) DO UPDATE SET
                extraction_status = 'failed',
                extraction_error = EXCLUDED.extraction_error,
                extracted_at = now()
            """,
            document_id,
            error,
        )


async def get_metadata(document_id: UUID) -> dict | None:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM paper_metadata WHERE document_id = $1", document_id
        )
    return dict(row) if row else None


async def get_metadata_for_documents(document_ids: list[UUID]) -> dict[UUID, dict]:
    if not document_ids:
        return {}
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM paper_metadata WHERE document_id = ANY($1::uuid[])", document_ids
        )
    return {r["document_id"]: dict(r) for r in rows}
