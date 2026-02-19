# Stop Management

CRUD operations for transit stops with GTFS-aligned data model and proximity search. Supports stop hierarchy (stations > stops), wheelchair accessibility metadata, and geographic coordinate-based nearby search using Haversine formula.

## Key Flows

### Create Stop

1. Validate input (name, GTFS stop_id, coordinates, location_type)
2. Check uniqueness of `gtfs_stop_id`
3. Persist to database with timestamps
4. Return stop response with generated ID

### List Stops (Paginated)

1. Parse pagination params (page, per_page)
2. Apply optional filters: search (name substring), active_only
3. Query database with filters and pagination
4. Return paginated response with total count

### Nearby Stops (Proximity Search)

1. Accept latitude, longitude, radius_meters
2. Compute Haversine distance for all stops with coordinates
3. Filter to stops within radius
4. Sort by distance ascending, return up to limit results

### Update Stop

1. Find stop by database ID (raise StopNotFoundError if missing)
2. Apply partial update (only non-None fields from StopUpdate)
3. Persist and return updated stop

### Delete Stop

1. Find stop by database ID (raise StopNotFoundError if missing)
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
| `stop_desc` | Text | Nullable | Stop description |
| `location_type` | Integer | Not null, default 0 | GTFS location_type (0=stop, 1=station) |
| `parent_station_id` | Integer | FK -> stops.id, nullable | Self-referential parent station |
| `wheelchair_boarding` | Integer | Not null, default 0 | GTFS wheelchair_boarding (0=unknown, 1=yes, 2=no) |
| `is_active` | Boolean | Not null, default true | Soft delete flag |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

## Business Rules

1. `gtfs_stop_id` must be unique across all stops
2. `stop_name` must be 1-200 characters
3. Coordinates are optional but must be valid WGS84 if provided (-90/90 lat, -180/180 lon)
4. `location_type` follows GTFS spec: 0=stop/platform, 1=station, 2=entrance, 3=generic node, 4=boarding area
5. `parent_station_id` is a self-referential FK for stop hierarchy
6. Proximity search uses Haversine formula on plain floats (not PostGIS geometry)
7. Delete is hard delete (no soft delete via is_active flag)

## Integration Points

- **Agent Transit Tools**: `search_stops` tool in `app/core/agents/tools/transit/` queries GTFS static cache, not this feature's database. These are separate data sources.
- **Shared Utilities**: Uses `PaginationParams`, `PaginatedResponse`, `TimestampMixin`, `get_db()`, `get_logger()`
- **Core Rate Limiting**: All endpoints rate-limited at 30/min (reads) or 10/min (writes)

## API Endpoints

| Method | Path | Rate Limit | Description |
|--------|------|-----------|-------------|
| GET | `/api/v1/stops/` | 30/min | List stops (paginated, searchable, filterable) |
| GET | `/api/v1/stops/nearby` | 30/min | Find stops within radius of coordinates |
| GET | `/api/v1/stops/{id}` | 30/min | Get stop by ID |
| POST | `/api/v1/stops/` | 10/min | Create a new stop |
| PATCH | `/api/v1/stops/{id}` | 10/min | Update a stop |
| DELETE | `/api/v1/stops/{id}` | 10/min | Delete a stop |
