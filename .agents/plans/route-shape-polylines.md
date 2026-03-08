# Plan: Route Shape Polylines

## Feature Metadata
**Feature Type**: Enhancement (extends existing `schedules` vertical slice)
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/schedules/` (models, schemas, import, export, repository, service, routes), frontend map components

## Feature Description

Add GTFS shapes.txt support to the VTV platform. Shapes define the geographic path a vehicle follows along a route — a sequence of lat/lon waypoints that form a polyline. This feature adds a `shapes` database table, parses shapes.txt during GTFS ZIP import, exports shapes.txt during GTFS export, and exposes a REST endpoint to retrieve shape geometry for a given route.

The GTFS shapes.txt file contains rows with: `shape_id`, `shape_pt_lat`, `shape_pt_lon`, `shape_pt_sequence`, and optionally `shape_dist_traveled`. Multiple rows share the same `shape_id` and together form an ordered polyline. Trips reference shapes via `shape_id`, and multiple trips on the same route often share the same shape (one per direction).

The backend stores shape points as individual rows (matching GTFS spec), groups them by `shape_id`, and returns ordered coordinate arrays via a new endpoint: `GET /api/v1/schedules/routes/{route_id}/shapes`. The frontend will consume this endpoint to render polylines on the route map using react-leaflet's `Polyline` component (frontend implementation is a separate task — this plan covers the backend API only).

## User Story

As a transit administrator viewing the routes map
I want to see the geographic path each route follows displayed as a polyline overlay
So that I can verify route geometry, identify coverage gaps, and correlate live vehicle positions with planned route paths

## Security Contexts

**Active contexts:**
- **CTX-RBAC**: New REST endpoint requires auth + role check. All authenticated users can read shapes (read-only data).
- **CTX-INPUT**: The new endpoint accepts a `route_id` path parameter. No user-provided search strings, but path param must be validated.

**Not applicable:**
- CTX-AUTH: No changes to auth/login flow
- CTX-FILE: GTFS ZIP upload already handled by existing import endpoint with size limits and ZIP bomb protection — no new file handling
- CTX-AGENT: No agent tool changes
- CTX-INFRA: No Docker/nginx/config changes

## Solution Approach

We extend the existing `schedules` vertical slice rather than creating a new one, because shapes are a core GTFS entity tightly coupled with routes and trips. The shapes table follows the same patterns as other GTFS entities (Agency, Route, Calendar, Trip, StopTime).

**Design decisions:**

1. **Store individual shape points (not encoded polylines)** — Matches GTFS spec exactly, enables lossless import/export round-trips, and keeps the data model simple. The API endpoint aggregates points into coordinate arrays grouped by shape_id.

2. **Link shapes to routes via trips** — GTFS links `shape_id` to trips (not routes directly). A route's shapes are found by: route → trips → distinct shape_ids → shape points. This matches the spec and handles routes with multiple shapes (one per direction).

3. **Add `shape_id` to Trip model** — The Trip table gets a nullable `shape_id` string column (GTFS ID, not FK). Shape points are stored in a separate `shapes` table with their own `shape_id` string column. No FK between trips and shapes — this matches GTFS's loose coupling where shape_id is an optional reference.

4. **Bulk insert for performance** — shapes.txt can have 100K+ rows. Use the same batch insert pattern as stop_times.

**Alternatives considered:**
- **PostGIS LineString geometry column**: Rejected — adds complexity, requires GeoAlchemy2 dependency on shapes table, and doesn't provide benefits for simple polyline rendering. The frontend just needs `[[lat, lon], ...]` arrays.
- **Encoded polyline string (Google format)**: Rejected — adds encoding/decoding complexity, loses precision, and makes GTFS export harder. Store raw points, let the API aggregate.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/schedules/models.py` (all lines) — Existing GTFS models (Agency, Route, Calendar, Trip, StopTime). New Shape model goes here.
- `app/schedules/schemas.py` (all lines) — Existing Pydantic schemas. New ShapePointResponse and RouteShapesResponse go here.
- `app/schedules/repository.py` (lines 1-65, 730-860) — Import patterns, batch size, bulk_create and bulk_upsert methods. New shape repository methods follow same patterns.
- `app/schedules/service.py` (lines 556-750) — GTFS import flow. Shape import inserts after route upsert.
- `app/schedules/gtfs_import.py` (all lines) — GTFS ZIP parser. Add `_parse_shapes()` method.
- `app/schedules/gtfs_export.py` (all lines) — GTFS ZIP exporter. Add `_shapes_csv()` method.
- `app/schedules/routes.py` (lines 1-50) — Router setup pattern. New endpoint goes here.

