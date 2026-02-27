# Plan: PostGIS Migration — Replace Haversine with ST_DWithin Spatial Queries

## Feature Metadata
**Feature Type**: Refactor / Infrastructure Enhancement
**Estimated Complexity**: High
**Primary Systems Affected**: stops (model, repository, service, tests), Docker infrastructure, GTFS import/export (indirect via trigger), agent tool (import path)
**Breaking Changes**: None — API contract is fully preserved

## Feature Description

The VTV stops feature currently stores coordinates as plain `Float` columns (`stop_lat`, `stop_lon`) and performs proximity searches using the Haversine formula in Python. The `search_nearby()` method loads ALL active stops into memory (up to 10,000) on every request and filters them one-by-one — an O(n) operation per query. This works for Riga's ~2,000 stops but will not scale to the full Latvia platform (10,000+ stops across multiple cities).

This migration adds PostGIS to the existing PostgreSQL 18 database, introduces a `geometry(Point, 4326)` column on the `stops` table, and replaces the Python Haversine proximity search with PostgreSQL `ST_DWithin` spatial queries backed by a GIST index. The result is sub-millisecond proximity searches regardless of stop count, with zero changes to the REST API contract.

The `pgvector/pgvector:pg18` Docker image runs Debian Bookworm with PostgreSQL 18, and the `postgresql-18-postgis-3` apt package is available in its repositories (verified in the running container). No base image change is needed — just a custom Dockerfile that installs PostGIS on top.

## User Story

As a VTV platform operator
I want spatial queries to use PostGIS instead of Python Haversine
So that proximity searches remain fast as the platform scales from Riga to all of Latvia

## Solution Approach

Add a `geom` column to the `stops` table as a derived column that is automatically synchronized from `stop_lat`/`stop_lon` via a PostgreSQL `BEFORE INSERT OR UPDATE` trigger. This approach preserves full backward compatibility — `stop_lat` and `stop_lon` remain the API-facing source of truth, while `geom` is the spatial index target used only for database queries.

**Approach Decision:**
We chose the **trigger-based sync** approach because:
- Works transparently with bulk_upsert (`INSERT ON CONFLICT DO UPDATE`) — the trigger fires for every row
- No application code changes needed for write paths (GTFS import, create, update)
- Single source of truth: lat/lon fields remain authoritative, geom is always derived
- No risk of sync bugs — the database enforces consistency

