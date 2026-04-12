"""Add GTFS snapshot tables for historical archive.

Revision ID: h1i2j3k4l5m6
Revises: 9d9e77b5b0bf
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h1i2j3k4l5m6"
down_revision: str | None = "9d9e77b5b0bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create gtfs_snapshots and shadow tables."""
    op.create_table(
        "gtfs_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("feed_name", sa.String(50), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("row_counts_json", sa.JSON(), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_id"),
    )
    op.create_index("ix_gtfs_snapshots_date", "gtfs_snapshots", ["snapshot_date"])

    op.create_table(
        "gtfs_snapshot_trips",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("gtfs_trip_id", sa.String(200), nullable=False),
        sa.Column("gtfs_route_id", sa.String(100), nullable=False),
        sa.Column("gtfs_service_id", sa.String(100), nullable=False),
        sa.Column("direction_id", sa.Integer(), nullable=True),
        sa.Column("trip_headsign", sa.String(200), nullable=True),
        sa.Column("shape_id", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(["snapshot_id"], ["gtfs_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "gtfs_trip_id", name="uq_snapshot_trip"),
    )
    op.create_index("ix_snapshot_trips_snapshot_id", "gtfs_snapshot_trips", ["snapshot_id"])

    op.create_table(
        "gtfs_snapshot_stop_times",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("gtfs_trip_id", sa.String(200), nullable=False),
        sa.Column("gtfs_stop_id", sa.String(100), nullable=False),
        sa.Column("stop_sequence", sa.Integer(), nullable=False),
        sa.Column("arrival_time", sa.String(8), nullable=False),
        sa.Column("departure_time", sa.String(8), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["gtfs_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "gtfs_trip_id",
            "stop_sequence",
            name="uq_snapshot_stop_time",
        ),
    )
    op.create_index(
        "ix_snapshot_stop_times_snapshot_id",
        "gtfs_snapshot_stop_times",
        ["snapshot_id"],
    )

    op.create_table(
        "gtfs_snapshot_calendars",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("gtfs_service_id", sa.String(100), nullable=False),
        sa.Column("monday", sa.Boolean(), nullable=False),
        sa.Column("tuesday", sa.Boolean(), nullable=False),
        sa.Column("wednesday", sa.Boolean(), nullable=False),
        sa.Column("thursday", sa.Boolean(), nullable=False),
        sa.Column("friday", sa.Boolean(), nullable=False),
        sa.Column("saturday", sa.Boolean(), nullable=False),
        sa.Column("sunday", sa.Boolean(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["gtfs_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "gtfs_service_id", name="uq_snapshot_calendar"),
    )
    op.create_index(
        "ix_snapshot_calendars_snapshot_id",
        "gtfs_snapshot_calendars",
        ["snapshot_id"],
    )


def downgrade() -> None:
    """Drop all GTFS snapshot tables."""
    op.drop_table("gtfs_snapshot_calendars")
    op.drop_table("gtfs_snapshot_stop_times")
    op.drop_table("gtfs_snapshot_trips")
    op.drop_table("gtfs_snapshots")