### Similar Features (Examples to Follow)
- `app/schedules/gtfs_import.py` (lines 368-424) — `_parse_trips()` method: parse CSV, build parallel ref lists, handle missing references. Shape parsing follows same pattern.
- `app/schedules/repository.py` (lines 823-860) — `bulk_upsert_routes()`: batch insert with conflict handling. Shape bulk insert is simpler (no upsert needed — delete+reinsert on import).
- `app/schedules/gtfs_export.py` (lines 162-175) — `_trips_csv()`: generate CSV from model instances. Shape export follows same pattern.

### Files to Modify
- `app/schedules/models.py` — Add Shape model, add shape_id to Trip model
- `app/schedules/schemas.py` — Add ShapePointResponse, RouteShapesResponse, update GTFSImportResponse
- `app/schedules/repository.py` — Add shape bulk create, delete, and query methods
- `app/schedules/service.py` — Add shape import logic, shape export logic, get_route_shapes method
- `app/schedules/gtfs_import.py` — Add _parse_shapes() and shape_id to trip parsing
- `app/schedules/gtfs_export.py` — Add shapes parameter and _shapes_csv()
- `app/schedules/routes.py` — Add GET route shapes endpoint

## Implementation Plan

### Phase 1: Foundation
Add Shape model, Trip.shape_id column, and Pydantic schemas. Create database migration.

### Phase 2: Core Implementation
Implement shape parsing in GTFS importer, bulk operations in repository, import/export logic in service, and shape CSV export.

### Phase 3: Integration & Validation
Add REST endpoint for shape retrieval, update GTFSImportResponse with shape counts, write tests.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Add Shape Model and Trip.shape_id
**File:** `app/schedules/models.py` (modify existing)
**Action:** UPDATE

Add the Shape model after StopTime class (end of file) and add `shape_id` to Trip model:

1. Add `shape_id` column to `Trip` model (after `block_id`):
   - `shape_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)`
   - This is a GTFS shape_id string reference, not a foreign key

2. Add new `Shape` model class at end of file:
   - `__tablename__ = "shapes"`
   - `__table_args__` with `UniqueConstraint("feed_id", "gtfs_shape_id", "shape_pt_sequence", name="uq_shape_feed_id_seq")`
   - Fields:
     - `id: Mapped[int]` — primary key, indexed
     - `gtfs_shape_id: Mapped[str]` — String(100), not null, indexed
     - `feed_id: Mapped[str]` — String(50), not null, indexed, default="riga"
     - `shape_pt_lat: Mapped[float]` — Float, not null
     - `shape_pt_lon: Mapped[float]` — Float, not null
     - `shape_pt_sequence: Mapped[int]` — Integer, not null
     - `shape_dist_traveled: Mapped[float | None]` — Float, nullable
   - Inherits `Base, TimestampMixin`
   - Google-style docstring: `"""Shape point database model (GTFS shapes.txt)."""`

3. Add imports: `Float` to the sqlalchemy import line

**Per-task validation:**
- `uv run ruff format app/schedules/models.py`
- `uv run ruff check --fix app/schedules/models.py`
- `uv run mypy app/schedules/models.py`

---

### Task 2: Add Shape Schemas and Update GTFSImportResponse
**File:** `app/schedules/schemas.py` (modify existing)
**Action:** UPDATE

Add new schemas after `StopTimesBulkUpdate` class (before `# --- Import ---` section, around line 258):

1. Add `ShapePointResponse` schema:
   ```python
   class ShapePointResponse(BaseModel):
       """Schema for a single shape point."""
       lat: float
       lon: float
       sequence: int
       dist_traveled: float | None = None
   ```