**Alternatives Considered:**
- **Application-level sync (set geom in repository)**: Rejected because bulk_upsert uses `pg_insert().values(dict_list)` which can't include SQL function calls in the values list. Would require restructuring all write paths.
- **Replace lat/lon with geometry column entirely**: Rejected because it breaks the existing API contract. Every schema, GTFS import/export, and frontend component reads `stop_lat`/`stop_lon`. The migration effort would be 3x larger with no additional benefit.
- **Generated column**: Rejected because PostgreSQL generated columns don't support PostGIS functions (requires `IMMUTABLE` functions, but `ST_SetSRID(ST_MakePoint(...))` is only `IMMUTABLE` if explicitly cast).

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/stops/models.py` (lines 1-36) — Current Stop model with Float columns for lat/lon
- `app/stops/repository.py` (lines 1-234) — Current repository with NO spatial queries; bulk_upsert at lines 159-196
- `app/stops/service.py` (lines 1-288) — Haversine function at lines 26-47, search_nearby at lines 249-287
- `app/stops/schemas.py` (lines 1-62) — StopNearbyParams at lines 56-62, StopResponse at lines 45-53
- `app/stops/routes.py` (lines 71-85) — nearby_stops endpoint

### Similar Features (Examples to Follow)
- `app/knowledge/models.py` — pgvector column mapping pattern (`embedding = mapped_column(Vector(1024))`)
- `alembic/versions/16befcf37286_initial_schema.py` — Extension creation pattern (`op.execute("CREATE EXTENSION IF NOT EXISTS vector")`)
- `alembic/versions/c7f9d2b03e58_add_gin_index_document_chunks_fulltext.py` — Custom index creation in migration

### Files to Modify
- `docker-compose.yml` (line 2) — Switch `image:` to `build:` for db service
- `pyproject.toml` (line 7-35) — Add geoalchemy2 dependency
- `app/stops/models.py` — Add geom column
- `app/stops/repository.py` — Add search_nearby method with ST_DWithin
- `app/stops/service.py` — Delegate search_nearby to repository, remove Haversine
- `app/core/agents/tools/transit/search_stops.py` — Import Haversine from shared

### Files That Do NOT Need Changes (trigger handles geom sync)
- `app/stops/schemas.py` — API contract preserved, no schema changes
- `app/stops/routes.py` — Endpoint signatures unchanged
- `app/main.py` — No new router registration needed
- `app/schedules/gtfs_import.py` (lines 520-531) — Sets stop_lat/stop_lon, trigger auto-populates geom
- `app/schedules/gtfs_export.py` (lines 213-220) — Reads stop_lat/stop_lon, not geom
- Frontend files — API contract unchanged

## Research Documentation

- [GeoAlchemy2 Docs](https://geoalchemy-2.readthedocs.io/en/latest/) — ORM Tutorial, Spatial Functions → Tasks 4-5
- [PostGIS ST_DWithin](https://postgis.net/docs/ST_DWithin.html) — Returns true if geometries within distance; uses spatial index → Task 7
- [PostGIS ST_Distance](https://postgis.net/docs/ST_Distance.html) — Geography type returns meters directly → Task 7

## Implementation Plan

### Phase 1: Infrastructure (Tasks 1-4) — Docker, dependency, migration
### Phase 2: Core Implementation (Tasks 5-8) — Model, repository, service, shared utils
### Phase 3: Integration & Validation (Tasks 9-12) — Agent tool, tests, full validation

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Create Custom Database Dockerfile
**File:** `db/Dockerfile` (create new)
**Action:** CREATE

Create a Dockerfile that extends the existing pgvector image with PostGIS. Base image is Debian Bookworm with PG 18.2. Packages verified available via `apt-cache search` in running container.

```dockerfile
FROM pgvector/pgvector:pg18

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-18-postgis-3 \
        postgresql-18-postgis-3-scripts && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
```

**Per-task validation:**
- `docker build -t vtv-db-test ./db` — image builds successfully

---

### Task 2: Update Docker Compose to Build Custom DB Image
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

Replace the `image:` directive for the `db` service with a `build:` directive:

**Change:**
```yaml
# BEFORE:
  db:
    image: pgvector/pgvector:pg18

# AFTER:
  db:
    build:
      context: ./db
      dockerfile: Dockerfile
```

All other db service configuration (environment, ports, volumes, healthcheck, security_opt, cap_drop, cap_add, deploy) remains unchanged.

**Per-task validation:**
- `docker compose build db` — builds successfully
- `docker compose up -d db` — starts and passes healthcheck
- `docker exec vtv-db-1 psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS postgis; SELECT PostGIS_Version();"` — returns PostGIS version

---

### Task 3: Add GeoAlchemy2 Dependency
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

1. Run `uv add geoalchemy2>=0.16.0` to add dependency
2. Add mypy override to `pyproject.toml` (geoalchemy2 lacks py.typed):
   ```toml
   [[tool.mypy.overrides]]
   module = "geoalchemy2.*"
   ignore_missing_imports = true
   ```

**Per-task validation:**
- `uv run python -c "import geoalchemy2; print(geoalchemy2.__version__)"` — prints version
- `uv run ruff format pyproject.toml`
- `uv run ruff check --fix pyproject.toml` passes

---

### Task 4: Create Alembic Migration for PostGIS + Geometry Column
**File:** `alembic/versions/XXXX_add_postgis_geometry_to_stops.py` (create new)
**Action:** CREATE

