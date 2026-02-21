"""Feature-specific exceptions for knowledge base.

Inherits from core exceptions for automatic HTTP status code mapping:
- DocumentNotFoundError -> 404
- ProcessingError -> 500
- EmbeddingProviderError -> 500
- UnsupportedDocumentTypeError -> 500
"""

from app.core.exceptions import AppError, NotFoundError


class KnowledgeBaseError(AppError):
    """Base exception for knowledge base errors."""


class DocumentNotFoundError(NotFoundError):
    """Raised when a document is not found by ID."""


class ProcessingError(KnowledgeBaseError):
    """Raised when document extraction, chunking, or embedding fails."""


class EmbeddingProviderError(KnowledgeBaseError):
    """Raised when the embedding API or model fails."""


class UnsupportedDocumentTypeError(KnowledgeBaseError):
    """Raised for unknown file extensions."""