2. Add `RouteShapeResponse` schema:
   ```python
   class RouteShapeResponse(BaseModel):
       """Schema for a single shape (ordered polyline) belonging to a route."""
       shape_id: str
       points: list[ShapePointResponse]
   ```

3. Add `RouteShapesResponse` schema:
   ```python
   class RouteShapesResponse(BaseModel):
       """Schema for all shapes associated with a route (typically 1-2 per direction)."""
       route_id: int
       gtfs_route_id: str
       shapes: list[RouteShapeResponse]
   ```

4. Update `GTFSImportResponse` — add after `stops_updated`:
   - `shapes_count: int = 0`

**Per-task validation:**
- `uv run ruff format app/schedules/schemas.py`
- `uv run ruff check --fix app/schedules/schemas.py`
- `uv run mypy app/schedules/schemas.py`

---

### Task 3: Add Shape Repository Methods
**File:** `app/schedules/repository.py` (modify existing)
**Action:** UPDATE

Add these methods to the `ScheduleRepository` class. Also add `Shape` to the model imports at the top.

1. Add `Shape` to the import from `app.schedules.models`

2. Add `bulk_create_shapes` method (follow `bulk_create_stop_times` pattern at line 780):
   ```python
   async def bulk_create_shapes(self, items: list[Shape]) -> None:
       """Bulk insert shape points. Flush only, no commit."""
       for i in range(0, len(items), _BATCH_SIZE):
           self.db.add_all(items[i : i + _BATCH_SIZE])
           await self.db.flush()
   ```

3. Add `delete_shapes_for_feed` method:
   ```python
   async def delete_shapes_for_feed(self, feed_id: str) -> int:
       """Delete all shape points for a feed. Returns count deleted."""
       result = await self.db.execute(
           delete(Shape).where(Shape.feed_id == feed_id)
       )
       await self.db.flush()
       return result.rowcount  # type: ignore[return-value]
   ```

4. Add `get_shapes_for_route` method:
   ```python
   async def get_shapes_for_route(self, route_id: int) -> list[Shape]:
       """Get all shape points for shapes referenced by a route's trips.

       Finds distinct shape_ids from trips belonging to this route,
       then returns all shape points ordered by shape_id and sequence.
       """
       # Subquery: distinct shape_ids from route's trips
       shape_ids_subq = (
           select(Trip.shape_id)
           .where(Trip.route_id == route_id, Trip.shape_id.isnot(None))
           .distinct()
           .scalar_subquery()
       )
       result = await self.db.execute(
           select(Shape)
           .where(Shape.gtfs_shape_id.in_(shape_ids_subq))
           .order_by(Shape.gtfs_shape_id, Shape.shape_pt_sequence)
       )
       return list(result.scalars().all())
   ```

5. Add `list_all_shapes` method (for GTFS export, follows `list_all_trips` pattern):
   ```python
   async def list_all_shapes(self, feed_id: str | None = None) -> list[Shape]:
       """List all shape points, optionally filtered by feed_id."""
       stmt = select(Shape).order_by(Shape.gtfs_shape_id, Shape.shape_pt_sequence)
       if feed_id:
           stmt = stmt.where(Shape.feed_id == feed_id)
       result = await self.db.execute(stmt)
       return list(result.scalars().all())
   ```

**Per-task validation:**
- `uv run ruff format app/schedules/repository.py`
- `uv run ruff check --fix app/schedules/repository.py`
- `uv run mypy app/schedules/repository.py`

---

### Task 4: Add Shape Parsing to GTFS Importer
**File:** `app/schedules/gtfs_import.py` (modify existing)
**Action:** UPDATE

1. Add `Shape` to the import from `app.schedules.models`

2. Add `shapes` field to `GTFSParseResult` dataclass (after `stops` field, before `skipped_stop_times`):
   ```python
   shapes: list[Shape] = field(default_factory=lambda: list[Shape]())
   ```

3. Update `_parse_trips()` method to capture `shape_id` from trips.txt:
   - In the `Trip()` constructor (around line 411), add after `block_id`:
     ```python
     shape_id=row.get("shape_id") or None,
     ```

