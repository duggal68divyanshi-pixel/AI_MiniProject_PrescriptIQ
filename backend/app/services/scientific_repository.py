"""
Data access for Phase 3 tables: paper_sections, scientific_entities,
paper_entities, paper_keyphrases, project_topics, paper_topic_assignments,
scientific_claims, paper_limitations, paper_relationships,
processing_jobs.

Follows the same conventions as document_repository.py / project_repository.py:
plain asyncpg, dicts in/out, no ORM.
"""
from __future__ import annotations

from uuid import UUID

from app.core.database import get_connection
from app.core.exceptions import JobNotFoundError

# ---------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------

async def replace_sections(document_id: UUID, spans: list[dict]) -> None:
    async with get_connection() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM paper_sections WHERE document_id = $1", document_id)
            for s in spans:
                await conn.execute(
                    """
                    INSERT INTO paper_sections
                        (document_id, section_label, heading_text, start_chunk_index,
                         end_chunk_index, page_start, page_end, detection_method, confidence)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    document_id,
                    s["section_label"],
                    s.get("heading_text"),
                    s["start_chunk_index"],
                    s["end_chunk_index"],
                    s.get("page_start"),
                    s.get("page_end"),
                    s["detection_method"],
                    s.get("confidence"),
                )


async def get_sections(document_id: UUID) -> list[dict]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM paper_sections WHERE document_id = $1 ORDER BY start_chunk_index",
            document_id,
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------

async def get_or_create_entity(entity_type: str, canonical_name: str) -> UUID:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO scientific_entities (entity_type, canonical_name)
            VALUES ($1, $2)
            ON CONFLICT (entity_type, canonical_name) DO UPDATE SET entity_type = EXCLUDED.entity_type
            RETURNING id
            """,
            entity_type,
            canonical_name,
        )
    return row["id"]


async def replace_paper_entities(document_id: UUID, mentions: list[dict]) -> None:
    """
    `mentions` items: entity_type, canonical_name, chunk_id, section_label,
    page_number, mention_text, source_excerpt, extraction_method, confidence
    """
    async with get_connection() as conn:
        async with conn.transaction():
            chunk_rows = await conn.fetch("SELECT id FROM document_chunks WHERE document_id = $1", document_id)
            valid_chunk_ids = {r["id"] for r in chunk_rows}

            await conn.execute("DELETE FROM paper_entities WHERE document_id = $1", document_id)
            for m in mentions:
                entity_row = await conn.fetchrow(
                    """
                    INSERT INTO scientific_entities (entity_type, canonical_name)
                    VALUES ($1, $2)
                    ON CONFLICT (entity_type, canonical_name) DO UPDATE SET entity_type = EXCLUDED.entity_type
                    RETURNING id
                    """,
                    m["entity_type"],
                    m["canonical_name"],
                )
                raw_chunk_id = m.get("chunk_id")
                chunk_id = raw_chunk_id if raw_chunk_id in valid_chunk_ids else None

                await conn.execute(
                    """
                    INSERT INTO paper_entities
                        (document_id, entity_id, chunk_id, section_label, page_number,
                         mention_text, source_excerpt, extraction_method, confidence)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    document_id,
                    entity_row["id"],
                    chunk_id,
                    m.get("section_label"),
                    m.get("page_number"),
                    m["mention_text"],
                    m["source_excerpt"],
                    m["extraction_method"],
                    m.get("confidence"),
                )


async def get_paper_entities(document_id: UUID) -> list[dict]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT pe.*, se.entity_type, se.canonical_name
            FROM paper_entities pe
            JOIN scientific_entities se ON se.id = pe.entity_id
            WHERE pe.document_id = $1
            ORDER BY se.entity_type, se.canonical_name
            """,
            document_id,
        )
    return [dict(r) for r in rows]


