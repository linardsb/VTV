# pyright: reportUnknownMemberType=false
"""SQLAlchemy models for agent memory entries."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class MemoryEntry(Base, TimestampMixin):
    """Agent memory entry with vector embedding for similarity recall.

    Stores learned patterns, session logs, durable facts, and query patterns.
    The embedding column uses pgvector's Vector type for cosine similarity search.
    """

    __tablename__ = "memory_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1024))
    metadata_json = mapped_column(JSONB, nullable=True)
    decay_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_evergreen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    recalled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
