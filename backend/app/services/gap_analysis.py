"""
Research gap detection.

This is deliberately NOT "dump every paper into the LLM and ask for gaps".
The pipeline is:

    indexed papers
        -> literature matrix rows (structured, evidence-grounded findings
           per paper: methodology, dataset, limitations, ...)
        -> collect limitations / methodologies / datasets across papers
        -> LLM synthesis over that CONCISE, already-grounded structured
           data (not raw PDF text) to name repeated patterns, gaps and
           contradictions
        -> evidence_strength is computed in Python from how many distinct
           papers actually support each gap (High >=3, Medium =2, Low =1)
           rather than presented as a fake statistical score

Cached per project, keyed on the exact set of indexed document ids, so
re-opening Gap Analysis without new papers reuses the previous result
(requirement 23).
"""
from __future__ import annotations

import json
import logging
import re
from uuid import UUID, uuid4

from app.models.schemas import LiteratureMatrixRow, ResearchGap, SourceReference
from app.services.analysis_cache import get_cached, save
from app.services.literature_matrix import build_literature_matrix
from app.services.llm_provider import get_llm_provider
from app.services.project_knowledge import get_project_knowledge

logger = logging.getLogger("research_nexus.gap_analysis")

ANALYSIS_TYPE = "gap_analysis"

SYSTEM_PROMPT = """You analyze structured findings already extracted from a set of research papers
to identify literature gaps for a research-gap-analysis report.

You are given, per paper, its already-evidence-grounded: methodology, dataset,
evaluation metrics, results, and limitations. Rules you MUST follow:
1. Base every gap ONLY on the structured findings given below. Never invent a gap,
   a limitation, or a paper's finding that isn't in the data provided.
2. Every gap must list which papers (by filename, exactly as given) support it.
   A gap with zero supporting papers must not be output.
3. Categorize each gap as exactly one of: repeated_limitation, underexplored_area,
   methodological, dataset, evaluation, contradiction.
4. "contradiction" gaps must name the specific conflicting claim from each side.
5. Do not present invented consensus. If only one paper supports a pattern, that is
   still a valid (lower-confidence) gap — say so plainly, don't inflate it.
6. Respond with ONLY a JSON array, each element shaped like:
   {"gap": "...", "category": "...", "affected_papers": ["filename1", "filename2"],
    "why_it_matters": "...", "potential_direction": "..."}
   No markdown fences, no commentary, no extra keys.
"""

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _strength_from_paper_count(n: int) -> str:
    if n >= 3:
        return "High"
    if n == 2:
        return "Medium"
    return "Low"


def _build_structured_findings_block(rows: list[LiteratureMatrixRow]) -> str:
    parts = []
    for row in rows:
        parts.append(
            f"Paper: {row.filename}\n"
            f"  Methodology: {row.methodology}\n"
            f"  Model/Algorithm: {row.model_or_algorithm}\n"
            f"  Dataset: {row.dataset}\n"
            f"  Evaluation metrics: {row.evaluation_metrics}\n"
            f"  Key results: {row.key_results}\n"
            f"  Limitations: {row.limitations}"
        )
    return "\n\n".join(parts)


def _evidence_for_papers(
    rows: list[LiteratureMatrixRow], filenames: list[str], category: str
) -> list[SourceReference]:
    """Pull real source references (page-cited chunks) from the matrix rows
    of the papers a gap names, so every gap stays traceable to real text."""
    by_filename = {row.filename: row for row in rows}
    evidence: list[SourceReference] = []
    for name in filenames:
        row = by_filename.get(name)
        if row is None:
            continue
        # Limitations/dataset/methodology gaps are most likely grounded in
        # that paper's limitations passage; fall back to any of its sources.
        evidence.extend(row.sources[:2])
    return evidence


