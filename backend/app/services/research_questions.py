"""Research question generation — derived strictly from a project's gap-analysis result."""
from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from app.core.database import get_connection
from app.models.schemas import ResearchGap, ResearchQuestionSet
from app.services.gap_analysis import analyze_gaps
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger("research_nexus.research_questions")

SYSTEM_PROMPT = """You turn a single identified research-literature gap into 2-3 concrete,
answerable research questions (RQs).

Rules you MUST follow:
1. Every question must follow directly from the gap described — do not introduce a
   new topic the gap didn't raise.
2. Questions must be specific and answerable by a study, not vague ("How can we improve X?"
   is too vague; "How does model accuracy change under Y-constrained conditions?" is specific).
3. Respond with ONLY a JSON array of question strings. No markdown fences, no commentary.
"""

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


async def _generate_questions_for_gap(gap: ResearchGap) -> list[str]:
    provider = get_llm_provider()
    try:
        raw = provider.generate(
            SYSTEM_PROMPT,
            f"Gap: {gap.gap}\nWhy it matters: {gap.why_it_matters}\n"
            f"Potential direction: {gap.potential_direction}\n\n"
            "Generate the research questions now, as a JSON array of strings.",
        )
    except Exception as exc:
        logger.warning("LLM call failed for gap %s: %s — using gap-derived fallback questions.", gap.id, exc)
        raw = ""

    if raw:
        try:
            match = _JSON_ARRAY_RE.search(raw)
            if match:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    questions = [str(q).strip() for q in data if str(q).strip()]
                    if questions:
                        return questions
        except Exception:
            pass

    # Fallback: derive questions directly from the gap metadata so we never
    # return empty when a gap is available but the LLM parse failed.
    fallback = []
    if gap.potential_direction:
        fallback.append(
            f"How can researchers address the gap of '{gap.gap[:120]}' "
            f"by pursuing: {gap.potential_direction}?"
        )
    if gap.why_it_matters:
        fallback.append(
            f"What experimental approaches would validate the claim that '{gap.why_it_matters[:120]}'?"
        )
    if not fallback:
        fallback.append(f"What methodological advances would resolve the identified gap: '{gap.gap[:120]}'?")
    return fallback


async def _get_cached_questions(gap_analysis_id: UUID) -> list[dict] | None:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT questions FROM research_questions
            WHERE gap_analysis_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            gap_analysis_id,
        )
    if row is None:
        return None
    content = row["questions"]
    return json.loads(content) if isinstance(content, str) else content


async def _save_questions(project_id: UUID, gap_analysis_id: UUID, question_sets: list[dict]) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO research_questions (project_id, gap_analysis_id, questions)
            VALUES ($1, $2, $3::jsonb)
            """,
            project_id,
            gap_analysis_id,
            json.dumps(question_sets),
        )


async def generate_research_questions(
    project_id: UUID, indexed_document_ids: list[UUID], force_refresh: bool = False
) -> tuple[list[ResearchQuestionSet], bool]:
    gaps, gaps_cached, gap_analysis_id = await analyze_gaps(
        project_id, indexed_document_ids, force_refresh=False
    )
    if not gaps:
        return [], gaps_cached

    if not force_refresh:
        cached = await _get_cached_questions(gap_analysis_id)
        if cached is not None:
            return [ResearchQuestionSet(**qs) for qs in cached], True

    question_sets: list[ResearchQuestionSet] = []
    for gap in gaps:
        try:
            questions = await _generate_questions_for_gap(gap)
        except Exception as exc:
            logger.warning("Research question generation failed for gap %s: %s", gap.id, exc)
            questions = []
        if questions:
            question_sets.append(ResearchQuestionSet(gap_id=gap.id, gap=gap.gap, questions=questions))

    await _save_questions(
        project_id, gap_analysis_id, [qs.model_dump(mode="json") for qs in question_sets]
    )
    return question_sets, False
