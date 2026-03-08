"""add vehicle_positions hypertable

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-03-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create vehicle_positions table and convert to TimescaleDB hypertable."""
    # Create the table
    op.create_table(
        "vehicle_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("feed_id", sa.String(50), nullable=False),
        sa.Column("vehicle_id", sa.String(100), nullable=False),
        sa.Column("route_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("route_short_name", sa.String(50), nullable=False, server_default=""),
        sa.Column("trip_id", sa.String(200), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("bearing", sa.Float(), nullable=True),
        sa.Column("speed_kmh", sa.Float(), nullable=True),
        sa.Column("delay_seconds", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column(
            "current_status",
            sa.String(20),
            nullable=False,
            server_default="IN_TRANSIT_TO",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vehicle_positions_vehicle_time",
        "vehicle_positions",
        ["vehicle_id", "recorded_at"],
    )
    op.create_index(
        "ix_vehicle_positions_route_time",
        "vehicle_positions",
        ["route_id", "recorded_at"],
    )
    op.create_index(
        "ix_vehicle_positions_feed_time",
        "vehicle_positions",
        ["feed_id", "recorded_at"],
    )

    # Convert to TimescaleDB hypertable (if TimescaleDB is available)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb')"
        )
    )
    has_timescaledb = result.scalar()

    if has_timescaledb:
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
        op.execute(
            "SELECT create_hypertable('vehicle_positions', 'recorded_at', "
            "chunk_time_interval => INTERVAL '1 day', "
            "migrate_data => true)"
        )
        op.execute(
            "ALTER TABLE vehicle_positions SET ("
            "timescaledb.compress, "
            "timescaledb.compress_segmentby = 'feed_id, vehicle_id, route_id', "
            "timescaledb.compress_orderby = 'recorded_at DESC'"
            ")"
        )
        op.execute("SELECT add_compression_policy('vehicle_positions', INTERVAL '7 days')")
        op.execute("SELECT add_retention_policy('vehicle_positions', INTERVAL '90 days')")


def downgrade() -> None:
    """Remove vehicle_positions hypertable and policies."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb')"
        )
    )
    if result.scalar():
        op.execute("SELECT remove_retention_policy('vehicle_positions', if_exists => true)")
        op.execute("SELECT remove_compression_policy('vehicle_positions', if_exists => true)")
    op.drop_table("vehicle_positions")
