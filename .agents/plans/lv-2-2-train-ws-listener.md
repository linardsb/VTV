# Plan: LV-2.2 Train Positions via WebSocket

## Context

Trains are the #1 missing transport mode in VTV. PV (Pasažieru Vilciens) publishes live train positions via WebSocket at `wss://trainmap.pv.lv/ws` — no API key needed. Adding trains alongside buses/trolleybuses/trams gives dispatchers a complete Latvia transit view.

## Security Context Assessment

**Active contexts:** CTX-INFRA (WebSocket connection to external service, new config settings)

- No new REST endpoints → CTX-RBAC not triggered (trains flow through existing pipeline)
- No user input handling → CTX-INPUT not triggered
- No file uploads → CTX-FILE not triggered
- No agent tools → CTX-AGENT not triggered
- External WebSocket connection → CTX-INFRA: URL must be configurable via env var, not hardcoded

## Research Summary

### Reference Pattern: `app/transit/ws_subscriber.py`
The existing Redis Pub/Sub subscriber (`ws_subscriber.py:22-93`) is the closest pattern — persistent async connection loop with exponential backoff reconnection (1s → 2s → 4s → ... → 30s max), CancelledError handling for graceful shutdown, module-level `_subscriber_task` management with `start_*`/`stop_*` functions.

### Write Pipeline: `app/transit/poller.py:84-208`
The GTFS-RT poller demonstrates the exact Redis + TimescaleDB + Pub/Sub write pipeline:
1. Build `EnrichedVehicle` dict (TypedDict at `poller.py:31-49`)
2. Redis pipeline write: `vehicle:{feed_id}:{vehicle_id}` keys + `feed:{feed_id}:vehicles` set (lines 107-135)
3. TimescaleDB batch insert via `batch_insert_positions()` from `repository.py:29-51` (lines 137-181)
4. Pub/Sub publish to `transit:vehicles:{feed_id}` channel (lines 183-203)

### Config Pattern: `app/core/config.py:85-103`
Feature flags follow `{feature}_enabled: bool = True` with related URL settings. Train WS settings should sit near the existing `poller_enabled` flag.

### Lifespan: `app/main.py:87-266`
Background tasks start between lines 123-174. Shutdown tasks register at lines 176-253 (LIFO order).

### Frontend: Auto-compatible
- `useVehiclePositions` hook (`hooks/use-vehicle-positions.ts`) already handles multi-feed via `feed_id`
- `routeTypeColor()` (line 73) returns orange (default) for `route_type=2` (rail) — needs a rail-specific color
- `MapFilters` (`map-filters.tsx:20-25`) needs a "Train" option added to `ROUTE_TYPE_OPTIONS`
- Vehicle filtering on map (`vehicle-map.tsx:95-110`, `map/page.tsx:121-131`) needs `route_type=2` case

### Dependencies
- `websockets` library needed — not currently in `pyproject.toml`

## Test Landscape

### Existing Test Patterns (from `app/transit/tests/`)
- **Mock Redis:** `AsyncMock()` for client, `MagicMock()` for pipelines, `AsyncMock` for `.execute()` and `.publish()`
- **Mock asyncio.sleep:** `@patch("...asyncio.sleep", new_callable=AsyncMock)` to avoid delays + verify backoff values
- **Reconnection tests:** `side_effect` functions that fail on first call, succeed on second (see `test_ws_subscriber.py`)
- **Start/stop lifecycle:** Verify task creation + cancellation patterns
- **No integration markers:** Transit tests use `@pytest.mark.asyncio` only

### Baseline Type Checks
- **Pyright:** 0 errors on `app/transit/`
- **Mypy:** 0 errors on `app/transit/` (40 source files)
- Target: **0 errors** after implementation

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| ADD DEP | `pyproject.toml` | Add `websockets>=14.0` |
| CREATE | `app/transit/train_ws_listener.py` | WebSocket client: connect, parse, normalize, write to Redis+TimescaleDB+Pub/Sub |
| UPDATE | `app/core/config.py` | Add `train_ws_enabled`, `train_ws_url`, `train_ws_reconnect_max` settings |
| UPDATE | `app/main.py` | Start/stop train WS listener in lifespan + shutdown coordinator |
| UPDATE | `cms/apps/web/src/hooks/use-vehicle-positions.ts` | Add rail color to `routeTypeColor()` |
| UPDATE | `cms/apps/web/src/components/map/map-filters.tsx` | Add "Train" to `ROUTE_TYPE_OPTIONS` |
| UPDATE | `cms/apps/web/src/components/map/vehicle-map.tsx` | Add `route_type=2` filter case |
| UPDATE | `cms/apps/web/src/app/[locale]/(dashboard)/map/page.tsx` | Add `route_type=2` filter case |
| UPDATE | `cms/apps/web/messages/en.json` | Add `map.filters.train` i18n key |
| UPDATE | `cms/apps/web/messages/lv.json` | Add `map.filters.train` i18n key |
| CREATE | `app/transit/tests/test_train_ws_listener.py` | 10+ unit tests |

