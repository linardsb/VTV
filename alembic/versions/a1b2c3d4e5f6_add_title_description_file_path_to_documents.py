"""add title description file_path to documents

Revision ID: a1b2c3d4e5f6
Revises: e4a05b88d90b
Create Date: 2026-02-19 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "e4a05b88d90b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add title, description, and file_path columns to documents table."""
    op.add_column("documents", sa.Column("title", sa.String(200), nullable=True))
    op.add_column("documents", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("file_path", sa.String(500), nullable=True))


def downgrade() -> None:
    """Remove title, description, and file_path columns from documents table."""
    op.drop_column("documents", "file_path")
    op.drop_column("documents", "description")
    op.drop_column("documents", "title")
