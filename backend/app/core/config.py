"""
Central application configuration.

All configuration is environment-driven (12-factor style). Nothing here
should ever contain a real secret — only defaults safe to commit.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Database (Supabase Postgres, accessed directly via asyncpg) ---
    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    supabase_url: str = ""
    supabase_key: str = ""

    # --- Embeddings ---
    # Any sentence-transformers model works; dimension MUST match the
    # `embedding vector(N)` column defined in the migration.
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # --- LLM generation (provider-agnostic) ---
    # "anthropic" | "openai" | "mock"  (mock is for offline dev/testing only
    # and is clearly labeled as such in every response it produces)
    llm_provider: str = "anthropic"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 1024

    # --- Chunking ---
    chunk_size_tokens: int = 400
    chunk_overlap_tokens: int = 80

    # --- Retrieval ---
    retrieval_top_k: int = 5
    similarity_threshold: float = 0.2

    # --- Uploads ---
    max_upload_size_mb: int = 25
    upload_dir: str = "./uploads"

    # --- App ---
    cors_origins: str = "http://localhost:5173"
    environment: str = "development"

    # --- Phase 3: Scientific Knowledge Extraction ---
    # Device used for local ML inference (keyphrase/topic models sit on
    # top of the sentence-transformers embedding model, which honors this
    # too). "cpu" is the safe default — no GPU is assumed.
    ml_device: str = "cpu"

    # KeyBERT reuses the SAME embedding model as Phase 1 retrieval by
    # default (no extra model download). Set to a different
    # sentence-transformers model name to decouple them.
    keyphrase_model_name: str = ""  # "" = reuse embedding_model_name
    keyphrase_top_n: int = 10

    # BERTopic also reuses the shared embedding model by default.
    topic_model_name: str = ""  # "" = reuse embedding_model_name
    topic_min_topic_size: int = 2  # small default so demo-sized projects (5-10 papers) still form topics

    # Scientific entity extraction. The gazetteer path (curated
    # models/datasets/methods/metrics lists + fuzzy matching) always
    # runs and needs no extra download. spaCy noun-chunk candidate
    # generation is an optional second pass — disable it if spaCy /
    # en_core_web_sm isn't installed in this environment.
    enable_spacy_candidates: bool = True
    spacy_model_name: str = "en_core_web_sm"
    entity_fuzzy_match_threshold: float = 0.84  # rapidfuzz ratio, 0-1

    # Section classification: heading-pattern detection always runs first
    # (deterministic, free). Embedding-similarity classification is used
    # only as a fallback for text that doesn't match a heading pattern.
    enable_section_embedding_fallback: bool = True
    section_embedding_confidence_floor: float = 0.35

    # Claim/limitation extraction candidate shortlisting, before the LLM
    # normalization pass. Keeps the LLM call small and grounded instead
    # of summarizing the whole paper.
    max_claim_candidates_per_document: int = 12
    max_limitation_candidates_per_document: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def resolved_keyphrase_model_name(self) -> str:
        return self.keyphrase_model_name or self.embedding_model_name

    @property
    def resolved_topic_model_name(self) -> str:
        return self.topic_model_name or self.embedding_model_name

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
