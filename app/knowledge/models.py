# pyright: reportUnknownMemberType=false
"""SQLAlchemy models for knowledge base documents and chunks."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin

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
