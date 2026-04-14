"""Add document versioning (KB-3).

Adds ``version``, ``parent_document_id``, and ``is_latest`` columns to
``documents`` so re-uploads of the same (title, domain) create a new row
linked to the prior via ``parent_document_id``, with the prior marked
``status='superseded'`` and ``is_latest=false`` (chunks retained — NO
cascade delete).

Revision ID: x8y9z0a1b2c3
Revises: w7x8y9z0a1b2
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "x8y9z0a1b2c3"
down_revision: str | None = "w7x8y9z0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "documents",
        sa.Column("parent_document_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_foreign_key(
        "fk_documents_parent_document_id",
        "documents",
        "documents",
        ["parent_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_documents_parent_document_id",
        "documents",
        ["parent_document_id"],
    )
    op.create_index(
        "ix_documents_is_latest",
        "documents",
        ["is_latest"],
    )
    op.create_index(
        "ix_documents_title_version",
        "documents",
        ["title", sa.text("version DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_title_version", table_name="documents")
    op.drop_index("ix_documents_is_latest", table_name="documents")
    op.drop_index("ix_documents_parent_document_id", table_name="documents")
    op.drop_constraint("fk_documents_parent_document_id", "documents", type_="foreignkey")
    op.drop_column("documents", "is_latest")
    op.drop_column("documents", "parent_document_id")
    op.drop_column("documents", "version")
