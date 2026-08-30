"""
Domain-level exceptions. Each maps to a specific HTTP status in main.py's
exception handlers, so route code can raise a meaningful, typed error
instead of leaking stack traces to the frontend.
"""


class ResearchNexusError(Exception):
    """Base class for all handled application errors."""

    status_code: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidFileTypeError(ResearchNexusError):
    status_code = 400
    default_message = "Only PDF files are supported."


class FileTooLargeError(ResearchNexusError):
    status_code = 413
    default_message = "The uploaded file exceeds the maximum allowed size."


class EmptyPDFError(ResearchNexusError):
    status_code = 422
    default_message = "No extractable text was found in this PDF (it may be a scanned image)."


class CorruptedPDFError(ResearchNexusError):
    status_code = 422
    default_message = "The PDF file appears to be corrupted or unreadable."


class DocumentNotFoundError(ResearchNexusError):
    status_code = 404
    default_message = "Document not found."


class EmbeddingGenerationError(ResearchNexusError):
    status_code = 502
    default_message = "Failed to generate embeddings."


class DatabaseConnectionError(ResearchNexusError):
    status_code = 503
    default_message = "Could not reach the database."


class MissingAPIKeyError(ResearchNexusError):
    status_code = 500
    default_message = "The LLM provider API key is not configured on the server."


class LLMGenerationError(ResearchNexusError):
    status_code = 502
    default_message = "The language model failed to generate a response."


class NoRelevantChunksError(ResearchNexusError):
    status_code = 200  # not a failure — a valid, answerable state
    default_message = "No relevant content was found for this question."


# ---------- Phase 2: research projects / literature intelligence ----------

class InsufficientPapersError(ResearchNexusError):
    status_code = 422
    default_message = "This operation needs more indexed papers in the project."


class AnalysisFailedError(ResearchNexusError):
    status_code = 502
    default_message = "Research analysis failed. Try again, or check the LLM provider configuration."


# ---------- Phase 3: scientific knowledge extraction ----------

class DocumentNotIndexedError(ResearchNexusError):
    status_code = 422
    default_message = "This document must finish Phase 1 indexing before scientific extraction can run."


class JobNotFoundError(ResearchNexusError):
    status_code = 404
    default_message = "Processing job not found."


class MLModelUnavailableError(ResearchNexusError):
    status_code = 503
    default_message = (
        "A required ML model/library is not installed in this environment. "
        "See README.md §Model download / setup."
    )
