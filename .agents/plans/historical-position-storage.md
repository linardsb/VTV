# Plan: Historical Position Storage (TimescaleDB)

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: transit, database infrastructure, analytics, agent tools

## Feature Description

Vehicle positions are currently ephemeral — the GTFS-RT poller writes enriched positions to Redis with a 120-second TTL, and once expired, those data points are lost forever. This prevents historical analytics (on-time trends over days/weeks), delay pattern detection (which routes are consistently late at specific times), and historical replay (investigating an incident that occurred hours or days ago).

This feature adds a TimescaleDB hypertable to store every vehicle position update as a time-series record. The poller's `poll_once()` method is extended to batch-insert positions into PostgreSQL alongside its existing Redis writes. New REST endpoints expose historical queries: position history for a vehicle, delay trends by route, and aggregated on-time performance over date ranges. The analytics service gains the ability to query historical data instead of relying on live GTFS-RT snapshots.

TimescaleDB is chosen because it's a PostgreSQL extension (same database, no new service), provides automatic time-based partitioning (hypertables), built-in compression policies for older data, and continuous aggregates for pre-computed rollups — all critical for a write-heavy time-series workload (~3,000 inserts/minute across 500+ vehicles at 10-second intervals).

## User Story

As a **transit planner or dispatcher**
I want to **view historical vehicle positions, delay trends, and on-time performance over configurable date ranges**
So that I can **identify recurring delay patterns, assess route reliability, and investigate past incidents with full position data**

## Security Contexts

**Active contexts** (detected from feature scope):
- **CTX-RBAC**: New REST endpoints require role-based access control — historical data is operationally sensitive
- **CTX-INPUT**: New Query parameters (date ranges, route filters) require validation and length constraints
- **CTX-INFRA**: Docker database image changes (adding TimescaleDB extension), new env vars for retention policy

**Not applicable:**
- CTX-AUTH: No changes to authentication flow
- CTX-FILE: No file uploads
- CTX-AGENT: No agent tool changes in this phase (future enhancement)

## Solution Approach

We use TimescaleDB as a PostgreSQL extension added to the existing `db/Dockerfile` image. This avoids introducing a new service — the hypertable lives in the same database as all other VTV tables, uses the same connection pool, and is managed by the same Alembic migration system.

**Approach Decision:**
We chose TimescaleDB extension within existing PostgreSQL because:
- Zero new infrastructure — same database, same connection pool, same backup strategy
- Hypertables provide automatic time-based partitioning with no application-level sharding logic
- Built-in compression policies reduce storage 10-20x for data older than 7 days
- Continuous aggregates enable pre-computed hourly/daily rollups for fast dashboard queries
- The Implementation Plan (`docs/PLANNING/Implementation-Plan.md`) explicitly designates TimescaleDB for this purpose

**Alternatives Considered:**
- **InfluxDB/QuestDB (separate time-series DB)**: Rejected — adds operational complexity (new service, new backup, new monitoring) for a workload that TimescaleDB handles natively within PostgreSQL
- **Plain PostgreSQL with BRIN indexes**: Rejected — lacks automatic partitioning, compression policies, and continuous aggregates; manual implementation of these features would be error-prone and unmaintainable
- **Keep positions in Redis with longer TTL**: Rejected — Redis is not designed for historical queries; memory costs would be prohibitive (500 vehicles × 6 positions/min × 90 days = ~230M records)

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/transit/poller.py` (lines 61-136) — `poll_once()` method that writes to Redis; extend to also write to PostgreSQL
- `app/transit/schemas.py` (lines 12-47) — `VehiclePosition` schema; reference fields for the DB model
- `app/transit/routes.py` (lines 1-68) — Existing transit endpoints; add new history endpoints here
- `app/transit/service.py` (lines 28-110) — `TransitService`; add history query methods
- `app/core/config.py` (lines 30-111) — `Settings` class; add TimescaleDB/retention config
- `app/core/database.py` (lines 1-80) — `Base`, `get_db()`, `get_db_context()`; understand session patterns
- `app/shared/models.py` (lines 1-42) — `TimestampMixin`; positions table does NOT use this (uses `recorded_at` as primary time column)
- `db/Dockerfile` (lines 1-10) — Custom PG18 image; add TimescaleDB extension

### Similar Features (Examples to Follow)
- `app/analytics/routes.py` (lines 78-131) — Query parameter patterns with date/time validation, rate limiting, auth
- `app/analytics/service.py` (lines 277-457) — Date validation, time window filtering, aggregation patterns
- `app/analytics/schemas.py` (lines 78-118) — Performance summary response schemas

### Files to Modify
- `db/Dockerfile` — Add TimescaleDB extension package
- `app/core/config.py` — Add retention/compression settings
- `app/transit/poller.py` — Add DB write alongside Redis write
- `app/transit/models.py` — CREATE new file for VehiclePositionRecord model
- `app/transit/schemas.py` — ADD history response schemas
- `app/transit/repository.py` — CREATE new file for history queries
- `app/transit/service.py` — ADD history query methods
- `app/transit/routes.py` — ADD history endpoints
- `app/main.py` — No changes needed (transit_router already registered)

## Implementation Plan

### Phase 1: Infrastructure Foundation
TimescaleDB extension in Docker image, Alembic migration for hypertable, config settings.

### Phase 2: Write Path
Extend the poller to batch-insert positions into the hypertable during each poll cycle.

### Phase 3: Read Path
Repository, service, and route layers for querying historical data.

### Phase 4: Testing & Validation
Unit tests for all new code, integration test for write+read round-trip.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Add TimescaleDB Extension to Database Image
**File:** `db/Dockerfile` (modify existing)
**Action:** UPDATE

Add the `timescaledb` PostgreSQL extension package. The base image is `pgvector/pgvector:pg18` (Debian Bookworm-based). TimescaleDB provides APT packages for PG18.

Add to the existing `RUN apt-get` block:
- Add the TimescaleDB APT repository (packagecloud)
- Install `timescaledb-2-postgresql-18`
- Add `timescaledb` to `shared_preload_libraries` in `postgresql.conf`

The Dockerfile should look like:
```dockerfile
FROM pgvector/pgvector:pg18

