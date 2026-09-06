"""
Literature Discovery Service.

Fetches scientific papers from arXiv and Semantic Scholar APIs, parses structured
metadata (authors, abstract, year, venue, DOI, citations, PDF links), and enables
1-click import into Research Nexus workspaces.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import UUID

import fitz  # PyMuPDF
import httpx

from app.core.config import get_settings
from app.core.exceptions import ResearchNexusError
from app.models.schemas import DiscoveredPaperItem, ImportDiscoveredPaperRequest
from app.services import document_repository as doc_repo
from app.services.document_processor import process_document

logger = logging.getLogger("research_nexus.discovery")

ARXIV_API_URL = "https://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def _clean_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _sanitize_filename(name: str) -> str:
    clean = re.sub(r'[^a-zA-Z0-9_\-\. ]+', "", name).strip()
    return clean[:100] if clean else "discovered_paper"


async def search_arxiv(query: str, limit: int = 10) -> list[DiscoveredPaperItem]:
    """Query the official arXiv API for scientific preprints."""
    if not query.strip():
        return []
    
    encoded_query = urllib.parse.quote(query.strip())
    url = f"{ARXIV_API_URL}?search_query=all:{encoded_query}&start=0&max_results={limit}&sortBy=relevance&sortOrder=descending"

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning("arXiv API returned HTTP %d", resp.status_code)
                return []
            
            root = ET.fromstring(resp.content)
            entries = root.findall("atom:entry", ATOM_NS)
            papers: list[DiscoveredPaperItem] = []

            for entry in entries:
                id_elem = entry.find("atom:id", ATOM_NS)
                title_elem = entry.find("atom:title", ATOM_NS)
                summary_elem = entry.find("atom:summary", ATOM_NS)
                published_elem = entry.find("atom:published", ATOM_NS)
                doi_elem = entry.find("arxiv:doi", ATOM_NS)
                journal_elem = entry.find("arxiv:journal_ref", ATOM_NS)

                raw_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                paper_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id
                title = _clean_text(title_elem.text) if title_elem is not None else "Untitled Paper"
                abstract = _clean_text(summary_elem.text) if summary_elem is not None else None

                authors = []
                for author_elem in entry.findall("atom:author", ATOM_NS):
                    name_elem = author_elem.find("atom:name", ATOM_NS)
                    if name_elem is not None and name_elem.text:
                        authors.append(name_elem.text.strip())

                pub_year = None
                if published_elem is not None and published_elem.text:
                    match = re.match(r"^(\d{4})", published_elem.text.strip())
                    if match:
                        pub_year = int(match.group(1))

                doi = doi_elem.text.strip() if doi_elem is not None and doi_elem.text else None
                venue = journal_elem.text.strip() if journal_elem is not None and journal_elem.text else "arXiv"

                # Find direct PDF link
                pdf_url = None
                paper_url = raw_id
                for link in entry.findall("atom:link", ATOM_NS):
                    if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                        pdf_url = link.attrib.get("href")
                        if pdf_url and not pdf_url.endswith(".pdf"):
                            pdf_url += ".pdf"
                    elif link.attrib.get("rel") == "alternate":
                        paper_url = link.attrib.get("href", raw_id)

                if not pdf_url and paper_id:
                    clean_id = re.sub(r"v\d+$", "", paper_id)
                    pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"

                papers.append(
                    DiscoveredPaperItem(
                        paper_id=paper_id,
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        publication_year=pub_year,
                        venue=venue,
                        doi=doi,
                        citation_count=None,
                        source="arXiv",
                        paper_url=paper_url,
                        pdf_url=pdf_url,
                    )
                )

            return papers
    except Exception as exc:
        logger.error("arXiv search error: %s", exc)
        return []


async def search_semantic_scholar(query: str, limit: int = 10) -> list[DiscoveredPaperItem]:
    """Query Semantic Scholar Graph API for indexed scientific literature."""
    if not query.strip():
        return []

    fields = "paperId,title,abstract,year,venue,authors,citationCount,externalIds,openAccessPdf,url"
    params = {"query": query.strip(), "limit": limit, "fields": fields}

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            resp = await client.get(SEMANTIC_SCHOLAR_API_URL, params=params)
            if resp.status_code != 200:
                logger.warning("Semantic Scholar returned HTTP %d", resp.status_code)
                return []

            data = resp.json()
            items = data.get("data", [])
            papers: list[DiscoveredPaperItem] = []

            for item in items:
                paper_id = item.get("paperId") or ""
                title = _clean_text(item.get("title")) or "Untitled"
                abstract = _clean_text(item.get("abstract")) or None
                year = item.get("year")
                venue = item.get("venue") or None
                citations = item.get("citationCount")
                url = item.get("url")

                authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
                ext_ids = item.get("externalIds") or {}
                doi = ext_ids.get("DOI")

                pdf_info = item.get("openAccessPdf") or {}
                pdf_url = pdf_info.get("url")

                # If openAccessPdf missing but arXiv ID present, build arXiv PDF URL
                if not pdf_url and ext_ids.get("ArXiv"):
                    pdf_url = f"https://arxiv.org/pdf/{ext_ids['ArXiv']}.pdf"

                papers.append(
                    DiscoveredPaperItem(
                        paper_id=paper_id,
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        publication_year=year,
                        venue=venue,
                        doi=doi,
                        citation_count=citations,
                        source="Semantic Scholar",
                        paper_url=url,
                        pdf_url=pdf_url,
                    )
                )

            return papers
    except Exception as exc:
        logger.error("Semantic Scholar search error: %s", exc)
        return []


OPENALEX_API_URL = "https://api.openalex.org/works"
CROSSREF_API_URL = "https://api.crossref.org/works"


def _reconstruct_openalex_abstract(inverted_index: dict | None) -> str | None:
    if not inverted_index or not isinstance(inverted_index, dict):
        return None
    positions = []
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions.append((pos, word))
    positions.sort(key=lambda x: x[0])
    text = " ".join(word for _, word in positions)
    return _clean_text(text) if text else None


async def search_openalex(query: str, limit: int = 10) -> list[DiscoveredPaperItem]:
    """Query OpenAlex API for open scholarly literature."""
    if not query.strip():
        return []

    encoded_query = urllib.parse.quote(query.strip())
    url = f"{OPENALEX_API_URL}?search={encoded_query}&per-page={limit}"

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            headers = {"User-Agent": "ResearchNexus/1.0 (mailto:researcher@example.com)"}
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning("OpenAlex API returned HTTP %d", resp.status_code)
                return []

            data = resp.json()
            items = data.get("results", [])
            papers: list[DiscoveredPaperItem] = []

            for item in items:
                raw_id = item.get("id") or ""
                paper_id = raw_id.split("/")[-1] if "/" in raw_id else raw_id
                title = _clean_text(item.get("display_name") or item.get("title")) or "Untitled"
                year = item.get("publication_year")
                citations = item.get("cited_by_count")

                authors = []
                for auth in item.get("authorships", []):
                    author_obj = auth.get("author") or {}
                    name = author_obj.get("display_name")
                    if name:
                        authors.append(name.strip())

                abstract = _reconstruct_openalex_abstract(item.get("abstract_inverted_index"))

                primary_loc = item.get("primary_location") or {}
                source_obj = primary_loc.get("source") or {}
                venue = source_obj.get("display_name") or None

                raw_doi = item.get("doi") or ""
                doi = raw_doi.replace("https://doi.org/", "") if raw_doi else None

                paper_url = primary_loc.get("landing_page_url") or item.get("id")
                open_access = item.get("open_access") or {}
                pdf_url = open_access.get("oa_url") if open_access.get("is_oa") else None

                papers.append(
                    DiscoveredPaperItem(
                        paper_id=paper_id,
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        publication_year=year,
                        venue=venue,
                        doi=doi,
                        citation_count=citations,
                        source="OpenAlex",
                        paper_url=paper_url,
                        pdf_url=pdf_url,
                    )
                )

            return papers
    except Exception as exc:
        logger.error("OpenAlex search error: %s", exc)
        return []


async def search_crossref(query: str, limit: int = 10) -> list[DiscoveredPaperItem]:
    """Query Crossref API for registered academic publications."""
    if not query.strip():
        return []

    params = {"query": query.strip(), "rows": limit}

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            headers = {"User-Agent": "ResearchNexus/1.0 (mailto:researcher@example.com)"}
            resp = await client.get(CROSSREF_API_URL, params=params, headers=headers)
            if resp.status_code != 200:
                logger.warning("Crossref API returned HTTP %d", resp.status_code)
                return []

            data = resp.json()
            items = data.get("message", {}).get("items", [])
            papers: list[DiscoveredPaperItem] = []

            for item in items:
                doi = item.get("DOI")
                paper_id = doi or item.get("URL") or "crossref_paper"
                titles = item.get("title") or []
                title = _clean_text(titles[0]) if titles else "Untitled"

                authors = []
                for a in item.get("author") or []:
                    given = a.get("given", "").strip()
                    family = a.get("family", "").strip()
                    name = f"{given} {family}".strip() or a.get("name", "").strip()
                    if name:
                        authors.append(name)

                pub_date = item.get("published-print") or item.get("published-online") or item.get("issued") or {}
                date_parts = pub_date.get("date-parts") or [[]]
                year = date_parts[0][0] if date_parts[0] and isinstance(date_parts[0][0], int) else None

                container = item.get("container-title") or []
                venue = container[0] if container else None

                citations = item.get("is-referenced-by-count")

                raw_abstract = item.get("abstract")
                abstract = _clean_text(re.sub(r"<[^>]+>", "", raw_abstract)) if raw_abstract else None

                paper_url = item.get("URL")
                pdf_url = None
                for link in item.get("link") or []:
                    if link.get("content-type") == "application/pdf":
                        pdf_url = link.get("URL")
                        break

                papers.append(
                    DiscoveredPaperItem(
                        paper_id=paper_id,
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        publication_year=year,
                        venue=venue,
                        doi=doi,
                        citation_count=citations,
                        source="Crossref",
                        paper_url=paper_url,
                        pdf_url=pdf_url,
                    )
                )

            return papers
    except Exception as exc:
        logger.error("Crossref search error: %s", exc)
        return []


async def search_scholarly_literature(
    query: str, source: str = "all", limit: int = 10
) -> list[DiscoveredPaperItem]:
    """
    Unified literature search across arXiv, Semantic Scholar, OpenAlex, and Crossref.
    Deduplicates papers by normalized title.
    """
    source_lower = source.lower()
    results: list[DiscoveredPaperItem] = []

    if source_lower in ("arxiv", "all"):
        arxiv_papers = await search_arxiv(query, limit=limit)
        results.extend(arxiv_papers)

    if source_lower in ("semantic_scholar", "semanticscholar", "all"):
        s2_papers = await search_semantic_scholar(query, limit=limit)
        results.extend(s2_papers)

    if source_lower in ("openalex", "all"):
        openalex_papers = await search_openalex(query, limit=limit)
        results.extend(openalex_papers)

    if source_lower in ("crossref", "all"):
        crossref_papers = await search_crossref(query, limit=limit)
        results.extend(crossref_papers)

    # Deduplicate by normalized lowercase alphanumeric title
    seen_titles = set()
    deduped: list[DiscoveredPaperItem] = []

    for paper in results:
        norm_title = re.sub(r"\W+", "", paper.title.lower())
        if norm_title and norm_title not in seen_titles:
            seen_titles.add(norm_title)
            deduped.append(paper)

    return deduped[:limit]


def _create_synthetic_paper_pdf(paper: ImportDiscoveredPaperRequest) -> bytes:
    """Create a clean PDF from paper metadata & abstract when direct PDF download is unavailable."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # Document Header
    y = 50
    page.insert_text((50, y), paper.title, fontsize=16, fontname="helv", color=(0.1, 0.2, 0.3))
    y += 30

    author_str = ", ".join(paper.authors) if paper.authors else "Unknown Authors"
    page.insert_text((50, y), f"Authors: {author_str}", fontsize=10, fontname="helv", color=(0.3, 0.3, 0.3))
    y += 18

    meta_parts = []
    if paper.publication_year:
        meta_parts.append(f"Year: {paper.publication_year}")
    if paper.venue:
        meta_parts.append(f"Venue: {paper.venue}")
    if paper.doi:
        meta_parts.append(f"DOI: {paper.doi}")
    if paper.source:
        meta_parts.append(f"Source: {paper.source}")

    if meta_parts:
        page.insert_text((50, y), " | ".join(meta_parts), fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))
        y += 25

    # Abstract Section
    page.insert_text((50, y), "Abstract", fontsize=13, fontname="helv", color=(0.1, 0.1, 0.1))
    y += 20

    abstract_text = paper.abstract or "No abstract provided for this publication."
    rect = fitz.Rect(50, y, 545, 780)
    page.insert_textbox(rect, abstract_text, fontsize=10, fontname="helv", color=(0.15, 0.15, 0.15))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