## Implementation Steps

### Step 1: Add `websockets` dependency
**File:** `pyproject.toml`
Add `"websockets>=14.0",` to the `dependencies` array.

**Validation:** `uv sync && uv run python -c "import websockets; print(websockets.__version__)"`

### Step 2: Add config settings
**File:** `app/core/config.py`

After the `gtfs_auto_import_hour_utc` setting (line ~103), add:

```python
# Train WebSocket listener (LV-2.2)
train_ws_enabled: bool = True
train_ws_url: str = "wss://trainmap.pv.lv/ws"
train_ws_reconnect_max_seconds: int = 60
```

**Validation:** `uv run pyright app/core/config.py`

### Step 3: Create `train_ws_listener.py`
**File:** `app/transit/train_ws_listener.py`

**Architecture** (follows `ws_subscriber.py` pattern):
- Module-level `_listener_task: asyncio.Task[None] | None = None`
- `MAX_BACKOFF_SECONDS` from config
- `async def _listen_loop(settings: Settings) -> None` — main loop:
  1. Connect to `settings.train_ws_url` via `websockets.connect()`
  2. Reset backoff on successful connection
  3. `async for message in ws:` — parse JSON messages
  4. Call `_process_message(message, redis_client, db_session_factory, settings)` for each
  5. On `CancelledError` → close WebSocket, log, return
  6. On any `Exception` → log warning, sleep with backoff, retry
- `async def _process_message(raw: str, redis, db_factory, settings) -> None`:
  1. Parse JSON → extract train position fields
  2. Build `EnrichedVehicle` dict with `feed_id="pv_trains"`, `route_type=2`, `operator_name="Pasažieru vilciens"`
  3. Write to Redis: `vehicle:pv_trains:{train_id}` + `feed:pv_trains:vehicles` set
  4. Write to TimescaleDB via `batch_insert_positions()` (non-blocking, errors logged)
  5. Publish to `transit:vehicles:pv_trains` Pub/Sub channel
- `async def start_train_ws_listener(settings: Settings) -> asyncio.Task[None]`
- `async def stop_train_ws_listener() -> None`

**Key design decisions:**
- Message format from `wss://trainmap.pv.lv/ws` must be discovered at runtime — add defensive JSON parsing with fallback field extraction. Log raw message on first connect for debugging.
- Use `websockets.connect()` with `ping_interval=20, ping_timeout=10, close_timeout=5`
- `source="train-ws"` in TimescaleDB records to distinguish from GTFS-RT positions

**Logging events:**
- `transit.train_ws.listener_started`
- `transit.train_ws.connected` (with url)
- `transit.train_ws.message_received` (per batch, with count)
- `transit.train_ws.message_parse_failed` (with error, raw snippet)
- `transit.train_ws.redis_write_failed`
- `transit.train_ws.history_write_completed` (with records_inserted)
- `transit.train_ws.pubsub_publish_failed`
- `transit.train_ws.reconnecting` (with error, backoff_seconds)
- `transit.train_ws.listener_stopped`

**Pyright directives** (line 1): `# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false`

**Validation:** `uv run ruff format app/transit/train_ws_listener.py && uv run ruff check --fix app/transit/train_ws_listener.py && uv run pyright app/transit/train_ws_listener.py && uv run mypy app/transit/train_ws_listener.py`

### Step 4: Register in lifespan
**File:** `app/main.py`

**Startup** — after `start_feed_import_task()` (around line 160), add:
```python
# Start train WebSocket listener (LV-2.2)
if settings.train_ws_enabled:
    from app.transit.train_ws_listener import start_train_ws_listener
    await start_train_ws_listener(settings)
    logger.info("transit.train_ws.listener_started")
```

**Shutdown** — after the `gtfs_feed_import` registration (around line 253), add:
```python
if settings.train_ws_enabled:
    from app.transit.train_ws_listener import stop_train_ws_listener
    coordinator.register(
        ShutdownTask(
            name="train_ws_listener",
            drain_timeout_s=5.0,
            drain=stop_train_ws_listener,
        )
    )
```

**Validation:** `uv run pyright app/main.py && uv run mypy app/main.py`

### Step 5: Frontend — add rail color + train filter

**5a. `cms/apps/web/src/hooks/use-vehicle-positions.ts` (line 73-79)**
Add rail case before the default return:
```typescript
function routeTypeColor(routeType: number): string {
  if (routeType === 0 || (routeType >= 900 && routeType <= 999)) return "#E53935"; // Tram
  if (routeType >= 800 && routeType <= 899) return "#1E88E5"; // Trolleybus
  // Rail (2, 100-199)
  if (routeType === 2 || (routeType >= 100 && routeType <= 199)) return "#43A047"; // Green for trains
  return "#FB8C00"; // Bus and default
}
```

