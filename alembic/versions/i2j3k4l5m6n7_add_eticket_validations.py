"""add eticket_validations hypertable and eticket_imports tracking table

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i2j3k4l5m6n7"
down_revision: str | None = "h1i2j3k4l5m6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create eticket_validations hypertable and eticket_imports tracking table."""
    # --- eticket_validations (high-volume, hypertable candidate) ---
    op.create_table(
        "eticket_validations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("record_id", sa.String(50), nullable=False),
        sa.Column("depot", sa.String(50), nullable=False),
        sa.Column("transport_type", sa.String(20), nullable=False),
        sa.Column("vehicle_number", sa.String(20), nullable=False),
        sa.Column("route_name", sa.String(100), nullable=False),
        sa.Column("route_code", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("validation_id", sa.String(50), nullable=False),
        sa.Column(
            "validated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_eticket_route_time",
        "eticket_validations",
        ["route_code", "validated_at"],
    )
    op.create_index(
        "ix_eticket_vehicle_time",
        "eticket_validations",
        ["vehicle_number", "validated_at"],
    )

    # --- eticket_imports (low-volume tracking table) ---
    op.create_table(
        "eticket_imports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("archive_month", sa.String(7), nullable=False, unique=True),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- TimescaleDB hypertable conversion (if available) ---
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb')")
    )
    has_timescaledb = result.scalar()

    if has_timescaledb:
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
        op.execute(
            "SELECT create_hypertable('eticket_validations', 'validated_at', "
            "chunk_time_interval => INTERVAL '7 days', "
            "migrate_data => true)"
        )
        op.execute(
            "ALTER TABLE eticket_validations SET ("
            "timescaledb.compress, "
            "timescaledb.compress_segmentby = 'route_code, vehicle_number', "
            "timescaledb.compress_orderby = 'validated_at DESC'"
            ")"
        )
        op.execute("SELECT add_compression_policy('eticket_validations', INTERVAL '30 days')")
        op.execute("SELECT add_retention_policy('eticket_validations', INTERVAL '1825 days')")


def downgrade() -> None:
    """Remove eticket tables and TimescaleDB policies."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb')")
    )
    if result.scalar():
        op.execute("SELECT remove_retention_policy('eticket_validations', if_exists => true)")
        op.execute("SELECT remove_compression_policy('eticket_validations', if_exists => true)")
    op.drop_table("eticket_imports")
    op.drop_table("eticket_validations")
