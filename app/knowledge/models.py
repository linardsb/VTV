# pyright: reportUnknownMemberType=false
"""SQLAlchemy models for knowledge base documents and chunks."""

from datetime import datetime

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin, utcnow

# Many-to-many association table for document <-> tag relationships
document_tags = Table(
    "document_tags",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("document_id", "tag_id"),
)


class Document(Base, TimestampMixin):
    """Knowledge base document metadata.

    Tracks uploaded files with processing status. Each document
    is split into chunks for vector search after ingestion.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="lv")
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    evergreen: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # KB-3: version tracking. A re-upload of the same (title, domain) creates
    # a new row linked via ``parent_document_id``; the prior row is flipped
    # to ``status='superseded'`` and ``is_latest=False`` (chunks untouched —
    # no cascade).
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=sa.text("1")
    )
    parent_document_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_latest: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
        index=True,
    )


class Tag(Base, TimestampMixin):
    """Knowledge base document tag.

    Simple string labels for categorizing and filtering documents.
    Documents can have multiple tags via the document_tags association table.
    """

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)


class DocumentChunk(Base, TimestampMixin):
    """Document chunk with vector embedding for similarity search.

    Each chunk stores extracted text and its vector embedding.
    The embedding column uses pgvector's Vector type for cosine similarity search.

    Parent-child relationships (AI-4.2): a multi-paragraph section is stored
    as one ``parent`` chunk plus one ``child`` chunk per paragraph. Children
    reference their parent via ``parent_chunk_id`` so retrieval can return
    the surrounding section context when a paragraph matches.
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding = mapped_column(Vector(1024))
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_chunk_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    heading_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    section_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # KB-2: UDPipe-lemmatized form of ``content``. Populated for Latvian
    # documents so BM25 (`to_tsvector('simple', ...)`) matches inflected
    # forms. NULL for non-Latvian docs and legacy chunks; the repository
    # falls back to ``content`` via COALESCE.
    lemmatized_content: Mapped[str | None] = mapped_column(Text, nullable=True)


class Entity(Base, TimestampMixin):
    """Named entity extracted from document chunks (KB-5).

    Canonical entity row shared across all chunks that mention the same
    entity. The unique ``(entity_type, normalized_name)`` constraint is
    used at upsert time so concurrent ingestions dedupe safely.
    """

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False)

    __table_args__ = (
        UniqueConstraint("entity_type", "normalized_name", name="uq_entities_type_normalized"),
    )


class EntityMention(Base):
    """Per-chunk mention of an entity (KB-5).

    Many-to-many join between ``entities`` and ``document_chunks``.
    Not a timestamped mixin — only ``created_at`` is tracked because
    mentions are immutable; an updated chunk gets its old mentions
    deleted via CASCADE and new ones inserted.
    """

    __tablename__ = "entity_mentions"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    extraction_method: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("entity_id", "chunk_id", name="uq_entity_mentions_pair"),)


class SearchFeedback(Base, TimestampMixin):
    """KB-4 thumbs-up/down signal for a cited chunk on a specific query.

    Unique on ``(user_id, query_hash, chunk_id)`` so re-voting upserts rather
    than duplicating. ``rank_source`` discriminates which retrieval branch
    surfaced the chunk, used by the daily RRF recompute.
    """

    __tablename__ = "search_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query_type: Mapped[str] = mapped_column(String(16), nullable=False)
    chunk_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rank_source: Mapped[str] = mapped_column(String(16), nullable=False)
    relevant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "query_hash", "chunk_id", name="uq_feedback_user_query_chunk"),
    )