**5b. `cms/apps/web/src/components/map/map-filters.tsx` (line 20-25)**
Add train option to `ROUTE_TYPE_OPTIONS`:
```typescript
const ROUTE_TYPE_OPTIONS: { type: number | null; key: string }[] = [
  { type: null, key: "allTypes" },
  { type: 3, key: "bus" },
  { type: 11, key: "trolleybus" },
  { type: 0, key: "tram" },
  { type: 2, key: "train" },
];
```

**5c. `cms/apps/web/src/components/map/vehicle-map.tsx` (lines 95-110)**
Add `route_type=2` case in the filter:
```typescript
if (selectedRouteType === 2)
  return v.routeType === 2 || (v.routeType >= 100 && v.routeType <= 199);
```

**5d. `cms/apps/web/src/app/[locale]/(dashboard)/map/page.tsx` (lines 121-131)**
Add `route_type=2` case in the filter (same pattern as vehicle-map):
```typescript
if (selectedRouteType === 2)
  return v.routeType === 2 || (v.routeType >= 100 && v.routeType <= 199);
```

**5e. i18n keys**
- `en.json`: Add `"train": "Train"` under `map.filters`
- `lv.json`: Add `"train": "Vilciens"` under `map.filters`

**Validation:** `cd cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint`

### Step 6: Write tests
**File:** `app/transit/tests/test_train_ws_listener.py`

Tests (following `test_ws_subscriber.py` patterns):

1. **`test_process_message_writes_to_redis`** — Mock Redis, verify `pipeline().set()` called with correct key pattern `vehicle:pv_trains:{train_id}`
2. **`test_process_message_enriches_with_feed_id`** — Verify `feed_id="pv_trains"` and `route_type=2` in enriched data
3. **`test_process_message_publishes_pubsub`** — Verify `redis.publish("transit:vehicles:pv_trains", ...)` called
4. **`test_process_message_writes_history`** — Mock `batch_insert_positions`, verify called with correct records
5. **`test_process_message_invalid_json`** — Pass `"not json"`, verify logged but no crash
6. **`test_process_message_missing_fields`** — Pass JSON missing required fields, verify logged
7. **`test_listener_reconnects_with_backoff`** — Mock `websockets.connect` to raise on first call, mock `asyncio.sleep`, verify backoff value
8. **`test_listener_backoff_caps_at_max`** — Verify backoff never exceeds `train_ws_reconnect_max_seconds`
9. **`test_start_creates_task`** — `start_train_ws_listener()` returns an `asyncio.Task`
10. **`test_stop_cancels_task`** — `stop_train_ws_listener()` cancels and awaits the task
11. **`test_history_write_failure_non_blocking`** — Mock `batch_insert_positions` to raise, verify Redis write still completes

**Mock patterns:**
- `@patch("app.transit.train_ws_listener.websockets.connect")` — mock WebSocket connection
- `@patch("app.transit.train_ws_listener.get_redis")` — mock Redis
- `@patch("app.transit.train_ws_listener.asyncio.sleep", new_callable=AsyncMock)` — avoid real delays
- `@patch("app.transit.train_ws_listener.get_db_context")` — mock DB session factory

**Validation:** `uv run pytest app/transit/tests/test_train_ws_listener.py -v`

## Preflight Warnings

- The WS message format from `wss://trainmap.pv.lv/ws` is undocumented. The implementation MUST log the first raw message received for format discovery, and handle unknown formats gracefully with structured error logging.
- `websockets` library typing may need pyright file-level directives (added in step 3).
- Redis pipeline mock pattern: `MagicMock()` for pipeline, `AsyncMock` for `.execute()` only (anti-pattern #35).

## Security Checklist

No new REST endpoints — existing auth + rate limiting covers the read path.

- [x] External URL configurable via env var (not hardcoded) — `TRAIN_WS_URL`
- [x] Feature gated via `TRAIN_WS_ENABLED` config flag
- [x] No credentials in WebSocket URL (public endpoint)
- [x] Error logging never includes raw message content beyond truncated snippet
- [x] Reconnect backoff prevents tight-loop resource exhaustion

## Verification

- [ ] `make lint` passes (ruff format + ruff check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `uv run pytest app/transit/tests/test_train_ws_listener.py -v` — all 11 tests pass
- [ ] `make test` passes — no regressions in existing 2179 tests
- [ ] Pyright errors on `app/transit/` = 0 (same as baseline)
- [ ] Frontend: `pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint` passes
- [ ] Manual: Start dev stack → if WS endpoint available, trains appear on `/map` as green rail icons