async def get_project_entities(document_ids: list[UUID]) -> list[dict]:
    if not document_ids:
        return []
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT se.id AS entity_id, se.entity_type, se.canonical_name,
                   COUNT(DISTINCT pe.document_id) AS paper_count,
                   COUNT(pe.id) AS mention_count
            FROM paper_entities pe
            JOIN scientific_entities se ON se.id = pe.entity_id
            WHERE pe.document_id = ANY($1::uuid[])
            GROUP BY se.id, se.entity_type, se.canonical_name
            ORDER BY paper_count DESC, mention_count DESC
            """,
            document_ids,
        )
    return [dict(r) for r in rows]


async def get_entity_detail(entity_id: UUID, document_ids: list[UUID] | None = None) -> dict | None:
    async with get_connection() as conn:
        entity_row = await conn.fetchrow(
            "SELECT * FROM scientific_entities WHERE id = $1", entity_id
        )
        if entity_row is None:
            return None
        if document_ids:
            mention_rows = await conn.fetch(
                """
                SELECT pe.*, d.filename
                FROM paper_entities pe
                JOIN documents d ON d.id = pe.document_id
                WHERE pe.entity_id = $1 AND pe.document_id = ANY($2::uuid[])
                ORDER BY pe.confidence DESC NULLS LAST
                """,
                entity_id,
                document_ids,
            )
        else:
            mention_rows = await conn.fetch(
                """
                SELECT pe.*, d.filename
                FROM paper_entities pe
                JOIN documents d ON d.id = pe.document_id
                WHERE pe.entity_id = $1
                ORDER BY pe.confidence DESC NULLS LAST
                """,
                entity_id,
            )
    return {"entity": dict(entity_row), "mentions": [dict(r) for r in mention_rows]}


# ---------------------------------------------------------------------
# Keyphrases
# ---------------------------------------------------------------------

async def replace_keyphrases(document_id: UUID, phrases: list[tuple[str, float]]) -> None:
    async with get_connection() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM paper_keyphrases WHERE document_id = $1", document_id)
            for rank, (phrase, score) in enumerate(phrases, start=1):
                await conn.execute(
                    """
                    INSERT INTO paper_keyphrases (document_id, phrase, score, rank)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (document_id, phrase) DO NOTHING
                    """,
                    document_id,
                    phrase,
                    score,
                    rank,
                )


async def get_keyphrases(document_id: UUID) -> list[dict]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM paper_keyphrases WHERE document_id = $1 ORDER BY rank", document_id
        )
    return [dict(r) for r in rows]


async def get_project_top_concepts(document_ids: list[UUID], limit: int = 20) -> list[dict]:
    if not document_ids:
        return []
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT phrase, COUNT(DISTINCT document_id) AS paper_count, AVG(score) AS avg_score
            FROM paper_keyphrases
            WHERE document_id = ANY($1::uuid[])
            GROUP BY phrase
            ORDER BY paper_count DESC, avg_score DESC
            LIMIT $2
            """,
            document_ids,
            limit,
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------

async def replace_project_topics(
    project_id: UUID, model_run_id: UUID, topics: list[dict], document_ids: list[UUID]
) -> dict[int, UUID]:
    """topics items: topic_index, label, keywords, document_indices, probabilities.
    Returns {topic_index: topic_row_id} so the caller can insert assignments."""
    topic_ids: dict[int, UUID] = {}
    async with get_connection() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                DELETE FROM paper_topic_assignments
                WHERE document_id = ANY($1::uuid[])
                """,
                document_ids,
            )
            await conn.execute("DELETE FROM project_topics WHERE project_id = $1", project_id)
            for t in topics:
                row = await conn.fetchrow(
                    """
                    INSERT INTO project_topics
                        (project_id, topic_index, label, keywords, document_count, model_run_id)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    project_id,
                    t["topic_index"],
                    t["label"],
                    t["keywords"],
                    len(t["document_indices"]),
                    model_run_id,
                )
                topic_ids[t["topic_index"]] = row["id"]
    return topic_ids


