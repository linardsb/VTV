# Transit — Multi-Feed GTFS-RT with Redis Caching + WebSocket Live Streaming + TimescaleDB Historical Storage

Multi-feed real-time vehicle tracking with Redis-backed caching, WebSocket push, and TimescaleDB time-series historical storage. Supports multiple GTFS-RT providers (Riga, Jurmala, Pieriga, ATD intercity) with per-feed background polling, Redis pipeline writes, batch MGET reads for sub-ms latency, WebSocket live streaming via Redis Pub/Sub fan-out, and persistent position history with compression and retention policies.

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
4. `poll_once()`: fetch protobuf -> parse -> enrich -> Redis pipeline write -> TimescaleDB batch insert -> Redis PUBLISH
5. After writing to Redis, batch inserts enriched positions into TimescaleDB `vehicle_positions` hypertable (non-blocking, failure logged but never blocks poller)
6. Publishes enriched vehicles to `transit:vehicles:{feed_id}` Pub/Sub channel
7. `stop_pollers()` called during shutdown, cancels all tasks gracefully
8. Graceful degradation: if Redis is unavailable at startup, pollers are skipped (app still serves other endpoints)
9. Pub/Sub publish failure is non-blocking (warning logged, polling continues)
10. TimescaleDB write failure is non-blocking (warning logged, polling continues)

### WebSocket Live Streaming

Replaces HTTP polling with push-based updates for near-instant vehicle position delivery.

**Architecture:** FeedPoller → Redis PUBLISH → Subscriber → ConnectionManager → WebSocket clients

1. Poller publishes enriched vehicle data to Redis Pub/Sub channel `transit:vehicles:{feed_id}`
2. Background subscriber task (`ws_subscriber.py`) in ALL Gunicorn workers listens to `transit:vehicles:*`
3. Subscriber dispatches to `ConnectionManager.broadcast()` with per-client feed/route filtering
4. ConnectionManager sends `WsVehicleUpdate` JSON to each matching WebSocket client
5. Disconnected clients auto-cleaned during broadcast; broken sends isolated per-client

**Multi-worker design:** Only the leader worker runs the poller (Redis-based leader election), but ALL workers subscribe to Pub/Sub. This ensures all connected clients receive updates regardless of which worker they're attached to.

