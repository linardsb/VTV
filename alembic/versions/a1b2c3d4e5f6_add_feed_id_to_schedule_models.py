"""add_feed_id_to_schedule_models

Revision ID: a1b2c3d4e5f6
Revises: 4f10502b5ce8
Create Date: 2026-03-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "4f10502b5ce8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add feed_id column and composite unique constraints to schedule models."""
    # 1. Add feed_id column with server_default so existing rows get "riga"
    op.add_column(
        "agencies", sa.Column("feed_id", sa.String(50), nullable=False, server_default="riga")
    )
    op.add_column(
        "routes", sa.Column("feed_id", sa.String(50), nullable=False, server_default="riga")
    )
    op.add_column(
        "calendars", sa.Column("feed_id", sa.String(50), nullable=False, server_default="riga")
    )
    op.add_column(
        "trips", sa.Column("feed_id", sa.String(50), nullable=False, server_default="riga")
    )

    # 2. Drop old single-column unique indexes
    op.drop_index("ix_agencies_gtfs_agency_id", table_name="agencies")
    op.drop_index("ix_routes_gtfs_route_id", table_name="routes")
    op.drop_index("ix_calendars_gtfs_service_id", table_name="calendars")
    op.drop_index("ix_trips_gtfs_trip_id", table_name="trips")

    # 3. Create non-unique indexes on the GTFS ID columns (for lookups)
    op.create_index("ix_agencies_gtfs_agency_id", "agencies", ["gtfs_agency_id"], unique=False)
    op.create_index("ix_routes_gtfs_route_id", "routes", ["gtfs_route_id"], unique=False)
    op.create_index("ix_calendars_gtfs_service_id", "calendars", ["gtfs_service_id"], unique=False)
    op.create_index("ix_trips_gtfs_trip_id", "trips", ["gtfs_trip_id"], unique=False)

    # 4. Create composite unique constraints
    op.create_unique_constraint("uq_agency_feed_gtfs_id", "agencies", ["feed_id", "gtfs_agency_id"])
    op.create_unique_constraint("uq_route_feed_gtfs_id", "routes", ["feed_id", "gtfs_route_id"])
    op.create_unique_constraint(
        "uq_calendar_feed_gtfs_id", "calendars", ["feed_id", "gtfs_service_id"]
    )
    op.create_unique_constraint("uq_trip_feed_gtfs_id", "trips", ["feed_id", "gtfs_trip_id"])

    # 5. Create indexes on feed_id for filtering
    op.create_index("ix_agencies_feed_id", "agencies", ["feed_id"])
    op.create_index("ix_routes_feed_id", "routes", ["feed_id"])
    op.create_index("ix_calendars_feed_id", "calendars", ["feed_id"])
    op.create_index("ix_trips_feed_id", "trips", ["feed_id"])

    # 6. Remove server defaults (existing rows already backfilled)
    op.alter_column("agencies", "feed_id", server_default=None)
    op.alter_column("routes", "feed_id", server_default=None)
    op.alter_column("calendars", "feed_id", server_default=None)
    op.alter_column("trips", "feed_id", server_default=None)


def downgrade() -> None:
    """Remove feed_id column and restore single-column unique constraints."""
    # Drop feed_id indexes
    op.drop_index("ix_agencies_feed_id", table_name="agencies")
    op.drop_index("ix_routes_feed_id", table_name="routes")
    op.drop_index("ix_calendars_feed_id", table_name="calendars")
    op.drop_index("ix_trips_feed_id", table_name="trips")

    # Drop composite unique constraints
    op.drop_constraint("uq_agency_feed_gtfs_id", "agencies", type_="unique")
    op.drop_constraint("uq_route_feed_gtfs_id", "routes", type_="unique")
    op.drop_constraint("uq_calendar_feed_gtfs_id", "calendars", type_="unique")
    op.drop_constraint("uq_trip_feed_gtfs_id", "trips", type_="unique")

    # Drop non-unique GTFS ID indexes
    op.drop_index("ix_agencies_gtfs_agency_id", table_name="agencies")
    op.drop_index("ix_routes_gtfs_route_id", table_name="routes")
    op.drop_index("ix_calendars_gtfs_service_id", table_name="calendars")
    op.drop_index("ix_trips_gtfs_trip_id", table_name="trips")

    # Restore original unique indexes on GTFS IDs
    op.create_index("ix_agencies_gtfs_agency_id", "agencies", ["gtfs_agency_id"], unique=True)
    op.create_index("ix_routes_gtfs_route_id", "routes", ["gtfs_route_id"], unique=True)
    op.create_index("ix_calendars_gtfs_service_id", "calendars", ["gtfs_service_id"], unique=True)
    op.create_index("ix_trips_gtfs_trip_id", "trips", ["gtfs_trip_id"], unique=True)

    # Drop feed_id columns
    op.drop_column("trips", "feed_id")
    op.drop_column("calendars", "feed_id")
    op.drop_column("routes", "feed_id")
    op.drop_column("agencies", "feed_id")
