# Transit Tools

Read-only AI agent tools for querying Riga's transit data via GTFS-RT feeds and GTFS static data from Rigas Satiksme.

## Implemented Tools

### `query_bus_status` (3 actions)

| Action | Required Params | Returns |
|--------|----------------|---------|
| `status` | `vehicle_id` OR `route_id` | JSON list of `BusStatus` (position, delay, severity, alerts) |
| `route_overview` | `route_id` | JSON `RouteOverview` (aggregate stats, headway, bunching detection) |
| `stop_departures` | `stop_id` | JSON `StopDepartures` (next 10 departures with predicted arrival) |

### `get_route_schedule` (timetable queries)

| Parameter | Required | Description |
|-----------|----------|-------------|
| `route_id` | Yes | GTFS route ID (e.g., `"bus_22"`) |
| `date` | No | Service date YYYY-MM-DD (defaults to today in Riga TZ) |
| `direction_id` | No | 0 or 1 to filter by direction |
| `time_from` | No | Filter trips departing after HH:MM |
| `time_until` | No | Filter trips departing before HH:MM |

Returns JSON `RouteSchedule` with per-direction trip summaries, first/last departure times, and a pre-formatted summary string. Capped at 30 trips per direction for token efficiency.

### `search_stops` (2 actions)

| Action | Required Params | Returns |
|--------|----------------|---------|
| `search` | `query` | JSON `StopSearchResults` (matching stops with names, coordinates, serving routes) |
| `nearby` | `latitude`, `longitude` | JSON `StopSearchResults` (stops within radius sorted by distance) |

Optional params: `radius_meters` (default 500, max 2000), `limit` (default 10, max 25).

Uses Haversine formula for geographic distance. Case-insensitive Unicode substring matching for Latvian stop names (supports diacritics: ā, ē, ī, ū, š, ž). Results include a `stop_routes` index mapping each stop to its serving route names.

### `get_adherence_report` (on-time performance)

| Parameter | Required | Description |
|-----------|----------|-------------|
| `route_id` | No | GTFS route ID for single-route report (omit for network-wide) |
| `date` | No | Service date YYYY-MM-DD (defaults to today in Riga TZ) |
| `time_from` | No | Filter trips departing after HH:MM |
| `time_until` | No | Filter trips departing before HH:MM |

Returns JSON `AdherenceReport` with per-route metrics: scheduled/tracked trips, on-time/late/early/no-data counts, on-time percentage, average delay, worst trip. Network mode aggregates all routes with RT data, sorted worst-first. On-time threshold: +/- 300 seconds (5 min). Capped at 30 trips per route, 15 routes for network reports.

### Planned Tools

- `check_driver_availability` — Available drivers for a shift/date

## Architecture

```
transit/
├── schemas.py              # Pydantic response models (BusStatus, RouteOverview, RouteSchedule, AdherenceReport, etc.)
├── deps.py                 # TransitDeps dataclass + create_transit_deps() factory
├── client.py               # GTFSRealtimeClient — protobuf parsing with 20s in-memory cache
├── static_cache.py         # GTFSStaticCache — ZIP parser for route/stop/trip/calendar/stop_times (24h TTL)
├── query_bus_status.py     # Tool 1: real-time status queries (3 actions)
├── get_route_schedule.py   # Tool 2: planned timetable queries with date/direction/time filters
├── search_stops.py         # Tool 3: stop search by name or proximity (2 actions)
├── get_adherence_report.py # Tool 4: on-time performance metrics (route + network)
└── tests/                  # 88 unit tests
    ├── test_client.py              # GTFS-RT client cache and error handling
    ├── test_query_bus_status.py    # Bus status tool function tests
    ├── test_get_route_schedule.py  # Schedule tool helpers + tool function tests
    ├── test_search_stops.py        # Stop search helpers + tool function tests (19 tests)
    ├── test_get_adherence_report.py # Adherence report helpers + tool function tests (19 tests)
    └── test_static_cache.py        # Calendar service resolution + stop_routes index tests
```

## Data Flow

### Real-time queries (query_bus_status)

1. Dispatcher asks agent a question (e.g., "How is route 22 performing?")
2. Agent selects `query_bus_status` with `action="route_overview", route_id="22"`
3. Tool fetches GTFS-RT protobuf feeds (vehicle positions, trip updates, alerts) via `GTFSRealtimeClient`
4. Tool enriches raw IDs with human-readable names via `GTFSStaticCache` (routes.txt, stops.txt, trips.txt)
5. Tool computes delay descriptions, severity levels, headway stats, bunching detection
6. Tool returns structured JSON response for the agent to summarize

