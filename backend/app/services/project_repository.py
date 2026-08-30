"""Data access for research_projects and their document membership."""
from __future__ import annotations

from uuid import UUID

from app.core.database import get_connection
from app.core.exceptions import ResearchNexusError


class ProjectNotFoundError(ResearchNexusError):
    status_code = 404
    default_message = "Research project not found."


async def create_project(name: str, description: str | None) -> UUID:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO research_projects (name, description)
            VALUES ($1, $2)
            RETURNING id
            """,
            name,
            description,
        )
        return row["id"]


async def list_projects() -> list[dict]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id, p.name, p.description, p.created_at, p.updated_at,
                   COUNT(d.id) AS document_count,
                   COUNT(d.id) FILTER (WHERE d.status = 'indexed') AS indexed_count
            FROM research_projects p
            LEFT JOIN documents d ON d.project_id = p.id
            GROUP BY p.id
            ORDER BY p.created_at DESC
            """
        )
    return [dict(r) for r in rows]


async def get_project(project_id: UUID) -> dict:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT p.id, p.name, p.description, p.created_at, p.updated_at,
                   COUNT(d.id) AS document_count,
                   COUNT(d.id) FILTER (WHERE d.status = 'indexed') AS indexed_count
            FROM research_projects p
            LEFT JOIN documents d ON d.project_id = p.id
            WHERE p.id = $1
            GROUP BY p.id
            """,
            project_id,
        )
    if row is None:
        raise ProjectNotFoundError(f"No research project with id {project_id}")
    return dict(row)


async def update_project(project_id: UUID, name: str | None, description: str | None) -> dict:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE research_projects
            SET name = COALESCE($2, name),
                description = COALESCE($3, description),
                updated_at = now()
            WHERE id = $1
            RETURNING id
            """,
            project_id,
            name,
            description,
        )
    if row is None:
        raise ProjectNotFoundError(f"No research project with id {project_id}")
    return await get_project(project_id)


async def delete_project(project_id: UUID) -> None:
    async with get_connection() as conn:
        result = await conn.execute("DELETE FROM research_projects WHERE id = $1", project_id)
    if result == "DELETE 0":
        raise ProjectNotFoundError(f"No research project with id {project_id}")


async def get_indexed_document_ids(project_id: UUID) -> list[UUID]:
    """Used to fingerprint a project's analyzable paper set for caching."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT id FROM documents WHERE project_id = $1 AND status = 'indexed' ORDER BY id",
            project_id,
        )
    return [r["id"] for r in rows]
