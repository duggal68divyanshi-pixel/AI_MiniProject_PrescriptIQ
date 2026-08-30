-- Research Nexus — Phase 2: Literature Intelligence
-- Migration 0002: research_projects, paper_metadata, research_analysis,
-- research_questions, and a project_id link on the existing `documents`
-- table.
--
-- This migration is purely additive. Every Phase 1 table, column, and
-- index is left untouched, so single-document upload/search/chat keeps
-- working exactly as before for documents that are never added to a
-- project (project_id stays NULL).
--
-- Run via `psql $DATABASE_URL -f supabase/migrations/0002_phase2_literature_intelligence.sql`
-- or paste into the Supabase SQL editor, after 0001 has already been run.

-- 1. research_projects
create table if not exists research_projects (
    id           uuid primary key default gen_random_uuid(),
    name         text not null,
    description  text,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

drop trigger if exists trg_research_projects_updated_at on research_projects;
create trigger trg_research_projects_updated_at
    before update on research_projects
    for each row
    execute function set_updated_at();

-- 2. Link documents to a project. Nullable and ON DELETE SET NULL so a
-- document never becomes orphaned/broken if its project is deleted — it
-- simply reverts to being a standalone Phase 1 document.
alter table documents
    add column if not exists project_id uuid references research_projects (id) on delete set null;

create index if not exists idx_documents_project_id on documents (project_id);

-- 3. paper_metadata — structured bibliographic fields extracted (best
-- effort, via LLM) once a paper finishes indexing. Anything that cannot
-- be reliably extracted is stored as NULL rather than guessed, and
-- extraction_status records whether extraction actually succeeded so the
-- frontend can show "unknown" instead of implying a confident answer.
create table if not exists paper_metadata (
    document_id        uuid primary key references documents (id) on delete cascade,
    title              text,
    authors            text[],
    publication_year   integer,
    abstract           text,
    keywords           text[],
    extraction_status  text not null default 'pending'
                       check (extraction_status in ('pending', 'extracted', 'failed', 'unavailable')),
    extraction_error   text,
    extracted_at       timestamptz
);

-- 4. research_analysis — cache for expensive, project-scoped analyses
-- (literature matrix rows, paper comparisons, gap analysis). Keyed by the
-- exact set of document ids that were analyzed (`document_ids`), so a
-- cached result is only reused when the project's indexed papers haven't
-- changed (see services/analysis_cache.py). `analysis_type` distinguishes
-- the different pipelines that write into this one table.
create table if not exists research_analysis (
    id             uuid primary key default gen_random_uuid(),
    project_id     uuid not null references research_projects (id) on delete cascade,
    analysis_type  text not null
                   check (analysis_type in ('literature_matrix_row', 'comparison', 'gap_analysis')),
    document_ids   uuid[] not null,
    content        jsonb not null,
    created_at     timestamptz not null default now()
);

create index if not exists idx_research_analysis_project_type
    on research_analysis (project_id, analysis_type);

-- 5. research_questions — potential RQs generated from a specific
-- gap-analysis result. Linked back to the research_analysis row that
-- produced them so the UI can show "generated from this gap analysis".
create table if not exists research_questions (
    id                 uuid primary key default gen_random_uuid(),
    project_id         uuid not null references research_projects (id) on delete cascade,
    gap_analysis_id    uuid references research_analysis (id) on delete cascade,
    questions          jsonb not null,
    created_at         timestamptz not null default now()
);

create index if not exists idx_research_questions_project on research_questions (project_id);

-- 6. Convenience view: project summary counts, useful for debugging from
-- the SQL editor and mirrors what GET /api/projects returns.
create or replace view v_project_overview as
select
    p.id,
    p.name,
    count(d.id) filter (where d.id is not null) as document_count,
    count(d.id) filter (where d.status = 'indexed') as indexed_count,
    p.created_at
from research_projects p
left join documents d on d.project_id = p.id
group by p.id, p.name, p.created_at
order by p.created_at desc;
