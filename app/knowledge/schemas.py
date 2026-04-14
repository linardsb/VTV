"""Pydantic schemas for knowledge base feature."""

import json
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

# KB-5: fixed vocabulary of entity types extracted from documents/queries.
EntityType = Literal["route", "stop", "regulation", "person", "org"]
ExtractionMethod = Literal["regex", "gazetteer", "spacy"]


class DocumentUpload(BaseModel):
    """Schema for document upload metadata (sent alongside file)."""

    domain: str = Field(..., min_length=1, max_length=50, description="Knowledge domain")
    language: str = Field(default="lv", pattern="^(lv|en)$", description="Document language")
    metadata_json: str | None = Field(None, description="Optional JSON metadata string")
    title: str | None = Field(None, max_length=200, description="Human-readable document title")
    description: str | None = Field(None, description="Optional document description")
    evergreen: bool = Field(default=False, description="Mark as evergreen to skip temporal decay")

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
    evergreen: bool | None = None

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> Self:
        """Reject empty PATCH bodies that would cause unnecessary DB round-trips."""
        if not any(v is not None for v in self.model_dump(exclude_unset=True).values()):
            raise ValueError("At least one field must be provided for update")
        return self


class TagCreate(BaseModel):
    """Schema for creating a new tag."""

    name: str = Field(..., min_length=1, max_length=100, description="Tag name")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """Strip whitespace and lowercase tag names for consistency."""
        return v.strip().lower()


class TagResponse(BaseModel):
    """Schema for tag responses."""

    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TagListResponse(BaseModel):
    """Schema for listing all tags."""

    tags: list[TagResponse]
    total: int


class DocumentTagRequest(BaseModel):
    """Schema for adding tags to a document."""

    tag_ids: list[int] = Field(..., min_length=1, max_length=20, description="Tag IDs to assign")


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
    ocr_applied: bool
    evergreen: bool
    tags: list[TagResponse] = []
    # KB-3: version tracking. Defaults keep legacy constructors working — the
    # ORM populates concrete values via ``from_attributes``.
    version: int = 1
    is_latest: bool = True
    parent_document_id: int | None = None
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
    domain: str | None = Field(default=None, description="Filter by domain")
    language: str | None = Field(default=None, description="Filter by language")
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return")
    created_after: datetime | None = Field(
        default=None, description="Filter documents created after this timestamp"
    )
    created_before: datetime | None = Field(
        default=None, description="Filter documents created before this timestamp"
    )
    include_superseded: bool = Field(
        default=False,
        description="Include superseded document versions in the search (KB-3).",
    )


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
    document_created_at: datetime

    # Parent-child retrieval (AI-4.3) — populated when the matched chunk
    # has a parent section and parent context expansion is enabled.
    parent_chunk_id: int | None = None
    parent_content: str | None = None
    heading_path: str | None = None

    # KB-3: version metadata for the source document.
    version: int = 1
    is_latest: bool = True

    # KB-5: canonical entity names mentioned in this chunk, populated after
    # the final top-K is selected. ``None`` when extraction is disabled or
    # the chunk has no recorded mentions.
    entities: list[str] | None = Field(
        default=None, description="Canonical entity names mentioned in this chunk"
    )


class ExtractedEntity(BaseModel):
    """A single entity extracted from text (KB-5).

    Non-ORM DTO passed between the extractor, repository upsert path, and
    service ingest/search loops.
    """

    entity_type: EntityType
    name: str = Field(max_length=500)
    normalized_name: str = Field(max_length=500)
    extraction_method: ExtractionMethod
    mention_count: int = Field(default=1, ge=1)


class SearchResponse(BaseModel):
    """Search response with results and metadata."""

    results: list[SearchResult]
    query: str
    total_candidates: int
    reranked: bool


class DocumentVersionItem(BaseModel):
    """One entry in a document's version history (KB-3)."""

    id: int
    version: int
    status: str
    is_latest: bool
    parent_document_id: int | None
    filename: str
    file_size_bytes: int | None
    chunk_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDiffResponse(BaseModel):
    """Unified-diff representation between two document versions (KB-3)."""

    document_id: int
    v1: int
    v2: int
    v1_document_id: int
    v2_document_id: int
    unified_diff: str
    lines_added: int
    lines_removed: int
