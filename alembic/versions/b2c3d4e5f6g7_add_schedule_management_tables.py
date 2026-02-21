"""add schedule management tables

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-21 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create schedule management tables in FK dependency order."""
    # 1. agencies
    op.create_table(
        "agencies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gtfs_agency_id", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("agency_name", sa.String(200), nullable=False),
        sa.Column("agency_url", sa.String(500), nullable=True),
        sa.Column("agency_timezone", sa.String(50), nullable=False, server_default="Europe/Riga"),
        sa.Column("agency_lang", sa.String(5), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # 2. routes (FK -> agencies)
    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gtfs_route_id", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column(
            "agency_id",
            sa.Integer(),
            sa.ForeignKey("agencies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("route_short_name", sa.String(50), nullable=False, index=True),
        sa.Column("route_long_name", sa.String(200), nullable=False),
        sa.Column("route_type", sa.Integer(), nullable=False),
        sa.Column("route_color", sa.String(6), nullable=True),
        sa.Column("route_text_color", sa.String(6), nullable=True),
        sa.Column("route_sort_order", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # 3. calendars
    op.create_table(
        "calendars",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gtfs_service_id", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("monday", sa.Boolean(), nullable=False),
        sa.Column("tuesday", sa.Boolean(), nullable=False),
        sa.Column("wednesday", sa.Boolean(), nullable=False),
        sa.Column("thursday", sa.Boolean(), nullable=False),
        sa.Column("friday", sa.Boolean(), nullable=False),
        sa.Column("saturday", sa.Boolean(), nullable=False),
        sa.Column("sunday", sa.Boolean(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # 4. calendar_dates (FK -> calendars)
    op.create_table(
        "calendar_dates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "calendar_id",
            sa.Integer(),
            sa.ForeignKey("calendars.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("exception_type", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # 5. trips (FK -> routes, calendars)
    op.create_table(
        "trips",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gtfs_trip_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column(
            "route_id",
            sa.Integer(),
            sa.ForeignKey("routes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "calendar_id",
            sa.Integer(),
            sa.ForeignKey("calendars.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("direction_id", sa.Integer(), nullable=True),
        sa.Column("trip_headsign", sa.String(200), nullable=True),
        sa.Column("block_id", sa.String(50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # 6. stop_times (FK -> trips, stops)
    op.create_table(
        "stop_times",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "trip_id",
            sa.Integer(),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "stop_id",
            sa.Integer(),
            sa.ForeignKey("stops.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("stop_sequence", sa.Integer(), nullable=False),
        sa.Column("arrival_time", sa.String(8), nullable=False),
        sa.Column("departure_time", sa.String(8), nullable=False),
        sa.Column("pickup_type", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("drop_off_type", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    """Drop schedule management tables in reverse FK order."""
    op.drop_table("stop_times")
    op.drop_table("trips")
    op.drop_table("calendar_dates")
    op.drop_table("calendars")
    op.drop_table("routes")
    op.drop_table("agencies")
