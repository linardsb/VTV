"""add GIN index for fulltext search on document_chunks

Revision ID: c7f9d2b03e58
Revises: b5e8c1a92d47
Create Date: 2026-02-23 06:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7f9d2b03e58"
down_revision: str | None = "b5e8c1a92d47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add GIN index for fulltext search on document_chunks.content.

    The search_fulltext() repository method uses to_tsvector('simple', content)
    without an index, causing sequential scans on every search query.
    """
    op.execute(
        sa.text(
            "CREATE INDEX idx_document_chunks_content_fts "
            "ON document_chunks USING gin(to_tsvector('simple', content))"
        )
    )


def downgrade() -> None:
    """Remove GIN fulltext search index."""
    op.execute(sa.text("DROP INDEX IF EXISTS idx_document_chunks_content_fts"))
