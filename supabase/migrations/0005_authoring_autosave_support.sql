-- Research Nexus — Phase 4: Authoring Auto-Save & Chat History Support
-- Migration 0005: Update research_analysis constraint and create chat_history table in Supabase PostgreSQL

-- 1. Relax check constraint on research_analysis to allow authoring section types and project chat history
ALTER TABLE research_analysis DROP CONSTRAINT IF EXISTS research_analysis_analysis_type_check;

ALTER TABLE research_analysis ADD CONSTRAINT research_analysis_analysis_type_check
CHECK (analysis_type IN (
    'literature_matrix_row',
    'comparison',
    'gap_analysis',
    'authoring_abstract',
    'authoring_introduction',
    'authoring_related_work',
    'authoring_methodology_comparison',
    'authoring_research_gaps',
    'authoring_conclusion',
    'authoring',
    'project_chat'
));

-- 2. Project Chat History Table for permanent Q&A persistence
CREATE TABLE IF NOT EXISTS project_chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_chat_history_project_id 
    ON project_chat_history (project_id, created_at DESC);
