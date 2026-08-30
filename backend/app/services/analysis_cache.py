"""
Cache layer over research_analysis.

Expensive multi-paper analyses (comparison, literature matrix rows, gap
analysis) are cached per project, keyed by exactly which indexed document
ids were analyzed. If the project's indexed paper set hasn't changed since
the last run, a cached result is reused instead of re-calling the LLM —
see requirement 23 (performance / avoid reprocessing).
"""
from __future__ import annotations

import json
from uuid import UUID

from app.core.database import get_connection


def _fingerprint(document_ids: list[UUID]) -> list[UUID]:
    return sorted(document_ids, key=str)


async def get_cached(
    project_id: UUID, analysis_type: str, document_ids: list[UUID]
) -> dict | None:
    fp = _fingerprint(document_ids)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, content, created_at
            FROM research_analysis
            WHERE project_id = $1 AND analysis_type = $2 AND document_ids = $3::uuid[]
            ORDER BY created_at DESC
            LIMIT 1
            """,
            project_id,
            analysis_type,
            fp,
        )
    if row is None:
        return None
    content = row["content"]
    if isinstance(content, str):
        content = json.loads(content)
    return {"id": row["id"], "content": content, "created_at": row["created_at"]}


async def save(
    project_id: UUID, analysis_type: str, document_ids: list[UUID], content: dict
) -> UUID:
    fp = _fingerprint(document_ids)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO research_analysis (project_id, analysis_type, document_ids, content)
            VALUES ($1, $2, $3::uuid[], $4::jsonb)
            RETURNING id
            """,
            project_id,
            analysis_type,
            fp,
            json.dumps(content, default=str),
        )
    return row["id"]