**Preferred:** Use `uv run alembic revision --autogenerate -m "add PostGIS geometry to stops"` then manually add extension/trigger/data population (autogenerate only detects the column, not custom SQL).

**If autogenerate fails:** Create migration manually. Operations **in this exact order**:

**upgrade():**
1. Enable PostGIS extension:
   ```python
   op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
   ```

2. Add geometry column to stops table:
   ```python
   op.add_column(
       "stops",
       sa.Column("geom", Geometry("POINT", srid=4326), nullable=True),
   )
   ```

3. Populate geom from existing lat/lon data:
   ```python
   op.execute("""
       UPDATE stops
       SET geom = ST_SetSRID(ST_MakePoint(stop_lon, stop_lat), 4326)
       WHERE stop_lat IS NOT NULL AND stop_lon IS NOT NULL
   """)
   ```

4. Create GIST spatial index:
   ```python
   op.create_index("idx_stops_geom", "stops", ["geom"], postgresql_using="gist")
   ```

5. Create trigger function for automatic geom sync:
   ```python
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
   ```

6. Create trigger on stops table:
   ```python
   op.execute("""
       CREATE TRIGGER trg_sync_stop_geom
       BEFORE INSERT OR UPDATE OF stop_lat, stop_lon ON stops
       FOR EACH ROW EXECUTE FUNCTION sync_stop_geom()
   """)
   ```

**downgrade():** Drop trigger → drop function → drop index → drop column. Do NOT drop PostGIS extension.

**Required imports:** `from geoalchemy2 import Geometry  # pyright: ignore[reportMissingTypeStubs]` plus standard alembic/sqlalchemy imports.

**Per-task validation:**
- `uv run alembic upgrade head` — migration applies without errors
- `docker exec vtv-db-1 psql -U postgres -d vtv_db -c "SELECT column_name, udt_name FROM information_schema.columns WHERE table_name='stops' AND column_name='geom';"` — shows geom column
- `docker exec vtv-db-1 psql -U postgres -d vtv_db -c "SELECT count(*) FROM stops WHERE geom IS NOT NULL;"` — matches count of stops with lat/lon
- `docker exec vtv-db-1 psql -U postgres -d vtv_db -c "SELECT indexname FROM pg_indexes WHERE tablename='stops' AND indexname='idx_stops_geom';"` — shows spatial index

---

### Task 5: Update Stop Model with Geometry Column
**File:** `app/stops/models.py` (modify existing)
**Action:** UPDATE

Add the `geom` column to the Stop model. The column is nullable because stops without coordinates will have `geom = NULL`.

1. Add import: `from geoalchemy2 import Geometry  # pyright: ignore[reportMissingTypeStubs]`
2. Add `geom` column after `stop_lon` (no `Mapped[...]` — same pattern as pgvector `Vector` in `knowledge/models.py`):
   ```python
   geom = mapped_column(
       Geometry("POINT", srid=4326),  # pyright: ignore[reportUnknownArgumentType]
       nullable=True,
   )
   ```
3. Update docstring: replace Haversine mention with "derived PostGIS geometry column (geom) for spatial queries. A database trigger auto-syncs geom from stop_lat/stop_lon."

**Per-task validation:**
- `uv run ruff format app/stops/models.py`
- `uv run ruff check --fix app/stops/models.py` passes
- `uv run mypy app/stops/models.py` passes with 0 errors
- `uv run pyright app/stops/models.py` passes

---

### Task 6: Extract Haversine to Shared Geo Utilities
**File:** `app/shared/geo.py` (create new)
**Action:** CREATE

Extract the Haversine distance function from `app/stops/service.py` to a shared utility. This eliminates the code duplication between `app/stops/service.py` (lines 26-47) and `app/core/agents/tools/transit/search_stops.py` (lines 33-53).

