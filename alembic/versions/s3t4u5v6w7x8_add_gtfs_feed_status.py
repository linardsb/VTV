"""Add gtfs_feed_status table for per-feed import tracking (LV-1.2).

Revision ID: s3t4u5v6w7x8
Revises: r2s3t4u5v6w7
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "s3t4u5v6w7x8"
down_revision: str | None = "r2s3t4u5v6w7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gtfs_feed_status",
        sa.Column("feed_id", sa.String(50), primary_key=True),
        sa.Column("operator_name", sa.String(200), nullable=False),
        sa.Column("static_url", sa.String(500), nullable=True),
        sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_import_routes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_import_trips", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_import_error", sa.String(2000), nullable=True),
        sa.Column("auto_import_enabled", sa.Boolean(), server_default="true", nullable=False),
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
    )

    # Seed row for existing Riga feed
    op.execute(
        sa.text(
            "INSERT INTO gtfs_feed_status (feed_id, operator_name, auto_import_enabled, created_at, updated_at) "
            "VALUES ('riga', 'Rigas Satiksme', true, NOW(), NOW()) "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    op.drop_table("gtfs_feed_status")
