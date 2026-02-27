# Stop Management

CRUD operations for transit stops with GTFS-aligned data model and proximity search. Supports stop hierarchy (stations > stops), wheelchair accessibility metadata, geographic coordinate-based nearby search using PostGIS `ST_DWithin` spatial queries with GIST indexing, and server-side filtering by `location_type` for terminus/station distinction.

## Key Flows

### Create Stop

1. Validate input (name, GTFS stop_id, coordinates, location_type, wheelchair_boarding)
2. Check uniqueness of `gtfs_stop_id` (raise `StopAlreadyExistsError` if duplicate)
3. Persist to database with auto-generated timestamps
4. Return stop response with generated ID

### List Stops (Paginated + Filtered)

1. Parse pagination params (page, page_size)
2. Apply optional filters:
   - `search` — case-insensitive name substring via `ilike`
   - `active_only` — boolean, default true
   - `location_type` — integer (0=stop, 1=station/terminus), filters server-side for accurate pagination counts
3. Query database with filters, ordered by `stop_name`
4. Return paginated response with total count matching filter criteria

### Nearby Stops (Proximity Search)

1. Accept latitude, longitude, radius_meters (default 500, max 5000)
2. Execute PostGIS `ST_DWithin` query against GIST-indexed `geom` column (sub-ms at city scale)
3. Filter to active stops within radius, compute distance via `ST_Distance` with WGS84 spheroid
4. Sort by distance ascending at database level
5. Return up to `limit` results (default 20, max 100)

### Update Stop

1. Find stop by database ID (raise `StopNotFoundError` if missing)
2. If `gtfs_stop_id` is changing, check new value doesn't conflict (raise `StopAlreadyExistsError`)
3. Apply partial update via `model_dump(exclude_unset=True)` — only submitted fields
4. Persist and return updated stop

### Delete Stop

1. Find stop by database ID (raise `StopNotFoundError` if missing)
2. Hard delete from database

## Database Schema

Table: `stops`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `gtfs_stop_id` | String(50) | Unique, indexed, not null | GTFS stop_id identifier |
| `stop_name` | String(200) | Not null, indexed | Human-readable stop name |
| `stop_lat` | Float | Nullable | WGS84 latitude |
| `stop_lon` | Float | Nullable | WGS84 longitude |
| `stop_desc` | Text | Nullable | Stop description (direction text, e.g., "Uz centru") |
| `location_type` | Integer | Not null, default 0 | GTFS location_type (0=stop, 1=station/terminus) |
| `parent_station_id` | Integer | FK -> stops.id, nullable | Self-referential parent station |
| `wheelchair_boarding` | Integer | Not null, default 0 | GTFS wheelchair_boarding (0=unknown, 1=yes, 2=no) |
| `is_active` | Boolean | Not null, default true | Soft delete flag |
| `created_at` | DateTime | Not null | Auto-set on create |
| `geom` | Geometry(Point, 4326) | Nullable, GIST indexed | PostGIS geometry auto-synced from lat/lon via DB trigger |
| `updated_at` | DateTime | Not null | Auto-set on update |

## Business Rules

1. `gtfs_stop_id` must be unique across all stops
2. `stop_name` must be 1-200 characters
3. Coordinates are optional but must be valid WGS84 if provided (-90/90 lat, -180/180 lon)
4. `location_type` follows GTFS spec: 0=stop/platform, 1=station/terminus, 2=entrance, 3=generic node, 4=boarding area
5. `parent_station_id` is a self-referential FK for stop hierarchy
6. Proximity search uses PostGIS `ST_DWithin` + `ST_Distance` on `geom` column with GIST spatial index — sub-ms queries at city scale. A database trigger (`trg_sync_stop_geom`) auto-syncs `geom` from `stop_lat`/`stop_lon` on INSERT/UPDATE
7. Delete is hard delete (no soft delete via is_active flag)
8. `location_type` filter is applied server-side (in SQL) to ensure pagination totals match filtered results

## Integration Points

- **CMS Frontend**: Stop management page at `/[locale]/stops` — Leaflet map with click-to-place, drag-to-reposition, terminus markers (green for `location_type=1`), direction text display, and copyable GTFS IDs
- **Agent Transit Tools**: `search_stops` tool in `app/core/agents/tools/transit/` queries GTFS static cache using Haversine (via `app/shared/geo.py`), not this feature's database. These are separate data sources.
- **Shared Utilities**: Uses `PaginationParams`, `PaginatedResponse`, `TimestampMixin`, `get_db()`, `get_logger()`. Haversine formula extracted to `app/shared/geo.py` for agent tool use (this feature uses PostGIS instead)
- **Core Rate Limiting**: All endpoints rate-limited at 30/min (reads) or 10/min (writes)

## API Endpoints

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| GET | `/api/v1/stops/` | 30/min | List stops (paginated, searchable, filterable by active_only + location_type) |
| GET | `/api/v1/stops/nearby` | 30/min | Find stops within radius of coordinates |
| GET | `/api/v1/stops/{id}` | 30/min | Get stop by ID |
| POST | `/api/v1/stops/` | 10/min | Create a new stop |
| PATCH | `/api/v1/stops/{id}` | 10/min | Update a stop (partial) |
| DELETE | `/api/v1/stops/{id}` | 10/min | Delete a stop |

### Query Parameters (GET `/api/v1/stops/`)

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page |
| `search` | string | — | Case-insensitive name substring filter |
| `active_only` | bool | true | Filter to active stops only |
| `location_type` | int (0-4) | — | Filter by GTFS location_type (0=stop, 1=station/terminus) |

## Tests

56 unit tests across 3 test files:
- `test_routes.py` — 10 route-level tests (HTTP via FastAPI test client)
- `test_service.py` — 14 service-level tests (mocked repository, PostGIS spatial queries)
- `test_repository.py` — 32 repository-level tests (async DB, PostGIS proximity queries)
