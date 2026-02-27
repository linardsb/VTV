"""add PostGIS geometry to stops

Revision ID: b039c337be87
Revises: bfd1f6566653
Create Date: 2026-02-27 07:12:27.192842

"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry  # pyright: ignore[reportMissingTypeStubs]

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b039c337be87"
down_revision: str | Sequence[str] | None = "bfd1f6566653"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add PostGIS extension, geometry column, spatial index, and sync trigger."""
    # 1. Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # 2. Add geometry column (GeoAlchemy2 auto-creates GIST index named idx_stops_geom)
    op.add_column(
        "stops",
        sa.Column("geom", Geometry("POINT", srid=4326), nullable=True),
    )

    # 3. Populate geom from existing lat/lon data
    op.execute("""
        UPDATE stops
        SET geom = ST_SetSRID(ST_MakePoint(stop_lon, stop_lat), 4326)
        WHERE stop_lat IS NOT NULL AND stop_lon IS NOT NULL
    """)

    # 4. Create trigger function for automatic geom sync
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_stop_geom()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.stop_lat IS NOT NULL AND NEW.stop_lon IS NOT NULL THEN
                NEW.geom := ST_SetSRID(ST_MakePoint(NEW.stop_lon, NEW.stop_lat), 4326);
            ELSE
                NEW.geom := NULL;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    # 5. Create trigger on stops table
    op.execute("""
        CREATE TRIGGER trg_sync_stop_geom
        BEFORE INSERT OR UPDATE OF stop_lat, stop_lon ON stops
        FOR EACH ROW EXECUTE FUNCTION sync_stop_geom()
    """)


def downgrade() -> None:
    """Remove PostGIS spatial query infrastructure from stops."""
    op.execute("DROP TRIGGER IF EXISTS trg_sync_stop_geom ON stops")
    op.execute("DROP FUNCTION IF EXISTS sync_stop_geom()")
    op.drop_index("idx_stops_geom", table_name="stops", postgresql_using="gist")
    op.drop_column("stops", "geom")
    # Do NOT drop PostGIS extension — other features may use it
