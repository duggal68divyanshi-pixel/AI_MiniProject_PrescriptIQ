# Changelog

All notable changes to Research Nexus are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Phase 5] — OCR & Paper Photo Ingestion Pipeline

### Added
- **`backend/app/services/ingestion_service.py`** — Common document ingestion abstraction for native PDFs, scanned PDFs, single paper photos, and multi-photo batches.
- **`backend/app/services/ocr_preprocessor.py`** — Image resolution normalization, EXIF auto-rotation, grayscale conversion, CLAHE adaptive contrast enhancement, and deskewing.
- **`backend/app/services/ocr_processor.py`** — Level 1 Local OCR (Tesseract / PyMuPDF), quality & confidence evaluation heuristics, Level 2 Vision-LLM fallback, and layout block extraction.
- **`backend/app/services/vision_ocr_provider.py`** — Modular Vision-Language Model OCR provider interface supporting Anthropic Claude 3.5 Sonnet, OpenAI GPT-4o Vision, and Mock Vision provider.
- **`supabase/migrations/0006_ocr_paper_photo_support.sql`** — Database migration creating `document_pages` table and adding `document_source_type` column to `documents`.
- **`frontend/src/components/MultiPhotoUploadModal.jsx`** — Interactive multi-page paper photo batch reordering, preview, deletion, and upload modal.
- **`frontend/src/components/OcrVerificationModal.jsx`** — Split-view OCR text inspection modal showing original page image vs. extracted text, OCR engine switcher, and text editor.
- **`backend/tests/test_ocr_ingestion.py`** — Comprehensive pytest suite for OCR, image preprocessing, and photo ingestion.

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