```python
"""Geographic utility functions.

Shared spatial calculations used by both the stops REST API
and the transit agent tools.
"""

import math

_EARTH_RADIUS_METERS = 6_371_000


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in meters.

    Uses the Haversine formula for accuracy at city-scale distances.
    Used by the agent search_stops tool for in-memory proximity filtering
    on GTFS static cache data.

    Args:
        lat1: Latitude of first point (WGS84 degrees).
        lon1: Longitude of first point (WGS84 degrees).
        lat2: Latitude of second point (WGS84 degrees).
        lon2: Longitude of second point (WGS84 degrees).

    Returns:
        Distance in meters.
    """
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_METERS * c
```

**Per-task validation:**
- `uv run ruff format app/shared/geo.py`
- `uv run ruff check --fix app/shared/geo.py` passes
- `uv run mypy app/shared/geo.py` passes with 0 errors
- `uv run pyright app/shared/geo.py` passes

---

### Task 7: Add Spatial Nearby Query to Repository
**File:** `app/stops/repository.py` (modify existing)
**Action:** UPDATE

Add a `search_nearby()` method that uses PostGIS `ST_DWithin` and `ST_Distance` for proximity search.

**Changes:**

1. Add imports at top of file:
   ```python
   from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakePoint, ST_SetSRID  # pyright: ignore[reportMissingTypeStubs]
   ```

2. Add pyright ignore directive at the top of the file (line 1):
   ```python
   # pyright: reportMissingTypeStubs=false
   ```
   This is needed because geoalchemy2 lacks type stubs and ST_* functions trigger unknown type errors.

3. Add the `search_nearby()` method to the `StopRepository` class (after `list_all()`):

   ```python
   async def search_nearby(
       self,
       latitude: float,
       longitude: float,
       radius_meters: int,
       limit: int = 20,
   ) -> list[Stop]:
       """Find stops within a radius using PostGIS ST_DWithin.

       Uses a GIST spatial index for sub-ms performance regardless of
       total stop count.

       Args:
           latitude: Center point latitude (WGS84).
           longitude: Center point longitude (WGS84).
           radius_meters: Search radius in meters.
           limit: Maximum results to return.

       Returns:
           List of Stop instances sorted by distance (nearest first).
       """
       center = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
       query = (
           select(Stop)
           .where(Stop.geom.isnot(None))
           .where(
               ST_DWithin(
                   Stop.geom,
                   center,
                   radius_meters,
                   use_spheroid=True,
               )
           )
           .order_by(ST_Distance(Stop.geom, center, use_spheroid=True))
           .limit(limit)
       )
       result = await self.db.execute(query)
       return list(result.scalars().all())
   ```

**Key design notes:**
- `use_spheroid=True` gives meter-accurate results on WGS84 spheroid (matches Haversine accuracy)
- `ST_MakePoint(longitude, latitude)` — longitude FIRST (PostGIS convention: x=lon, y=lat)
- GIST index enables sub-ms spatial filtering via `ST_DWithin`
- If `use_spheroid=True` causes issues, fallback: `func.cast(Stop.geom, Geography)` with explicit casting

**Per-task validation:**
- `uv run ruff format app/stops/repository.py`
- `uv run ruff check --fix app/stops/repository.py` passes
- `uv run mypy app/stops/repository.py` passes
- `uv run pyright app/stops/repository.py` passes

---

### Task 8: Refactor Service to Use Repository Spatial Query
**File:** `app/stops/service.py` (modify existing)
**Action:** UPDATE

Remove the in-memory Haversine proximity search and delegate to the repository's PostGIS query.

**Changes:**

1. **Remove** the `_EARTH_RADIUS_METERS` constant (line 23) and the `_haversine_distance()` function (lines 26-47). Also remove the `import math` (line 5) since it's no longer needed.