4. Add `_parse_shapes()` method (after `_parse_stops`, before the module-level `_parse_gtfs_date`):
   ```python
   def _parse_shapes(self, zf: zipfile.ZipFile, file_names: list[str]) -> list[Shape]:
       """Parse shapes.txt.

       Args:
           zf: Open ZipFile instance.
           file_names: List of files in the ZIP.

       Returns:
           List of Shape model instances ordered by shape_id and sequence.
       """
       reader = self._read_csv(zf, "shapes.txt")
       if reader is None:
           return []
       _ = file_names
       shapes: list[Shape] = []
       for row in reader:
           shape_id = row.get("shape_id", "")
           if not shape_id:
               continue

           lat_str = row.get("shape_pt_lat", "")
           lon_str = row.get("shape_pt_lon", "")
           seq_str = row.get("shape_pt_sequence", "0")
           dist_str = row.get("shape_dist_traveled", "")

           try:
               lat = float(lat_str)
               lon = float(lon_str)
           except (ValueError, TypeError):
               self.warnings.append(
                   f"Skipping shape point {shape_id}/{seq_str}: invalid coordinates"
               )
               continue

           sequence = int(seq_str) if seq_str.isdigit() else 0
           dist_traveled: float | None = None
           if dist_str:
               try:
                   dist_traveled = float(dist_str)
               except (ValueError, TypeError):
                   pass

           shapes.append(
               Shape(
                   gtfs_shape_id=shape_id,
                   feed_id=self.feed_id,
                   shape_pt_lat=lat,
                   shape_pt_lon=lon,
                   shape_pt_sequence=sequence,
                   shape_dist_traveled=dist_traveled,
               )
           )
       return shapes
   ```

5. Update `parse()` method to call `_parse_shapes()`:
   - After the stop_times parsing block (around line 148), before the `return GTFSParseResult(...)`:
     ```python
     # Parse shapes
     shapes = self._parse_shapes(zf, file_names)
     ```
   - Add `shapes=shapes,` to the GTFSParseResult constructor

**Per-task validation:**
- `uv run ruff format app/schedules/gtfs_import.py`
- `uv run ruff check --fix app/schedules/gtfs_import.py`
- `uv run mypy app/schedules/gtfs_import.py`

---

### Task 5: Add Shape Export to GTFS Exporter
**File:** `app/schedules/gtfs_export.py` (modify existing)
**Action:** UPDATE

1. Add `Shape` to the import from `app.schedules.models` (line 12)

2. Add `shapes` parameter to `GTFSExporter.__init__()`:
   - Add after `stops` parameter: `shapes: list[Shape] | None = None,`
   - Add to body: `self.shapes = shapes or []`

3. Add `_shapes_csv()` method (after `_stops_csv`):
   ```python
   def _shapes_csv(self) -> str:
       """Generate shapes.txt CSV content."""
       fields = [
           "shape_id",
           "shape_pt_lat",
           "shape_pt_lon",
           "shape_pt_sequence",
           "shape_dist_traveled",
       ]
       rows = [
           {
               "shape_id": s.gtfs_shape_id,
               "shape_pt_lat": str(s.shape_pt_lat),
               "shape_pt_lon": str(s.shape_pt_lon),
               "shape_pt_sequence": str(s.shape_pt_sequence),
               "shape_dist_traveled": str(s.shape_dist_traveled)
               if s.shape_dist_traveled is not None
               else "",
           }
           for s in self.shapes
       ]
       return _write_csv(rows, fields)
   ```

4. Update `export()` method — add after stops.txt write (line 75):
   ```python
   if self.shapes:
       zf.writestr("shapes.txt", self._shapes_csv())
   ```

5. Update `_trips_csv()` — add `shape_id` to trips.txt output:
   - Add `"shape_id"` to the fields list
   - Add to each row dict: `"shape_id": t.shape_id or "",`

**Per-task validation:**
- `uv run ruff format app/schedules/gtfs_export.py`
- `uv run ruff check --fix app/schedules/gtfs_export.py`
- `uv run mypy app/schedules/gtfs_export.py`

