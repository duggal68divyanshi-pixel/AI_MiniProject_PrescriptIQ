"""
Project analytics — every number here comes from data already stored
(paper_metadata.publication_year, cached literature_matrix_row content).
Nothing is invented: if the literature matrix hasn't been generated yet,
common_methods/common_datasets are returned empty rather than guessed.
"""
from __future__ import annotations

from collections import Counter
from uuid import UUID

from app.core.database import get_connection
from app.models.schemas import AnalyticsResponse, YearCount
from app.services import metadata_repository as meta_repo
from app.services.analysis_cache import get_cached
from app.services.literature_matrix import ANALYSIS_TYPE as MATRIX_ANALYSIS_TYPE


async def _get_all_matrix_rows(project_id: UUID, document_ids: list[UUID]) -> list[dict]:
    rows = []
    for document_id in document_ids:
        cached = await get_cached(project_id, MATRIX_ANALYSIS_TYPE, [document_id])
        if cached is not None:
            rows.append(cached["content"])
    return rows


def _top_terms(values: list[str], limit: int = 5) -> list[str]:
    """Very simple frequency count over short extracted phrases — no invented ranking."""
    counter = Counter(v.strip() for v in values if v and "not reported" not in v.lower())
    return [term for term, _ in counter.most_common(limit)]


async def get_project_analytics(project_id: UUID, document_ids: list[UUID]) -> AnalyticsResponse:
    metadata_map = await meta_repo.get_metadata_for_documents(document_ids)
    extracted = [m for m in metadata_map.values() if m.get("extraction_status") == "extracted"]

    year_counts = Counter(m["publication_year"] for m in extracted if m.get("publication_year"))
    years = [YearCount(year=y, count=c) for y, c in sorted(year_counts.items())]

    matrix_rows = await _get_all_matrix_rows(project_id, document_ids)
    common_methods = _top_terms([r.get("model_or_algorithm", "") for r in matrix_rows])
    common_datasets = _top_terms([r.get("dataset", "") for r in matrix_rows])

    return AnalyticsResponse(
        project_id=project_id,
        paper_count=len(document_ids),
        metadata_extracted_count=len(extracted),
        years=years,
        common_methods=common_methods,
        common_datasets=common_datasets,
        matrix_available=len(matrix_rows) > 0,
    )
