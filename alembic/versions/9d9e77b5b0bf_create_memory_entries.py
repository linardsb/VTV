"""Create memory_entries table.

Revision ID: 9d9e77b5b0bf
Revises: g5h6i7j8k9l0
Create Date: 2026-04-09
"""

from collections.abc import Sequence

import pgvector.sqlalchemy.vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d9e77b5b0bf"
down_revision: str | None = "g5h6i7j8k9l0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("memory_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.vector.VECTOR(dim=1024),
            nullable=True,
        ),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("decay_weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("is_evergreen", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("recalled_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_memory_entries_agent_type", "memory_entries", ["agent_type"])
    op.create_index("ix_memory_entries_memory_type", "memory_entries", ["memory_type"])
    op.create_index("ix_memory_entries_source", "memory_entries", ["source"])
    # IVFFlat index for cosine similarity search
    op.execute(
        "CREATE INDEX ix_memory_entries_embedding ON memory_entries "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memory_entries_embedding")
    op.drop_table("memory_entries")