# Install PostGIS and TimescaleDB extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-18-postgis-3 \
        postgresql-18-postgis-3-scripts \
        gnupg lsb-release wget && \
    echo "deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -cs) main" > /etc/apt/sources.list.d/timescaledb.list && \
    wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | gpg --dearmor -o /etc/apt/trusted.gpg.d/timescaledb.gpg && \
    apt-get update && \
    apt-get install -y --no-install-recommends timescaledb-2-postgresql-18 && \
    apt-get purge -y gnupg lsb-release wget && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Enable TimescaleDB in PostgreSQL shared_preload_libraries
RUN echo "shared_preload_libraries = 'timescaledb'" >> /usr/share/postgresql/postgresql.conf.sample
```

**Per-task validation:**
- Verify Dockerfile syntax is valid (no broken `RUN` commands)
- `docker build ./db -t vtv-db-test` builds successfully (run only if Docker is available)

---

### Task 2: Add Retention Configuration Settings
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add TimescaleDB retention and compression settings to the `Settings` class. Insert after the `db_pool_recycle` setting (around line 145):

```python
# Historical position storage (TimescaleDB)
position_history_enabled: bool = True
position_history_retention_days: int = 90
position_history_compression_after_days: int = 7
position_history_batch_size: int = 500
```

These control:
- `position_history_enabled` — master switch, allows disabling DB writes without stopping the poller
- `position_history_retention_days` — auto-drop data older than N days (default 90, matches GDPR retention)
- `position_history_compression_after_days` — compress chunks older than N days (10-20x space savings)
- `position_history_batch_size` — max records per batch insert (guards against memory spikes)

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py`
- `uv run mypy app/core/config.py`

---

### Task 3: Create Vehicle Position History Model
**File:** `app/transit/models.py` (create new)
**Action:** CREATE

Create the SQLAlchemy model for the `vehicle_positions` hypertable. This table does NOT use `TimestampMixin` because its primary time column is `recorded_at` (when the position was measured), not `created_at`/`updated_at`.

```python
"""SQLAlchemy models for historical vehicle position storage.

The vehicle_positions table is converted to a TimescaleDB hypertable
in the Alembic migration, enabling automatic time-based partitioning,
compression policies, and continuous aggregates.
"""

import datetime

from sqlalchemy import Float, Index, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VehiclePositionRecord(Base):
    """A single historical vehicle position record.

    Stored in a TimescaleDB hypertable partitioned by recorded_at.
    Each row represents one position update from a GTFS-RT poll cycle.

    Attributes:
        id: Auto-incrementing primary key.
        recorded_at: Timestamp when the position was measured (UTC, from GTFS-RT).
        feed_id: Source feed identifier (e.g., "riga").
        vehicle_id: Fleet vehicle identifier (e.g., "4521").
        route_id: GTFS route identifier.
        route_short_name: Human-readable route number (e.g., "22").
        trip_id: GTFS trip identifier, if available.
        latitude: WGS84 latitude.
        longitude: WGS84 longitude.
        bearing: Compass heading in degrees (0-360).
        speed_kmh: Speed in km/h.
        delay_seconds: Schedule deviation in seconds (positive=late).
        current_status: GTFS-RT vehicle stop status.
    """

    __tablename__ = "vehicle_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        "recorded_at",
        nullable=False,
        index=True,
    )
    feed_id: Mapped[str] = mapped_column(String(50), nullable=False)
    vehicle_id: Mapped[str] = mapped_column(String(100), nullable=False)
    route_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    route_short_name: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    trip_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    bearing: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    delay_seconds: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    current_status: Mapped[str] = mapped_column(String(20), nullable=False, default="IN_TRANSIT_TO")

    __table_args__ = (
        Index("ix_vehicle_positions_vehicle_time", "vehicle_id", "recorded_at"),
        Index("ix_vehicle_positions_route_time", "route_id", "recorded_at"),
        Index("ix_vehicle_positions_feed_time", "feed_id", "recorded_at"),
    )
```

**Per-task validation:**
- `uv run ruff format app/transit/models.py`
- `uv run ruff check --fix app/transit/models.py`
- `uv run mypy app/transit/models.py`

---

### Task 4: Create Alembic Migration for Hypertable
**File:** `alembic/versions/[auto-generated]_add_vehicle_positions_hypertable.py` (create new)
**Action:** CREATE

Create an Alembic migration that:
1. Creates the `vehicle_positions` table
2. Converts it to a TimescaleDB hypertable
3. Adds compression policy (compress chunks older than `position_history_compression_after_days`)
4. Adds retention policy (drop chunks older than `position_history_retention_days`)

**If database is running:**
```bash
uv run alembic revision --autogenerate -m "add vehicle_positions hypertable"
```
Then manually add the TimescaleDB-specific SQL after the `create_table` call.

**If database is NOT running (manual fallback):**
Create the migration file manually with these operations:

