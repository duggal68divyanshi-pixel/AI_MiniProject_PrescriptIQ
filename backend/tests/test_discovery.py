"""
Tests for the Literature Discovery subsystem (arXiv / Semantic Scholar & Import).
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import Response

from app.models.schemas import DiscoveredPaperItem, ImportDiscoveredPaperRequest
from app.services.discovery import (
    search_arxiv,
    search_scholarly_literature,
    search_semantic_scholar,
)

SAMPLE_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <title>Deep Learning for Melanoma Classification</title>
    <summary>We present a deep convolutional architecture for skin cancer screening.</summary>
    <published>2023-01-01T12:00:00Z</published>
    <author>
      <name>Alice Smith</name>
    </author>
    <author>
      <name>Bob Jones</name>
    </author>
    <arxiv:doi>10.1000/182</arxiv:doi>
    <arxiv:journal_ref>IEEE TMI 2023</arxiv:journal_ref>
    <link rel="alternate" href="http://arxiv.org/abs/2301.00001v1" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2301.00001v1.pdf" type="application/pdf"/>
  </entry>
</feed>
"""

SAMPLE_SEMANTIC_SCHOLAR_JSON = {
    "data": [
        {
            "paperId": "s2-paper-123",
            "title": "Skin Lesion Analysis Towards Melanoma Detection",
            "abstract": "Analysis of dermoscopy images using residual networks.",
            "year": 2022,
            "venue": "ISBI 2022",
            "citationCount": 42,
            "authors": [{"name": "Carol Danvers"}, {"name": "David Banner"}],
            "externalIds": {"DOI": "10.1109/ISBI.2022.123", "ArXiv": "2201.00002"},
            "openAccessPdf": {"url": "https://example.com/paper.pdf"},
            "url": "https://semanticscholar.org/paper/s2-paper-123",
        }
    ]
}


@pytest.mark.asyncio
async def test_search_arxiv_parses_xml_properly():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, content=SAMPLE_ARXIV_XML.encode("utf-8"))
        results = await search_arxiv("melanoma classification", limit=5)

        assert len(results) == 1
        paper = results[0]
        assert paper.title == "Deep Learning for Melanoma Classification"
        assert paper.authors == ["Alice Smith", "Bob Jones"]
        assert paper.publication_year == 2023
        assert paper.venue == "IEEE TMI 2023"
        assert paper.doi == "10.1000/182"
        assert paper.source == "arXiv"
        assert paper.pdf_url == "http://arxiv.org/pdf/2301.00001v1.pdf"


@pytest.mark.asyncio
async def test_search_semantic_scholar_parses_json_properly():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = Response(200, json=SAMPLE_SEMANTIC_SCHOLAR_JSON)
        results = await search_semantic_scholar("skin lesion", limit=5)

        assert len(results) == 1
        paper = results[0]
        assert paper.title == "Skin Lesion Analysis Towards Melanoma Detection"
        assert paper.authors == ["Carol Danvers", "David Banner"]
        assert paper.publication_year == 2022
        assert paper.citation_count == 42
        assert paper.venue == "ISBI 2022"
        assert paper.source == "Semantic Scholar"


@pytest.mark.asyncio
async def test_search_scholarly_literature_deduplicates():
    with patch("app.services.discovery.search_arxiv", new_callable=AsyncMock) as mock_arxiv, \
         patch("app.services.discovery.search_semantic_scholar", new_callable=AsyncMock) as mock_s2, \
         patch("app.services.discovery.search_openalex", new_callable=AsyncMock) as mock_openalex, \
         patch("app.services.discovery.search_crossref", new_callable=AsyncMock) as mock_crossref:

        mock_arxiv.return_value = [
            DiscoveredPaperItem(
                paper_id="2301.00001",
                title="Transformer Models in Oncology",
                authors=["Alice"],
                source="arXiv",
                publication_year=2023,
            )
        ]
        mock_s2.return_value = [
            DiscoveredPaperItem(
                paper_id="s2-999",
                title="Transformer Models in Oncology",  # Same title
                authors=["Alice Smith"],
                source="Semantic Scholar",
                publication_year=2023,
            ),
            DiscoveredPaperItem(
                paper_id="s2-888",
                title="Novel CNN Architectures",
                authors=["Bob"],
                source="Semantic Scholar",
                publication_year=2024,
            ),
        ]
        mock_openalex.return_value = []
        mock_crossref.return_value = []

        results = await search_scholarly_literature("transformer oncology", source="all", limit=10)
        assert len(results) == 2  # Deduplicated from 3 to 2
        titles = [p.title for p in results]
        assert "Transformer Models in Oncology" in titles
        assert "Novel CNN Architectures" in titles


@pytest.mark.asyncio
async def test_empty_query_returns_empty_list():
    res1 = await search_arxiv("   ")
    res2 = await search_semantic_scholar("")
    res3 = await search_scholarly_literature("")
    assert res1 == []
    assert res2 == []
    assert res3 == []