---

### Task 6: Update Service Layer with Shape Import/Export/Query
**File:** `app/schedules/service.py` (modify existing)
**Action:** UPDATE

1. Add `Shape` to the model imports (if not already imported)
2. Add `RouteShapeResponse, RouteShapesResponse, ShapePointResponse` to the schema imports

3. **Update `import_gtfs()` method** — add shape import step after stop_times (step 7), before `await self.db.commit()`:
   ```python
   # 8. Delete + re-insert shapes for this feed
   shapes_count = 0
   if result.shapes:
       await self.repository.delete_shapes_for_feed(feed_id)
       await self.repository.bulk_create_shapes(result.shapes)
       shapes_count = len(result.shapes)
   ```
   - Update the GTFSImportResponse return at the end of import_gtfs to include `shapes_count=shapes_count`
   - Update the logger.info "schedules.import_completed" call to include `shapes=shapes_count`

4. **Update `export_gtfs()` method** — add shapes to the exporter:
   - After loading other entities, add: `shapes = await self.repository.list_all_shapes(feed_id=feed_id)`
   - Pass `shapes=shapes` to the `GTFSExporter()` constructor

5. **Add `get_route_shapes()` method** to the service class:
   ```python
   async def get_route_shapes(self, route_id: int) -> RouteShapesResponse:
       """Get all shapes for a route, grouped by shape_id.

       Args:
           route_id: Database route ID.

       Returns:
           RouteShapesResponse with ordered coordinate arrays per shape.

       Raises:
           NotFoundError: If route does not exist.
       """
       route = await self.repository.get_route(route_id)
       if route is None:
           raise NotFoundError(f"Route {route_id} not found")

       shape_points = await self.repository.get_shapes_for_route(route_id)

       # Group points by shape_id
       shapes_by_id: dict[str, list[ShapePointResponse]] = {}
       for sp in shape_points:
           if sp.gtfs_shape_id not in shapes_by_id:
               shapes_by_id[sp.gtfs_shape_id] = []
           shapes_by_id[sp.gtfs_shape_id].append(
               ShapePointResponse(
                   lat=sp.shape_pt_lat,
                   lon=sp.shape_pt_lon,
                   sequence=sp.shape_pt_sequence,
                   dist_traveled=sp.shape_dist_traveled,
               )
           )

       return RouteShapesResponse(
           route_id=route.id,
           gtfs_route_id=route.gtfs_route_id,
           shapes=[
               RouteShapeResponse(shape_id=sid, points=pts)
               for sid, pts in shapes_by_id.items()
           ],
       )
   ```

6. Ensure `NotFoundError` is imported from `app.core.exceptions`

**Per-task validation:**
- `uv run ruff format app/schedules/service.py`
- `uv run ruff check --fix app/schedules/service.py`
- `uv run mypy app/schedules/service.py`

---

### Task 7: Add REST Endpoint for Route Shapes
**File:** `app/schedules/routes.py` (modify existing)
**Action:** UPDATE

1. Add `RouteShapesResponse` to the schema imports

2. Add endpoint after the existing route CRUD endpoints (after DELETE route, before calendar endpoints):
   ```python
   @router.get(
       "/routes/{route_id}/shapes",
       response_model=RouteShapesResponse,
       summary="Get route shapes",
       description="Returns all shape polylines for a route, grouped by shape_id. "
       "Each shape contains an ordered array of lat/lon coordinates.",
   )
   async def get_route_shapes(
       route_id: int,
       service: ScheduleService = Depends(get_service),  # noqa: B008
       _user: User = Depends(get_current_user),  # noqa: B008
   ) -> RouteShapesResponse:
       """Get shape polylines for a route."""
       return await service.get_route_shapes(route_id)
   ```

**Per-task validation:**
- `uv run ruff format app/schedules/routes.py`
- `uv run ruff check --fix app/schedules/routes.py`
- `uv run mypy app/schedules/routes.py`

---

### Task 8: Create Database Migration
**Action:** CREATE migration

