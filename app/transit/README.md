# Transit REST API — Multi-Feed GTFS-RT with Redis Caching

Multi-feed real-time vehicle tracking with Redis-backed caching. Supports multiple GTFS-RT providers (Riga, Jurmala, Pieriga, ATD intercity) with per-feed background polling, Redis pipeline writes, and batch MGET reads for sub-ms latency.

## Key Flows

### Dual-Mode Vehicle Position Retrieval

**Mode 1: Poller-enabled (production)** — `TRANSIT_POLLER_ENABLED=true`
1. Background poller tasks fetch GTFS-RT feeds at configurable intervals (default 10s)
2. Each poller parses protobuf, enriches with static GTFS data (route names, stop names)
3. Positions written to Redis via pipeline: `transit:vehicles:{feed_id}:{vehicle_id}` (60s TTL)
4. REST endpoint reads from Redis via batch MGET + JSON deserialize
5. Optional `?feed_id=X` filter applied server-side

**Mode 2: Direct fetch (legacy/fallback)** — `TRANSIT_POLLER_ENABLED=false`
1. Frontend polls `GET /api/v1/transit/vehicles` every 10 seconds
2. Service fetches GTFS-RT directly via `GTFSRealtimeClient` (20s in-memory cache)
3. Enriches with static GTFS data, applies optional `?route_id=X` filter
4. Returns `VehiclePositionsResponse`

### Background Poller Lifecycle

1. `start_pollers()` called during FastAPI lifespan startup
2. Creates one asyncio task per enabled feed from `TRANSIT_FEEDS_JSON` config
3. Each task runs `poll_once()` in a loop with `asyncio.sleep(poll_interval)`
4. `poll_once()`: fetch protobuf -> parse -> enrich -> Redis pipeline write
5. `stop_pollers()` called during shutdown, cancels all tasks gracefully
6. Graceful degradation: if Redis is unavailable at startup, pollers are skipped (app still serves other endpoints)

### Error Handling

1. Redis unavailable at startup: logged, pollers skipped, app starts in degraded mode
2. Redis write failure during poll: logged, poll returns 0, retries on next interval
3. GTFS-RT feed unavailable: `TransitDataError` propagates, HTTP 503 returned
4. Individual feed failure doesn't affect other feeds (per-feed isolation)

## Database Schema

No database tables. All data is ephemeral:
- **Redis**: Vehicle positions with 60s TTL per key
- **In-memory**: GTFS static cache (routes, stops, trips) with 24h TTL

## Business Rules

1. Route ID resolved from vehicle data first, then trip-to-route lookup via static cache
2. Delay computed from next stop time update relative to current stop sequence
3. Speed converted from GTFS-RT m/s to km/h (rounded to 1 decimal)
4. Timestamps converted from POSIX to ISO 8601 UTC
5. Each feed has independent `feed_id` and `operator_name` attached to vehicle positions
6. Feed configs support per-feed `poll_interval_seconds` and `enabled` toggle
7. Legacy single-feed config (`GTFS_RT_VEHICLE_URL`) auto-migrates to multi-feed format
8. No authentication required (GTFS-RT data is public)

## Integration Points

- **`app.core.redis`**: Redis client singleton (`get_redis()`, `close_redis()`) with lifespan management
- **`app.core.config`**: `TransitFeedConfig` model, `transit_feeds` computed property, `REDIS_URL`
- **`app.core.agents.tools.transit.client`**: Reuses `GTFSRealtimeClient` for GTFS-RT feed parsing
- **`app.core.agents.tools.transit.static_cache`**: Reuses `GTFSStaticCache` singleton for route/stop/trip name resolution
- **`app.core.agents.exceptions`**: Uses `TransitDataError` for feed failure propagation (HTTP 503)
- **`app.core.health`**: Redis health check at `/health/redis`, included in `/health/ready`
- **CMS Frontend**: `cms/apps/web/src/hooks/use-vehicle-positions.ts` polls the vehicles endpoint

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/transit/vehicles` | All vehicle positions across all feeds (optional `?route_id=X`, `?feed_id=Y`) |
| GET | `/api/v1/transit/vehicles/{feed_id}` | Vehicle positions for a specific feed |
| GET | `/api/v1/transit/feeds` | Status of all configured feeds (feed_id, operator, enabled, vehicle count) |

### Response Schema (vehicles)

```json
{
  "count": 42,
  "vehicles": [
    {
      "vehicle_id": "4521",
      "route_id": "22",
      "route_short_name": "22",
      "latitude": 56.9496,
      "longitude": 24.1052,
      "bearing": 180.0,
      "speed_kmh": 36.0,
      "delay_seconds": 120,
      "current_status": "IN_TRANSIT_TO",
      "next_stop_name": "Centraltirgus",
      "current_stop_name": "Stacija",
      "timestamp": "2024-01-15T10:30:00+00:00",
      "feed_id": "riga",
      "operator_name": "Rigas Satiksme"
    }
  ],
  "fetched_at": "2024-01-15T10:30:05+00:00"
}
```

### Response Schema (feeds)

```json
{
  "feeds": [
    {
      "feed_id": "riga",
      "operator_name": "Rigas Satiksme",
      "enabled": true,
      "vehicle_count": 42,
      "last_poll_at": "2024-01-15T10:30:00+00:00"
    }
  ]
}
```

## Configuration

```bash
# Redis
REDIS_URL=redis://localhost:6379/0

# Multi-feed config (JSON array)
TRANSIT_FEEDS_JSON='[{"feed_id":"riga","operator_name":"Rigas Satiksme","gtfs_rt_vehicle_url":"https://...","gtfs_rt_trip_url":"https://...","gtfs_static_url":"https://...","poll_interval_seconds":10,"enabled":true}]'

# Polling control
TRANSIT_POLLER_ENABLED=true
TRANSIT_POLL_INTERVAL=10

# Legacy single-feed (backward compatible, used when TRANSIT_FEEDS_JSON is empty)
GTFS_RT_VEHICLE_URL=https://...
GTFS_RT_TRIP_URL=https://...
GTFS_STATIC_URL=https://...
```

## Planned Upgrades

| Upgrade | Phase | Description |
|---------|-------|-------------|
| WebSocket streaming | Phase 1 | `WS /api/v1/transit/vehicles/stream` with subscription filtering |
| GTFS database import | Phase 1 | Persist GTFS static data to PostgreSQL tables (currently in-memory only) |
| Additional city feeds | Phase 2 | Daugavpils, Liepaja, Rezekne GPS text feeds |
| Train positions | Phase 2 | WebSocket listener for `wss://trainmap.pv.lv/ws` |
| ETA calculator | Phase 2 | Valhalla map-matching + distance-to-stop / speed calculation |
| GTFS-RT publisher | Phase 2 | Serve combined GTFS-RT feed at `/api/v1/transit/gtfs-rt/*.pb` |

See `docs/PLANNING/Implementation-Plan.md` for the complete 4-phase roadmap.