```python
"""add vehicle_positions hypertable

Revision ID: [generate]
Revises: [latest head]
"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # Create the table
    op.create_table(
        "vehicle_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.Column("current_status", sa.String(20), nullable=False, server_default="IN_TRANSIT_TO"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicle_positions_recorded_at", "vehicle_positions", ["recorded_at"])
    op.create_index("ix_vehicle_positions_vehicle_time", "vehicle_positions", ["vehicle_id", "recorded_at"])
    op.create_index("ix_vehicle_positions_route_time", "vehicle_positions", ["route_id", "recorded_at"])
    op.create_index("ix_vehicle_positions_feed_time", "vehicle_positions", ["feed_id", "recorded_at"])

    # Convert to TimescaleDB hypertable
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.execute(
        "SELECT create_hypertable('vehicle_positions', 'recorded_at', "
        "chunk_time_interval => INTERVAL '1 day', "
        "migrate_data => true)"
    )

    # Compression policy: compress chunks older than 7 days
    op.execute(
        "ALTER TABLE vehicle_positions SET ("
        "timescaledb.compress, "
        "timescaledb.compress_segmentby = 'feed_id, vehicle_id, route_id', "
        "timescaledb.compress_orderby = 'recorded_at DESC'"
        ")"
    )
    op.execute(
        "SELECT add_compression_policy('vehicle_positions', INTERVAL '7 days')"
    )

    # Retention policy: drop chunks older than 90 days
    op.execute(
        "SELECT add_retention_policy('vehicle_positions', INTERVAL '90 days')"
    )


def downgrade() -> None:
    # Remove policies before dropping
    op.execute("SELECT remove_retention_policy('vehicle_positions', if_exists => true)")
    op.execute("SELECT remove_compression_policy('vehicle_positions', if_not_exists => true)")
    op.drop_table("vehicle_positions")
```

**Per-task validation:**
- `uv run ruff format alembic/versions/*vehicle_positions*.py`
- `uv run ruff check --fix alembic/versions/*vehicle_positions*.py`
- If DB is running: `uv run alembic upgrade head`

---

### Task 5: Add History Schemas
**File:** `app/transit/schemas.py` (modify existing)
**Action:** UPDATE

Add response schemas for historical position queries. Append after the existing `VehiclePositionsResponse` class:

```python
class HistoricalPosition(BaseModel):
    """A single historical position data point."""

    model_config = ConfigDict(strict=True)

    recorded_at: str
    vehicle_id: str
    route_id: str
    route_short_name: str
    latitude: float
    longitude: float
    bearing: float | None = None
    speed_kmh: float | None = None
    delay_seconds: int = 0
    current_status: str
    feed_id: str = ""


class VehicleHistoryResponse(BaseModel):
    """Response for vehicle position history query."""

    model_config = ConfigDict(strict=True)

    vehicle_id: str
    count: int
    positions: list[HistoricalPosition]
    from_time: str
    to_time: str


class RouteDelayTrendPoint(BaseModel):
    """A single data point in a delay trend time series."""

    model_config = ConfigDict(strict=True)

    time_bucket: str
    avg_delay_seconds: float
    min_delay_seconds: float
    max_delay_seconds: float
    sample_count: int


class RouteDelayTrendResponse(BaseModel):
    """Response for route delay trend query."""

    model_config = ConfigDict(strict=True)

    route_id: str
    route_short_name: str
    interval_minutes: int
    count: int
    data_points: list[RouteDelayTrendPoint]
    from_time: str
    to_time: str
```

**Per-task validation:**
- `uv run ruff format app/transit/schemas.py`
- `uv run ruff check --fix app/transit/schemas.py`
- `uv run mypy app/transit/schemas.py`

---

### Task 6: Create History Repository
**File:** `app/transit/repository.py` (create new)
**Action:** CREATE

Create the repository for historical position database queries. This handles both writes (batch insert from poller) and reads (history queries for API).

```python
"""Repository for historical vehicle position storage and queries.

Handles batch inserts from the poller and time-range queries for
the REST API. All queries use parameterized SQLAlchemy expressions.
"""

import datetime

from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.transit.models import VehiclePositionRecord

logger = get_logger(__name__)


async def batch_insert_positions(
    db: AsyncSession,
    records: list[dict[str, object]],
) -> int:
    """Batch insert vehicle position records.

    Args:
        db: Async database session.
        records: List of position dicts matching VehiclePositionRecord columns.

    Returns:
        Number of records inserted.
    """
    if not records:
        return 0

    stmt = insert(VehiclePositionRecord)
    await db.execute(stmt, records)
    await db.commit()
    return len(records)


async def get_vehicle_history(
    db: AsyncSession,
    vehicle_id: str,
    from_time: datetime.datetime,
    to_time: datetime.datetime,
    limit: int = 1000,
) -> list[VehiclePositionRecord]:
    """Get position history for a single vehicle within a time range.

    Args:
        db: Async database session.
        vehicle_id: Fleet vehicle identifier.
        from_time: Start of time range (inclusive).
        to_time: End of time range (inclusive).
        limit: Maximum records to return.

    Returns:
        List of VehiclePositionRecord ordered by recorded_at ASC.
    """
    stmt = (
        select(VehiclePositionRecord)
        .where(
            VehiclePositionRecord.vehicle_id == vehicle_id,
            VehiclePositionRecord.recorded_at >= from_time,
            VehiclePositionRecord.recorded_at <= to_time,
        )
        .order_by(VehiclePositionRecord.recorded_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_route_delay_trend(
    db: AsyncSession,
    route_id: str,
    from_time: datetime.datetime,
    to_time: datetime.datetime,
    interval_minutes: int = 60,
) -> list[dict[str, object]]:
    """Get aggregated delay trend for a route using time_bucket.

    Uses TimescaleDB's time_bucket function for efficient time-series
    aggregation. Falls back to date_trunc if TimescaleDB is unavailable.

    Args:
        db: Async database session.
        route_id: GTFS route identifier.
        from_time: Start of time range.
        to_time: End of time range.
        interval_minutes: Bucket size in minutes (default 60).

    Returns:
        List of dicts with time_bucket, avg/min/max delay, sample_count.
    """
    interval_str = f"{interval_minutes} minutes"
    stmt = text(
        "SELECT "
        "  time_bucket(:interval, recorded_at) AS time_bucket, "
        "  AVG(delay_seconds)::float AS avg_delay, "
        "  MIN(delay_seconds)::int AS min_delay, "
        "  MAX(delay_seconds)::int AS max_delay, "
        "  COUNT(*)::int AS sample_count "
        "FROM vehicle_positions "
        "WHERE route_id = :route_id "
        "  AND recorded_at >= :from_time "
        "  AND recorded_at <= :to_time "
        "GROUP BY time_bucket "
        "ORDER BY time_bucket ASC"
    ).bindparams(
        interval=interval_str,
        route_id=route_id,
        from_time=from_time,
        to_time=to_time,
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "time_bucket": row[0].isoformat() if row[0] else "",
            "avg_delay": round(float(row[1]), 1) if row[1] is not None else 0.0,
            "min_delay": int(row[2]) if row[2] is not None else 0,
            "max_delay": int(row[3]) if row[3] is not None else 0,
            "sample_count": int(row[4]) if row[4] is not None else 0,
        }
        for row in rows
    ]
```