2. **Rewrite** `search_nearby()` method (lines 249-287) to delegate to repository:

   ```python
   async def search_nearby(self, params: StopNearbyParams, limit: int = 20) -> list[StopResponse]:
       """Find stops within a radius of a geographic point.

       Uses PostGIS ST_DWithin for index-backed spatial queries.

       Args:
           params: Latitude, longitude, and radius parameters.
           limit: Maximum results to return.

       Returns:
           List of StopResponse sorted by distance (nearest first).
       """
       logger.info(
           "stops.nearby_started",
           latitude=params.latitude,
           longitude=params.longitude,
           radius_meters=params.radius_meters,
       )

       stops = await self.repository.search_nearby(
           latitude=params.latitude,
           longitude=params.longitude,
           radius_meters=params.radius_meters,
           limit=limit,
       )

       results = [StopResponse.model_validate(stop) for stop in stops]

       logger.info("stops.nearby_completed", result_count=len(results))

       return results
   ```

3. **Remove** `from app.stops.models import Stop` — no longer used after rewrite (was only in old `search_nearby` type annotation). Verify with grep that it's not used elsewhere in the file before removing.

**Per-task validation:**
- `uv run ruff format app/stops/service.py`
- `uv run ruff check --fix app/stops/service.py` passes
- `uv run mypy app/stops/service.py` passes with 0 errors
- `uv run pyright app/stops/service.py` passes

---

### Task 9: Update Agent Tool to Import Haversine from Shared
**File:** `app/core/agents/tools/transit/search_stops.py` (modify existing)
**Action:** UPDATE

Replace local `_haversine_distance()` with import from shared utility.

1. **Remove** `import math`, `_EARTH_RADIUS_METERS` constant, and `_haversine_distance()` function (lines 10, 30, 33-53)
2. **Add** `from app.shared.geo import haversine_distance`
3. **Update** call site in `_search_nearby()` (line 151): `_haversine_distance(` → `haversine_distance(`

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/search_stops.py`
- `uv run ruff check --fix app/core/agents/tools/transit/search_stops.py` passes
- `uv run mypy app/core/agents/tools/transit/search_stops.py` passes
- `uv run pyright app/core/agents/tools/transit/search_stops.py` passes

---

### Task 10: Update Service Tests for PostGIS Delegation
**File:** `app/stops/tests/test_service.py` (modify existing)
**Action:** UPDATE

Service `search_nearby()` now delegates to `repository.search_nearby()`. Tests must mock the repository method instead of patching Haversine.

1. **Remove** `@patch("app.stops.service._haversine_distance")` decorator and `mock_haversine` parameter. Remove `patch` from imports if no longer used elsewhere in file.

2. **Rewrite** `test_search_nearby_success()` (lines 145-158):

   ```python
   async def test_search_nearby_success(service):
       near_stop = make_stop(id=1, stop_name="Near", stop_lat=56.9497, stop_lon=24.1053)
       service.repository.search_nearby = AsyncMock(return_value=[near_stop])

       params = StopNearbyParams(latitude=56.9496, longitude=24.1052, radius_meters=500)
       result = await service.search_nearby(params, limit=10)

       assert len(result) == 1
       assert result[0].stop_name == "Near"
       service.repository.search_nearby.assert_awaited_once_with(
           latitude=56.9496,
           longitude=24.1052,
           radius_meters=500,
           limit=10,
       )
   ```

3. **Rewrite** `test_search_nearby_no_results()` (lines 161-170):

   ```python
   async def test_search_nearby_no_results(service):
       service.repository.search_nearby = AsyncMock(return_value=[])

       params = StopNearbyParams(latitude=56.9496, longitude=24.1052, radius_meters=100)
       result = await service.search_nearby(params, limit=10)

       assert len(result) == 0
   ```

4. **Rewrite** `test_search_nearby_sorted_by_distance()` (lines 173-188):

   ```python
   async def test_search_nearby_sorted_by_distance(service):
       # Repository returns stops pre-sorted by ST_Distance
       near = make_stop(id=2, stop_name="Near", stop_lat=56.9497, stop_lon=24.1053)
       medium = make_stop(id=1, stop_name="Medium", stop_lat=56.95, stop_lon=24.11)
       service.repository.search_nearby = AsyncMock(return_value=[near, medium])

       params = StopNearbyParams(latitude=56.9496, longitude=24.1052, radius_meters=500)
       result = await service.search_nearby(params, limit=10)

       assert len(result) == 2
       assert result[0].stop_name == "Near"
       assert result[1].stop_name == "Medium"
   ```

**Per-task validation:**
- `uv run ruff format app/stops/tests/test_service.py`
- `uv run ruff check --fix app/stops/tests/test_service.py` passes
- `uv run pytest app/stops/tests/test_service.py -v` — all tests pass

---

### Task 11: Add Shared Geo Utility Tests
**File:** `app/shared/tests/test_geo.py` (create new)
**Action:** CREATE

Test the extracted Haversine function to ensure it works correctly after extraction.

```python
"""Unit tests for shared geographic utilities."""

