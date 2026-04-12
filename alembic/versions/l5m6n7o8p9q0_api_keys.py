"""Add API keys and usage tracking tables (ML-5.3).

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l5m6n7o8p9q0"
down_revision: str | Sequence[str] | None = "k4l5m6n7o8p9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create api_keys and api_key_usage tables with optional TimescaleDB hypertable."""
    # --- api_keys ---
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_hash", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("key_preview", sa.String(20), nullable=False),
        sa.Column(
            "owner_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("tier", sa.String(10), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
    )

    # --- api_key_usage ---
    op.create_table(
        "api_key_usage",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "api_key_id",
            sa.Integer,
            sa.ForeignKey("api_keys.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("endpoint", sa.String(100), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("response_time_ms", sa.Integer, nullable=False),
    )
    op.create_index(
        "ix_api_key_usage_key_recorded",
        "api_key_usage",
        ["api_key_id", "recorded_at"],
    )

    # Optional TimescaleDB hypertable (follows existing pattern from b7c8d9e0f1a2)
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')")
    )
    has_timescale = result.scalar()

    if has_timescale:
        op.execute(
            "SELECT create_hypertable('api_key_usage', 'recorded_at', "
            "chunk_time_interval => INTERVAL '1 day', migrate_data => true)"
        )
        # Compress chunks older than 7 days
        op.execute(
            "ALTER TABLE api_key_usage SET ("
            "timescaledb.compress, timescaledb.compress_segmentby = 'api_key_id')"
        )
        op.execute("SELECT add_compression_policy('api_key_usage', INTERVAL '7 days')")
        # Drop chunks older than 90 days
        op.execute("SELECT add_retention_policy('api_key_usage', INTERVAL '90 days')")


def downgrade() -> None:
    """Drop API key tables."""
    op.drop_table("api_key_usage")
    op.drop_table("api_keys")
