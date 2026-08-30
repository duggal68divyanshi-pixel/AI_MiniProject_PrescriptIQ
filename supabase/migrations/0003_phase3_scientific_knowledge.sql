-- Research Nexus — Phase 3: Scientific Knowledge Extraction
-- Migration 0003: paper_sections, scientific_entities, paper_entities,
-- paper_keyphrases, project_topics, paper_topic_assignments,
-- scientific_claims, paper_limitations, paper_relationships,
-- processing_jobs.
--
-- Purely additive — every Phase 1 and Phase 2 table, column and index is
-- left untouched. A document/project that never runs Phase 3 analysis
-- behaves exactly as it did before this migration.
--
-- Run via `psql $DATABASE_URL -f supabase/migrations/0003_phase3_scientific_knowledge.sql`
-- after 0001 and 0002 have already been run.

-- ---------------------------------------------------------------------
-- 1. paper_sections — scientific section structure of a document
-- ---------------------------------------------------------------------
create table if not exists paper_sections (
    id              uuid primary key default gen_random_uuid(),
    document_id     uuid not null references documents (id) on delete cascade,
    section_label   text not null
                    check (section_label in (
                        'title','abstract','introduction','related_work','methodology',
                        'dataset','experiments','results','discussion','conclusion',
                        'limitations','future_work','references','other'
                    )),
    heading_text    text,             -- the raw heading text as it appeared, if any
    start_chunk_index integer not null,
    end_chunk_index   integer not null,
    page_start      integer,
    page_end        integer,
    detection_method text not null    -- 'heading_pattern' | 'embedding_similarity' | 'fallback'
                    check (detection_method in ('heading_pattern','embedding_similarity','fallback')),
    confidence      real,             -- null when detection_method = 'heading_pattern' (deterministic)
    created_at      timestamptz not null default now()
);

create index if not exists idx_paper_sections_document on paper_sections (document_id);
create index if not exists idx_paper_sections_label on paper_sections (document_id, section_label);

-- ---------------------------------------------------------------------
-- 2. scientific_entities — the canonical/global dictionary of entities
--    (one row per distinct normalized entity, e.g. "SciBERT" once, ever)
-- ---------------------------------------------------------------------
create table if not exists scientific_entities (
    id              uuid primary key default gen_random_uuid(),
    entity_type     text not null
                    check (entity_type in ('model','dataset','method','metric','domain','task')),
    canonical_name  text not null,
    aliases         text[] not null default '{}',
    created_at      timestamptz not null default now(),
    unique (entity_type, canonical_name)
);

create index if not exists idx_scientific_entities_type on scientific_entities (entity_type);

-- ---------------------------------------------------------------------
-- 3. paper_entities — a specific mention of an entity in a specific
--    paper, with full provenance back to the source chunk
-- ---------------------------------------------------------------------
create table if not exists paper_entities (
    id              uuid primary key default gen_random_uuid(),
    document_id     uuid not null references documents (id) on delete cascade,
    entity_id       uuid not null references scientific_entities (id) on delete cascade,
    chunk_id        uuid references document_chunks (id) on delete set null,
    section_label   text,
    page_number     integer,
    mention_text    text not null,     -- the exact surface text that matched
    source_excerpt  text not null,     -- surrounding sentence for human review
    extraction_method text not null    -- 'gazetteer_match' | 'spacy_candidate' | 'llm_normalized'
                    check (extraction_method in ('gazetteer_match','spacy_candidate','llm_normalized')),
    confidence      real,              -- fuzzy-match score in [0,1], or null if not applicable
    created_at      timestamptz not null default now()
);

create index if not exists idx_paper_entities_document on paper_entities (document_id);
create index if not exists idx_paper_entities_entity on paper_entities (entity_id);

-- ---------------------------------------------------------------------
-- 4. paper_keyphrases — KeyBERT-extracted keyphrases per document
-- ---------------------------------------------------------------------
create table if not exists paper_keyphrases (
    id              uuid primary key default gen_random_uuid(),
    document_id     uuid not null references documents (id) on delete cascade,
    phrase          text not null,
    score           real not null,     -- cosine similarity of phrase embedding to document embedding
    rank            integer not null,
    created_at      timestamptz not null default now(),
    unique (document_id, phrase)
);

create index if not exists idx_paper_keyphrases_document on paper_keyphrases (document_id, rank);

-- ---------------------------------------------------------------------
-- 5. project_topics — BERTopic-discovered topics, scoped to one project
--    (topics are re-discovered per project rather than globally, since a
--    topic model is only meaningful over a coherent corpus)
-- ---------------------------------------------------------------------
create table if not exists project_topics (
    id              uuid primary key default gen_random_uuid(),
    project_id      uuid not null references research_projects (id) on delete cascade,
    topic_index     integer not null,   -- BERTopic's internal topic id (-1 = outlier, never stored)
    label           text not null,      -- human-readable label built from top keywords
    keywords        text[] not null,
    document_count  integer not null,
    model_run_id    uuid not null,      -- groups all topics from one discovery run, for cache invalidation
    created_at      timestamptz not null default now()
);

create index if not exists idx_project_topics_project on project_topics (project_id, model_run_id);

