# Plan: WebSocket Live Streaming for Vehicle Positions

## Feature Metadata
**Feature Type**: Enhancement (real-time upgrade to existing transit module)
**Estimated Complexity**: High
**Primary Systems Affected**: `app/transit/`, `app/core/config.py`, `app/core/redis.py`, `nginx/nginx.conf`

## Feature Description

Replace the current HTTP polling pattern for vehicle positions with WebSocket push notifications. The existing system has the backend poller writing to Redis every 10 seconds and the frontend polling the REST API every 10 seconds via SWR. This creates up to 20 seconds of combined latency (worst case: poller just wrote, frontend just polled, next poll in 10s).

WebSocket streaming eliminates the frontend polling leg entirely. After the backend poller writes fresh vehicle positions to Redis, it publishes a notification on a Redis Pub/Sub channel. A background subscriber task receives the notification and pushes the data to all connected WebSocket clients instantly. This reduces end-to-end latency from ~10-20s to ~100ms (Redis Pub/Sub + WebSocket push).

The REST API endpoint (`GET /api/v1/transit/vehicles`) is preserved as a fallback. The frontend will attempt WebSocket first and degrade to HTTP polling if the connection fails. This plan covers the **backend WebSocket infrastructure only** — the frontend hook changes are a separate `/fe-planning` task that depends on this backend work.

## User Story

As a transit dispatcher viewing the live map,
I want vehicle positions to update in near-real-time via WebSocket push,
So that I can see vehicle movements with sub-second latency instead of 10-20 second polling delays.

## Solution Approach

**Architecture: Redis Pub/Sub + WebSocket fan-out**

The poller already writes enriched vehicle data to Redis. We add a single `PUBLISH` call after each poll cycle to broadcast the updated positions on a `transit:vehicles:{feed_id}` channel. A background asyncio task subscribes to these channels and fans out the data to all connected WebSocket clients via a ConnectionManager.

```
Poller → Redis SET (existing) + Redis PUBLISH (new)
                                      ↓
                          Pub/Sub Subscriber (new background task)
                                      ↓
                          ConnectionManager.broadcast() (new)
                                      ↓
                          WebSocket clients (filtered by route/feed)
```

**Approach Decision:**
We chose Redis Pub/Sub because:
- Zero new infrastructure — Redis is already running for vehicle caching
- Poller already writes to Redis — adding PUBLISH is a one-line change per cycle
- Pub/Sub handles multi-worker fan-out — even with 4 Gunicorn workers, only the leader runs the poller, but ALL workers can subscribe and push to their own WebSocket clients
- Sub-millisecond latency — Redis PUBLISH/SUBSCRIBE is near-instant

**Alternatives Considered:**
- **Direct asyncio broadcast (no Pub/Sub)**: Rejected because only the leader worker runs the poller. Other workers wouldn't receive updates for their WebSocket clients. Pub/Sub solves multi-worker fan-out.
- **Server-Sent Events (SSE)**: Rejected because SSE is unidirectional (server→client only). WebSocket allows the client to send subscribe/unsubscribe messages with route/feed filters, enabling per-connection filtering. SSE would require separate endpoints per filter combination.
- **WebSocket with direct GTFS-RT fetch per client**: Rejected because it would multiply GTFS-RT API calls. The poller pattern (one fetch, many readers) is the correct architecture for shared real-time data.

**WebSocket Authentication:**
Browser WebSocket API does not support custom headers. JWT is passed as a query parameter (`?token=JWT`), validated on connection handshake. The token is verified using the same `decode_token` + `is_token_revoked` logic as HTTP endpoints, but without FastAPI's dependency injection (WebSocket endpoints use manual validation).

