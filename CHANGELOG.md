# Changelog

All notable changes to Research Nexus are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Phase 4] — Visual Research Knowledge Graph

### Added
- **`backend/app/services/knowledge_graph.py`** — New `KnowledgeGraphService`
  that dynamically constructs a typed, enriched knowledge graph payload from
  all project research data (entities, topics, claims, gaps, findings).
- **`backend/app/api/intelligence.py`** — Two new REST endpoints:
  - `GET /api/projects/{id}/knowledge-graph` — returns full graph (nodes, edges, stats)
  - `POST /api/projects/{id}/knowledge-graph/query` — LLM-grounded graph query
- **`backend/app/models/schemas.py`** — Extended Pydantic schemas:
  `GraphNode`, `GraphEdge`, `KnowledgeGraphResponse`, `GraphQueryRequest`,
  `GraphQueryResponse` with enriched metadata fields.
- **`backend/app/services/scientific_repository.py`** — New graph entity query methods:
  `get_graph_nodes()`, `get_graph_edges()`, `get_entity_metadata()`,
  `get_project_graph_summary()`.
- **`backend/app/services/project_chat.py`** — Graph topology injected into
  the LLM system prompt for graph-aware chat answers.
- **`backend/tests/test_knowledge_graph.py`** — Comprehensive test suite.
- **`frontend/src/components/projects/tabs/VisualKnowledgeGraph.jsx`** — New
  interactive React Flow graph tab with 6 node types, animated edges, query panel.
- **`frontend/src/services/api.js`** — Added graph API service methods.
- **`frontend/package.json`** — Added @xyflow/react v12 dependency.
- **`README.md`** — Full Phase 4 documentation.

---

## [Phase 3] — Scientific Knowledge Extraction

### Added
- Section detection, entity extraction, keyphrase/topic extraction
- Claim and limitation normalization via LLM
- Relationship derivation from section context
- New API: /analyze, /intelligence, /entities, /claims, /topics, /knowledge
- Paper Intelligence and Knowledge Explorer tabs
- Phase 3 Supabase migration

---

## [Phase 2] — Literature Intelligence

### Added
- Multi-paper research projects with cross-paper RAG chat
- Structured comparison, literature matrix, gap analysis, research questions
- Project analytics dashboard and analysis caching
- Phase 2 Supabase migration and full React project workspace

---

## [Phase 1] — Research Intelligence Core

### Added
- PDF upload, chunking, embedding, pgvector retrieval, RAG chat
- Anthropic / OpenAI / mock LLM provider interface
- Phase 1 Supabase migration and React frontend