**Authentication:** JWT token via `?token=` query parameter (browser WebSocket API doesn't support custom headers). Validated using same `decode_token` + `is_token_revoked` logic as HTTP endpoints.

**Protocol (bidirectional JSON text messages):**
- Client → Server: `{"action": "subscribe", "route_id": "22", "feed_id": "riga"}` — subscribe with optional filters
- Client → Server: `{"action": "unsubscribe"}` — reset filters
- Client → Server: `{"action": "pong"}` — keepalive response to server ping
- Server → Client: `{"type": "vehicle_update", ...}` — vehicle position push
- Server → Client: `{"type": "ping"}` — application-level keepalive (every 30s)
- Server → Client: `{"type": "ack", ...}` — action acknowledgement with current filter state
- Server → Client: `{"type": "error", ...}` — error notification

### Historical Position Queries

**Vehicle History** — `GET /api/v1/transit/vehicles/{vehicle_id}/history`
1. Parse and validate ISO 8601 time range parameters (422 on invalid format)
2. Require admin, dispatcher, or editor role (403 for viewer)
3. Query `vehicle_positions` hypertable with time range filter, ordered by `recorded_at ASC`
4. Map ORM records to `HistoricalPosition` schema with route name resolution
5. Return `VehicleHistoryResponse` with position array (default limit 1000, max 10000)

**Route Delay Trend** — `GET /api/v1/transit/routes/{route_id}/delay-trend`
1. Parse time range and interval_minutes (5-1440, default 60)
2. Require admin, dispatcher, or editor role
3. Use TimescaleDB `time_bucket()` for efficient time-series aggregation
4. Return `RouteDelayTrendResponse` with avg/min/max delay and sample count per bucket

### Error Handling

1. Redis unavailable at startup: logged, pollers skipped, app starts in degraded mode
2. Redis write failure during poll: logged, poll returns 0, retries on next interval
3. GTFS-RT feed unavailable: `TransitDataError` propagates, HTTP 503 returned
4. Individual feed failure doesn't affect other feeds (per-feed isolation)
5. WebSocket subscriber reconnects with exponential backoff (1s → 30s max) on Redis connection loss
6. One broken WebSocket client doesn't block broadcast to other clients (per-client error isolation)
7. Pub/Sub publish failure in poller is non-blocking (warning logged, polling continues)
8. TimescaleDB write failure in poller is non-blocking (warning logged, polling continues)
9. Invalid ISO 8601 time parameters return 422 with descriptive error message

## Database Schema

### Real-time (ephemeral)
- **Redis keys**: Vehicle positions with 60s TTL per key (`vehicle:{feed_id}:{vehicle_id}`)
- **Redis Pub/Sub**: Vehicle updates published to `transit:vehicles:{feed_id}` channels
- **In-memory**: GTFS static cache (routes, stops, trips) with 24h TTL
- **In-memory**: WebSocket ConnectionManager tracks active clients with `dict[int, _ClientSubscription]`

### Historical (persistent) — TimescaleDB Hypertable

Table: `vehicle_positions` (converted to TimescaleDB hypertable, partitioned by `recorded_at`)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | Primary key |
| `recorded_at` | DateTime(tz) | Not null, indexed | GTFS-RT measurement timestamp (UTC) |
| `feed_id` | String(50) | Not null | Source feed (e.g., "riga") |
| `vehicle_id` | String(100) | Not null | Fleet vehicle identifier |
| `route_id` | String(100) | Not null, default="" | GTFS route ID |
| `route_short_name` | String(50) | Not null, default="" | Human-readable route number |
| `trip_id` | String(200) | Nullable | GTFS trip identifier |
| `latitude` | Float | Not null | WGS84 latitude |
| `longitude` | Float | Not null | WGS84 longitude |
| `bearing` | Float | Nullable | Compass heading (0-360) |
| `speed_kmh` | Float | Nullable | Speed in km/h |
| `delay_seconds` | SmallInteger | Not null, default=0 | Schedule deviation (positive=late) |
| `current_status` | String(20) | Not null, default="IN_TRANSIT_TO" | GTFS-RT vehicle stop status |

**Indexes:** `(vehicle_id, recorded_at)`, `(route_id, recorded_at)`, `(feed_id, recorded_at)`

**TimescaleDB policies:**
- Compression: automatic after 7 days (`segmentby: feed_id, vehicle_id; orderby: recorded_at DESC`)
- Retention: automatic drop after 90 days

**Note:** Does not use `TimestampMixin`. The hypertable is partitioned by `recorded_at` (GTFS-RT measurement time), not DB insert time. Adding `created_at`/`updated_at` would increase row size on a high-volume table without operational benefit.

## Business Rules

1. Route ID resolved from vehicle data first, then trip-to-route lookup via static cache
2. Delay computed from next stop time update relative to current stop sequence
3. Speed converted from GTFS-RT m/s to km/h (rounded to 1 decimal)
4. Timestamps converted from POSIX to ISO 8601 UTC
5. Each feed has independent `feed_id` and `operator_name` attached to vehicle positions
6. Feed configs support per-feed `poll_interval_seconds` and `enabled` toggle
7. Legacy single-feed config (`GTFS_RT_VEHICLE_URL`) auto-migrates to multi-feed format
8. Real-time REST endpoints: authenticated (any role) — GTFS-RT vehicle positions and feed status
9. Historical REST endpoints: require admin, dispatcher, or editor role (RBAC via `require_role()`)
10. WebSocket endpoint: JWT authentication required via `?token=` query parameter
11. Historical position writes controlled by `POSITION_HISTORY_ENABLED` feature flag
12. Vehicle positions retained for 90 days (TimescaleDB retention policy), compressed after 7 days
10. WebSocket max connections capped at `WS_MAX_CONNECTIONS` (default 100) to prevent memory exhaustion
11. Nginx limits WebSocket connections to 10 per IP (`limit_conn addr 10`)

## Integration Points

- **`app.core.redis`**: Redis client singleton (`get_redis()`, `close_redis()`) with lifespan management
- **`app.core.config`**: `TransitFeedConfig` model, `transit_feeds` computed property, `REDIS_URL`
- **`app.core.agents.tools.transit.client`**: Reuses `GTFSRealtimeClient` for GTFS-RT feed parsing
- **`app.core.agents.tools.transit.static_cache`**: Reuses `GTFSStaticCache` singleton for route/stop/trip name resolution
- **`app.core.agents.tools.transit.static_store`**: DB-backed GTFSStaticStore for route/stop/trip name resolution (replaced HTTP-based GTFSStaticCache)
- **`app.core.agents.exceptions`**: Uses `TransitDataError` for feed failure propagation (HTTP 503)
- **`app.core.database`**: `get_db()` for REST endpoint sessions, `get_db_context()` for standalone poller writes
- **`app.core.health`**: Redis health check at `/health/redis`, included in `/health/ready`
- **`app.transit.ws_manager`**: ConnectionManager singleton, shared between ws_routes (client mgmt) and ws_subscriber (broadcast)
- **`app.transit.ws_subscriber`**: Background asyncio task bridging Redis Pub/Sub → ConnectionManager
- **`nginx/nginx.conf`**: `/ws/` location block with WebSocket upgrade headers, 3600s timeouts, 10/IP connection limit
- **CMS Frontend**: `cms/apps/web/src/hooks/use-vehicle-positions.ts` uses WebSocket real-time push (~100ms latency) with automatic HTTP polling fallback, route filtering via subscribe message, connection status badge (Live/Polling/Connecting)

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/transit/vehicles` | Any role | All vehicle positions across all feeds (optional `?route_id=X`, `?feed_id=Y`) |
| GET | `/api/v1/transit/feeds` | Any role | Status of all configured feeds (feed_id, operator, enabled) |
| GET | `/api/v1/transit/vehicles/{vehicle_id}/history` | admin/dispatcher/editor | Historical positions for a vehicle within a time range |
| GET | `/api/v1/transit/routes/{route_id}/delay-trend` | admin/dispatcher/editor | Aggregated delay trend with TimescaleDB `time_bucket()` |
| WS | `/ws/transit/vehicles?token=JWT` | JWT token | Live vehicle position stream with subscribe/unsubscribe filtering |

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

# WebSocket live streaming
WS_ENABLED=true                      # Feature flag (disable to stop accepting WS connections)
WS_HEARTBEAT_INTERVAL_SECONDS=30     # Application-level ping interval
WS_MAX_CONNECTIONS=100               # Hard cap on concurrent WebSocket connections

# Historical position storage (TimescaleDB)
POSITION_HISTORY_ENABLED=true        # Feature flag for TimescaleDB writes from poller
REDIS_VEHICLE_TTL_SECONDS=60         # TTL for Redis vehicle position keys
```

## Planned Upgrades

| Upgrade | Phase | Description |
|---------|-------|-------------|
| ~~WebSocket streaming~~ | ~~Phase 1~~ | ✅ **Implemented** — `WS /ws/transit/vehicles` with per-client feed/route filtering, Redis Pub/Sub fan-out |
| ~~GTFS database import~~ | ~~Phase 1~~ | ✅ **Implemented** — DB-backed GTFSStaticStore replacing HTTP/ZIP-based cache |
| ~~TimescaleDB history~~ | ~~Phase 1~~ | ✅ **Implemented** — `vehicle_positions` hypertable with compression, 90-day retention, vehicle history + delay trend endpoints |
| Additional city feeds | Phase 2 | Daugavpils, Liepaja, Rezekne GPS text feeds |
| Train positions | Phase 2 | WebSocket listener for `wss://trainmap.pv.lv/ws` |
| ETA calculator | Phase 2 | Valhalla map-matching + distance-to-stop / speed calculation |
| GTFS-RT publisher | Phase 2 | Serve combined GTFS-RT feed at `/api/v1/transit/gtfs-rt/*.pb` |

See `docs/PLANNING/Implementation-Plan.md` for the complete 4-phase roadmap.
