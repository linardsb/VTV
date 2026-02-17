# Transit Tools

Read-only AI agent tools for querying Riga's real-time transit data via GTFS-RT feeds from Rigas Satiksme.

## Implemented Tools

### `query_bus_status` (3 actions)

| Action | Required Params | Returns |
|--------|----------------|---------|
| `status` | `vehicle_id` OR `route_id` | JSON list of `BusStatus` (position, delay, severity, alerts) |
| `route_overview` | `route_id` | JSON `RouteOverview` (aggregate stats, headway, bunching detection) |
| `stop_departures` | `stop_id` | JSON `StopDepartures` (next 10 departures with predicted arrival) |

### Planned Tools

- `get_route_schedule` — Timetable for a route and service date
- `search_stops` — Search stops by name or proximity (lat/lon)
- `get_adherence_report` — On-time performance metrics
- `check_driver_availability` — Available drivers for a shift/date

## Architecture

```
transit/
├── schemas.py          # Pydantic response models (BusStatus, RouteOverview, etc.)
├── deps.py             # TransitDeps dataclass + create_transit_deps() factory
├── client.py           # GTFSRealtimeClient — protobuf parsing with 20s in-memory cache
├── static_cache.py     # GTFSStaticCache — ZIP parser for route/stop/trip name resolution (24h TTL)
├── query_bus_status.py # Tool function registered with Pydantic AI agent
└── tests/              # 16 unit tests (test_query_bus_status.py, test_client.py)
```

## Data Flow

1. Dispatcher asks agent a question (e.g., "How is route 22 performing?")
2. Agent selects `query_bus_status` with `action="route_overview", route_id="22"`
3. Tool fetches GTFS-RT protobuf feeds (vehicle positions, trip updates, alerts) via `GTFSRealtimeClient`
4. Tool enriches raw IDs with human-readable names via `GTFSStaticCache` (routes.txt, stops.txt, trips.txt)
5. Tool computes delay descriptions, severity levels, headway stats, bunching detection
6. Tool returns structured JSON response for the agent to summarize

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

## Integration Points

- **Agent module** (`agent.py`) — Tool registered via `tools=[query_bus_status]`
- **Agent service** (`service.py`) — `TransitDeps` injected via `create_transit_deps()`
- **Config** (`app/core/config.py`) — 6 GTFS feed settings
- **Exceptions** (`exceptions.py`) — `TransitDataError` mapped to HTTP 503