**Per-task validation:**
- `uv run ruff format app/transit/repository.py`
- `uv run ruff check --fix app/transit/repository.py`
- `uv run mypy app/transit/repository.py`

---

### Task 7: Extend Poller to Write to Database
**File:** `app/transit/poller.py` (modify existing)
**Action:** UPDATE

Modify `FeedPoller.poll_once()` to batch-insert enriched positions into the database alongside Redis writes. The DB write must be non-blocking — failures are logged but never stop the poller or the Redis write path.

**Changes to make:**

1. Add import at top of file:
```python
from app.transit.repository import batch_insert_positions
```

2. After the existing Redis pipeline execute (line ~104), add a new block to write to the database. Insert after the `await pipe.execute()` try/except block and before the Pub/Sub publish block:

```python
        # Write to historical position storage (TimescaleDB)
        if self._settings.position_history_enabled and count > 0:
            try:
                if self._db_session_factory is None:
                    from app.core.database import get_db_context
                    self._db_session_factory = get_db_context
                async with self._db_session_factory() as db_session:
                    db_records: list[dict[str, object]] = []
                    for ev in enriched_vehicles:
                        ts_str = str(ev.get("timestamp", ""))
                        if not ts_str:
                            continue
                        db_records.append({
                            "recorded_at": ts_str,
                            "feed_id": str(ev.get("feed_id", "")),
                            "vehicle_id": str(ev.get("vehicle_id", "")),
                            "route_id": str(ev.get("route_id", "")),
                            "route_short_name": str(ev.get("route_short_name", "")),
                            "trip_id": ev.get("trip_id") if ev.get("trip_id") else None,
                            "latitude": float(ev.get("latitude", 0)),
                            "longitude": float(ev.get("longitude", 0)),
                            "bearing": float(ev["bearing"]) if ev.get("bearing") is not None else None,
                            "speed_kmh": float(ev["speed_kmh"]) if ev.get("speed_kmh") is not None else None,
                            "delay_seconds": int(ev.get("delay_seconds", 0)),
                            "current_status": str(ev.get("current_status", "IN_TRANSIT_TO")),
                        })
                    if db_records:
                        inserted = await batch_insert_positions(db_session, db_records)
                        logger.debug(
                            "transit.poller.history_write_completed",
                            feed_id=feed_id,
                            records_inserted=inserted,
                        )
            except Exception as e:
                # History write failure must NEVER block the poller
                logger.warning(
                    "transit.poller.history_write_failed",
                    feed_id=feed_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
```

**Per-task validation:**
- `uv run ruff format app/transit/poller.py`
- `uv run ruff check --fix app/transit/poller.py`
- `uv run mypy app/transit/poller.py`

---

### Task 8: Add History Query Methods to Service
**File:** `app/transit/service.py` (modify existing)
**Action:** UPDATE

Add methods to `TransitService` for querying historical data. These methods accept a DB session and delegate to the repository.

1. Add imports at top:
```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.transit.repository import get_route_delay_trend, get_vehicle_history
from app.transit.schemas import (
    HistoricalPosition,
    RouteDelayTrendPoint,
    RouteDelayTrendResponse,
    VehicleHistoryResponse,
)
```

2. Add two new methods to the `TransitService` class (after `_fetch_direct`):

```python
    async def get_vehicle_history(
        self,
        db: AsyncSession,
        vehicle_id: str,
        from_time: datetime,
        to_time: datetime,
        limit: int = 1000,
    ) -> VehicleHistoryResponse:
        """Get historical positions for a vehicle.

        Args:
            db: Async database session.
            vehicle_id: Fleet vehicle identifier.
            from_time: Start of time range (UTC).
            to_time: End of time range (UTC).
            limit: Maximum number of positions to return.

        Returns:
            VehicleHistoryResponse with ordered position history.
        """
        records = await get_vehicle_history(db, vehicle_id, from_time, to_time, limit)
        positions = [
            HistoricalPosition(
                recorded_at=r.recorded_at.isoformat(),
                vehicle_id=r.vehicle_id,
                route_id=r.route_id,
                route_short_name=r.route_short_name,
                latitude=r.latitude,
                longitude=r.longitude,
                bearing=r.bearing,
                speed_kmh=r.speed_kmh,
                delay_seconds=r.delay_seconds,
                current_status=r.current_status,
                feed_id=r.feed_id,
            )
            for r in records
        ]
        return VehicleHistoryResponse(
            vehicle_id=vehicle_id,
            count=len(positions),
            positions=positions,
            from_time=from_time.isoformat(),
            to_time=to_time.isoformat(),
        )

    async def get_route_delay_trend(
        self,
        db: AsyncSession,
        route_id: str,
        from_time: datetime,
        to_time: datetime,
        interval_minutes: int = 60,
    ) -> RouteDelayTrendResponse:
        """Get aggregated delay trend for a route.

        Args:
            db: Async database session.
            route_id: GTFS route identifier.
            from_time: Start of time range (UTC).
            to_time: End of time range (UTC).
            interval_minutes: Time bucket size in minutes.

        Returns:
            RouteDelayTrendResponse with time-bucketed delay data.
        """
        raw_points = await get_route_delay_trend(
            db, route_id, from_time, to_time, interval_minutes
        )
        from app.core.agents.tools.transit.static_store import get_static_store
        from app.core.database import get_db_context

        static = await get_static_store(get_db_context, self._settings)
        route_short_name = static.get_route_name(route_id)

        data_points = [
            RouteDelayTrendPoint(
                time_bucket=str(p["time_bucket"]),
                avg_delay_seconds=float(p["avg_delay"]),
                min_delay_seconds=int(p["min_delay"]),
                max_delay_seconds=int(p["max_delay"]),
                sample_count=int(p["sample_count"]),
            )
            for p in raw_points
        ]
        return RouteDelayTrendResponse(
            route_id=route_id,
            route_short_name=route_short_name,
            interval_minutes=interval_minutes,
            count=len(data_points),
            data_points=data_points,
            from_time=from_time.isoformat(),
            to_time=to_time.isoformat(),
        )
```