### Schedule queries (get_route_schedule)

1. Dispatcher asks "What's the schedule for route 22 tomorrow?"
2. Agent selects `get_route_schedule` with `route_id="bus_22", date="2026-02-18"`
3. Tool loads `GTFSStaticCache` (stop_times.txt, calendar.txt, calendar_dates.txt)
4. Tool resolves active service IDs for the date (weekly patterns + exceptions)
5. Tool filters trips by service, direction, and time window
6. Tool builds per-direction schedules with first/last departure, trip count, summary
7. Tool returns structured JSON `RouteSchedule` for the agent to relay

### Adherence queries (get_adherence_report)

1. Dispatcher asks "How is route 22 performing today?" or "Give me a network performance report"
2. Agent selects `get_adherence_report` with `route_id="bus_22"` (or omits for network)
3. Tool fetches GTFS-RT trip updates via `GTFSRealtimeClient` for current delay data
4. Tool loads `GTFSStaticCache` (calendar, trips, stop_times) for scheduled trips
5. Tool resolves active service IDs, filters trips by date and optional time window
6. Tool cross-references each scheduled trip against RT data: on_time (<=300s), late, early, no_data
7. Tool computes percentages, average delay, identifies worst trip by absolute delay
8. For network mode: aggregates per-route, sorts by worst on-time %, caps at 15 routes
9. Tool returns structured JSON `AdherenceReport` for the agent to summarize

### Stop search queries (search_stops)

1. Dispatcher asks "Where is the Brīvības stop?" or "Find stops near the central station"
2. Agent selects `search_stops` with `action="search", query="Brīvības"` or `action="nearby", latitude=56.9496, longitude=24.1052`
3. Tool loads `GTFSStaticCache` (stops.txt, stop_times.txt for stop-to-routes index)
4. For name search: case-insensitive Unicode substring match across all stop names
5. For nearby search: Haversine distance calculation, filtered by radius, sorted by proximity
6. Results enriched with serving route names via `stop_routes` index
7. Tool returns structured JSON `StopSearchResults` with stop details and composition hints

## Configuration

All settings have defaults pointing to Rigas Satiksme public endpoints (no API key required):

| Setting | Default | Description |
|---------|---------|-------------|
| `GTFS_RT_VEHICLE_POSITIONS_URL` | `https://saraksti.rigassatiksme.lv/vehicle_positions.pb` | Vehicle positions feed |
| `GTFS_RT_TRIP_UPDATES_URL` | `https://saraksti.rigassatiksme.lv/trip_updates.pb` | Trip updates feed |
| `GTFS_RT_ALERTS_URL` | `https://saraksti.rigassatiksme.lv/gtfs_realtime.pb` | Service alerts feed |
| `GTFS_STATIC_URL` | `https://saraksti.rigassatiksme.lv/gtfs.zip` | Static GTFS ZIP |
| `GTFS_RT_CACHE_TTL_SECONDS` | `20` | Real-time cache TTL |
| `GTFS_STATIC_CACHE_TTL_HOURS` | `24` | Static data cache TTL |

## Delay Severity Classification

| Severity | Threshold | Meaning |
|----------|-----------|---------|
| `normal` | < 3 min | On schedule |
| `warning` | 3-10 min | Notable delay |
| `critical` | > 10 min | Severe delay, needs attention |

## Service Resolution Algorithm

`GTFSStaticCache.get_active_service_ids(date)` determines which services run on a given date:

1. Check `calendar.txt` — match weekly day-of-week patterns within start_date/end_date range
2. Apply `calendar_dates.txt` exceptions — type 1 adds service, type 2 removes service

This handles weekday/weekend schedules, holidays, and special service dates.

## Integration Points

- **Agent module** (`agent.py`) — Tools registered via `tools=[query_bus_status, get_route_schedule, search_stops]`
- **Agent service** (`service.py`) — `TransitDeps` injected via `create_transit_deps()`
- **Config** (`app/core/config.py`) — 6 GTFS feed settings
- **Exceptions** (`exceptions.py`) — `TransitDataError` mapped to HTTP 503
