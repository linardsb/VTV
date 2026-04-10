"""Add parent-child hierarchy columns to document_chunks.

Revision ID: g5h6i7j8k9l0
Revises: f3a4b5c6d7e8
Create Date: 2026-04-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g5h6i7j8k9l0"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("parent_chunk_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("heading_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("section_type", sa.String(length=20), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_chunks_parent_chunk_id",
        "document_chunks",
        "document_chunks",
        ["parent_chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_document_chunks_parent_chunk_id",
        "document_chunks",
        ["parent_chunk_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_parent_chunk_id", table_name="document_chunks")
    op.drop_constraint(
        "fk_document_chunks_parent_chunk_id",
        "document_chunks",
        type_="foreignkey",
    )
    op.drop_column("document_chunks", "section_type")
    op.drop_column("document_chunks", "heading_path")
    op.drop_column("document_chunks", "parent_chunk_id")
