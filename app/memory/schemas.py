"""Pydantic schemas for memory entry requests and responses."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryType = Literal["procedural", "episodic", "semantic", "query_pattern"]
MemorySource = Literal["agent", "dispatcher", "compaction"]


class MemoryEntryCreate(BaseModel):
    """Request schema for creating a memory entry."""

    agent_type: str = Field(max_length=50)
    memory_type: MemoryType
    content: str = Field(max_length=10000)
    embedding: list[float] | None = None
    metadata_json: dict[str, Any] | None = None
    decay_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    is_evergreen: bool = False
    source: MemorySource


class MemoryRecallRequest(BaseModel):
    """Request schema for recalling memories by similarity."""

    embedding: list[float] = Field(min_length=1024, max_length=1024)
    agent_type: str | None = Field(default=None, max_length=50)
    memory_type: MemoryType | None = None
    limit: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class MemoryEntryResponse(BaseModel):
    """Response schema for a memory entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_type: str
    memory_type: str
    content: str
    metadata_json: dict[str, Any] | None = None
    decay_weight: float
    is_evergreen: bool
    source: str
    recalled_count: int
    created_at: datetime
    updated_at: datetime


class MemoryRecallResponse(BaseModel):
    """Response schema for a recalled memory with similarity score."""

    memory: MemoryEntryResponse
    score: float = Field(description="Cosine similarity score (1.0 = identical)")


class MemoryRecallByQueryRequest(BaseModel):
    """Request schema for text-based memory recall (service embeds the query)."""

    query: str = Field(max_length=2000)
    agent_type: str | None = Field(default=None, max_length=50)
    memory_type: MemoryType | None = None
    limit: int = Field(default=5, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class CompactionResult(BaseModel):
    """Response for memory compaction operation."""

    decayed_deleted: int = Field(description="Entries below decay threshold removed")
    merged: int = Field(description="Pairs of similar entries merged")
    promoted: int = Field(description="Episodic entries promoted to procedural")


class PromotionResult(BaseModel):
    """Response for episodic-to-procedural promotion."""

    promoted: int = Field(description="Number of entries promoted")
