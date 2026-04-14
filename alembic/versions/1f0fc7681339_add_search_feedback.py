"""Add search_feedback table (KB-4).

Captures user thumbs-up/down on cited chunks from search results. The
daily recompute task aggregates these signals into tuned RRF weights
per query type (keyword/semantic/mixed) stored in Redis, with fallback
to static config when sample size is below the minimum threshold.

Revision ID: 1f0fc7681339
Revises: x8y9z0a1b2c3
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "1f0fc7681339"  # pragma: allowlist secret
down_revision: str | None = "x8y9z0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("query_type", sa.String(16), nullable=False),
        sa.Column(
            "chunk_id",
            sa.Integer(),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank_source", sa.String(16), nullable=False),
        sa.Column("relevant", sa.Boolean(), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_search_feedback_query_hash",
        "search_feedback",
        ["query_hash"],
    )
    op.create_index(
        "ix_search_feedback_chunk_id",
        "search_feedback",
        ["chunk_id"],
    )
    op.create_index(
        "ix_search_feedback_qtype_created",
        "search_feedback",
        ["query_type", "created_at"],
    )
    op.create_unique_constraint(
        "uq_feedback_user_query_chunk",
        "search_feedback",
        ["user_id", "query_hash", "chunk_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_feedback_user_query_chunk", "search_feedback", type_="unique")
    op.drop_index("ix_search_feedback_qtype_created", table_name="search_feedback")
    op.drop_index("ix_search_feedback_chunk_id", table_name="search_feedback")
    op.drop_index("ix_search_feedback_query_hash", table_name="search_feedback")
    op.drop_table("search_feedback")