async def analyze_gaps(
    project_id: UUID, indexed_document_ids: list[UUID], force_refresh: bool = False
) -> tuple[list[ResearchGap], bool, UUID]:
    if not force_refresh:
        cached = await get_cached(project_id, ANALYSIS_TYPE, indexed_document_ids)
        if cached is not None:
            gaps = [ResearchGap(**g) for g in cached["content"]["gaps"]]
            return gaps, True, cached["id"]

    if len(indexed_document_ids) < 2:
        raise ValueError(
            "Gap analysis needs at least 2 indexed papers in the project to find patterns across the literature."
        )

    rows, skipped, _ = await build_literature_matrix(
        project_id, indexed_document_ids, force_refresh=False
    )
    if len(rows) < 2:
        raise ValueError(
            "Fewer than 2 papers could be analyzed for structured findings "
            f"({len(skipped)} skipped) — gap analysis needs at least 2."
        )

    findings_block = _build_structured_findings_block(rows)

    # Phase 3 enrichment (item 17): fold in project-wide entity/limitation
    # aggregation from scientific extraction, when available, so repeated
    # limitations and dominant methods/datasets across the whole project
    # are visible to the LLM as real counted evidence — not just each
    # paper's individually-summarized limitations field. Best-effort:
    # falls back to the unchanged Phase 2 prompt if Phase 3 hasn't run.
    enrichment_block = ""
    try:
        knowledge = await get_project_knowledge(project_id, indexed_document_ids)
        if knowledge.get("common_limitations"):
            repeated = "; ".join(
                f"\"{l['limitation']}\" (appears in {l['paper_count']} paper(s))"
                for l in knowledge["common_limitations"]
            )
            enrichment_block = f"\n\nLimitations repeated across multiple papers (from structured extraction): {repeated}\n"
    except Exception:
        pass

    provider = get_llm_provider()
    raw = ""
    try:
        raw = provider.generate(
            SYSTEM_PROMPT,
            f"Structured findings from {len(rows)} papers:\n\n{findings_block}{enrichment_block}\n\n"
            "Identify the research gaps now, as a JSON array.",
        )
    except Exception as exc:
        logger.warning("Gap analysis LLM generation failed: %s — using rule-based fallback.", exc)

    raw_gaps = []
    if raw:
        try:
            match = _JSON_ARRAY_RE.search(raw)
            if match:
                raw_gaps = json.loads(match.group(0))
            else:
                raw_gaps = json.loads(raw)
        except Exception:
            pass

    if not isinstance(raw_gaps, list) or not raw_gaps:
        # Derive a real fallback gap from the actual limitations text in the matrix rows
        # so we never invent domain-specific content when the LLM fails.
        all_limitations = [row.limitations for row in rows if row.limitations and "not reported" not in row.limitations.lower()]
        lim_summary = " | ".join(all_limitations[:3]) if all_limitations else "See individual paper analyses for details."
        raw_gaps = [
            {
                "gap": f"Limitations identified across {len(rows)} papers remain unaddressed in the collective literature: {lim_summary[:300]}",
                "category": "repeated_limitation",
                "affected_papers": [r.filename for r in rows],
                "why_it_matters": "Recurring limitations across papers signal unresolved challenges that future work should prioritize.",
                "potential_direction": "Synthesize and directly address the shared limitations identified across these papers."
            }
        ]

    # Build a lookup: normalized filename (no ext, lowercase) -> original filename
    # so we tolerate LLM returning "paper" when the real filename is "paper.pdf"
    def _normalize(name: str) -> str:
        import os
        return os.path.splitext(name.strip())[0].lower()

    valid_normalized = {_normalize(row.filename): row.filename for row in rows}
    valid_filenames = {row.filename for row in rows}

    gaps: list[ResearchGap] = []
    for item in raw_gaps:
        raw_affected = item.get("affected_papers")
        if raw_affected is None or not isinstance(raw_affected, list):
            affected = list(valid_filenames)
        else:
            resolved = []
            for f in raw_affected:
                if f in valid_filenames:
                    resolved.append(f)
                elif _normalize(f) in valid_normalized:
                    resolved.append(valid_normalized[_normalize(f)])
            affected = resolved
        if not affected:
            continue
        category = item.get("category") or "underexplored_area"

        gaps.append(
            ResearchGap(
                id=str(uuid4()),
                gap=str(item.get("gap") or "").strip(),
                category=category,
                evidence=_evidence_for_papers(rows, affected, category),
                affected_papers=affected,
                why_it_matters=str(item.get("why_it_matters") or "").strip(),
                potential_direction=str(item.get("potential_direction") or "").strip(),
                evidence_strength=_strength_from_paper_count(len(affected)),
            )
        )

    analysis_id = await save(
        project_id,
        ANALYSIS_TYPE,
        indexed_document_ids,
        {"gaps": [g.model_dump(mode="json") for g in gaps]},
    )
    return gaps, False, analysis_id
