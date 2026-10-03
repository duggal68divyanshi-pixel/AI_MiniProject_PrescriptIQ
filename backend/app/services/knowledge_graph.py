"""
Visual Knowledge Graph Generation and AI Synthesis Service.

Dynamically constructs an interactive, multi-entity research knowledge graph
from real project documents, scientific entities, topics, claims, limitations,
research questions, authors, and relationships.
"""
from __future__ import annotations

import math
import re
from uuid import UUID
from collections import defaultdict
import logging

from app.services import document_repository as doc_repo
from app.services import metadata_repository as meta_repo
from app.services import project_repository as proj_repo
from app.services import scientific_repository as sci_repo
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger("research_nexus.knowledge_graph")


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", cleaned)[:40]


async def build_project_knowledge_graph(project_id: UUID) -> dict:
    """
    Constructs an interactive visual knowledge graph payload for a project.
    All data is derived from actual research data stored in the database.
    """
    await proj_repo.get_project(project_id)
    doc_rows = await doc_repo.list_documents(project_id=project_id)
    if not doc_rows:
        return {
            "project_id": str(project_id),
            "nodes": [],
            "edges": [],
            "stats": {"total_nodes": 0, "total_edges": 0, "node_types": {}},
            "message": "No documents added to this project yet."
        }

    indexed_ids = [d["id"] for d in doc_rows if d["status"] == "indexed"]
    metadata_map = await meta_repo.get_metadata_for_documents([d["id"] for d in doc_rows])
    
    # Fetch structured scientific knowledge
    entities = await sci_repo.get_project_entities(indexed_ids) if indexed_ids else []
    topics = await sci_repo.get_project_topics(project_id)
    claims = await sci_repo.get_project_claims(indexed_ids) if indexed_ids else []
    limitations = await sci_repo.get_project_limitations(indexed_ids) if indexed_ids else []
    relationships = await sci_repo.get_project_relationships(indexed_ids, limit=150) if indexed_ids else []
    top_concepts = await sci_repo.get_project_top_concepts(indexed_ids, limit=25) if indexed_ids else []

    # Fetch paper-topic assignments
    topic_assignments = await sci_repo.get_paper_topic_assignments(indexed_ids) if indexed_ids else []

    # Fetch research questions
    rq_rows = await sci_repo.get_project_research_questions(project_id)

    # Fetch keyphrases per document to map concepts to papers
    keyphrase_rows = await sci_repo.get_project_keyphrases_top_n(indexed_ids, top_n=5) if indexed_ids else []

    nodes = []
    edges = []
    node_ids = set()
    edge_ids = set()
    node_type_counts = defaultdict(int)
    label_lookup = {}
    paper_titles = {}

    for doc in doc_rows:
        meta = metadata_map.get(doc["id"]) or {}
        paper_titles[doc["id"]] = meta.get("title") or doc.get("title") or doc.get("filename")

    # Pre-aggregate structured knowledge per paper
    paper_methods = defaultdict(list)
    paper_models = defaultdict(list)
    paper_datasets = defaultdict(list)
    paper_metrics = defaultdict(list)
    paper_algorithms = defaultdict(list)
    paper_findings = defaultdict(list)
    paper_gaps = defaultdict(list)
    paper_assigned_topics = defaultdict(list)
    dataset_models = defaultdict(set)
    dataset_methods = defaultdict(set)
    model_datasets = defaultdict(set)
    model_topics = defaultdict(set)

    for c in claims:
        doc_id = c.get("document_id")
        if doc_id and c.get("claim_text"):
            paper_findings[doc_id].append(c["claim_text"])

    for lim in limitations:
        doc_id = lim.get("document_id")
        if doc_id and lim.get("limitation_text"):
            paper_gaps[doc_id].append(lim["limitation_text"])

    for rel in relationships:
        doc_id = rel.get("document_id")
        etype = (rel.get("entity_type") or "").lower()
        ename = rel.get("entity_name") or ""
        if not ename or not doc_id:
            continue
        if etype == "method" and ename not in paper_methods[doc_id]:
            paper_methods[doc_id].append(ename)
        elif etype == "model" and ename not in paper_models[doc_id]:
            paper_models[doc_id].append(ename)
        elif etype == "dataset" and ename not in paper_datasets[doc_id]:
            paper_datasets[doc_id].append(ename)
        elif etype == "metric" and ename not in paper_metrics[doc_id]:
            paper_metrics[doc_id].append(ename)
        elif etype == "algorithm" and ename not in paper_algorithms[doc_id]:
            paper_algorithms[doc_id].append(ename)

    for doc in doc_rows:
        d_id = doc["id"]
        for d_name in paper_datasets[d_id]:
            for m_name in paper_models[d_id]:
                dataset_models[d_name].add(m_name)
                model_datasets[m_name].add(d_name)
            for m_tech in paper_methods[d_id]:
                dataset_methods[d_name].add(m_tech)

    topic_label_map = {t["id"]: t["label"] for t in topics}
    for ta in topic_assignments:
        d_id = ta.get("document_id")
        t_id = ta.get("topic_id")
        t_lbl = topic_label_map.get(t_id)
        if d_id and t_lbl:
            paper_assigned_topics[d_id].append(t_lbl)
            for m_name in paper_models[d_id]:
                model_topics[m_name].add(t_lbl)

    def add_node(node_id: str, node_type: str, label: str, data: dict, x: float = 0.0, y: float = 0.0):
        if node_id not in node_ids:
            node_ids.add(node_id)
            label_lookup[node_id] = label
            node_type_counts[node_type] += 1
            nodes.append({
                "id": node_id,
                "type": node_type,
                "label": label,
                "data": {**data, "node_type": node_type, "label": label},
                "position": {"x": round(x, 1), "y": round(y, 1)}
            })

    def add_edge(source_id: str, target_id: str, predicate: str, label: str = "", data: dict | None = None):
        if source_id in node_ids and target_id in node_ids:
            edge_id = f"e-{source_id}-{target_id}-{predicate}"
            if edge_id not in edge_ids:
                edge_ids.add(edge_id)
                s_lbl = label_lookup.get(source_id, source_id)
                t_lbl = label_lookup.get(target_id, target_id)
                edge_data = {
                    "source_id": source_id,
                    "target_id": target_id,
                    "source_label": s_lbl,
                    "target_label": t_lbl,
                    "predicate": predicate,
                    "label": label or predicate.replace("_", " "),
                    "description": f"{s_lbl} {label or predicate.replace('_', ' ')} {t_lbl}",
                    **(data or {})
                }
                edges.append({
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "label": label or predicate.replace("_", " "),
                    "predicate": predicate,
                    "data": edge_data
                })

    # --- 1. Paper Nodes ---
    paper_count = len(doc_rows)
    paper_radius = 280 if paper_count > 1 else 0
    paper_coords = {}

    for idx, doc in enumerate(doc_rows):
        doc_id = doc["id"]
        meta = metadata_map.get(doc_id) or {}
        title = meta.get("title") or doc.get("title") or doc.get("filename")
        angle = (2 * math.pi * idx) / max(paper_count, 1)
        px = paper_radius * math.cos(angle)
        py = paper_radius * math.sin(angle)
        paper_node_id = f"paper-{doc_id}"
        paper_coords[doc_id] = (px, py)

        add_node(
            node_id=paper_node_id,
            node_type="paper",
            label=title,
            data={
                "document_id": str(doc_id),
                "filename": doc["filename"],
                "title": title,
                "authors": meta.get("authors") or [],
                "publication_year": meta.get("publication_year"),
                "venue": meta.get("venue") or "Academic Publication",
                "doi": meta.get("doi") or "",
                "abstract": meta.get("abstract") or "",
                "status": doc["status"],
                "methods": paper_methods[doc_id],
                "models": paper_models[doc_id],
                "datasets": paper_datasets[doc_id],
                "metrics": paper_metrics[doc_id],
                "algorithms": paper_algorithms[doc_id],
                "findings": paper_findings[doc_id][:5],
                "gaps": paper_gaps[doc_id][:5],
                "topics": paper_assigned_topics[doc_id],
            },
            x=px,
            y=py
        )

    # --- 2. Author Nodes & Written-By Edges ---
    author_papers = defaultdict(list)
    for doc in doc_rows:
        doc_id = doc["id"]
        meta = metadata_map.get(doc_id) or {}
        for author in (meta.get("authors") or []):
            author_clean = author.strip()
            if author_clean:
                author_papers[author_clean].append(doc_id)

    # Add notable authors (those on at least 1 paper, max 15)
    sorted_authors = sorted(author_papers.items(), key=lambda x: len(x[1]), reverse=True)[:15]
    for a_idx, (author_name, p_ids) in enumerate(sorted_authors):
        a_id = f"author-{_slugify(author_name)}"
        angle = (2 * math.pi * a_idx) / max(len(sorted_authors), 1)
        ax = (paper_radius + 220) * math.cos(angle)
        ay = (paper_radius + 220) * math.sin(angle)
        add_node(
            node_id=a_id,
            node_type="author",
            label=author_name,
            data={"name": author_name, "paper_count": len(p_ids)},
            x=ax,
            y=ay
        )
        for pid in p_ids:
            add_edge(f"paper-{pid}", a_id, "written_by", "written by")

    # --- 3. Topic Nodes & Studies Edges ---
    for t_idx, topic in enumerate(topics):
        t_id = f"topic-{topic['id']}"
        angle = (2 * math.pi * t_idx) / max(len(topics), 1) + 0.4
        tx = 130 * math.cos(angle)
        ty = 130 * math.sin(angle)
        add_node(
            node_id=t_id,
            node_type="topic",
            label=topic["label"],
            data={
                "topic_id": str(topic["id"]),
                "keywords": topic.get("keywords") or [],
                "document_count": topic.get("document_count", 0)
            },
            x=tx,
            y=ty
        )

    for ta in topic_assignments:
        add_edge(
            f"paper-{ta['document_id']}",
            f"topic-{ta['topic_id']}",
            "studies",
            "studies",
            {"probability": ta["probability"]}
        )

    # --- 4. Scientific Entity Nodes (Model, Dataset, Method, Metric, Domain, Algorithm) ---
    entity_paper_map = defaultdict(set)
    for rel in relationships:
        if rel.get("object_entity_id"):
            entity_paper_map[rel["object_entity_id"]].add(rel["document_id"])

    # Position entities around outer ring
    all_top_entities = []
    for e in entities:
        if isinstance(e, dict) and e.get("canonical_name"):
            all_top_entities.append(e)

    # Limit to top 35 most referenced entities to keep graph responsive & clear
    all_top_entities = sorted(all_top_entities, key=lambda x: x.get("paper_count", 1), reverse=True)[:35]

    for e_idx, e in enumerate(all_top_entities):
        e_type = e.get("entity_type", "entity")
        e_name = e.get("canonical_name")
        e_id = f"entity-{_slugify(f'{e_type}-{e_name}')}"
        
        connected_docs = entity_paper_map.get(e.get("entity_id"), set())
        if connected_docs and len(connected_docs) == 1:
            doc_id = list(connected_docs)[0]
            cx, cy = paper_coords.get(doc_id, (0, 0))
            offset_angle = (2 * math.pi * e_idx) / max(len(all_top_entities), 1)
            ex = cx + 180 * math.cos(offset_angle)
            ey = cy + 180 * math.sin(offset_angle)
        else:
            angle = (2 * math.pi * e_idx) / max(len(all_top_entities), 1)
            ex = (paper_radius + 320) * math.cos(angle)
            ey = (paper_radius + 320) * math.sin(angle)

        entity_node_data = {
            "canonical_name": e_name,
            "entity_type": e_type,
            "paper_count": e.get("paper_count", 1),
            "connected_papers": [paper_titles.get(pid, "Paper") for pid in connected_docs if pid in paper_titles],
        }
        if e_type == "dataset":
            entity_node_data["associated_models"] = list(dataset_models.get(e_name, set()))
            entity_node_data["associated_methods"] = list(dataset_methods.get(e_name, set()))
        elif e_type in ("model", "algorithm"):
            entity_node_data["associated_datasets"] = list(model_datasets.get(e_name, set()))
            entity_node_data["associated_topics"] = list(model_topics.get(e_name, set()))

        add_node(
            node_id=e_id,
            node_type=e_type,
            label=e_name,
            data=entity_node_data,
            x=ex,
            y=ey
        )

    # Connect relationships
    for rel in relationships:
        doc_id = rel.get("document_id")
        p_node_id = f"paper-{doc_id}"
        e_type = rel.get("entity_type")
        e_name = rel.get("entity_name")
        predicate = rel.get("predicate", "uses")

        if e_type and e_name:
            e_node_id = f"entity-{_slugify(f'{e_type}-{e_name}')}"
            if e_node_id in node_ids:
                add_edge(p_node_id, e_node_id, predicate, predicate.replace("_", " "))

    # --- 5. Key Concept Nodes (KeyBERT Keyphrases) ---
    for c_idx, c in enumerate(top_concepts[:15]):
        phrase = c["phrase"]
        c_node_id = f"concept-{_slugify(phrase)}"
        angle = (2 * math.pi * c_idx) / max(len(top_concepts[:15]), 1) + 1.2
        cx = (paper_radius + 170) * math.cos(angle)
        cy = (paper_radius + 170) * math.sin(angle)
        add_node(
            node_id=c_node_id,
            node_type="concept",
            label=phrase,
            data={"phrase": phrase, "paper_count": c.get("paper_count", 1), "avg_score": c.get("avg_score")},
            x=cx,
            y=cy
        )

    for kp in keyphrase_rows:
        c_node_id = f"concept-{_slugify(kp['phrase'])}"
        p_node_id = f"paper-{kp['document_id']}"
        if c_node_id in node_ids and p_node_id in node_ids:
            add_edge(p_node_id, c_node_id, "discusses", "discusses")

    # --- 6. Research Gap / Limitation Nodes ---
    for l_idx, lim in enumerate(limitations[:15]):
        lim_id = f"gap-{lim.get('id') or l_idx}"
        doc_id = lim.get("document_id")
        cx, cy = paper_coords.get(doc_id, (0, 0))
        angle = (2 * math.pi * l_idx) / max(len(limitations[:15]), 1) + 0.8
        gx = cx + 220 * math.cos(angle)
        gy = cy + 220 * math.sin(angle)
        
        lim_text = lim.get("limitation_text", "")
        short_label = (lim_text[:35] + "…") if len(lim_text) > 35 else lim_text
        doc_topic = paper_assigned_topics.get(doc_id, ["General"])[0] if paper_assigned_topics.get(doc_id) else "Research"
        add_node(
            node_id=lim_id,
            node_type="gap",
            label=short_label,
            data={
                "description": lim_text,
                "category": lim.get("category", "other"),
                "evidence_text": lim.get("evidence_text", ""),
                "document_id": str(doc_id) if doc_id else None,
                "source_paper_title": paper_titles.get(doc_id, "Unknown Paper"),
                "associated_topic": doc_topic,
                "potential_directions": f"Address {lim.get('category', 'methodological')} constraints through benchmark validation and cross-dataset testing.",
            },
            x=gx,
            y=gy
        )
        if doc_id:
            add_edge(f"paper-{doc_id}", lim_id, "has_limitation", "identifies gap")

    # --- 7. Key Findings / Claim Nodes ---
    for f_idx, claim in enumerate(claims[:12]):
        claim_id = f"claim-{claim.get('id') or f_idx}"
        doc_id = claim.get("document_id")
        cx, cy = paper_coords.get(doc_id, (0, 0))
        angle = (2 * math.pi * f_idx) / max(len(claims[:12]), 1) - 0.5
        fx = cx + 210 * math.cos(angle)
        fy = cy + 210 * math.sin(angle)

        c_text = claim.get("claim_text", "")
        short_label = (c_text[:35] + "…") if len(c_text) > 35 else c_text
        add_node(
            node_id=claim_id,
            node_type="finding",
            label=short_label,
            data={
                "claim_text": c_text,
                "claim_type": claim.get("claim_type", "finding"),
                "evidence_text": claim.get("evidence_text", ""),
                "document_id": str(doc_id) if doc_id else None,
                "source_paper_title": paper_titles.get(doc_id, "Unknown Paper"),
            },
            x=fx,
            y=fy
        )
        if doc_id:
            add_edge(f"paper-{doc_id}", claim_id, "reports", "reports")

    # --- 8. Research Question Nodes ---
    rq_count = 0
    for rq_row in rq_rows:
        raw_qs = rq_row.get("questions")
        if isinstance(raw_qs, str):
            import json
            try:
                raw_qs = json.loads(raw_qs)
            except Exception:
                raw_qs = []
        if isinstance(raw_qs, list):
            for q_idx, q_item in enumerate(raw_qs):
                if isinstance(q_item, dict) and q_item.get("question"):
                    rq_count += 1
                    q_id = f"rq-{rq_row['id']}-{q_idx}"
                    q_text = q_item["question"]
                    short_q = (q_text[:35] + "…") if len(q_text) > 35 else q_text
                    rx = -360 + (rq_count * 70)
                    ry = 340
                    add_node(
                        node_id=q_id,
                        node_type="question",
                        label=short_q,
                        data={
                            "question": q_text,
                            "rationale": q_item.get("rationale", ""),
                            "gap_addressed": q_item.get("gap_addressed", "")
                        },
                        x=rx,
                        y=ry
                    )
                    # Link to first paper or matching gap
                    if doc_rows:
                        add_edge(f"paper-{doc_rows[0]['id']}", q_id, "addresses", "addresses")

    # --- 9. Shared Entity / Inter-Paper Edges ---
    # Connect papers that share significant entities
    paper_entity_sets = defaultdict(set)
    for rel in relationships:
        e_name = rel.get("entity_name")
        d_id = rel.get("document_id")
        if e_name and d_id:
            paper_entity_sets[d_id].add(e_name)

    doc_id_list = list(paper_coords.keys())
    for i in range(len(doc_id_list)):
        for j in range(i + 1, len(doc_id_list)):
            d1 = doc_id_list[i]
            d2 = doc_id_list[j]
            shared = paper_entity_sets[d1].intersection(paper_entity_sets[d2])
            if shared:
                add_edge(
                    f"paper-{d1}",
                    f"paper-{d2}",
                    "related_to",
                    f"shares {len(shared)} entities",
                    {"shared_entities": list(shared)}
                )

    return {
        "project_id": str(project_id),
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": dict(node_type_counts),
        }
    }


