"""Add share_links table (LV-3.4).

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v6w7x8y9z0a1"
down_revision: str | None = "u5v6w7x8y9z0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "share_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("vehicle_id", sa.String(100), nullable=False),
        sa.Column("route_id", sa.String(50), nullable=True),
        sa.Column("feed_id", sa.String(50), nullable=False, server_default="riga"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_share_links_token_hash", "share_links", ["token_hash"])
    op.create_index("ix_share_links_expires_at", "share_links", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_share_links_expires_at")
    op.drop_index("ix_share_links_token_hash")
    op.drop_table("share_links")