-- ---------------------------------------------------------------------
-- 6. paper_topic_assignments — which paper belongs to which discovered
--    topic (a paper's dominant topic; BERTopic assigns one topic per doc
--    at the granularity we run it at — whole-abstract/whole-paper text)
-- ---------------------------------------------------------------------
create table if not exists paper_topic_assignments (
    id              uuid primary key default gen_random_uuid(),
    document_id     uuid not null references documents (id) on delete cascade,
    topic_id        uuid not null references project_topics (id) on delete cascade,
    probability     real,              -- BERTopic's topic-assignment probability, if computed
    created_at      timestamptz not null default now(),
    unique (document_id, topic_id)
);

create index if not exists idx_paper_topic_assignments_document on paper_topic_assignments (document_id);

-- ---------------------------------------------------------------------
-- 7. scientific_claims — findings / contributions / results / conclusions
-- ---------------------------------------------------------------------
create table if not exists scientific_claims (
    id              uuid primary key default gen_random_uuid(),
    document_id     uuid not null references documents (id) on delete cascade,
    claim_type      text not null
                    check (claim_type in ('finding','contribution','result','observation','conclusion')),
    claim_text      text not null,      -- LLM-normalized, single-sentence statement
    evidence_text   text not null,      -- the original sentence(s) it was normalized from
    chunk_id        uuid references document_chunks (id) on delete set null,
    section_label   text,
    page_number     integer,
    created_at      timestamptz not null default now()
);

create index if not exists idx_scientific_claims_document on scientific_claims (document_id, claim_type);

-- ---------------------------------------------------------------------
-- 8. paper_limitations
-- ---------------------------------------------------------------------
create table if not exists paper_limitations (
    id              uuid primary key default gen_random_uuid(),
    document_id     uuid not null references documents (id) on delete cascade,
    limitation_text text not null,      -- LLM-normalized statement
    category        text not null default 'other'
                    check (category in (
                        'dataset','computational','generalization','evaluation',
                        'methodological','future_work','other'
                    )),
    evidence_text   text not null,
    chunk_id        uuid references document_chunks (id) on delete set null,
    section_label   text,
    page_number     integer,
    created_at      timestamptz not null default now()
);

create index if not exists idx_paper_limitations_document on paper_limitations (document_id);

-- ---------------------------------------------------------------------
-- 9. paper_relationships — the seed of the Research Nexus knowledge graph.
--    Stored relationally now; the (subject, predicate, object) shape maps
--    directly onto graph edges if this is ever migrated to a graph store.
-- ---------------------------------------------------------------------
create table if not exists paper_relationships (
    id                uuid primary key default gen_random_uuid(),
    document_id       uuid not null references documents (id) on delete cascade,
    predicate         text not null
                      check (predicate in (
                          'uses','proposes','evaluates_on','reports',
                          'has_limitation','extends'
                      )),
    object_type       text not null check (object_type in ('entity','claim','limitation','text')),
    object_entity_id  uuid references scientific_entities (id) on delete cascade,
    object_claim_id   uuid references scientific_claims (id) on delete cascade,
    object_limitation_id uuid references paper_limitations (id) on delete cascade,
    object_text       text,             -- used when object_type = 'text' (e.g. a free-text result value)
    confidence        real,
    created_at        timestamptz not null default now()
);

create index if not exists idx_paper_relationships_document on paper_relationships (document_id);
create index if not exists idx_paper_relationships_entity on paper_relationships (object_entity_id);

-- ---------------------------------------------------------------------
-- 10. processing_jobs — lightweight background-job tracking for Phase 3
--     extraction (no Celery/Redis; polled from the frontend the same way
--     document status already is)
-- ---------------------------------------------------------------------
create table if not exists processing_jobs (
    id              uuid primary key default gen_random_uuid(),
    job_type        text not null check (job_type in ('paper_intelligence', 'project_topics')),
    document_id     uuid references documents (id) on delete cascade,
    project_id      uuid references research_projects (id) on delete cascade,
    status          text not null default 'queued'
                    check (status in ('queued','running','completed','failed')),
    progress_stage  text,              -- e.g. 'sections', 'entities', 'keyphrases', 'claims', 'limitations', 'relationships'
    error_message   text,
    started_at      timestamptz,
    finished_at     timestamptz,
    created_at      timestamptz not null default now()
);

create index if not exists idx_processing_jobs_document on processing_jobs (document_id, created_at desc);
create index if not exists idx_processing_jobs_project on processing_jobs (project_id, created_at desc);

-- ---------------------------------------------------------------------
-- 11. Convenience views
-- ---------------------------------------------------------------------
create or replace view v_document_intelligence_status as
select
    d.id as document_id,
    d.filename,
    d.status as document_status,
    (select count(*) from paper_sections s where s.document_id = d.id) as section_count,
    (select count(*) from paper_entities e where e.document_id = d.id) as entity_mention_count,
    (select count(*) from scientific_claims c where c.document_id = d.id) as claim_count,
    (select count(*) from paper_limitations l where l.document_id = d.id) as limitation_count,
    (select status from processing_jobs j
       where j.document_id = d.id and j.job_type = 'paper_intelligence'
       order by j.created_at desc limit 1) as last_job_status
from documents d;