Run the autogenerate migration:
```bash
uv run alembic revision --autogenerate -m "add shapes table and trip shape_id"
uv run alembic upgrade head
```

**If database is NOT running (manual fallback):**

Create migration manually with:
- **New table `shapes`:**
  - `id`: Integer, primary_key, autoincrement
  - `gtfs_shape_id`: String(100), nullable=False, indexed
  - `feed_id`: String(50), nullable=False, indexed, default="riga"
  - `shape_pt_lat`: Float, nullable=False
  - `shape_pt_lon`: Float, nullable=False
  - `shape_pt_sequence`: Integer, nullable=False
  - `shape_dist_traveled`: Float, nullable=True
  - `created_at`: DateTime(timezone=True), server_default=func.now()
  - `updated_at`: DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
  - UniqueConstraint on (feed_id, gtfs_shape_id, shape_pt_sequence) named "uq_shape_feed_id_seq"

- **Alter table `trips`:**
  - Add column `shape_id`: String(100), nullable=True, indexed

**Per-task validation:**
- `uv run alembic check` (no pending migrations)
- Verify migration file exists in `alembic/versions/`

---

### Task 9: Write Unit Tests
**File:** `app/schedules/tests/test_shapes.py` (create new)
**Action:** CREATE

Write tests covering:

**Test 1: Shape parsing from GTFS ZIP**
```python
def test_parse_shapes_from_gtfs_zip():
    """Test that shapes.txt is parsed correctly from a GTFS ZIP."""
    # Create a minimal GTFS ZIP with shapes.txt containing 2 shapes
    # Verify correct number of Shape objects returned
    # Verify coordinates and sequence ordering
    # Verify shape_id grouping
```

**Test 2: Shape parsing with missing shapes.txt**
```python
def test_parse_shapes_missing_file():
    """Test that missing shapes.txt produces empty list and no error."""
    # Create GTFS ZIP without shapes.txt
    # Verify result.shapes is empty list
```

**Test 3: Shape parsing with invalid coordinates**
```python
def test_parse_shapes_invalid_coords():
    """Test that invalid coordinates are skipped with warning."""
    # Create shapes.txt with one valid and one invalid row
    # Verify only valid row is returned
    # Verify warning is added
```

**Test 4: Trip shape_id parsing**
```python
def test_parse_trip_shape_id():
    """Test that shape_id is captured from trips.txt."""
    # Create GTFS ZIP with trips.txt containing shape_id column
    # Verify Trip objects have shape_id set
```

**Test 5: Shape export CSV generation**
```python
def test_shapes_csv_export():
    """Test that shapes are exported to shapes.txt in GTFS ZIP."""
    # Create GTFSExporter with shape data
    # Export and verify shapes.txt exists in ZIP
    # Verify CSV content matches input
```

**Test 6: Schema validation**
```python
def test_route_shapes_response_schema():
    """Test RouteShapesResponse serialization."""
    # Create response with known data
    # Verify JSON structure
```

**Test 7: GTFSImportResponse includes shapes_count**
```python
def test_import_response_includes_shapes_count():
    """Test that GTFSImportResponse has shapes_count field."""
    # Verify schema field exists and defaults to 0
```

**Per-task validation:**
- `uv run ruff format app/schedules/tests/test_shapes.py`
- `uv run ruff check --fix app/schedules/tests/test_shapes.py`
- `uv run pytest app/schedules/tests/test_shapes.py -v`

---

## Migration

**Prefer autogenerate when database is running:**
```bash
uv run alembic revision --autogenerate -m "add shapes table and trip shape_id"
uv run alembic upgrade head
```

**When database may not be running:** Manual migration creation is an acceptable fallback. See Task 8 for column types, nullable flags, and constraints needed.

## Logging Events

- `schedules.import_completed` — Already exists, update to include `shapes=<count>` in the log context
- No new logging events needed — shape operations are part of the existing import flow

## Testing Strategy

### Unit Tests
**Location:** `app/schedules/tests/test_shapes.py`
- GTFS importer shape parsing (valid, missing file, invalid coords)
- Trip shape_id parsing from trips.txt
- GTFS exporter shapes.txt generation
- Schema validation (ShapePointResponse, RouteShapesResponse)
- GTFSImportResponse shapes_count field

