"""
Phase 3 ML service layer.

Every scientific-NLP capability (section classification, entity
extraction, keyphrase extraction, topic modeling, claim/limitation
extraction) is exposed here behind a small, stable function interface —
`services/scientific_extraction.py` (the pipeline orchestrator) only
imports from this package, never from `sentence_transformers`,
`keybert`, `bertopic`, `spacy`, or `rapidfuzz` directly.

This means any individual model is replaceable (task requirement 21)
without touching orchestration code, and every module here does its own
lazy loading + CPU fallback + clear error messages if an optional
dependency isn't installed (task requirement 24).
"""
