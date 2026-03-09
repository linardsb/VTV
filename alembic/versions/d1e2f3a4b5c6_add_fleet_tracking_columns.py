"""Add tracked_devices table and fleet columns to vehicle_positions.

Revision ID: d1e2f3a4b5c6
Revises: c8d9e0f1a2b3
Create Date: 2026-03-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :name)"
        ),
        {"name": name},
    ).scalar()
    return bool(result)


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column)"
        ),
        {"table": table, "column": column},
    ).scalar()
    return bool(result)


def _index_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = :name)"),
        {"name": name},
    ).scalar()
    return bool(result)


def upgrade() -> None:
    """Create tracked_devices table and add source/obd_data to vehicle_positions."""
    # Create tracked_devices table (idempotent — may exist from prior partial run)
    if not _table_exists("tracked_devices"):
        op.create_table(
            "tracked_devices",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("imei", sa.String(15), nullable=False),
            sa.Column("device_name", sa.String(100), nullable=True),
            sa.Column("sim_number", sa.String(20), nullable=True),
            sa.Column(
                "protocol_type",
                sa.String(20),
                nullable=False,
                server_default="teltonika",
            ),
            sa.Column("firmware_version", sa.String(50), nullable=True),
            sa.Column("vehicle_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("traccar_device_id", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
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
            sa.ForeignKeyConstraint(
                ["vehicle_id"],
                ["vehicles.id"],
                ondelete="SET NULL",
            ),
            sa.CheckConstraint(
                "status IN ('active', 'inactive', 'offline')",
                name="ck_tracked_devices_status",
            ),
            sa.CheckConstraint(
                "protocol_type IN ('teltonika', 'queclink', 'general', 'osmand', 'other')",
                name="ck_tracked_devices_protocol",
            ),
        )

    if not _index_exists("ix_tracked_devices_id"):
        op.create_index("ix_tracked_devices_id", "tracked_devices", ["id"])
    if not _index_exists("ix_tracked_devices_imei"):
        op.create_index("ix_tracked_devices_imei", "tracked_devices", ["imei"], unique=True)
    if not _index_exists("ix_tracked_devices_vehicle_id"):
        op.create_index("ix_tracked_devices_vehicle_id", "tracked_devices", ["vehicle_id"])

    # Add source and obd_data columns to vehicle_positions
    if not _column_exists("vehicle_positions", "source"):
        op.add_column(
            "vehicle_positions",
            sa.Column("source", sa.String(20), nullable=False, server_default="gtfs-rt"),
        )
    if not _column_exists("vehicle_positions", "obd_data"):
        op.add_column(
            "vehicle_positions",
            sa.Column("obd_data", JSONB(), nullable=True),
        )
    if not _index_exists("ix_vehicle_positions_source"):
        op.create_index("ix_vehicle_positions_source", "vehicle_positions", ["source"])


def downgrade() -> None:
    """Drop fleet tracking columns and tracked_devices table."""
    op.drop_index("ix_vehicle_positions_source", table_name="vehicle_positions")
    op.drop_column("vehicle_positions", "obd_data")
    op.drop_column("vehicle_positions", "source")

    op.drop_index("ix_tracked_devices_vehicle_id", table_name="tracked_devices")
    op.drop_index("ix_tracked_devices_imei", table_name="tracked_devices")
    op.drop_index("ix_tracked_devices_id", table_name="tracked_devices")
    op.drop_table("tracked_devices")
