"""Add entities + entity_mentions tables (KB-5).

Entity/knowledge-graph overlay: extract named entities during chunking
and store them so search can boost chunks sharing entities with the
query. Extraction uses deterministic regex (routes, regulations) plus
a GTFS-backed stop gazetteer, with optional spaCy NER for people/orgs.

Revision ID: e5n6t6k6b6
Revises: 725c03f
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5n6t6k6b6"
# Base on current alembic head.
down_revision: str | None = "w7x8y9z0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("normalized_name", sa.String(500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "entity_type", "normalized_name", name="uq_entities_type_normalized"
        ),
    )
    op.create_index(
        "ix_entities_type_norm",
        "entities",
        ["entity_type", "normalized_name"],
    )

    op.create_table(
        "entity_mentions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "entity_id",
            sa.Integer(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            sa.Integer(),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mention_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("extraction_method", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "entity_id", "chunk_id", name="uq_entity_mentions_pair"
        ),
    )
    op.create_index(
        "ix_entity_mentions_chunk", "entity_mentions", ["chunk_id"]
    )
    op.create_index(
        "ix_entity_mentions_entity", "entity_mentions", ["entity_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_entity_mentions_entity", table_name="entity_mentions")
    op.drop_index("ix_entity_mentions_chunk", table_name="entity_mentions")
    op.drop_table("entity_mentions")
    op.drop_index("ix_entities_type_norm", table_name="entities")
    op.drop_table("entities")
