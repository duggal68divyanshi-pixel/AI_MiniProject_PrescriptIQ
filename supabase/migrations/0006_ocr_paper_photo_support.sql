-- Research Nexus — Phase 5: OCR & Paper Photo Processing Support
-- Migration 0006: document_pages table & document_source_type column

-- 1. Add document_source_type to documents table
alter table documents
    add column if not exists document_source_type text default 'native_pdf'
    check (document_source_type in ('native_pdf', 'scanned_pdf', 'single_photo', 'multi_photo'));

-- 2. Create document_pages table for page images, OCR metadata, and human verification
create table if not exists document_pages (
    id                  uuid primary key default gen_random_uuid(),
    document_id         uuid not null references documents (id) on delete cascade,
    page_number         integer not null,
    image_path          text,
    extracted_text      text,
    ocr_engine          text, -- 'tesseract' | 'fitz_native' | 'vision_llm' | 'easyocr' | 'mock'
    ocr_confidence      real, -- null when confidence cannot be calculated reliably
    ocr_status          text not null default 'pending'
                        check (ocr_status in ('pending', 'processing', 'completed', 'failed')),
    error_message       text,
    layout_blocks       jsonb default '[]'::jsonb,
    user_edited         boolean not null default false,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (document_id, page_number)
);

create index if not exists idx_document_pages_doc_page on document_pages (document_id, page_number);

-- 3. Trigger to keep document_pages.updated_at fresh
drop trigger if exists trg_document_pages_updated_at on document_pages;
create trigger trg_document_pages_updated_at
    before update on document_pages
    for each row
    execute function set_updated_at();