async def insert_topic_assignments(assignments: list[dict]) -> None:
    """items: document_id, topic_id, probability"""
    if not assignments:
        return
    async with get_connection() as conn:
        async with conn.transaction():
            for a in assignments:
                await conn.execute(
                    """
                    INSERT INTO paper_topic_assignments (document_id, topic_id, probability)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (document_id, topic_id) DO NOTHING
                    """,
                    a["document_id"],
                    a["topic_id"],
                    a.get("probability"),
                )


async def get_project_topics(project_id: UUID) -> list[dict]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM project_topics WHERE project_id = $1 ORDER BY document_count DESC",
            project_id,
        )
    return [dict(r) for r in rows]


async def get_topic_detail(topic_id: UUID) -> dict | None:
    async with get_connection() as conn:
        topic_row = await conn.fetchrow("SELECT * FROM project_topics WHERE id = $1", topic_id)
        if topic_row is None:
            return None
        doc_rows = await conn.fetch(
            """
            SELECT d.id AS document_id, d.filename, pta.probability
            FROM paper_topic_assignments pta
            JOIN documents d ON d.id = pta.document_id
            WHERE pta.topic_id = $1
            ORDER BY pta.probability DESC NULLS LAST
            """,
            topic_id,
        )
    return {"topic": dict(topic_row), "papers": [dict(r) for r in doc_rows]}


async def get_paper_topics(document_id: UUID) -> list[dict]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT pt.*, pta.probability
            FROM paper_topic_assignments pta
            JOIN project_topics pt ON pt.id = pta.topic_id
            WHERE pta.document_id = $1
            """,
            document_id,
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Claims & Limitations
# ---------------------------------------------------------------------

async def replace_claims(document_id: UUID, claims: list[dict]) -> None:
    async with get_connection() as conn:
        async with conn.transaction():
            chunk_rows = await conn.fetch("SELECT id FROM document_chunks WHERE document_id = $1", document_id)
            valid_chunk_ids = {r["id"] for r in chunk_rows}

            await conn.execute("DELETE FROM scientific_claims WHERE document_id = $1", document_id)
            for c in claims:
                raw_chunk_id = c.get("chunk_id")
                chunk_id = raw_chunk_id if raw_chunk_id in valid_chunk_ids else None
                await conn.execute(
                    """
                    INSERT INTO scientific_claims
                        (document_id, claim_type, claim_text, evidence_text, chunk_id,
                         section_label, page_number)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    document_id,
                    c["claim_type"],
                    c["claim_text"],
                    c["evidence_text"],
                    chunk_id,
                    c.get("section_label"),
                    c.get("page_number"),
                )


async def get_claims(document_id: UUID) -> list[dict]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM scientific_claims WHERE document_id = $1 ORDER BY created_at", document_id
        )
    return [dict(r) for r in rows]


async def replace_limitations(document_id: UUID, limitations: list[dict]) -> None:
    async with get_connection() as conn:
        async with conn.transaction():
            chunk_rows = await conn.fetch("SELECT id FROM document_chunks WHERE document_id = $1", document_id)
            valid_chunk_ids = {r["id"] for r in chunk_rows}

            await conn.execute("DELETE FROM paper_limitations WHERE document_id = $1", document_id)
            for lim in limitations:
                raw_chunk_id = lim.get("chunk_id")
                chunk_id = raw_chunk_id if raw_chunk_id in valid_chunk_ids else None
                await conn.execute(
                    """
                    INSERT INTO paper_limitations
                        (document_id, limitation_text, category, evidence_text, chunk_id,
                         section_label, page_number)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    document_id,
                    lim["limitation_text"],
                    lim.get("category", "other"),
                    lim["evidence_text"],
                    chunk_id,
                    lim.get("section_label"),
                    lim.get("page_number"),
                )


async def get_limitations(document_id: UUID) -> list[dict]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM paper_limitations WHERE document_id = $1 ORDER BY created_at", document_id
        )
    return [dict(r) for r in rows]


async def get_project_limitations(document_ids: list[UUID]) -> list[dict]:
    if not document_ids:
        return []
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT pl.*, d.filename
            FROM paper_limitations pl
            JOIN documents d ON d.id = pl.document_id
            WHERE pl.document_id = ANY($1::uuid[])
            ORDER BY pl.category, pl.created_at
            """,
            document_ids,
        )
    return [dict(r) for r in rows]


