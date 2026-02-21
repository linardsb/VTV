# Schedule Management

GTFS-compliant schedule management for transit timetables, service calendars, trip CRUD, and GTFS ZIP import/export. Enables dispatchers and planners to manage the full schedule lifecycle with validation against the GTFS specification.

## Key Flows

### GTFS ZIP Import

1. Upload GTFS ZIP file via `POST /import`
2. Parse CSV files (agency.txt, routes.txt, calendar.txt, calendar_dates.txt, trips.txt, stop_times.txt)
3. Build stop map from existing stops (cross-feature read from `StopRepository`)
4. Clear all existing schedule data (reverse FK order)
5. Bulk insert in FK order: agencies -> routes -> calendars -> calendar_dates -> trips -> stop_times
6. Single commit at end, return entity counts + warnings for skipped records

### Schedule Validation

1. `POST /validate` triggers comprehensive checks
2. Calendar date range validation (`start_date <= end_date`)
3. Trip reference integrity (valid route_id and calendar_id)
4. StopTime sequence ordering checks
5. Time format validation (HH:MM:SS regex, supports >24:00:00 for overnight trips)
6. Returns `ValidationResult` with errors and warnings lists

### Trip with Stop Times

1. Create trip via `POST /trips` (validates route and calendar exist)
2. Add/replace stop times via `PUT /trips/{id}/stop-times` (atomic bulk replace)
3. Get trip detail via `GET /trips/{id}` returns trip + all stop_times

## Database Schema

### Table: `agencies`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `gtfs_agency_id` | String(50) | Unique, indexed | GTFS agency_id |
| `agency_name` | String(200) | Not null | Agency display name |
| `agency_url` | String(500) | Nullable | Agency website |
| `agency_timezone` | String(50) | Default "Europe/Riga" | GTFS timezone |
| `agency_lang` | String(5) | Nullable | Language code |
| `created_at` / `updated_at` | DateTime | Not null | TimestampMixin |

### Table: `routes`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `gtfs_route_id` | String(50) | Unique, indexed | GTFS route_id |
| `agency_id` | Integer | FK -> agencies.id CASCADE, indexed | Parent agency |
| `route_short_name` | String(50) | Indexed | Short name (e.g., "22") |
| `route_long_name` | String(200) | Not null | Full route name |
| `route_type` | Integer | Not null | GTFS route type (0-12) |
| `route_color` | String(6) | Nullable | Hex color |
| `route_text_color` | String(6) | Nullable | Hex text color |
| `route_sort_order` | Integer | Nullable | Display order |
| `is_active` | Boolean | Default true | Active flag |
| `created_at` / `updated_at` | DateTime | Not null | TimestampMixin |

### Table: `calendars`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `gtfs_service_id` | String(50) | Unique, indexed | GTFS service_id |
| `monday` - `sunday` | Boolean | Not null | Day-of-week flags |
| `start_date` | Date | Not null | Service period start |
| `end_date` | Date | Not null | Service period end |
| `created_at` / `updated_at` | DateTime | Not null | TimestampMixin |

### Table: `calendar_dates`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `calendar_id` | Integer | FK -> calendars.id CASCADE, indexed | Parent calendar |
| `date` | Date | Not null | Exception date |
| `exception_type` | Integer | Not null | 1=added, 2=removed |
| `created_at` / `updated_at` | DateTime | Not null | TimestampMixin |

### Table: `trips`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `gtfs_trip_id` | String(100) | Unique, indexed | GTFS trip_id |
| `route_id` | Integer | FK -> routes.id CASCADE, indexed | Parent route |
| `calendar_id` | Integer | FK -> calendars.id CASCADE, indexed | Service calendar |
| `direction_id` | Integer | Nullable | 0=outbound, 1=inbound |
| `trip_headsign` | String(200) | Nullable | Destination sign |
| `block_id` | String(50) | Nullable | Vehicle block |
| `created_at` / `updated_at` | DateTime | Not null | TimestampMixin |

