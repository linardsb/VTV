"""Pydantic schemas for knowledge base feature."""

import json
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


class DocumentUpload(BaseModel):
    """Schema for document upload metadata (sent alongside file)."""

    domain: str = Field(..., min_length=1, max_length=50, description="Knowledge domain")
    language: str = Field(default="lv", pattern="^(lv|en)$", description="Document language")
    metadata_json: str | None = Field(None, description="Optional JSON metadata string")
    title: str | None = Field(None, max_length=200, description="Human-readable document title")
    description: str | None = Field(None, description="Optional document description")

    @field_validator("metadata_json")
    @classmethod
    def validate_metadata_json(cls, v: str | None) -> str | None:
        """Ensure metadata_json is valid JSON if provided."""
        if v is None:
            return v
        if len(v) > 10_000:
            raise ValueError("metadata_json must not exceed 10,000 characters")
        try:
            json.loads(v)
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"metadata_json must be valid JSON: {e}") from e
        return v


class DocumentUpdate(BaseModel):
    """Schema for updating document metadata (PATCH semantics)."""

    title: str | None = None
    description: str | None = None
    domain: str | None = Field(None, min_length=1, max_length=50)
    language: str | None = Field(None, pattern="^(lv|en)$")

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> Self:
        """Reject empty PATCH bodies that would cause unnecessary DB round-trips."""
        if not any(v is not None for v in self.model_dump(exclude_unset=True).values()):
            raise ValueError("At least one field must be provided for update")
        return self


class DocumentResponse(BaseModel):
    """Schema for document responses."""

    id: int
    filename: str
    title: str | None
    description: str | None
    domain: str
    source_type: str
    language: str
    file_size_bytes: int | None
    status: str
    error_message: str | None
    chunk_count: int
    metadata_json: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_file(self) -> bool:
        """Whether the original file is stored on disk."""
        return self.file_size_bytes is not None and self.file_size_bytes > 0


class DocumentChunkResponse(BaseModel):
    """Schema for a single document chunk."""

    chunk_index: int
    content: str

    model_config = ConfigDict(from_attributes=True)


class DocumentContentResponse(BaseModel):
    """Schema wrapping document metadata with its text chunks."""

    document_id: int
    filename: str
    title: str | None
    total_chunks: int
    chunks: list[DocumentChunkResponse]


class DomainListResponse(BaseModel):
    """Schema for listing unique knowledge domains."""

    domains: list[str]
    total: int


class SearchRequest(BaseModel):
    """Schema for knowledge base search."""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query text")
    domain: str | None = Field(None, description="Filter by domain")
    language: str | None = Field(None, description="Filter by language")
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return")


class SearchResult(BaseModel):
    """Single search result with relevance score."""

    chunk_content: str
    document_id: int
    document_filename: str
    domain: str
    language: str
    chunk_index: int
    score: float
    metadata_json: str | None


class SearchResponse(BaseModel):
    """Search response with results and metadata."""

    results: list[SearchResult]
    query: str
    total_candidates: int
    reranked: bool