async def get_project_claims(document_ids: list[UUID], claim_types: list[str] | None = None) -> list[dict]:
    if not document_ids:
        return []
    async with get_connection() as conn:
        if claim_types:
            rows = await conn.fetch(
                """
                SELECT sc.*, d.filename
                FROM scientific_claims sc
                JOIN documents d ON d.id = sc.document_id
                WHERE sc.document_id = ANY($1::uuid[]) AND sc.claim_type = ANY($2::text[])
                ORDER BY sc.created_at
                """,
                document_ids,
                claim_types,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT sc.*, d.filename
                FROM scientific_claims sc
                JOIN documents d ON d.id = sc.document_id
                WHERE sc.document_id = ANY($1::uuid[])
                ORDER BY sc.created_at
                """,
                document_ids,
            )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------

async def replace_relationships(document_id: UUID, relationships: list[dict]) -> None:
    async with get_connection() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM paper_relationships WHERE document_id = $1", document_id)
            for r in relationships:
                await conn.execute(
                    """
                    INSERT INTO paper_relationships
                        (document_id, predicate, object_type, object_entity_id,
                         object_claim_id, object_limitation_id, object_text, confidence)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    document_id,
                    r["predicate"],
                    r["object_type"],
                    r.get("object_entity_id"),
                    r.get("object_claim_id"),
                    r.get("object_limitation_id"),
                    r.get("object_text"),
                    r.get("confidence"),
                )


async def get_relationships(document_id: UUID) -> list[dict]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT pr.*, se.canonical_name AS entity_name, se.entity_type AS entity_type,
                   sc.claim_text, pl.limitation_text
            FROM paper_relationships pr
            LEFT JOIN scientific_entities se ON se.id = pr.object_entity_id
            LEFT JOIN scientific_claims sc ON sc.id = pr.object_claim_id
            LEFT JOIN paper_limitations pl ON pl.id = pr.object_limitation_id
            WHERE pr.document_id = $1
            ORDER BY pr.predicate
            """,
            document_id,
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Processing jobs
# ---------------------------------------------------------------------

async def create_job(job_type: str, document_id: UUID | None = None, project_id: UUID | None = None) -> UUID:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO processing_jobs (job_type, document_id, project_id, status)
            VALUES ($1, $2, $3, 'queued')
            RETURNING id
            """,
            job_type,
            document_id,
            project_id,
        )
    return row["id"]


async def update_job(
    job_id: UUID,
    status: str | None = None,
    progress_stage: str | None = None,
    error_message: str | None = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    async with get_connection() as conn:
        await conn.execute(
            f"""
            UPDATE processing_jobs
            SET status = COALESCE($2, status),
                progress_stage = COALESCE($3, progress_stage),
                error_message = COALESCE($4, error_message)
                {", started_at = now()" if started else ""}
                {", finished_at = now()" if finished else ""}
            WHERE id = $1
            """,
            job_id,
            status,
            progress_stage,
            error_message,
        )


async def get_job(job_id: UUID) -> dict:
    async with get_connection() as conn:
        row = await conn.fetchrow("SELECT * FROM processing_jobs WHERE id = $1", job_id)
    if row is None:
        raise JobNotFoundError(f"No processing job with id {job_id}")
    return dict(row)


async def get_latest_job(document_id: UUID, job_type: str) -> dict | None:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM processing_jobs
            WHERE document_id = $1 AND job_type = $2
            ORDER BY created_at DESC LIMIT 1
            """,
            document_id,
            job_type,
        )
    return dict(row) if row else None


# ---------------------------------------------------------------------
# Document intelligence rollup (used by API + literature matrix / gap analysis enrichment)
# ---------------------------------------------------------------------

async def has_intelligence(document_id: UUID) -> bool:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM paper_sections WHERE document_id = $1 LIMIT 1", document_id
        )
    return row is not None
