from __future__ import annotations

from app.services.citations import (
    format_apa,
    format_chicago,
    format_ieee,
    format_mla,
    generate_bibtex,
    generate_ris,
    get_all_citations,
)


def test_citation_formatting():
    paper = {
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
        "publication_year": 2017,
        "venue": "NeurIPS",
        "doi": "10.5555/3295222.3295349",
        "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
    }

    apa = format_apa(paper)
    assert "Vaswani, A." in apa
    assert "(2017)." in apa
    assert "Attention Is All You Need" in apa

    ieee = format_ieee(paper)
    assert "A. Vaswani" in ieee
    assert '"Attention Is All You Need,"' in ieee

    mla = format_mla(paper)
    assert "Vaswani, Ashish, et al." in mla

    chicago = format_chicago(paper)
    assert "Vaswani" in chicago

    bibtex = generate_bibtex(paper)
    assert "@article{" in bibtex
    assert "title = {Attention Is All You Need}" in bibtex
    assert "author = {Ashish Vaswani and Noam Shazeer and Niki Parmar}" in bibtex

    ris = generate_ris(paper)
    assert "TY  - JOUR" in ris
    assert "TI  - Attention Is All You Need" in ris
    assert "AU  - Ashish Vaswani" in ris
    assert "ER  - " in ris

    all_citations = get_all_citations(paper)
    assert set(all_citations.keys()) == {"apa", "ieee", "mla", "chicago", "bibtex", "ris"}