**Connection Lifecycle:**
1. Client connects to `ws://host/ws/transit/vehicles?token=JWT`
2. Server validates JWT, accepts connection
3. Client sends JSON subscribe message: `{"action": "subscribe", "route_id": "22", "feed_id": "riga"}`
4. Server registers client with filters in ConnectionManager
5. On each poller cycle, Pub/Sub subscriber receives data, ConnectionManager broadcasts to matching clients
6. Server sends periodic ping frames (30s interval) for keepalive
7. Client disconnect: ConnectionManager removes client and cleans up filters

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/transit/poller.py` (lines 55-101) — `poll_once()` method where Redis PUBLISH will be added
- `app/transit/poller.py` (lines 226-286) — `start_pollers()` for background task lifecycle pattern
- `app/transit/poller.py` (lines 289-330) — `stop_pollers()` for graceful shutdown pattern
- `app/transit/redis_reader.py` (lines 15-54) — `get_vehicles_from_redis()` for Redis read pattern
- `app/transit/schemas.py` (lines 1-66) — `VehiclePosition` and `VehiclePositionsResponse` schemas
- `app/transit/routes.py` (lines 1-68) — Existing REST endpoints, auth pattern
- `app/transit/service.py` (lines 1-85) — Service layer, singleton pattern
- `app/core/redis.py` (lines 1-57) — Redis client singleton
- `app/core/config.py` (lines 77-92) — Transit-related settings
- `app/auth/dependencies.py` (lines 45-118) — `get_current_user()` for JWT validation pattern (we replicate this logic for WebSocket)
- `app/auth/token.py` — `decode_token()` and `is_token_revoked()` functions
- `app/core/middleware.py` (lines 151-183) — `setup_middleware()` for understanding middleware stack
- `app/main.py` (lines 60-112) — Application lifespan for start/stop of background tasks

### Similar Features (Examples to Follow)
- `app/transit/poller.py` (lines 159-176) — Background task loop pattern (FeedPoller.run)
- `app/transit/poller.py` (lines 185-224) — Redis-based leader election pattern (for subscriber)
- `app/core/agents/routes.py` — Example of SSE streaming endpoint (similar async generator pattern)

### Files to Modify
- `app/transit/poller.py` — Add Redis PUBLISH after poll_once writes
- `app/core/config.py` — Add WebSocket settings
- `app/main.py` — Register WebSocket router, start/stop subscriber in lifespan
- `nginx/nginx.conf` — Add WebSocket proxy location block

## Implementation Plan

### Phase 1: Foundation
Add configuration settings and define message schemas for WebSocket communication. These are the building blocks that all subsequent tasks depend on.

### Phase 2: Core Implementation
Build the three core components: ConnectionManager (tracks WebSocket clients and handles broadcast), Redis Pub/Sub integration (publish in poller, subscribe in background task), and the WebSocket endpoint (handles auth, connection lifecycle, and message routing).

### Phase 3: Integration & Validation
Wire everything into the application lifespan, update nginx for WebSocket proxying, and write comprehensive tests.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Add WebSocket Configuration Settings
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add WebSocket-related settings to the `Settings` class. These control whether WebSocket is enabled and connection behavior.

Add these fields to the `Settings` class (after the existing `poller_leader_lock_ttl` field around line 92):

```python
# WebSocket live streaming
ws_enabled: bool = True
ws_heartbeat_interval_seconds: int = 30
ws_max_connections: int = 100
```

- `ws_enabled` — Feature flag to disable WebSocket without code changes. Default `True` since the infrastructure is available when poller is running.
- `ws_heartbeat_interval_seconds` — Interval for WebSocket ping frames. 30s keeps connections alive through proxies and load balancers that typically have 60s idle timeouts.
- `ws_max_connections` — Hard cap on concurrent WebSocket connections. Prevents memory exhaustion. 100 is generous for 10-20 dispatchers.

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py`
- `uv run mypy app/core/config.py`
- `uv run pyright app/core/config.py`

---

### Task 2: Create WebSocket Message Schemas
**File:** `app/transit/ws_schemas.py` (create new)
**Action:** CREATE

Define Pydantic models for WebSocket message protocol. These are separate from REST schemas because WebSocket messages have different structure (action-based, bidirectional).

```python
"""Pydantic schemas for WebSocket vehicle position streaming.

These define the bidirectional message protocol:
- Client → Server: subscribe/unsubscribe with optional filters
- Server → Client: vehicle position updates, errors, acknowledgements
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class WsSubscribeMessage(BaseModel):
    """Client request to subscribe to vehicle position updates.

    Attributes:
        action: Must be "subscribe".
        route_id: Optional route filter (e.g., "22"). None = all routes.
        feed_id: Optional feed filter (e.g., "riga"). None = all feeds.
    """

    model_config = ConfigDict(strict=True)

    action: Literal["subscribe"]
    route_id: str | None = None
    feed_id: str | None = None


class WsUnsubscribeMessage(BaseModel):
    """Client request to unsubscribe from updates.

    Attributes:
        action: Must be "unsubscribe".
    """

    model_config = ConfigDict(strict=True)

    action: Literal["unsubscribe"]


class WsVehicleUpdate(BaseModel):
    """Server push of vehicle position data.

    Attributes:
        type: Message type discriminator.
        feed_id: Which feed this update is from.
        count: Number of vehicles in this update.
        vehicles: List of vehicle position dicts (same shape as REST VehiclePosition).
        timestamp: ISO 8601 server time when update was assembled.
    """

    model_config = ConfigDict(strict=True)

    type: Literal["vehicle_update"] = "vehicle_update"
    feed_id: str
    count: int
    vehicles: list[dict[str, object]]
    timestamp: str


class WsError(BaseModel):
    """Server error message sent to client.

    Attributes:
        type: Message type discriminator.
        code: Machine-readable error code.
        message: Human-readable error description.
    """

    model_config = ConfigDict(strict=True)

    type: Literal["error"] = "error"
    code: str
    message: str


class WsAck(BaseModel):
    """Server acknowledgement of client action.

    Attributes:
        type: Message type discriminator.
        action: Which client action was acknowledged.
        filters: Currently active filters after the action.
    """

    model_config = ConfigDict(strict=True)

    type: Literal["ack"] = "ack"
    action: str
    filters: dict[str, str | None]
```