Note: Import `datetime` from the `datetime` module is already imported at line 11 as `from datetime import UTC, datetime`.

**Per-task validation:**
- `uv run ruff format app/transit/service.py`
- `uv run ruff check --fix app/transit/service.py`
- `uv run mypy app/transit/service.py`

---

### Task 9: Add History REST Endpoints
**File:** `app/transit/routes.py` (modify existing)
**Action:** UPDATE

Add two new endpoints for historical position queries. These follow the same patterns as existing transit and analytics endpoints.

1. Add imports:
```python
import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.core.database import get_db
from app.transit.schemas import (
    RouteDelayTrendResponse,
    VehicleHistoryResponse,
    VehiclePositionsResponse,
)
```

Remove the existing individual import of `VehiclePositionsResponse` since it's now included in the grouped import.

2. Add two new endpoints after the existing `get_feeds` endpoint:

```python
@router.get("/vehicles/{vehicle_id}/history", response_model=VehicleHistoryResponse)
@limiter.limit("10/minute")
async def get_vehicle_history(
    request: Request,
    vehicle_id: str,
    from_time: str = Query(  # noqa: B008
        ...,
        max_length=30,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
        description="ISO 8601 start time (UTC)",
    ),
    to_time: str = Query(  # noqa: B008
        ...,
        max_length=30,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
        description="ISO 8601 end time (UTC)",
    ),
    limit: int = Query(1000, ge=1, le=10000),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(require_role(["admin", "dispatcher", "editor"])),  # noqa: B008
) -> VehicleHistoryResponse:
    """Get historical positions for a specific vehicle within a time range.

    Requires admin, dispatcher, or editor role. Rate limited to 10/minute.

    Args:
        request: HTTP request (rate limiting).
        vehicle_id: Fleet vehicle identifier.
        from_time: ISO 8601 start time (UTC).
        to_time: ISO 8601 end time (UTC).
        limit: Maximum positions to return (1-10000, default 1000).
        db: Async database session.

    Returns:
        VehicleHistoryResponse with ordered position history.
    """
    _ = request
    logger.info(
        "transit.api.vehicle_history_requested",
        vehicle_id=vehicle_id,
        from_time=from_time,
        to_time=to_time,
    )
    from_dt = dt.datetime.fromisoformat(from_time).replace(tzinfo=dt.UTC)
    to_dt = dt.datetime.fromisoformat(to_time).replace(tzinfo=dt.UTC)

    service = get_transit_service()
    return await service.get_vehicle_history(db, vehicle_id, from_dt, to_dt, limit)


@router.get("/routes/{route_id}/delay-trend", response_model=RouteDelayTrendResponse)
@limiter.limit("10/minute")
async def get_route_delay_trend(
    request: Request,
    route_id: str,
    from_time: str = Query(  # noqa: B008
        ...,
        max_length=30,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
        description="ISO 8601 start time (UTC)",
    ),
    to_time: str = Query(  # noqa: B008
        ...,
        max_length=30,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
        description="ISO 8601 end time (UTC)",
    ),
    interval_minutes: int = Query(60, ge=5, le=1440),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _current_user: User = Depends(require_role(["admin", "dispatcher", "editor"])),  # noqa: B008
) -> RouteDelayTrendResponse:
    """Get aggregated delay trend for a route over a time range.

    Uses TimescaleDB time_bucket for efficient time-series aggregation.
    Rate limited to 10/minute.

    Args:
        request: HTTP request (rate limiting).
        route_id: GTFS route identifier.
        from_time: ISO 8601 start time (UTC).
        to_time: ISO 8601 end time (UTC).
        interval_minutes: Time bucket size (5-1440 minutes, default 60).
        db: Async database session.

    Returns:
        RouteDelayTrendResponse with time-bucketed delay data.
    """
    _ = request
    logger.info(
        "transit.api.route_delay_trend_requested",
        route_id=route_id,
        from_time=from_time,
        to_time=to_time,
        interval_minutes=interval_minutes,
    )
    from_dt = dt.datetime.fromisoformat(from_time).replace(tzinfo=dt.UTC)
    to_dt = dt.datetime.fromisoformat(to_time).replace(tzinfo=dt.UTC)

    service = get_transit_service()
    return await service.get_route_delay_trend(
        db, route_id, from_dt, to_dt, interval_minutes
    )
```

**Per-task validation:**
- `uv run ruff format app/transit/routes.py`
- `uv run ruff check --fix app/transit/routes.py`
- `uv run mypy app/transit/routes.py`

---

### Task 10: Create Unit Tests for Models and Repository
**File:** `app/transit/tests/test_position_history.py` (create new)
**Action:** CREATE

Create unit tests for the model and repository. Use mocked DB sessions for unit tests. Mark integration tests with `@pytest.mark.integration`.