### Table: `stop_times`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `trip_id` | Integer | FK -> trips.id CASCADE, indexed | Parent trip |
| `stop_id` | Integer | FK -> stops.id CASCADE, indexed | Referenced stop |
| `stop_sequence` | Integer | Not null | Order in trip |
| `arrival_time` | String(8) | Not null | HH:MM:SS (supports >24:00:00 for overnight) |
| `departure_time` | String(8) | Not null | HH:MM:SS |
| `pickup_type` | Integer | Default 0 | GTFS pickup type (0-3) |
| `drop_off_type` | Integer | Default 0 | GTFS drop-off type (0-3) |
| `created_at` / `updated_at` | DateTime | Not null | TimestampMixin |

## Business Rules

1. GTFS IDs (`gtfs_agency_id`, `gtfs_route_id`, `gtfs_service_id`, `gtfs_trip_id`) must be unique
2. Routes must reference an existing agency
3. Trips must reference an existing route and calendar
4. StopTimes must reference an existing trip and stop (from `stops` feature)
5. Calendar `start_date` must be <= `end_date`
6. StopTime times use HH:MM:SS format, allowing values > 24:00:00 for overnight trips (GTFS spec)
7. GTFS import clears ALL existing schedule data before inserting (full replace strategy)
8. StopTimes for unknown stops (not in DB) are skipped during GTFS import with warning count
9. Calendar exception_type: 1 = service added, 2 = service removed

## Integration Points

- **Stops** (`app/stops/`): StopTime references `stops.id` via FK. GTFS import reads all stops via `StopRepository` to build `gtfs_stop_id -> db_stop_id` mapping. Read-only access.

## API Endpoints

| Method | Path | Description | Rate Limit |
|--------|------|-------------|------------|
| GET | `/api/v1/schedules/agencies` | List all agencies | 30/min |
| POST | `/api/v1/schedules/agencies` | Create agency | 10/min |
| GET | `/api/v1/schedules/routes` | List routes (paginated, search, filter by type/agency) | 30/min |
| POST | `/api/v1/schedules/routes` | Create route | 10/min |
| GET | `/api/v1/schedules/routes/{id}` | Get route by ID | 30/min |
| PATCH | `/api/v1/schedules/routes/{id}` | Update route | 10/min |
| DELETE | `/api/v1/schedules/routes/{id}` | Delete route | 10/min |
| GET | `/api/v1/schedules/calendars` | List calendars (paginated, filter by active_on date) | 30/min |
| POST | `/api/v1/schedules/calendars` | Create calendar | 10/min |
| GET | `/api/v1/schedules/calendars/{id}` | Get calendar by ID | 30/min |
| PATCH | `/api/v1/schedules/calendars/{id}` | Update calendar | 10/min |
| DELETE | `/api/v1/schedules/calendars/{id}` | Delete calendar (cascades calendar_dates) | 10/min |
| POST | `/api/v1/schedules/calendars/{id}/exceptions` | Add calendar exception | 10/min |
| DELETE | `/api/v1/schedules/calendar-exceptions/{id}` | Remove calendar exception | 10/min |
| GET | `/api/v1/schedules/trips` | List trips (paginated, filter by route/calendar/direction) | 30/min |
| POST | `/api/v1/schedules/trips` | Create trip | 10/min |
| GET | `/api/v1/schedules/trips/{id}` | Get trip with stop_times | 30/min |
| PATCH | `/api/v1/schedules/trips/{id}` | Update trip | 10/min |
| DELETE | `/api/v1/schedules/trips/{id}` | Delete trip (cascades stop_times) | 10/min |
| PUT | `/api/v1/schedules/trips/{id}/stop-times` | Replace all stop_times for trip | 10/min |
| POST | `/api/v1/schedules/import` | Import GTFS ZIP file | 5/min |
| POST | `/api/v1/schedules/validate` | Validate current schedule data | 5/min |
