-- Research Nexus — Research Intelligence Core
-- Migration 0001: documents + document_chunks with pgvector
--
-- Run this in the Supabase SQL Editor, or via `supabase db push` /
-- `psql $DATABASE_URL -f supabase/migrations/0001_init_research_core.sql`

-- 1. Enable pgvector
create extension if not exists vector;

-- 2. documents
create table if not exists documents (
    id           uuid primary key default gen_random_uuid(),
    filename     text not null,
    title        text,
    status       text not null default 'uploaded'
                 check (status in ('uploaded','extracting','chunking','embedding','indexed','failed')),
    page_count   integer,
    error_message text,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

create index if not exists idx_documents_status on documents (status);
create index if not exists idx_documents_created_at on documents (created_at desc);

-- 3. document_chunks
-- NOTE: vector(384) matches the default embedding model
-- (sentence-transformers/all-MiniLM-L6-v2). If you change
-- EMBEDDING_MODEL_NAME in .env, update this dimension to match and
-- re-run a fresh migration — pgvector requires a fixed dimension per column.
create table if not exists document_chunks (
    id            uuid primary key default gen_random_uuid(),
    document_id   uuid not null references documents (id) on delete cascade,
    chunk_index   integer not null,
    page_number   integer,
    content       text not null,
    embedding     vector(384) not null,
    created_at    timestamptz not null default now(),
    unique (document_id, chunk_index)
);

create index if not exists idx_chunks_document_id on document_chunks (document_id);

-- 4. Vector similarity index (cosine distance).
-- IVFFlat requires an estimate of row count for `lists`; 100 is a
-- reasonable default for a few thousand chunks and can be tuned later.
-- It also requires ANALYZE after data is loaded to be effective.
create index if not exists idx_chunks_embedding_cosine
    on document_chunks
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- 5. Keep documents.updated_at fresh automatically
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_documents_updated_at on documents;
create trigger trg_documents_updated_at
    before update on documents
    for each row
    execute function set_updated_at();

-- 6. Convenience view for debugging retrieval quality from the SQL editor
create or replace view v_chunk_overview as
select
    d.filename,
    d.status,
    c.chunk_index,
    c.page_number,
    left(c.content, 120) as content_preview
from document_chunks c
join documents d on d.id = c.document_id
order by d.created_at desc, c.chunk_index asc;
