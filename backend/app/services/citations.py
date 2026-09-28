"""
Citation & Bibliography Export Service.

Generates standard academic citations in APA, IEEE, MLA, Chicago, BibTeX, and RIS formats.
"""
from __future__ import annotations

import re


def _format_authors_apa(authors: list[str]) -> str:
    if not authors:
        return "Unknown Author."
    formatted = []
    for a in authors:
        parts = a.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            initials = " ".join(f"{p[0]}." for p in parts[:-1] if p)
            formatted.append(f"{last}, {initials}")
        else:
            formatted.append(a.strip())

    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]}, & {formatted[1]}"
    if len(formatted) > 2:
        return f"{', '.join(formatted[:-1])}, & {formatted[-1]}"
    return ", ".join(formatted)


def _format_authors_ieee(authors: list[str]) -> str:
    if not authors:
        return "Unknown Author"
    formatted = []
    for a in authors:
        parts = a.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            initials = " ".join(f"{p[0]}." for p in parts[:-1] if p)
            formatted.append(f"{initials} {last}")
        else:
            formatted.append(a.strip())

    if len(formatted) > 3:
        return f"{formatted[0]} et al."
    return ", ".join(formatted)


def format_apa(paper: dict) -> str:
    authors = _format_authors_apa(paper.get("authors") or [])
    year = f"({paper.get('publication_year')})." if paper.get("publication_year") else "(n.d.)."
    title = paper.get("title") or "Untitled"
    venue = f" {paper.get('venue')}." if paper.get("venue") else ""
    doi = f" https://doi.org/{paper.get('doi')}" if paper.get("doi") else ""
    return f"{authors} {year} {title}.{venue}{doi}".strip()


def format_ieee(paper: dict) -> str:
    authors = _format_authors_ieee(paper.get("authors") or [])
    title = f'"{paper.get("title") or "Untitled"},"'
    venue = f" {paper.get('venue')}," if paper.get("venue") else ""
    year = f" {paper.get('publication_year')}." if paper.get("publication_year") else "."
    doi = f" doi: {paper.get('doi')}." if paper.get("doi") else ""
    return f"{authors}, {title}{venue}{year}{doi}".strip()


def format_mla(paper: dict) -> str:
    authors_list = paper.get("authors") or []
    if authors_list:
        parts = authors_list[0].strip().split()
        if len(parts) >= 2:
            first_author = f"{parts[-1]}, {' '.join(parts[:-1])}"
        else:
            first_author = authors_list[0]

        if len(authors_list) == 2:
            authors = f"{first_author}, and {authors_list[1]}"
        elif len(authors_list) > 2:
            authors = f"{first_author}, et al."
        else:
            authors = first_author
    else:
        authors = "Unknown Author"

    title = f'"{paper.get("title") or "Untitled"}."'
    venue = f" {paper.get('venue')}," if paper.get("venue") else ""
    year = f" {paper.get('publication_year')}." if paper.get("publication_year") else "."
    return f"{authors}. {title}{venue}{year}".strip()


def format_chicago(paper: dict) -> str:
    authors_list = paper.get("authors") or []
    authors = ", ".join(authors_list) if authors_list else "Unknown Author"
    title = f'"{paper.get("title") or "Untitled"}."'
    venue = f" {paper.get('venue')}" if paper.get("venue") else ""
    year = f" ({paper.get('publication_year')})." if paper.get("publication_year") else "."
    return f"{authors}. {title}{venue}{year}".strip()


def generate_bibtex(paper: dict) -> str:
    authors = " and ".join(paper.get("authors") or ["Unknown Author"])
    title = paper.get("title") or "Untitled"
    year = paper.get("publication_year") or ""
    venue = paper.get("venue") or ""
    doi = paper.get("doi") or ""

    first_author = (paper.get("authors") or ["Author"])[0].split()[-1].lower()
    first_author = re.sub(r"\W+", "", first_author)
    title_word = re.sub(r"\W+", "", (title.split()[0] if title else "paper")).lower()
    cite_key = f"{first_author}{year}{title_word}"

    lines = [f"@article{{{cite_key},"]
    lines.append(f'  title = {{{title}}},')
    lines.append(f'  author = {{{authors}}},')
    if year:
        lines.append(f'  year = {{{year}}},')
    if venue:
        lines.append(f'  journal = {{{venue}}},')
    if doi:
        lines.append(f'  doi = {{{doi}}},')
    lines.append("}")
    return "\n".join(lines)


def generate_ris(paper: dict) -> str:
    lines = ["TY  - JOUR"]
    lines.append(f"TI  - {paper.get('title') or 'Untitled'}")
    for author in paper.get("authors") or []:
        lines.append(f"AU  - {author}")
    if paper.get("publication_year"):
        lines.append(f"PY  - {paper.get('publication_year')}")
    if paper.get("venue"):
        lines.append(f"JO  - {paper.get('venue')}")
    if paper.get("doi"):
        lines.append(f"DO  - {paper.get('doi')}")
    if paper.get("abstract"):
        lines.append(f"AB  - {paper.get('abstract')}")
    lines.append("ER  - ")
    return "\n".join(lines)


def get_all_citations(paper: dict) -> dict[str, str]:
    return {
        "apa": format_apa(paper),
        "ieee": format_ieee(paper),
        "mla": format_mla(paper),
        "chicago": format_chicago(paper),
        "bibtex": generate_bibtex(paper),
        "ris": generate_ris(paper),
    }