### Integration Tests
**Location:** `app/schedules/tests/test_shapes.py`
**Mark with:** `@pytest.mark.integration`
- Repository `get_shapes_for_route` with real database (route → trips → shapes join)
- Repository `bulk_create_shapes` and `delete_shapes_for_feed`
- Full import round-trip: import GTFS ZIP with shapes → export → verify shapes.txt present

### Edge Cases
- Route with no trips → empty shapes response
- Route with trips but no shape_id on trips → empty shapes response
- Route with multiple shapes (direction 0 and 1) → two shape groups returned
- shapes.txt with empty rows → skipped gracefully
- shapes.txt with very large point count (10K+) → handled via batch insert
- shape_dist_traveled missing → stored as None

## Acceptance Criteria

This feature is complete when:
- [ ] Shape model exists with all GTFS fields (shape_id, lat, lon, sequence, dist_traveled)
- [ ] Trip model has nullable shape_id column
- [ ] GTFS import parses shapes.txt and stores shape points in database
- [ ] GTFS import captures shape_id from trips.txt
- [ ] GTFS export includes shapes.txt when shapes exist
- [ ] GTFS export includes shape_id in trips.txt
- [ ] GET /api/v1/schedules/routes/{route_id}/shapes returns grouped shape polylines
- [ ] Endpoint requires authentication (get_current_user dependency)
- [ ] GTFSImportResponse includes shapes_count field
- [ ] Database migration creates shapes table and adds trip.shape_id column
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + integration)
- [ ] No type suppressions added
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order (1-9)
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
uv run pytest app/schedules/tests/test_shapes.py -v
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

- Shared utilities used: `TimestampMixin` from `app.shared.models`, `PaginatedResponse` from `app.shared.schemas`
- Core modules used: `Base` from `app.core.database`, `get_logger` from `app.core.logging`, `NotFoundError` from `app.core.exceptions`
- New dependencies: None (all required libraries already installed)
- New env vars: None

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules from `_shared/python-anti-patterns.md`. Key rules for this task:

- **Rule 5**: No unused imports — only import Shape/schemas where actually used
- **Rule 11**: Schema field additions break consumers — adding `shapes_count` to GTFSImportResponse requires checking ALL constructors. Grep for `GTFSImportResponse(` across the codebase.
- **Rule 29**: Adding optional fields to existing schemas — `shapes_count: int = 0` has a default so it's safe, but verify no test assertions break.
- **Rule 41**: ILIKE search params must escape wildcards — not applicable here (no text search)
- **Rule 48**: Unique constraints for GTFS composite keys — shapes table needs `UniqueConstraint("feed_id", "gtfs_shape_id", "shape_pt_sequence")`

**Additional pitfalls:**
- shapes.txt can be very large (100K+ rows for a city-wide GTFS feed). Use batch insert (`_BATCH_SIZE = 2000`).
- The `delete_shapes_for_feed` + `bulk_create_shapes` pattern (delete+reinsert) is simpler than upsert for shapes since shape points don't have meaningful update semantics.
- Trip.shape_id is a string reference, NOT a foreign key. GTFS doesn't guarantee referential integrity between trips and shapes.

## Notes

- **Frontend follow-up**: After this backend work, a separate frontend task will add a `Polyline` component to `route-map.tsx` that fetches from `GET /api/v1/schedules/routes/{route_id}/shapes` and renders polylines using react-leaflet's `<Polyline>` component.
- **Performance**: For routes with many shape points (1000+), consider adding response caching (Redis) in a future iteration. For now, the database query with proper indexing should be fast enough.
- **Riga's GTFS feed**: The RS GTFS feed at `saraksti.rigassatiksme.lv/gtfs.zip` includes shapes.txt. After this implementation, importing the feed will automatically populate shape data.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach (individual points, not encoded polylines)
- [ ] Clear on task execution order (models → schemas → repo → importer → exporter → service → routes → migration → tests)
- [ ] Validation commands are executable in this environment