from app.shared.geo import haversine_distance


def test_haversine_same_point() -> None:
    """Distance from a point to itself is zero."""
    dist = haversine_distance(56.9496, 24.1052, 56.9496, 24.1052)
    assert dist == 0.0


def test_haversine_known_distance() -> None:
    """Distance between two known Riga points is approximately correct."""
    # Centrala stacija to Brivibas iela area (~2.7km)
    dist = haversine_distance(56.9496, 24.1052, 56.9520, 24.1100)
    assert 300 < dist < 500  # ~370m


def test_haversine_riga_to_jurmala() -> None:
    """Distance from Riga to Jurmala is approximately 25km."""
    dist = haversine_distance(56.9496, 24.1052, 56.9680, 23.7726)
    assert 20_000 < dist < 30_000


def test_haversine_symmetry() -> None:
    """Distance A->B equals distance B->A."""
    d1 = haversine_distance(56.9496, 24.1052, 56.9700, 24.1500)
    d2 = haversine_distance(56.9700, 24.1500, 56.9496, 24.1052)
    assert abs(d1 - d2) < 0.001  # Sub-millimeter precision
```

**Per-task validation:**
- `uv run ruff format app/shared/tests/test_geo.py`
- `uv run ruff check --fix app/shared/tests/test_geo.py` passes
- `uv run pytest app/shared/tests/test_geo.py -v` — all tests pass

---

### Task 12: Verify Existing Tests Still Pass
**Action:** VALIDATE

Run the full stops test suite and agent tool tests to confirm nothing is broken:

```bash
uv run pytest app/stops/tests/ -v
uv run pytest app/core/agents/tools/transit/tests/ -v -k "search_stops"
```

If tests fail due to `geom` column, add `"geom": None` to `make_stop()` factory defaults in `app/stops/tests/conftest.py`.

**Per-task validation:**
- `uv run pytest app/stops/tests/ -v` — all tests pass
- `uv run pytest app/core/agents/tools/transit/tests/ -v` — all tests pass
- `uv run pytest app/shared/tests/test_geo.py -v` — all tests pass

---

## Migration

See Task 4 for full migration content. Prefer autogenerate when db is running, then manually add extension/trigger/data population. Manual fallback column specs: `geom` Geometry('POINT', srid=4326) nullable, GIST index, trigger function + trigger.

## Logging Events

No new events. Existing `stops.nearby_started` and `stops.nearby_completed` preserved — change is internal.

## Testing Strategy

- **Service tests** (`test_service.py`): Mock `repository.search_nearby`, verify delegation and result ordering
- **Shared geo tests** (`test_geo.py`): Haversine zero distance, known distance, symmetry, long distance
- **Integration tests**: Not required — PostGIS correctness verified via migration validation commands
- **Edge cases**: NULL coords → geom=NULL (excluded by ST_DWithin), zero-radius → exact matches only

## Acceptance Criteria

This feature is complete when:
- [ ] PostGIS extension is installed and available in the database container
- [ ] `stops.geom` column exists with GIST spatial index
- [ ] Database trigger auto-populates `geom` from `stop_lat`/`stop_lon` on INSERT/UPDATE
- [ ] All existing stops have `geom` populated from their lat/lon values
- [ ] `GET /api/v1/stops/nearby` uses PostGIS `ST_DWithin` instead of Python Haversine
- [ ] API response format is identical to before (no schema changes)
- [ ] Haversine function extracted to `app/shared/geo.py` (single copy, no duplication)
- [ ] Agent tool `search_stops` imports Haversine from shared utils
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (stops + agent tools + shared)
- [ ] No type suppressions added beyond the geoalchemy2 library overrides
- [ ] GTFS import still works (trigger handles geom population transparently)

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 12 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Docker database rebuilt with PostGIS
- [ ] Migration applied successfully
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
uv run pytest app/stops/tests/ -v
uv run pytest app/shared/tests/test_geo.py -v
uv run pytest app/core/agents/tools/transit/tests/ -v -k "search_stops"
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
docker exec vtv-db-1 psql -U postgres -d vtv_db -c "SELECT PostGIS_Version();"
docker exec vtv-db-1 psql -U postgres -d vtv_db -c "SELECT count(*) FROM stops WHERE geom IS NOT NULL;"
docker exec vtv-db-1 psql -U postgres -d vtv_db -c "SELECT stop_name FROM stops WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(24.1052, 56.9496), 4326), 500, true) LIMIT 5;"
curl -s http://localhost:8123/health
```