GRAPH_AI_SYSTEM_PROMPT = """You are the Research Nexus Knowledge Graph AI Analyst.

You analyze research landscapes based on the provided Graph Topology:
- Nodes (papers, topics, authors, models, datasets, methodologies, metrics, concepts, findings, and research gaps)
- Edges (predicates connecting these entities)

Rules:
1. Answer strictly using the entities, relationships, and connections from the supplied Knowledge Graph context.
2. Explicitly name the connected nodes (papers, datasets, methods, etc.) and explain how they relate.
3. If a connection is not present in the graph data, clearly state that it is not present in the current knowledge graph.
4. Keep the answer structured, insightful, and directly relevant to the researcher's query.
"""


async def query_knowledge_graph(project_id: UUID, question: str, focused_node_ids: list[str] | None = None) -> dict:
    """
    Answers questions grounded directly in the project's knowledge graph topology.
    """
    graph_data = await build_project_knowledge_graph(project_id)
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    if not nodes:
        return {
            "question": question,
            "answer": "The project knowledge graph does not contain any indexed papers or extracted entities yet. Run 'Analyze All Papers' first to populate the graph.",
            "relevant_nodes": []
        }

    # Filter or highlight relevant sub-network from question terms
    q_words = [re.sub(r"\W+", "", w).lower() for w in question.split()]
    q_terms = [w for w in q_words if len(w) >= 3]
    relevant_node_map = {}

    for n in nodes:
        label = n.get("label", "").lower()
        ntype = n.get("type", "").lower()
        matched = False
        for term in q_terms:
            if term in label or term in ntype or (len(ntype) >= 3 and ntype in term):
                matched = True
                break
        if matched:
            relevant_node_map[n["id"]] = n

    if focused_node_ids:
        for n in nodes:
            if n["id"] in set(focused_node_ids):
                relevant_node_map[n["id"]] = n

    # Format graph topology context for LLM
    context_lines = [
        f"Knowledge Graph Overview: {len(nodes)} nodes, {len(edges)} edges across the project.",
        "\nKey Entities in Graph:"
    ]

    # Summarize nodes by type
    by_type = defaultdict(list)
    for n in nodes:
        by_type[n["type"]].append(n["label"])

    for ntype, labels in by_type.items():
        sample = ", ".join(labels[:10])
        context_lines.append(f"- {ntype.upper()} ({len(labels)}): {sample}")

    context_lines.append("\nKey Relationships (Edges):")
    for e in edges[:40]:
        context_lines.append(f"- [{e.get('predicate')}] {e.get('source')} ──> {e.get('target')} ({e.get('label')})")

    context_text = "\n".join(context_lines)

    user_prompt = (
        f"Knowledge Graph Context:\n{context_text}\n\n"
        f"Researcher Question: {question}\n\n"
        "Provide an analytical, grounded answer synthesizing the nodes, connections, and research landscape."
    )

    provider = get_llm_provider()
    try:
        answer_text = provider.generate(GRAPH_AI_SYSTEM_PROMPT, user_prompt)
    except Exception as exc:
        logger.warning("LLM generation for graph query failed: %s", exc)
        answer_text = (
            "Based on the Knowledge Graph data:\n\n"
            f"- Extracted {len(nodes)} entities across {len(edges)} verified relationships.\n"
            f"- Available models/datasets/methods: {', '.join(by_type.get('model', []) + by_type.get('dataset', []))}\n"
            f"- Key topics: {', '.join(by_type.get('topic', []))}"
        )

    # Highlight any nodes explicitly mentioned in the generated answer as well
    ans_lower = answer_text.lower()
    for n in nodes:
        lbl = n.get("label", "").lower()
        if len(lbl) >= 3 and lbl in ans_lower:
            relevant_node_map[n["id"]] = n

    return {
        "question": question,
        "answer": answer_text,
        "stats": graph_data.get("stats"),
        "relevant_nodes": list(relevant_node_map.keys())[:20]
    }
