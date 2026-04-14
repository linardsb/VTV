"""Add lemmatized_content to document_chunks (KB-2).

Revision ID: w7x8y9z0a1b2
Revises: v6w7x8y9z0a1
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "w7x8y9z0a1b2"
down_revision: str | None = "v6w7x8y9z0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("lemmatized_content", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "lemmatized_content")
