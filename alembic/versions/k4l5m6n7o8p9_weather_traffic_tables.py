"""Add weather and traffic observation tables (ML-1.3).

Revision ID: k4l5m6n7o8p9
Revises: h1i2j3k4l5m6
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k4l5m6n7o8p9"
down_revision: str | None = "h1i2j3k4l5m6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create weather and traffic tables with PostGIS and optional TimescaleDB."""
    # Ensure PostGIS is available
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # --- weather_stations ---
    op.create_table(
        "weather_stations",
        sa.Column("station_id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "location",
            sa.Column(
                "location",
                sa.Text(),
                nullable=False,
            ).type,
            nullable=False,
        ),
    )
    # PostGIS geography column added via raw SQL for proper type
    op.execute(
        "ALTER TABLE weather_stations "
        "ALTER COLUMN location TYPE geography(POINT, 4326) "
        "USING ST_SetSRID(ST_MakePoint(0, 0), 4326)::geography"
    )
    op.execute("ALTER TABLE weather_stations ALTER COLUMN location SET NOT NULL")
    op.create_index(
        "ix_weather_stations_location",
        "weather_stations",
        ["location"],
        postgresql_using="gist",
    )

    # --- weather_observations ---
    op.create_table(
        "weather_observations",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("station_id", sa.String(50), nullable=False, index=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("temp_c", sa.Float(), nullable=True),
        sa.Column("wind_mps", sa.Float(), nullable=True),
        sa.Column("precip_mm", sa.Float(), nullable=True),
        sa.Column("phenomena", JSONB(), nullable=True),
    )
    # Add geography column
    op.execute("ALTER TABLE weather_observations ADD COLUMN location geography(POINT, 4326)")
    op.create_index(
        "ix_weather_obs_station_time",
        "weather_observations",
        ["station_id", "observed_at"],
    )
    op.create_index(
        "ix_weather_obs_location",
        "weather_observations",
        ["location"],
        postgresql_using="gist",
    )
    op.execute(
        "ALTER TABLE weather_observations ADD CONSTRAINT uq_weather_obs_station_time "
        "UNIQUE (station_id, observed_at)"
    )

    # Convert to hypertable if TimescaleDB is available
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb')")
    )
    has_timescaledb = result.scalar()

    if has_timescaledb:
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
        op.execute(
            "SELECT create_hypertable('weather_observations', 'observed_at', "
            "chunk_time_interval => INTERVAL '1 day', "
            "migrate_data => true)"
        )
        op.execute(
            "ALTER TABLE weather_observations SET ("
            "timescaledb.compress, "
            "timescaledb.compress_segmentby = 'station_id', "
            "timescaledb.compress_orderby = 'observed_at DESC'"
            ")"
        )
        op.execute("SELECT add_compression_policy('weather_observations', INTERVAL '7 days')")
        op.execute("SELECT add_retention_policy('weather_observations', INTERVAL '365 days')")

    # --- traffic_counts ---
    op.create_table(
        "traffic_counts",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("point_id", sa.String(50), nullable=False, index=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("avg_count_per_day", sa.Float(), nullable=False),
        sa.Column("vehicle_class", sa.String(50), nullable=True),
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
            onupdate=sa.func.now(),
        ),
    )
    op.execute("ALTER TABLE traffic_counts ADD COLUMN location geography(POINT, 4326)")
    op.execute(
        "ALTER TABLE traffic_counts ADD CONSTRAINT uq_traffic_count_key "
        "UNIQUE (point_id, period_start, period_end, vehicle_class)"
    )
    op.create_index(
        "ix_traffic_counts_location",
        "traffic_counts",
        ["location"],
        postgresql_using="gist",
    )

    # --- traffic_accidents ---
    op.create_table(
        "traffic_accidents",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("source_id", sa.String(100), nullable=False, unique=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("fatalities", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("injuries", sa.Integer(), nullable=False, server_default="0"),
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
            onupdate=sa.func.now(),
        ),
    )
    op.execute("ALTER TABLE traffic_accidents ADD COLUMN location geography(POINT, 4326)")
    op.create_index(
        "ix_traffic_accidents_location",
        "traffic_accidents",
        ["location"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    """Drop weather and traffic tables."""
    # Remove TimescaleDB policies first (if they exist)
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS(SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb')")
    )
    has_timescaledb = result.scalar()

    if has_timescaledb:
        conn.execute(
            sa.text("SELECT remove_retention_policy('weather_observations', if_exists => true)")
        )
        conn.execute(
            sa.text("SELECT remove_compression_policy('weather_observations', if_exists => true)")
        )

    op.drop_table("traffic_accidents")
    op.drop_table("traffic_counts")
    op.drop_table("weather_observations")
    op.drop_table("weather_stations")
