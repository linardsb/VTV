# Geofences

PostGIS-powered geographic zone monitoring for fleet vehicles. Detects entry, exit, and dwell events when vehicles cross zone boundaries, with configurable alert integration.

## Key Flows

### Create Geofence Zone

1. Validate polygon coordinates (min 4 points, closed ring, valid WGS84 lat/lon)
2. Convert GeoJSON coordinates to WKT POLYGON string
3. Persist zone with PostGIS geometry column (SRID 4326)
4. Return response with coordinates extracted via ST_AsGeoJSON

### Background Evaluation (every 30s)

1. Scan Redis for all vehicle position updates (`vehicle:*` keys)
2. For each vehicle, query active geofences using `ST_Contains(geometry, point)`
3. Compare current containment state against previous state (cached in Redis `geofence_state:{vehicle_id}`)
4. Detect transitions:
   - **Entry**: vehicle now inside zone but wasn't before → create `enter` event + alert
   - **Exit**: vehicle was inside but isn't now → close open entry, calculate dwell_seconds, create `exit` event + alert
   - **Dwell exceeded**: vehicle still inside, elapsed time ≥ threshold → create `dwell_exceeded` event + alert
5. Update Redis state with 5-minute TTL

### Dwell Report

1. Verify geofence exists
2. Aggregate events: total count, avg/max dwell seconds, currently-inside vehicle count
3. Return `DwellTimeReport` with time range filtering

## Database Schema

### Table: `geofences`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `name` | String(200) | NOT NULL, indexed | Zone display name |
| `zone_type` | String(20) | NOT NULL, CHECK | depot, terminal, restricted, customer, custom |
| `geometry` | Geometry(POLYGON, 4326) | NOT NULL, GIST indexed | PostGIS polygon (partial index on `is_active=true`) |
| `color` | String(7) | nullable | Hex color `#RRGGBB` |
| `description` | Text | nullable | Long description |
| `alert_on_enter` | Boolean | default true | Trigger alert on vehicle entry |
| `alert_on_exit` | Boolean | default true | Trigger alert on vehicle exit |
| `alert_on_dwell` | Boolean | default false | Trigger alert when dwell threshold exceeded |
| `dwell_threshold_minutes` | Integer | nullable, 1-1440 | Minutes before dwell alert fires |
| `alert_severity` | String(20) | default 'medium', CHECK | critical, high, medium, low, info |
| `is_active` | Boolean | default true | Active zones are evaluated by background task |
| `created_at` | DateTime(tz) | NOT NULL | TimestampMixin |
| `updated_at` | DateTime(tz) | NOT NULL | TimestampMixin |

### Table: `geofence_events`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `geofence_id` | Integer | FK (CASCADE), indexed | References `geofences.id` |
| `vehicle_id` | String(100) | NOT NULL, indexed | Vehicle identifier |
| `event_type` | String(20) | NOT NULL, CHECK | enter, exit, dwell_exceeded |
| `entered_at` | DateTime(tz) | NOT NULL | Entry timestamp |
| `exited_at` | DateTime(tz) | nullable | Set on exit (NULL while inside) |
| `dwell_seconds` | Integer | nullable | Duration calculated on close_entry |
| `latitude` | Float | NOT NULL | Position at event time |
| `longitude` | Float | NOT NULL | Position at event time |
| `created_at` | DateTime(tz) | NOT NULL | TimestampMixin |
| `updated_at` | DateTime(tz) | NOT NULL | TimestampMixin |

Compound index: `(geofence_id, entered_at)` for event lookup.

## Business Rules

1. Polygon coordinates must form a closed ring (first == last point) with at least 4 points
2. Longitude: [-180, 180], Latitude: [-90, 90] (WGS84)
3. Dwell threshold: 1-1440 minutes (1 minute to 24 hours)
4. Only active geofences (`is_active=true`) are checked by the background evaluator
5. Alert deduplication via `find_active_duplicate()` — prevents duplicate alerts for same vehicle/zone
6. PATCH updates reject empty bodies (all fields None)

## Integration Points

- **Alerts**: Background evaluator creates `AlertInstance` records for enter/exit/dwell events. Uses `geofence_enter`, `geofence_exit`, `geofence_dwell` alert types (added to `AlertRuleType` Literal)
- **Transit (Redis)**: Reads vehicle positions from Redis (`vehicle:*` keys) — same cache populated by GTFS-RT pollers
- **Config**: `geofence_evaluator_enabled` and `geofence_check_interval_seconds` in `app/core/config.py`

## API Endpoints

| Method | Path | RBAC | Description |
|--------|------|------|-------------|
| GET | `/api/v1/geofences/` | All users | List zones (search, zone_type, is_active filters) |
| POST | `/api/v1/geofences/` | admin, editor | Create zone with polygon coordinates |
| GET | `/api/v1/geofences/events` | All users | List all events across zones |
| GET | `/api/v1/geofences/{id}` | All users | Get zone by ID |
| PATCH | `/api/v1/geofences/{id}` | admin, editor | Update zone |
| DELETE | `/api/v1/geofences/{id}` | admin only | Delete zone |
| GET | `/api/v1/geofences/{id}/events` | All users | List events for zone |
| GET | `/api/v1/geofences/{id}/dwell-report` | All users | Aggregated dwell statistics |
