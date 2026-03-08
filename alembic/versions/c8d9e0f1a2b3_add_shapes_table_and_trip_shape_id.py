"""add shapes table and trip shape_id

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-03-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create shapes table
    op.create_table(
        "shapes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gtfs_shape_id", sa.String(length=100), nullable=False),
        sa.Column("feed_id", sa.String(length=50), nullable=False, server_default="riga"),
        sa.Column("shape_pt_lat", sa.Float(), nullable=False),
        sa.Column("shape_pt_lon", sa.Float(), nullable=False),
        sa.Column("shape_pt_sequence", sa.Integer(), nullable=False),
        sa.Column("shape_dist_traveled", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "feed_id", "gtfs_shape_id", "shape_pt_sequence", name="uq_shape_feed_id_seq"
        ),
    )
    op.create_index(op.f("ix_shapes_id"), "shapes", ["id"], unique=False)
    op.create_index(op.f("ix_shapes_gtfs_shape_id"), "shapes", ["gtfs_shape_id"], unique=False)
    op.create_index(op.f("ix_shapes_feed_id"), "shapes", ["feed_id"], unique=False)

    # Add shape_id column to trips table
    op.add_column("trips", sa.Column("shape_id", sa.String(length=100), nullable=True))
    op.create_index(op.f("ix_trips_shape_id"), "trips", ["shape_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_trips_shape_id"), table_name="trips")
    op.drop_column("trips", "shape_id")
    op.drop_index(op.f("ix_shapes_feed_id"), table_name="shapes")
    op.drop_index(op.f("ix_shapes_gtfs_shape_id"), table_name="shapes")
    op.drop_index(op.f("ix_shapes_id"), table_name="shapes")
    op.drop_table("shapes")