```python
"""Tests for historical vehicle position storage."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.transit.models import VehiclePositionRecord
from app.transit.schemas import (
    HistoricalPosition,
    RouteDelayTrendPoint,
    RouteDelayTrendResponse,
    VehicleHistoryResponse,
)


class TestVehiclePositionRecordModel:
    """Tests for the VehiclePositionRecord SQLAlchemy model."""

    def test_tablename(self) -> None:
        assert VehiclePositionRecord.__tablename__ == "vehicle_positions"

    def test_required_columns_exist(self) -> None:
        columns = {c.name for c in VehiclePositionRecord.__table__.columns}
        required = {"id", "recorded_at", "feed_id", "vehicle_id", "route_id",
                     "latitude", "longitude", "delay_seconds", "current_status"}
        assert required.issubset(columns)

    def test_optional_columns_exist(self) -> None:
        columns = {c.name for c in VehiclePositionRecord.__table__.columns}
        optional = {"bearing", "speed_kmh", "trip_id", "route_short_name"}
        assert optional.issubset(columns)


class TestHistoricalPositionSchema:
    """Tests for history response schemas."""

    def test_historical_position_creation(self) -> None:
        pos = HistoricalPosition(
            recorded_at="2026-03-07T12:00:00+00:00",
            vehicle_id="4521",
            route_id="22",
            route_short_name="22",
            latitude=56.9496,
            longitude=24.1052,
            delay_seconds=45,
            current_status="IN_TRANSIT_TO",
        )
        assert pos.vehicle_id == "4521"
        assert pos.delay_seconds == 45

    def test_vehicle_history_response(self) -> None:
        resp = VehicleHistoryResponse(
            vehicle_id="4521",
            count=0,
            positions=[],
            from_time="2026-03-07T00:00:00+00:00",
            to_time="2026-03-07T23:59:59+00:00",
        )
        assert resp.count == 0
        assert resp.vehicle_id == "4521"

    def test_route_delay_trend_response(self) -> None:
        point = RouteDelayTrendPoint(
            time_bucket="2026-03-07T12:00:00+00:00",
            avg_delay_seconds=30.5,
            min_delay_seconds=-10,
            max_delay_seconds=120,
            sample_count=42,
        )
        resp = RouteDelayTrendResponse(
            route_id="22",
            route_short_name="22",
            interval_minutes=60,
            count=1,
            data_points=[point],
            from_time="2026-03-07T00:00:00+00:00",
            to_time="2026-03-07T23:59:59+00:00",
        )
        assert resp.count == 1
        assert resp.data_points[0].sample_count == 42
```

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_position_history.py`
- `uv run ruff check --fix app/transit/tests/test_position_history.py`
- `uv run pytest app/transit/tests/test_position_history.py -v`

---

### Task 11: Create Unit Tests for Poller History Write
**File:** `app/transit/tests/test_poller_history.py` (create new)
**Action:** CREATE

Test that the poller correctly writes to the database when `position_history_enabled` is True and gracefully handles failures.

```python
"""Tests for poller historical position write path."""

import json
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.transit.poller import FeedPoller
from app.core.config import TransitFeedConfig


def _make_feed_config() -> TransitFeedConfig:
    return TransitFeedConfig(
        feed_id="test",
        operator_name="Test Operator",
        rt_vehicle_positions_url="http://test/vp.pb",
        rt_trip_updates_url="http://test/tu.pb",
        static_url="http://test/gtfs.zip",
    )


class TestPollerHistoryWrite:
    """Tests for the poller's historical position write path."""

    @pytest.mark.asyncio
    async def test_history_write_disabled(self) -> None:
        """When position_history_enabled is False, no DB write occurs."""
        settings = MagicMock()
        settings.position_history_enabled = False
        settings.redis_vehicle_ttl_seconds = 120
        settings.poller_enabled = True

        poller = FeedPoller(
            feed_config=_make_feed_config(),
            settings=settings,
        )

        mock_redis = AsyncMock()
        mock_redis.pipeline.return_value = AsyncMock()
        mock_redis.pipeline.return_value.execute = AsyncMock(return_value=[])
        mock_redis.pipeline.return_value.set = MagicMock()
        mock_redis.pipeline.return_value.delete = MagicMock()
        mock_redis.pipeline.return_value.sadd = MagicMock()
        mock_redis.pipeline.return_value.expire = MagicMock()
        mock_redis.publish = AsyncMock()

        with patch.object(poller, "_rt_client") as mock_rt, \
             patch("app.transit.poller.get_static_store") as mock_store:
            mock_rt.fetch_vehicle_positions = AsyncMock(return_value=[])
            mock_rt.fetch_trip_updates = AsyncMock(return_value=[])
            mock_store.return_value = MagicMock()

            result = await poller.poll_once(mock_redis)

        assert result == 0

    @pytest.mark.asyncio
    async def test_history_write_failure_does_not_block_poller(self) -> None:
        """DB write failure must not prevent Redis writes or crash the poller."""
        settings = MagicMock()
        settings.position_history_enabled = True
        settings.redis_vehicle_ttl_seconds = 120
        settings.poller_enabled = True

        poller = FeedPoller(
            feed_config=_make_feed_config(),
            settings=settings,
        )

        # Mock a DB session factory that raises
        @asynccontextmanager
        async def failing_db() -> AsyncIterator[AsyncMock]:
            raise RuntimeError("DB unavailable")
            yield AsyncMock()  # pragma: no cover

        poller._db_session_factory = failing_db  # type: ignore[assignment]

        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.set = MagicMock()
        mock_pipeline.delete = MagicMock()
        mock_pipeline.sadd = MagicMock()
        mock_pipeline.expire = MagicMock()
        mock_pipeline.execute = AsyncMock(return_value=[])
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis.publish = AsyncMock()

        mock_vp = MagicMock()
        mock_vp.vehicle_id = "4521"
        mock_vp.route_id = "22"
        mock_vp.trip_id = None
        mock_vp.latitude = 56.9496
        mock_vp.longitude = 24.1052
        mock_vp.bearing = 180.0
        mock_vp.speed = 12.0
        mock_vp.timestamp = 1709827200
        mock_vp.current_status = "IN_TRANSIT_TO"
        mock_vp.stop_id = None
        mock_vp.current_stop_sequence = None

        with patch.object(poller, "_rt_client") as mock_rt, \
             patch("app.transit.poller.get_static_store") as mock_store:
            mock_rt.fetch_vehicle_positions = AsyncMock(return_value=[mock_vp])
            mock_rt.fetch_trip_updates = AsyncMock(return_value=[])
            mock_static = MagicMock()
            mock_static.get_trip_route_id.return_value = None
            mock_static.get_route_name.return_value = "22"
            mock_static.routes = {"22": MagicMock(route_type=3)}
            mock_static.get_stop_name.return_value = None
            mock_store.return_value = mock_static

            result = await poller.poll_once(mock_redis)

        # Redis write should still succeed
        assert result == 1
        mock_pipeline.execute.assert_awaited_once()