async def import_discovered_paper(
    project_id: UUID | None, paper: ImportDiscoveredPaperRequest
) -> UUID:
    """Download PDF or create indexed paper record and trigger extraction pipeline."""
    settings = get_settings()
    safe_name = _sanitize_filename(paper.title) + ".pdf"
    pdf_bytes: bytes | None = None

    # Try downloading real PDF if URL is present
    if paper.pdf_url:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (ResearchNexus; OpenSourceAcademicAssistant)"}
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=headers) as client:
                res = await client.get(paper.pdf_url)
                if res.status_code == 200 and len(res.content) > 1000 and res.content[:4] == b"%PDF":
                    pdf_bytes = res.content
                    logger.info("Successfully fetched remote PDF (%d bytes) for '%s'", len(pdf_bytes), paper.title)
        except Exception as exc:
            logger.warning("Could not download direct PDF for '%s' (%s): %s", paper.title, paper.pdf_url, exc)

    # Fallback to creating a formatted PDF from metadata + abstract
    if not pdf_bytes:
        logger.info("Generating indexed PDF from paper metadata for '%s'", paper.title)
        pdf_bytes = _create_synthetic_paper_pdf(paper)

    # Store document and initiate processing pipeline
    document_id = await doc_repo.create_document(
        filename=safe_name, title=paper.title, project_id=project_id
    )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / f"{document_id}.pdf").write_bytes(pdf_bytes)

    # Trigger background processing
    await process_document(document_id, pdf_bytes, safe_name)
    return document_id
