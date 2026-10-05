"""
Database access layer.

We talk to Supabase's underlying Postgres directly with asyncpg so we get
full control over pgvector types and raw SQL for similarity search. The
Supabase REST/Storage client is not required for this subsystem.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator
from urllib.parse import urlparse, unquote

import asyncpg

from app.core.config import get_settings

logger = logging.getLogger("research_nexus.db")

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    global _pool
    settings = get_settings()
    if _pool is not None:
        return
    try:
        # Parse the DSN manually so asyncpg receives explicit kwargs.
        # This avoids asyncpg misinterpreting dots in the username
        # (e.g. Supabase session-pooler usernames like postgres.PROJECT_REF).
        parsed = urlparse(settings.database_url)
        _pool = await asyncpg.create_pool(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=unquote(parsed.username or ""),
            password=unquote(parsed.password or ""),
            database=(parsed.path or "/postgres").lstrip("/") or "postgres",
            min_size=1,
            max_size=10,
            command_timeout=30,
        )
        logger.info("Database pool initialized")
    except Exception as exc:  # pragma: no cover - startup failure path
        logger.warning("Postgres database pool not available (%s). Running in offline in-memory mode.", exc)
        _pool = None


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError(
            "Database pool is not initialized. Did startup succeed? "
            "Check DATABASE_URL in your .env file."
        )
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncIterator[asyncpg.Connection]:
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


def vector_literal(embedding: list[float]) -> str:
    """Format a Python float list as a pgvector text literal, e.g. '[0.1,0.2]'."""
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


async def check_connection() -> bool:
    try:
        async with get_connection() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False