```

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_poller_history.py`
- `uv run ruff check --fix app/transit/tests/test_poller_history.py`
- `uv run pytest app/transit/tests/test_poller_history.py -v`

---

### Task 12: Create Unit Tests for History Endpoints
**File:** `app/transit/tests/test_history_routes.py` (create new)
**Action:** CREATE

Test the new REST endpoints with mocked service. Follow the pattern from `app/transit/tests/test_routes.py`.

```python
"""Tests for historical position REST endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import get_current_user
from app.core.database import get_db


@pytest.fixture
def client() -> TestClient:
    """Test client with mocked auth and DB."""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.role = "admin"

    async def mock_get_user() -> MagicMock:
        return mock_user

    async def mock_get_db_override():  # type: ignore[no-untyped-def]
        yield AsyncMock()

    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = mock_get_user
    app.dependency_overrides[get_db] = mock_get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = saved_overrides


class TestVehicleHistoryEndpoint:
    """Tests for GET /api/v1/transit/vehicles/{id}/history."""

    def test_vehicle_history_requires_time_params(self, client: TestClient) -> None:
        response = client.get("/api/v1/transit/vehicles/4521/history")
        assert response.status_code == 422

    @patch("app.transit.routes.get_transit_service")
    def test_vehicle_history_success(
        self, mock_service_fn: MagicMock, client: TestClient
    ) -> None:
        mock_service = MagicMock()
        mock_service.get_vehicle_history = AsyncMock(
            return_value=MagicMock(
                model_dump=MagicMock(return_value={
                    "vehicle_id": "4521",
                    "count": 0,
                    "positions": [],
                    "from_time": "2026-03-07T00:00:00+00:00",
                    "to_time": "2026-03-07T23:59:59+00:00",
                })
            )
        )
        mock_service_fn.return_value = mock_service

        response = client.get(
            "/api/v1/transit/vehicles/4521/history",
            params={
                "from_time": "2026-03-07T00:00:00",
                "to_time": "2026-03-07T23:59:59",
            },
        )
        assert response.status_code == 200


class TestRouteDelayTrendEndpoint:
    """Tests for GET /api/v1/transit/routes/{id}/delay-trend."""

    def test_delay_trend_requires_time_params(self, client: TestClient) -> None:
        response = client.get("/api/v1/transit/routes/22/delay-trend")
        assert response.status_code == 422

    @patch("app.transit.routes.get_transit_service")
    def test_delay_trend_success(
        self, mock_service_fn: MagicMock, client: TestClient
    ) -> None:
        mock_service = MagicMock()
        mock_service.get_route_delay_trend = AsyncMock(
            return_value=MagicMock(
                model_dump=MagicMock(return_value={
                    "route_id": "22",
                    "route_short_name": "22",
                    "interval_minutes": 60,
                    "count": 0,
                    "data_points": [],
                    "from_time": "2026-03-07T00:00:00+00:00",
                    "to_time": "2026-03-07T23:59:59+00:00",
                })
            )
        )
        mock_service_fn.return_value = mock_service

        response = client.get(
            "/api/v1/transit/routes/22/delay-trend",
            params={
                "from_time": "2026-03-07T00:00:00",
                "to_time": "2026-03-07T23:59:59",
            },
        )
        assert response.status_code == 200
```

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_history_routes.py`
- `uv run ruff check --fix app/transit/tests/test_history_routes.py`
- `uv run pytest app/transit/tests/test_history_routes.py -v`

---

## Migration

**Prefer autogenerate when database is running:**
```bash
uv run alembic revision --autogenerate -m "add vehicle_positions hypertable"
uv run alembic upgrade head
```

Then manually add TimescaleDB-specific SQL to the generated migration (CREATE EXTENSION, create_hypertable, compression policy, retention policy). See Task 4 for exact SQL.

**When database is NOT running:** Create the migration manually following the template in Task 4. Column specs:
- `id`: Integer, PK, autoincrement
- `recorded_at`: DateTime(timezone=True), NOT NULL, indexed
- `feed_id`: String(50), NOT NULL
- `vehicle_id`: String(100), NOT NULL
- `route_id`: String(100), NOT NULL, default=""
- `route_short_name`: String(50), NOT NULL, default=""
- `trip_id`: String(200), NULL
- `latitude`: Float, NOT NULL
- `longitude`: Float, NOT NULL
- `bearing`: Float, NULL
- `speed_kmh`: Float, NULL
- `delay_seconds`: SmallInteger, NOT NULL, default=0
- `current_status`: String(20), NOT NULL, default="IN_TRANSIT_TO"

## Logging Events

- `transit.poller.history_write_completed` — After successful batch insert (debug level, per poll cycle)
- `transit.poller.history_write_failed` — When DB write fails (warning level, includes error details)
- `transit.api.vehicle_history_requested` — When vehicle history endpoint is called
- `transit.api.route_delay_trend_requested` — When delay trend endpoint is called

## Testing Strategy

### Unit Tests
**Location:** `app/transit/tests/test_position_history.py`
- VehiclePositionRecord model — table name, required/optional columns
- Schema creation — HistoricalPosition, VehicleHistoryResponse, RouteDelayTrendResponse
- Schema validation — required fields, defaults

**Location:** `app/transit/tests/test_poller_history.py`
- Poller with history disabled — no DB write attempted
- Poller with history enabled + DB failure — Redis still succeeds, no crash
- Poller with history enabled + success — records inserted

**Location:** `app/transit/tests/test_history_routes.py`
- Vehicle history endpoint — requires time params (422 without), succeeds with valid params
- Route delay trend endpoint — requires time params (422 without), succeeds with valid params
- Auth check — endpoints require authentication (covered by TestAllEndpointsRequireAuth convention test)

### Integration Tests
**Mark with:** `@pytest.mark.integration`
- Round-trip: write positions via repository, read back via repository (requires TimescaleDB)
- Delay trend aggregation with time_bucket (requires TimescaleDB)

### Edge Cases
- Empty time range — returns 0 positions
- Very large time range — respects limit parameter
- Future time range — returns 0 positions
- Invalid ISO 8601 format — FastAPI validation returns 422
- Poller runs when DB is completely unavailable — Redis path unaffected

## Acceptance Criteria

This feature is complete when:
- [ ] TimescaleDB extension installs in the Docker database image
- [ ] `vehicle_positions` hypertable created with Alembic migration
- [ ] Compression policy active (chunks >7 days compressed automatically)
- [ ] Retention policy active (chunks >90 days dropped automatically)
- [ ] Poller writes positions to DB alongside Redis (when `position_history_enabled=True`)
- [ ] Poller gracefully handles DB write failures without affecting Redis path
- [ ] `GET /api/v1/transit/vehicles/{id}/history` returns position history with time range
- [ ] `GET /api/v1/transit/routes/{id}/delay-trend` returns aggregated delay data
- [ ] Both endpoints require authentication and role-based access (admin/dispatcher/editor)
- [ ] Both endpoints validate input parameters (ISO 8601 format, max_length, range constraints)
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + integration)
- [ ] Structured logging follows `domain.component.action_state` pattern
- [ ] No type suppressions added (except existing pyright directives on transit files)
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order (Tasks 1-12)
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/transit/tests/test_position_history.py app/transit/tests/test_poller_history.py app/transit/tests/test_history_routes.py -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- **Shared utilities used:** `app.core.database.Base`, `app.core.database.get_db`, `app.core.database.get_db_context`, `app.core.logging.get_logger`, `app.core.config.Settings`
- **Core modules used:** `app.auth.dependencies.get_current_user`, `app.auth.dependencies.require_role`, `app.core.rate_limit.limiter`
- **New dependencies:** None — TimescaleDB is a PostgreSQL extension, not a Python package. SQLAlchemy's `text()` handles `time_bucket()` queries directly.
- **New env vars:**
  - `POSITION_HISTORY_ENABLED` (bool, default `True`) — Master switch for historical writes
  - `POSITION_HISTORY_RETENTION_DAYS` (int, default `90`) — Auto-drop data after N days
  - `POSITION_HISTORY_COMPRESSION_AFTER_DAYS` (int, default `7`) — Compress chunks after N days
  - `POSITION_HISTORY_BATCH_SIZE` (int, default `500`) — Max records per batch insert

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules from `_shared/python-anti-patterns.md`.

**Feature-specific pitfalls:**
- **TimescaleDB `time_bucket()` is not available in plain PostgreSQL** — Integration tests that use `time_bucket()` must be marked `@pytest.mark.integration` and will only pass when the DB has TimescaleDB enabled
- **Poller DB write must NEVER block Redis** — The try/except around the history write block must catch `Exception` broadly and log a warning (not error), never re-raise
- **`datetime` import shadowing** — `app/transit/service.py` already imports `from datetime import UTC, datetime`. The new history methods also need `datetime`. Use the existing import; in routes.py use `import datetime as dt` to avoid the shadow (anti-pattern #39)
- **`require_role()` returns a dependency, not `get_current_user`** — History endpoints use `require_role(["admin", "dispatcher", "editor"])` for RBAC, which provides stricter access than `get_current_user` alone
- **`text()` queries bypass SQLAlchemy's type checking** — The `time_bucket` query uses `text()` because TimescaleDB functions aren't in SQLAlchemy's dialect. Parameters are bound via `.bindparams()` to prevent SQL injection
- **Docker image rebuild required** — After modifying `db/Dockerfile`, the database container must be rebuilt: `docker compose build db`

## Notes

- **Storage estimates:** At 500 vehicles × 6 updates/minute × 60 minutes × 24 hours = ~4.3M rows/day. With compression after 7 days (~10x reduction), 90-day retention uses approximately 2-4 GB of disk.
- **Future enhancements (not in this plan):**
  - Continuous aggregates for pre-computed hourly/daily rollups (when query load warrants it)
  - Agent tool integration (`get_adherence_report` can query historical data instead of live GTFS-RT)
  - Historical replay endpoint (returns positions at a specific past timestamp for map visualization)
  - Materialized view for "delay by stop, hour, day-of-week" pattern analysis
- **GDPR compliance:** 90-day retention policy aligns with the PRD's GPS data retention limit. The retention policy runs automatically via TimescaleDB's background scheduler.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed the Implementation Plan's TimescaleDB references (`docs/PLANNING/Implementation-Plan.md`)
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order (1-12)
- [ ] Validation commands are executable in this environment
