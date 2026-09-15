"""
AI-Assisted Paper Authoring Service (Module 8 of Research Nexus Proposal).

Uses accumulated project research context — literature matrix findings, extracted scientific
entities, detected gaps, and grounded paper RAG passages — to assist researchers in drafting
structured academic manuscript sections (Abstract, Introduction, Related Work, Methodology Comparison,
Research Gap Motivation, and Conclusion).
"""
from __future__ import annotations

from uuid import UUID

from app.services.analysis_cache import get_cached, save
from app.services.gap_analysis import analyze_gaps
from app.services.literature_matrix import build_literature_matrix
from app.services.llm_provider import get_llm_provider
from app.services.project_knowledge import get_project_knowledge
from app.services.project_repository import get_indexed_document_ids, get_project


SECTION_PROMPTS = {
    "abstract": (
        "Draft a high-impact, 250-word scientific paper Abstract for a manuscript synthesizing "
        "this literature collection. Include: Background & Motivation, Methodological Paradigms, "
        "Key Datasets & Benchmarks, and Main Insights/Takeaways. Output in formal academic prose."
    ),
    "introduction": (
        "Draft an academic Introduction section for a research paper on this topic. Structure with: "
        "1. Problem Domain & Significance\n"
        "2. Current Approaches & Technical Challenges\n"
        "3. Research Gaps & Motivations\n"
        "4. Overview of Contributions."
    ),
    "related_work": (
        "Draft a comprehensive, citation-grounded Related Work / Literature Review section. Group the "
        "analyzed papers by methodology or dataset theme. Explicitly cite individual papers by author "
        "and year (e.g., Vaswani et al., 2017) or filename based on the provided structured findings. "
        "Compare strengths, weaknesses, and structural differences across studies."
    ),
    "methodology_comparison": (
        "Draft a rigorous Methodology & Model Comparison section comparing the algorithms, model architectures, "
        "loss functions, and evaluation metrics used across the analyzed literature. Highlight dominant "
        "paradigms and technical trade-offs."
    ),
    "research_gaps": (
        "Draft a Research Gaps & Problem Statement section. Detail the key limitations, dataset biases, "
        "evaluation shortcomings, and underexplored directions observed across the literature set. "
        "Formulate precise research questions to guide novel manuscript contributions."
    ),
    "conclusion": (
        "Draft a formal Conclusion & Future Directions section summarizing the state of research, "
        "principal insights synthesized from the literature, and promising future avenues of study."
    ),
}


async def get_saved_manuscript_section(
    project_id: UUID, section_type: str = "related_work"
) -> dict | None:
    try:
        indexed_ids = await get_indexed_document_ids(project_id)
        if not indexed_ids:
            return None
        analysis_type = f"authoring_{section_type}"
        cached = await get_cached(project_id, analysis_type, indexed_ids)
        if cached is not None and "content" in cached:
            return cached["content"]
    except Exception:
        pass
    return None


async def generate_manuscript_section(
    project_id: UUID,
    section_type: str = "related_work",
    custom_instructions: str | None = None,
    force_refresh: bool = False,
) -> dict:
    project = await get_project(project_id)
    indexed_ids = await get_indexed_document_ids(project_id)
    analysis_type = f"authoring_{section_type}"

    # Auto-restore saved draft if not forcing refresh
    if not force_refresh:
        try:
            cached = await get_cached(project_id, analysis_type, indexed_ids)
            if cached is not None and "content" in cached:
                return cached["content"]
        except Exception:
            pass

    # Gather rich project context
    rows, _, _ = await build_literature_matrix(project_id, indexed_ids, force_refresh=False)
    knowledge = await get_project_knowledge(project_id, indexed_ids)

    gaps_summary = ""
    try:
        gaps, _, _ = await analyze_gaps(project_id, indexed_ids, force_refresh=False)
        if gaps:
            gaps_summary = "\n".join(
                f"- Gap [{g.category}]: {g.gap} (Affected: {', '.join(g.affected_papers)})"
                for g in gaps
            )
    except Exception:
        pass

    # Build context prompt
    findings_str = "\n".join(
        f"Paper: {r.title or r.filename} ({r.publication_year or 'n.d.'})\n"
        f"  Authors: {', '.join(r.authors) if r.authors else 'Unknown'}\n"
        f"  Problem: {r.research_problem}\n"
        f"  Methodology: {r.methodology}\n"
        f"  Model/Algorithm: {r.model_or_algorithm}\n"
        f"  Dataset: {r.dataset}\n"
        f"  Results: {r.key_results}\n"
        f"  Limitations: {r.limitations}\n"
        for r in rows
    )

    common_methods = ", ".join(
        e["canonical_name"] for e in knowledge.get("top_methods", []) if isinstance(e, dict) and e.get("canonical_name")
    ) or "None extracted"
    common_datasets = ", ".join(
        e["canonical_name"] for e in knowledge.get("top_datasets", []) if isinstance(e, dict) and e.get("canonical_name")
    ) or "None extracted"

    section_guidance = SECTION_PROMPTS.get(section_type, SECTION_PROMPTS["related_work"])
    extra_prompt = f"\nUser Custom Focus: {custom_instructions}" if custom_instructions else ""

    system_prompt = (
        "You are an expert academic paper authoring assistant for Research Nexus. "
        "Your role is to write clear, publication-quality academic manuscript sections "
        "grounded strictly in the provided research literature context. Use formal academic prose, "
        "clear heading structures, and explicit citations to papers in the collection."
    )

    user_prompt = (
        f"Project Name: {project['name']}\n\n"
        f"Structured Literature Matrix Findings ({len(rows)} papers):\n{findings_str}\n\n"
        f"Aggregated Dominant Methods: {common_methods}\n"
        f"Aggregated Dominant Datasets: {common_datasets}\n\n"
        f"Identified Literature Gaps:\n{gaps_summary if gaps_summary else 'None recorded.'}\n\n"
        f"Task Instructions:\n{section_guidance}{extra_prompt}\n\n"
        "Generate the complete manuscript section now in Markdown format."
    )

    provider = get_llm_provider()
    try:
        content = provider.generate(system_prompt, user_prompt)
    except Exception as err:
        content = (
            f"# Draft Section: {section_type.replace('_', ' ').title()}\n\n"
            f"*(Generated from indexed literature context for {project['name']})*\n\n"
            "## Structured Synthesis\n"
            f"- **Analyzed Papers**: {len(rows)}\n"
            f"- **Dominant Methods**: {common_methods}\n"
            f"- **Dominant Datasets**: {common_datasets}\n\n"
            "### Context Overview\n"
            f"{findings_str[:1000]}..."
        )

    result = {
        "project_id": str(project_id),
        "section_type": section_type,
        "content": content,
        "papers_analyzed": len(rows),
    }

    # Auto-save generated result to persistent DB cache
    try:
        await save(project_id, analysis_type, indexed_ids, result)
    except Exception:
        pass

    return result