**Per-task validation:**
- `uv run ruff format app/transit/ws_schemas.py`
- `uv run ruff check --fix app/transit/ws_schemas.py`
- `uv run mypy app/transit/ws_schemas.py`
- `uv run pyright app/transit/ws_schemas.py`

---

### Task 3: Create WebSocket Connection Manager
**File:** `app/transit/ws_manager.py` (create new)
**Action:** CREATE

The ConnectionManager tracks active WebSocket connections, their subscription filters, and handles broadcasting vehicle updates to matching clients.

Key design:
- Each connection has optional `route_id` and `feed_id` filters
- `broadcast()` checks each client's filters before sending
- Thread-safe via asyncio (single event loop, no locks needed)
- Automatic cleanup on disconnect
- Hard cap on `max_connections` from settings

Implementation requirements:
- Class `ConnectionManager` with:
  - `__init__(self, max_connections: int)` — Initialize with connection limit
  - `async connect(self, websocket: WebSocket, route_id: str | None, feed_id: str | None) -> bool` — Accept connection if under limit. Returns False if limit reached (caller sends 1008 close). Store connection with filters in a dict keyed by WebSocket id.
  - `disconnect(self, websocket: WebSocket) -> None` — Remove connection from tracking dict.
  - `update_filters(self, websocket: WebSocket, route_id: str | None, feed_id: str | None) -> None` — Update subscription filters for an existing connection.
  - `async broadcast(self, feed_id: str, vehicles: list[dict[str, object]], timestamp: str) -> None` — Send vehicle update to all matching clients. Match logic: client matches if (client.feed_id is None OR client.feed_id == feed_id) AND (client.route_id is None means send all, OR filter vehicles to matching route_id). Use `WsVehicleUpdate` schema for serialization. Catch and log `WebSocketDisconnect` and any `Exception` per client (don't let one broken client stop broadcast to others). Remove disconnected clients.
  - `@property active_count(self) -> int` — Number of active connections.
- Use structlog logger with `transit.ws.` prefix for all events
- Import `WebSocket` from `fastapi`, `WebSocketDisconnect` from `starlette.websockets`
- Import `WsVehicleUpdate` from `app.transit.ws_schemas`
- Import `get_logger` from `app.core.logging`

Internal data structure for tracking connections:
```python
@dataclass
class _ClientSubscription:
    websocket: WebSocket
    route_id: str | None
    feed_id: str | None
```
Use `dict[int, _ClientSubscription]` keyed by `id(websocket)`.

**Per-task validation:**
- `uv run ruff format app/transit/ws_manager.py`
- `uv run ruff check --fix app/transit/ws_manager.py`
- `uv run mypy app/transit/ws_manager.py`
- `uv run pyright app/transit/ws_manager.py`

---

### Task 4: Add Redis PUBLISH to Poller
**File:** `app/transit/poller.py` (modify existing)
**Action:** UPDATE

After the existing `pipe.execute()` in `poll_once()` (line 92), add a Redis PUBLISH call to broadcast the updated vehicle data on a Pub/Sub channel. This is the "push trigger" that notifies WebSocket subscribers.

Changes to `poll_once()` method:
1. After the successful `await pipe.execute()` on line 92 (inside the try block, before `return count`), add:

```python
# Publish vehicle update to Pub/Sub channel for WebSocket subscribers
if count > 0:
    try:
        channel = f"transit:vehicles:{feed_id}"
        # Serialize the full vehicle list as JSON for subscribers
        # (subscribers push directly to WebSocket clients without re-reading Redis)
        payload = json.dumps({
            "feed_id": feed_id,
            "count": count,
            "vehicles": [
                self._enrich_vehicle(vp, trip_update_map, static)
                for vp in raw_vehicles
            ],
            "timestamp": datetime.now(tz=UTC).isoformat(),
        })
        await redis_client.publish(channel, payload)
    except Exception as e:
        # Pub/Sub failure must never block the poller
        logger.warning(
            "transit.poller.pubsub_publish_failed",
            feed_id=feed_id,
            error=str(e),
            error_type=type(e).__name__,
        )
```

IMPORTANT: The vehicles are already enriched in the loop above, but the enriched dicts are not saved — they're serialized directly into Redis SET. To avoid re-enriching, collect the enriched dicts during the existing loop. Modify the loop that starts at line 77:

Change the existing loop from:
```python
for vp in raw_vehicles:
    vehicle_data = self._enrich_vehicle(vp, trip_update_map, static)
    key = f"vehicle:{feed_id}:{vp.vehicle_id}"
    pipe.set(key, json.dumps(vehicle_data), ex=ttl)
    count += 1
```

To:
```python
enriched_vehicles: list[dict[str, object]] = []
for vp in raw_vehicles:
    vehicle_data = self._enrich_vehicle(vp, trip_update_map, static)
    key = f"vehicle:{feed_id}:{vp.vehicle_id}"
    pipe.set(key, json.dumps(vehicle_data), ex=ttl)
    enriched_vehicles.append(vehicle_data)
    count += 1
```

Then the PUBLISH payload uses `enriched_vehicles` instead of re-calling `_enrich_vehicle`:
```python
payload = json.dumps({
    "feed_id": feed_id,
    "count": count,
    "vehicles": enriched_vehicles,
    "timestamp": datetime.now(tz=UTC).isoformat(),
})
```

Also add `from datetime import UTC, datetime` — this import already exists at line 7, so no change needed.

**Per-task validation:**
- `uv run ruff format app/transit/poller.py`
- `uv run ruff check --fix app/transit/poller.py`
- `uv run mypy app/transit/poller.py`
- `uv run pyright app/transit/poller.py`
- `uv run pytest app/transit/tests/test_poller.py -v` — existing tests still pass

---

### Task 5: Create Redis Pub/Sub Subscriber
**File:** `app/transit/ws_subscriber.py` (create new)
**Action:** CREATE

Background asyncio task that subscribes to Redis Pub/Sub channels and dispatches vehicle updates to the ConnectionManager for WebSocket broadcast.

Key design:
- Subscribes to `transit:vehicles:*` pattern (all feed channels)
- Parses each message as JSON, extracts feed_id and vehicles
- Calls `ConnectionManager.broadcast()` with the parsed data
- Runs as a background asyncio task, started in app lifespan
- Handles reconnection on Redis disconnect (exponential backoff: 1s, 2s, 4s, max 30s)
- Graceful shutdown via cancellation

Implementation requirements:
- `async def start_ws_subscriber(manager: ConnectionManager) -> asyncio.Task[None]` — Creates and returns the subscriber background task. Stores the manager reference in a module-level variable for the task to access.
- `async def stop_ws_subscriber() -> None` — Cancels the subscriber task, handles CancelledError.
- Internal `async def _subscribe_loop(manager: ConnectionManager) -> None`:
  1. Get Redis client via `get_redis()`
  2. Create a Pub/Sub subscription: `pubsub = redis_client.pubsub()`
  3. Subscribe to pattern: `await pubsub.psubscribe("transit:vehicles:*")`
  4. Loop: `async for message in pubsub.listen():`
     - Skip non-pmessage types (subscribe confirmations, etc.)
     - Parse `message["data"]` as JSON
     - Extract `feed_id`, `vehicles`, `timestamp`
     - Call `await manager.broadcast(feed_id, vehicles, timestamp)`
  5. On exception: log warning, sleep with exponential backoff, reconnect
  6. On `CancelledError`: unsubscribe, close pubsub, break

- Import `asyncio`, `json` from stdlib
- Import `get_redis` from `app.core.redis`
- Import `get_logger` from `app.core.logging`
- Import `get_settings` from `app.core.config`
- Import `ConnectionManager` from `app.transit.ws_manager`
- Add pyright file-level directive: `# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false`
- Add `# type: ignore[misc]` on Redis pubsub await lines (Redis async stubs issue, rule 34)

**Per-task validation:**
- `uv run ruff format app/transit/ws_subscriber.py`
- `uv run ruff check --fix app/transit/ws_subscriber.py`
- `uv run mypy app/transit/ws_subscriber.py`
- `uv run pyright app/transit/ws_subscriber.py`

---

### Task 6: Create WebSocket Route
**File:** `app/transit/ws_routes.py` (create new)
**Action:** CREATE

FastAPI WebSocket endpoint with JWT authentication. This is the client-facing entry point for live vehicle streaming.

Key design:
- Path: `/ws/transit/vehicles` (separate prefix from REST `/api/v1/transit/`)
- Auth: JWT token in query parameter `?token=...`
- Protocol: JSON text messages for subscribe/unsubscribe, JSON text for server pushes
- Heartbeat: Server sends WebSocket ping frames at configured interval

Implementation:
```python
"""WebSocket endpoint for real-time vehicle position streaming.

Authentication is via JWT query parameter since the browser WebSocket API
does not support custom headers. The token is validated using the same
decode_token + is_token_revoked logic as HTTP endpoints.
"""
```

- Create `ws_router = APIRouter()` (no prefix — path is explicit in the endpoint decorator)
- Single endpoint: `@ws_router.websocket("/ws/transit/vehicles")`
- Function signature: `async def ws_vehicle_stream(websocket: WebSocket, token: str | None = Query(None)):`

**Authentication flow (manual, not via Depends):**
1. If `token` is None: `await websocket.close(code=4001, reason="Missing token")` and return
2. Call `decode_token(token)` from `app.auth.token`
3. If payload is None or `payload.type != "access"`: close with code 4001 "Invalid token"
4. Call `await is_token_revoked(payload.jti)` from `app.auth.token`
5. If revoked: close with code 4001 "Token revoked"
6. Token valid — proceed to accept

**Connection flow:**
1. Get `ConnectionManager` singleton via `get_ws_manager()`
2. Call `manager.connect(websocket, route_id=None, feed_id=None)` — initially no filters
3. If connect returns False (limit reached): close with code 1013 "Try again later"
4. `await websocket.accept()`
5. Log `transit.ws.connected` with user info from token payload
6. Send initial ack: `WsAck(action="connected", filters={"route_id": None, "feed_id": None})`

**Message loop (try/except WebSocketDisconnect):**
```python
try:
    while True:
        raw = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=settings.ws_heartbeat_interval_seconds + 10,
        )
        # Parse and handle subscribe/unsubscribe messages
        ...
except WebSocketDisconnect:
    ...
except asyncio.TimeoutError:
    # Client missed heartbeat window — close stale connection
    ...
finally:
    manager.disconnect(websocket)
    logger.info("transit.ws.disconnected", ...)
```

**Message handling:**
- Parse incoming JSON with try/except (send WsError on parse failure)
- Check `data.get("action")`:
  - `"subscribe"`: Validate with `WsSubscribeMessage`, update filters, send WsAck
  - `"unsubscribe"`: Reset filters to None/None, send WsAck
  - Unknown action: Send WsError with code `"unknown_action"`

**Heartbeat:**
- Use a separate asyncio task that sends `websocket.send_json({"type": "ping"})` every `ws_heartbeat_interval_seconds`
- Start after accept, cancel on disconnect
- This is an application-level ping (not WebSocket protocol ping) for clients that don't handle protocol pings

**Module-level singleton:**
```python
_ws_manager: ConnectionManager | None = None

def get_ws_manager() -> ConnectionManager:
    global _ws_manager
    if _ws_manager is None:
        settings = get_settings()
        _ws_manager = ConnectionManager(max_connections=settings.ws_max_connections)
    return _ws_manager
```

Also add `close_ws_manager()` for shutdown cleanup.

**Imports needed:**
- `asyncio`, `json` from stdlib
- `APIRouter`, `WebSocket`, `Query` from `fastapi`
- `WebSocketDisconnect` from `starlette.websockets`
- `decode_token`, `is_token_revoked` from `app.auth.token`
- `get_settings` from `app.core.config`
- `get_logger` from `app.core.logging`
- `ConnectionManager` from `app.transit.ws_manager`
- `WsSubscribeMessage`, `WsUnsubscribeMessage`, `WsError`, `WsAck` from `app.transit.ws_schemas`
- Add pyright directive: `# pyright: reportUnknownMemberType=false`

**Per-task validation:**
- `uv run ruff format app/transit/ws_routes.py`
- `uv run ruff check --fix app/transit/ws_routes.py`
- `uv run mypy app/transit/ws_routes.py`
- `uv run pyright app/transit/ws_routes.py`

---

### Task 7: Register WebSocket Router and Update Lifespan
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

1. Add imports at the top (after existing transit imports around line 44):
```python
from app.transit.ws_routes import ws_router, get_ws_manager, close_ws_manager
from app.transit.ws_subscriber import start_ws_subscriber, stop_ws_subscriber
```

2. In the `lifespan()` function, after `await start_pollers()` (line 97), add WebSocket subscriber startup:
```python
    # Start WebSocket subscriber (pushes Redis Pub/Sub → WebSocket clients)
    if settings.ws_enabled and settings.poller_enabled:
        ws_manager = get_ws_manager()
        await start_ws_subscriber(ws_manager)
        logger.info("transit.ws.subscriber_started")
```

3. In the shutdown section (before `await close_redis()`), add WebSocket cleanup:
```python
    # Stop WebSocket subscriber and manager
    await stop_ws_subscriber()
    close_ws_manager()
    logger.info("transit.ws.lifecycle_stopped")
```

4. Register the WebSocket router (after existing `app.include_router(transit_router)` around line 142):
```python
app.include_router(ws_router)
```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py`
- `uv run pyright app/main.py`

---

### Task 8: Update Nginx Configuration for WebSocket Proxy
**File:** `nginx/nginx.conf` (modify existing)
**Action:** UPDATE

Add a WebSocket-specific location block BEFORE the general `/api/` catch-all (before line 262). WebSocket connections require `Upgrade` and `Connection` headers to be forwarded.

Add this location block:

```nginx
        # WebSocket: real-time vehicle positions
        # Long-lived connections — no rate limiting (auth is per-connection via JWT)
        location /ws/ {
            proxy_pass http://fastapi;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket-specific timeouts (longer than HTTP)
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;

            # Disable buffering for real-time streaming
            proxy_buffering off;
        }
```

Key decisions:
- `proxy_read_timeout 3600s` — Allow connections to stay open for 1 hour. The application handles keepalive via heartbeat pings.
- No rate limiting — WebSocket auth happens once at connection time. Rate limiting per-message is handled application-side by the ConnectionManager.
- `proxy_buffering off` — Ensures messages are pushed immediately without nginx buffering.

**Per-task validation:**
- Manually verify nginx config syntax: `docker exec vtv-nginx-1 nginx -t 2>/dev/null || echo "nginx not running — config will be validated on next docker-compose up"`

---

### Task 9: Unit Tests for Connection Manager
**File:** `app/transit/tests/test_ws_manager.py` (create new)
**Action:** CREATE

Test the ConnectionManager in isolation using mock WebSocket objects.

**Test cases:**

1. `test_connect_and_disconnect` — Connect a mock WebSocket, verify `active_count` increments, disconnect, verify count decrements.

2. `test_connect_respects_max_connections` — Create manager with `max_connections=2`, connect 2 clients successfully, verify 3rd returns False.

3. `test_broadcast_sends_to_all_unfiltered_clients` — Connect 2 clients with no filters, broadcast for feed "riga", verify both received the message.

4. `test_broadcast_filters_by_feed_id` — Connect client A with `feed_id="riga"`, client B with `feed_id="jurmala"`. Broadcast for feed "riga". Verify A received, B did not.

5. `test_broadcast_filters_by_route_id` — Connect client with `route_id="22"`. Broadcast vehicles for feed "riga" containing routes "22" and "7". Verify client receives only route "22" vehicles.

6. `test_broadcast_handles_disconnected_client` — Connect 2 clients. Make client A's `send_json` raise `WebSocketDisconnect`. Broadcast. Verify client B still receives data and A is removed.

7. `test_update_filters` — Connect client with no filters, then call `update_filters` with `route_id="22"`. Broadcast all routes. Verify client only receives route "22".

**Mock pattern:**
```python
from unittest.mock import AsyncMock, MagicMock

def _mock_websocket() -> MagicMock:
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws
```

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_ws_manager.py`
- `uv run ruff check --fix app/transit/tests/test_ws_manager.py`
- `uv run pytest app/transit/tests/test_ws_manager.py -v`

---

### Task 10: Unit Tests for WebSocket Route
**File:** `app/transit/tests/test_ws_routes.py` (create new)
**Action:** CREATE

Test the WebSocket endpoint authentication and message handling. Use FastAPI's `TestClient` (synchronous) with `client.websocket_connect()`.

**IMPORTANT:** FastAPI's `TestClient` uses `httpx` which supports `with client.websocket_connect(url) as ws:` pattern. The WebSocket test client sends/receives JSON via `ws.send_json()` and `ws.receive_json()`.

**Test cases:**

1. `test_ws_connect_without_token_rejected` — Connect to `/ws/transit/vehicles` without token query param. Expect connection close with code 4001.

2. `test_ws_connect_with_invalid_token_rejected` — Connect with `?token=invalid`. Expect close code 4001.

3. `test_ws_connect_with_valid_token_accepted` — Mock `decode_token` to return valid payload, mock `is_token_revoked` to return False. Connect. Expect first message is ack with `action="connected"`.

4. `test_ws_subscribe_updates_filters` — After connecting, send `{"action": "subscribe", "route_id": "22"}`. Expect ack with `filters.route_id == "22"`.

5. `test_ws_unsubscribe_resets_filters` — After subscribing with route filter, send `{"action": "unsubscribe"}`. Expect ack with `filters.route_id == None`.

6. `test_ws_unknown_action_returns_error` — Send `{"action": "unknown"}`. Expect error message with code `"unknown_action"`.

7. `test_ws_invalid_json_returns_error` — Send non-JSON text. Expect error message with code `"parse_error"`.

**Mock setup:**
- Patch `app.transit.ws_routes.decode_token` and `app.transit.ws_routes.is_token_revoked`
- Use the app's TestClient from conftest or create inline

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_ws_routes.py`
- `uv run ruff check --fix app/transit/tests/test_ws_routes.py`
- `uv run pytest app/transit/tests/test_ws_routes.py -v`

---

### Task 11: Unit Tests for Pub/Sub Publisher (Poller Integration)
**File:** `app/transit/tests/test_poller.py` (modify existing)
**Action:** UPDATE

Add test cases to the existing poller test file to verify the new Redis PUBLISH behavior.

**Test cases to add:**

1. `test_poll_once_publishes_to_pubsub` — Mock Redis pipeline and `redis_client.publish`. After poll_once completes, verify `publish` was called with channel `transit:vehicles:{feed_id}` and a JSON payload containing the correct vehicle count and feed_id.

2. `test_poll_once_skips_publish_on_zero_vehicles` — Mock GTFS client to return empty list. Verify `publish` was NOT called.

3. `test_poll_once_continues_on_publish_failure` — Mock `publish` to raise an exception. Verify `poll_once` still returns the correct count (publish failure doesn't break polling).

**Pattern:** Follow existing test patterns in the file — they mock `GTFSRealtimeClient`, `get_static_cache`, and Redis pipeline. Add `publish = AsyncMock()` to the mock Redis client.

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_poller.py`
- `uv run ruff check --fix app/transit/tests/test_poller.py`
- `uv run pytest app/transit/tests/test_poller.py -v`

---

### Task 12: Unit Tests for Pub/Sub Subscriber
**File:** `app/transit/tests/test_ws_subscriber.py` (create new)
**Action:** CREATE

Test the subscriber background task in isolation.

**Test cases:**

1. `test_subscriber_dispatches_to_manager` — Mock Redis pubsub to yield one `pmessage` with valid vehicle JSON. Mock ConnectionManager. Verify `manager.broadcast()` was called with correct feed_id, vehicles, and timestamp.

2. `test_subscriber_skips_non_pmessage` — Mock pubsub to yield a `subscribe` confirmation message. Verify `manager.broadcast()` was NOT called.

3. `test_subscriber_handles_invalid_json` — Mock pubsub to yield a pmessage with invalid JSON data. Verify no crash and warning logged (mock the logger).

4. `test_subscriber_reconnects_on_error` — Mock pubsub to raise `ConnectionError` on first iteration, then yield valid data on reconnect. Verify broadcast eventually called. Use `asyncio.sleep` mock to avoid actual delay.

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_ws_subscriber.py`
- `uv run ruff check --fix app/transit/tests/test_ws_subscriber.py`
- `uv run pytest app/transit/tests/test_ws_subscriber.py -v`

---

## Logging Events

- `transit.ws.connected` — When a WebSocket client connects (include user_id from JWT)
- `transit.ws.disconnected` — When a client disconnects (include user_id, duration_seconds)
- `transit.ws.subscribe_updated` — When client updates filters (include route_id, feed_id)
- `transit.ws.broadcast_completed` — After broadcast cycle (include feed_id, client_count, vehicle_count)
- `transit.ws.broadcast_client_error` — When individual client send fails (include error type)
- `transit.ws.subscriber_started` — When Pub/Sub subscriber starts
- `transit.ws.subscriber_reconnecting` — On Redis disconnect with backoff delay
- `transit.ws.subscriber_stopped` — When subscriber shuts down
- `transit.ws.auth_failed` — When JWT validation fails on connect (include reason)
- `transit.ws.connection_limit_reached` — When max_connections exceeded
- `transit.poller.pubsub_publish_failed` — When PUBLISH fails (non-fatal)

## Testing Strategy

### Unit Tests
**Location:** `app/transit/tests/`
- `test_ws_manager.py` — ConnectionManager: connect/disconnect, filtering, broadcast, max connections (7 tests)
- `test_ws_routes.py` — WebSocket endpoint: auth, subscribe/unsubscribe, error handling (7 tests)
- `test_ws_subscriber.py` — Pub/Sub subscriber: dispatch, reconnect, error handling (4 tests)
- `test_poller.py` — Additional tests for PUBLISH integration (3 tests)

### Integration Tests
**Mark with:** `@pytest.mark.integration`
Not required for this plan — WebSocket integration testing requires a real WebSocket server and Redis, which is better suited for E2E tests. Unit tests with mocks provide sufficient coverage for the backend logic.

### Edge Cases
- Client connects with expired JWT — rejected with 4001
- Client connects with revoked token — rejected with 4001
- Redis Pub/Sub disconnects mid-stream — subscriber reconnects with backoff
- Client sends malformed JSON — receives error message, connection stays open
- Max connections reached — new client gets 1013 close code
- Poller PUBLISH fails — poller continues normally, warning logged
- All WebSocket clients disconnect — subscriber continues listening (no crash on empty broadcast)
- Client subscribes to nonexistent route — receives empty updates (no error)

## Acceptance Criteria

This feature is complete when:
- [ ] WebSocket endpoint at `/ws/transit/vehicles` accepts authenticated connections
- [ ] JWT query parameter authentication with same security as REST endpoints
- [ ] Client can subscribe with optional route_id and feed_id filters
- [ ] Vehicle position updates are pushed to clients within ~100ms of poller completing
- [ ] Pub/Sub publish failure does not break the existing poller
- [ ] Connection manager enforces max_connections limit
- [ ] Nginx proxies WebSocket connections with proper Upgrade headers
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit, 21+ new tests)
- [ ] Structured logging follows `transit.ws.action_state` pattern
- [ ] No type suppressions added (except known Redis stubs, rule 34)
- [ ] WebSocket router registered in `app/main.py`
- [ ] Subscriber starts/stops in application lifespan
- [ ] No regressions in existing transit tests
- [ ] REST API endpoint still works unchanged (graceful degradation)

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 12 tasks completed in order
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
uv run pytest app/transit/tests/ -v
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

- Shared utilities used: `app.core.logging.get_logger`, `app.core.config.get_settings`, `app.core.redis.get_redis`
- Core modules used: `app.auth.token.decode_token`, `app.auth.token.is_token_revoked`
- New dependencies: **None** — FastAPI includes WebSocket support natively via Starlette. Redis Pub/Sub is part of the existing `redis[hiredis]` package.
- New env vars: `WS_ENABLED` (bool, default True), `WS_HEARTBEAT_INTERVAL_SECONDS` (int, default 30), `WS_MAX_CONNECTIONS` (int, default 100)

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules loaded via `@_shared/python-anti-patterns.md`. Particularly relevant for this feature:

- **Rule 34**: Redis async stubs — `await` on Redis Pub/Sub returns `Awaitable[T] | T`. Add `# type: ignore[misc]` on pubsub await lines. Add pyright file-level directives for Redis files.
- **Rule 35**: `redis.pipeline()` is sync — mock with `MagicMock()`, not `AsyncMock()`. Only `execute()` is async.
- **Rule 37**: Bare `except: pass` violates S110 — always log in except blocks.
- **Rule 38**: Background asyncio tasks must handle ALL exceptions — catch both `CancelledError` and `Exception` separately in subscriber loop.
- **Rule 16**: Singleton close must handle closed event loops — wrap `close_ws_manager()` in try/except RuntimeError.
- **Rule 55**: `HTTPBearer(auto_error=False)` pattern — not applicable here (we use manual JWT validation for WebSocket), but the same token validation logic applies.
- **Rule 5**: No unused imports — only import what's used in each file.

**WebSocket-specific pitfalls:**
- FastAPI WebSocket endpoints do NOT support `Depends()` for auth — must validate JWT manually.
- WebSocket `close()` after `accept()` uses different codes than HTTP status codes. Use 4000-4999 range for application errors.
- `websocket.receive_text()` blocks indefinitely — use `asyncio.wait_for` with timeout for stale connection detection.
- Starlette `WebSocketDisconnect` must be caught, not `ConnectionError`.

## Notes

**Frontend follow-up:** This plan creates the backend WebSocket infrastructure. A separate `/fe-planning` task should create a `useVehicleWebSocket` hook that:
1. Attempts WebSocket connection with JWT from session
2. Falls back to existing SWR HTTP polling on failure
3. Sends subscribe message with route/feed filters
4. Updates the same `BusPosition[]` state as the current hook

**Multi-worker considerations:** In production with 4 Gunicorn workers:
- Only the leader worker runs the poller (existing leader election)
- ALL workers subscribe to Redis Pub/Sub (each has its own subscriber)
- Each worker's WebSocket clients receive updates from their worker's subscriber
- This is correct behavior — Pub/Sub fan-out handles multi-worker distribution

**Performance:** With 100 connected clients and ~1000 vehicles per feed:
- Each broadcast serializes ~200KB JSON per client
- At 10s intervals: ~2MB/s outbound per 100 clients
- Redis PUBLISH adds <1ms per cycle
- Well within single-server capacity

**Future enhancements:**
- Binary protocol (MessagePack/Protobuf) for reduced bandwidth
- Delta updates (only send changed vehicles) for less data
- Per-client rate limiting (prevent reconnect storms)

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the Redis Pub/Sub broadcast pattern
- [ ] Clear on WebSocket JWT authentication (manual, not via Depends)
- [ ] Understood connection manager filtering logic
- [ ] Clear on task execution order (config → schemas → manager → poller → subscriber → routes → main → nginx → tests)
- [ ] Validation commands are executable in this environment
