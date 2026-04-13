"""add auth_audit_events hypertable

Revision ID: q1r2s3t4u5v6
Revises: p9q0r1s2t3u4
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "q1r2s3t4u5v6"
down_revision: str | Sequence[str] | None = "p9q0r1s2t3u4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create auth_audit_events table and convert to TimescaleDB hypertable."""
    op.create_table(
        "auth_audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("status_code", sa.SmallInteger(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("enforcement_layer", sa.String(50), nullable=False),
        sa.Column("client_ip", sa.String(45), nullable=True),
        sa.Column("user_role", sa.String(20), nullable=True),
        sa.Column("extra", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_audit_events_recorded_at",
        "auth_audit_events",
        ["recorded_at"],
    )
    op.create_index(
        "ix_auth_audit_events_user_id",
        "auth_audit_events",
        ["user_id"],
    )
    op.create_index(
        "ix_auth_audit_events_user_time",
        "auth_audit_events",
        ["user_id", sa.text("recorded_at DESC")],
    )

    # Convert to TimescaleDB hypertable (if TimescaleDB is available)
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb')")
    )
    has_timescaledb = result.scalar()

    if has_timescaledb:
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
        op.execute(
            "SELECT create_hypertable('auth_audit_events', 'recorded_at', "
            "chunk_time_interval => INTERVAL '1 day', "
            "migrate_data => true)"
        )
        op.execute(
            "ALTER TABLE auth_audit_events SET ("
            "timescaledb.compress, "
            "timescaledb.compress_segmentby = 'enforcement_layer', "
            "timescaledb.compress_orderby = 'recorded_at DESC'"
            ")"
        )
        op.execute("SELECT add_compression_policy('auth_audit_events', INTERVAL '7 days')")
        op.execute("SELECT add_retention_policy('auth_audit_events', INTERVAL '90 days')")


def downgrade() -> None:
    """Remove auth_audit_events hypertable and policies."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb')")
    )
    if result.scalar():
        op.execute("SELECT remove_retention_policy('auth_audit_events', if_exists => true)")
        op.execute("SELECT remove_compression_policy('auth_audit_events', if_exists => true)")
    op.drop_table("auth_audit_events")
