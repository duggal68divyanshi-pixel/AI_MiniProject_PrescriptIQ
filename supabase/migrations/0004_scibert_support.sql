-- Migration 0004: Support SciBERT & SPECTER 768-dimension scientific embeddings
--
-- Run this in the Supabase SQL Editor if switching EMBEDDING_MODEL_NAME to SciBERT
-- (e.g. sentence-transformers/allenai-scibert_scivocab_uncased) or SPECTER.

-- Convert embedding column to flexible vector type (supports 384 and 768 dimensions)
ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector;
