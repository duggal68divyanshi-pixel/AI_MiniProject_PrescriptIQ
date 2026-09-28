"""Pydantic models shared across the API layer."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXED = "indexed"
    FAILED = "failed"


# ---------- Documents ----------

class DocumentOut(BaseModel):
    id: UUID
    filename: str
    title: str | None = None
    status: DocumentStatus
    page_count: int | None = None
    chunk_count: int | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    status: DocumentStatus
    message: str


# ---------- Search ----------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    document_id: UUID | None = Field(
        default=None, description="Optionally restrict search to one document"
    )
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_filename: str
    content: str
    page_number: int | None
    similarity: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]


# ---------- Chat / RAG ----------

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    document_id: UUID | None = Field(
        default=None, description="Optionally restrict retrieval to one document"
    )
    top_k: int = Field(default=5, ge=1, le=20)


class SourceReference(BaseModel):
    document: str
    document_id: UUID
    page: int | None
    chunk_id: UUID
    similarity: float
    excerpt: str


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceReference]
    grounded: bool = Field(
        description="False when no relevant chunks were retrieved and the "
        "model was told to say it doesn't know."
    )


# ---------- Phase 2: Research Projects ----------

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    document_count: int
    indexed_count: int
    created_at: datetime
    updated_at: datetime


class ProjectDocumentOut(DocumentOut):
    """A document as seen within a project — adds extracted metadata when available."""

    metadata: "PaperMetadataOut | None" = None


# ---------- Phase 2: Paper metadata ----------

class PaperMetadataOut(BaseModel):
    document_id: UUID
    title: str | None = None
    authors: list[str] | None = None
    publication_year: int | None = None
    abstract: str | None = None
    keywords: list[str] | None = None
    extraction_status: str
    extraction_error: str | None = None


# ---------- Phase 2: Project-scoped chat / synthesis ----------

class ProjectChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=30)


class ProjectChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceReference]
    papers_cited: list[str]
    grounded: bool


# ---------- Phase 2: Comparison ----------

class CompareRequest(BaseModel):
    document_ids: list[UUID] = Field(..., min_length=2, max_length=6)


class ComparisonDimension(BaseModel):
    dimension: str
    values: dict[str, str]  # document_id (str) -> value for that dimension


class ComparisonResponse(BaseModel):
    documents: list[DocumentOut]
    dimensions: list[ComparisonDimension]
    sources: list[SourceReference]
    cached: bool


# ---------- Phase 2: Literature matrix ----------

class LiteratureMatrixRow(BaseModel):
    document_id: UUID
    filename: str
    title: str | None
    authors: list[str] | None
    publication_year: int | None
    research_problem: str
    methodology: str
    model_or_algorithm: str
    dataset: str
    evaluation_metrics: str
    key_results: str
    contributions: str
    limitations: str
    sources: list[SourceReference]


class LiteratureMatrixResponse(BaseModel):
    project_id: UUID
    rows: list[LiteratureMatrixRow]
    skipped: list[dict]  # documents that couldn't be analyzed, with a reason
    cached: bool


# ---------- Phase 2: Gap analysis ----------

class ResearchGap(BaseModel):
    id: str
    gap: str
    category: str  # repeated_limitation | underexplored_area | methodological | dataset | evaluation | contradiction
    evidence: list[SourceReference]
    affected_papers: list[str]
    why_it_matters: str
    potential_direction: str
    evidence_strength: str  # High | Medium | Low


class GapAnalysisRequest(BaseModel):
    force_refresh: bool = False


class GapAnalysisResponse(BaseModel):
    project_id: UUID
    gaps: list[ResearchGap]
    papers_analyzed: int
    cached: bool
    analysis_id: UUID


# ---------- Phase 2: Research questions ----------

class AuthoringRequest(BaseModel):
    section_type: str = "related_work"  # abstract | introduction | related_work | methodology_comparison | research_gaps | conclusion
    custom_instructions: str | None = None
    force_refresh: bool = False


class AuthoringResponse(BaseModel):
    project_id: UUID
    section_type: str
    content: str
    papers_analyzed: int

class ResearchQuestionSet(BaseModel):
    gap_id: str
    gap: str
    questions: list[str]


class ResearchQuestionsRequest(BaseModel):
    force_refresh: bool = False


class ResearchQuestionsResponse(BaseModel):
    project_id: UUID
    question_sets: list[ResearchQuestionSet]
    cached: bool


# ---------- Phase 2: Analytics ----------

class YearCount(BaseModel):
    year: int
    count: int


class AnalyticsResponse(BaseModel):
    project_id: UUID
    paper_count: int
    metadata_extracted_count: int
    years: list[YearCount]
    common_methods: list[str]
    common_datasets: list[str]
    matrix_available: bool


# ---------- Phase 3: Scientific Knowledge Extraction ----------

class ProcessingJobOut(BaseModel):
    id: UUID
    job_type: str
    document_id: UUID | None = None
    project_id: UUID | None = None
    status: str
    progress_stage: str | None = None
    error_message: str | None = None
    created_at: datetime


class AnalyzeDocumentResponse(BaseModel):
    document_id: UUID
    job_id: UUID
    status: str
    message: str


class SectionOut(BaseModel):
    section_label: str
    heading_text: str | None
    start_chunk_index: int
    end_chunk_index: int
    page_start: int | None
    page_end: int | None
    detection_method: str
    confidence: float | None


class EntityMentionOut(BaseModel):
    entity_type: str
    canonical_name: str
    mention_text: str
    section_label: str | None
    page_number: int | None
    source_excerpt: str
    extraction_method: str
    confidence: float | None


class KeyphraseOut(BaseModel):
    phrase: str
    score: float
    rank: int


class ClaimOut(BaseModel):
    claim_type: str
    claim_text: str
    evidence_text: str
    section_label: str | None
    page_number: int | None


class LimitationOut(BaseModel):
    limitation_text: str
    category: str
    evidence_text: str
    section_label: str | None
    page_number: int | None


class RelationshipOut(BaseModel):
    predicate: str
    object_type: str
    entity_name: str | None = None
    entity_type: str | None = None
    claim_text: str | None = None
    limitation_text: str | None = None
    object_text: str | None = None
    confidence: float | None = None


class PaperIntelligenceResponse(BaseModel):
    document_id: UUID
    filename: str
    analysis_available: bool
    last_job_status: str | None
    sections: list[SectionOut]
    entities: list[EntityMentionOut]
    keyphrases: list[KeyphraseOut]
    claims: list[ClaimOut]
    limitations: list[LimitationOut]
    relationships: list[RelationshipOut]
    topics: list[dict]


class ProjectEntitySummary(BaseModel):
    entity_id: UUID
    entity_type: str
    canonical_name: str
    paper_count: int
    mention_count: int


class ProjectTopicOut(BaseModel):
    id: UUID
    topic_index: int
    label: str
    keywords: list[str]
    document_count: int


class ProjectKnowledgeResponse(BaseModel):
    project_id: UUID
    paper_count: int
    analyzed_count: int = 0
    top_models: list[dict]
    top_datasets: list[dict]
    top_methods: list[dict]
    top_metrics: list[dict]
    top_domains: list[dict]
    top_tasks: list[dict]
    top_concepts: list[dict]
    topics: list[dict]
    common_limitations: list[dict]
    key_findings: list[dict]
    top_relationships: list[dict] = []



class EntityDetailResponse(BaseModel):
    entity: dict
    mentions: list[dict]


class TopicDetailResponse(BaseModel):
    topic: dict
    papers: list[dict]


class ProjectAnalyzeRequest(BaseModel):
    include_topics: bool = True


class ProjectAnalyzeResponse(BaseModel):
    project_id: UUID
    jobs: list[ProcessingJobOut]
    topics_job_id: UUID | None = None
    message: str


class MLModelInfoOut(BaseModel):
    task: str
    library: str
    model_name: str
    repository: str
    license: str
    runs_locally: bool
    replaces_handcrafted: str
    available: bool
    notes: str = ""


# ---------- Health ----------

class HealthResponse(BaseModel):
    status: str
    database: bool
    embedding_model: str
    llm_provider: str


# ---------- Literature Discovery ----------

class DiscoveredPaperItem(BaseModel):
    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    publication_year: int | None = None
    venue: str | None = None
    doi: str | None = None
    citation_count: int | None = None
    source: str
    paper_url: str | None = None
    pdf_url: str | None = None


class DiscoverySearchResponse(BaseModel):
    query: str
    source: str
    total_results: int
    papers: list[DiscoveredPaperItem]


class ImportDiscoveredPaperRequest(BaseModel):
    title: str
    pdf_url: str | None = None
    paper_url: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    publication_year: int | None = None
    venue: str | None = None
    doi: str | None = None
    source: str | None = None