**Success:** Levels 1-4 exit code 0. Level 5 shows PostGIS version, populated geom data, and spatial query results.

## Dependencies

- **New:** `uv add geoalchemy2>=0.16.0` (Python) + `postgresql-18-postgis-3` (apt in Docker)
- **New infrastructure:** Custom `db/Dockerfile` extending pgvector image
- **No new env vars** — PostGIS is a database extension

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules from `@_shared/python-anti-patterns.md`.

**PostGIS-specific pitfalls:**

1. **ST_MakePoint(longitude, latitude)** — lon FIRST (x, y convention). Riga: `ST_MakePoint(24.11, 56.95)`.
2. **GeoAlchemy2 lacks type stubs** — Add mypy override + pyright `reportMissingTypeStubs=false` directives.
3. **No `Mapped[...]` for geom** — Use plain `mapped_column()` without type annotation (same as pgvector `Vector` pattern in `app/knowledge/models.py`).
4. **`use_spheroid=True`** — Casts geometry to geography internally for meter distances. Fallback: explicit `func.cast(Stop.geom, Geography)`.
5. **Migration ordering** — Extension → column → data population → index → trigger function → trigger.
6. **Docker volume persistence** — `postgres_data` external volume persists. Rebuild image + `alembic upgrade head` enables PostGIS.
7. **Bulk upsert** — Trigger handles geom, no changes needed to `bulk_upsert()`.
8. **Test factories** — `make_stop()` should work without `geom` (nullable). If not, add `"geom": None` to defaults.

## Notes

**Performance:** O(n) Python Haversine → O(log n) PostGIS GIST index. 10-100x faster as stop count grows.

**Future:** `geom` enables `ST_Contains`, `ST_Intersects`, `ST_Buffer` for route coverage. Route shapes can use `ST_LineString`. Agent tool could migrate from static cache to database via `get_db_context()`.

**Rollback:** `alembic downgrade -1` cleanly removes trigger, function, index, and column. PostGIS extension left installed.

## Pre-Implementation Checklist

- [ ] Read all files in "Relevant Files" section
- [ ] Docker db container running and healthy
- [ ] Understood trigger-based sync and ST_MakePoint(lon, lat) order
- [ ] Clear on task execution order: infrastructure → model → repository → service → tests
