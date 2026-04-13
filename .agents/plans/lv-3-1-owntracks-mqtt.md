# Plan: LV-3.1 OwnTracks MQTT Integration

## Context

Fastest path to intercity tracking — drivers install OwnTracks on their phone, zero hardware cost. Gets real positions for routes with no GTFS-RT feed. Proves the concept before investing in Teltonika hardware.

**Scope:** Deploy Mosquitto MQTT broker (Docker sidecar), create `app/transit/owntracks_listener.py` — subscribes to OwnTracks position topics, normalizes to EnrichedVehicle, writes to Redis + TimescaleDB + Pub/Sub. Admin endpoints to assign phone → vehicle → route.

## Security Context Assessment

| Context | Active | Rationale |
|---------|--------|-----------|
| CTX-AUTH | No | No auth flow changes |
| CTX-RBAC | **Yes** | 3 new admin endpoints need role protection |
| CTX-INPUT | **Yes** | Admin endpoints accept user input; MQTT messages are external input |
| CTX-INFRA | **Yes** | Docker Mosquitto sidecar, new config settings, MQTT credentials |
| CTX-FILE | No | No file uploads |
| CTX-AGENT | No | No agent tool changes |

## Research Summary

### Reference Implementation: `app/transit/train_ws_listener.py`
The train WebSocket listener is the **closest pattern** — external connection, message parsing, Redis + TimescaleDB + Pub/Sub write pipeline, asyncio task lifecycle with start/stop functions.

### Key Patterns to Reuse
- **Redis write:** `pipe.set(f"vehicle:{FEED_ID}:{vid}", json.dumps(enriched), ex=ttl)` + feed tracking set `feed:{FEED_ID}:vehicles` (`train_ws_listener.py:148-171`)
- **TimescaleDB write:** `batch_insert_positions(db_session, db_records)` from `app/transit/repository.py:29-51` — non-blocking, failures logged as warnings
- **Pub/Sub publish:** `redis_client.publish(f"transit:vehicles:{FEED_ID}", payload)` (`train_ws_listener.py:214-231`)
- **Enriched vehicle dict:** Same structure as `train_ws_listener.py:120-137` (vehicle_id, route_id, route_short_name, route_type, lat, lon, bearing, speed_kmh, delay_seconds, trip_id, current_status, timestamp, feed_id, operator_name)
- **Lifecycle:** Module-level `_listener_task`, `start_*()` returns `asyncio.Task`, `stop_*()` cancels+awaits (`train_ws_listener.py:295-314`)
- **Shutdown:** `ShutdownCoordinator.register(ShutdownTask(...))` in `app/main.py:261-270`
- **Config pattern:** `train_ws_enabled: bool`, `train_ws_url: str`, `train_ws_reconnect_max_seconds: int` (`app/core/config.py:119-122`)
- **Source discriminator:** `source: Mapped[str]` on `VehiclePositionRecord` (`app/transit/models.py:67`) — use `"owntracks"`
- **Docker sidecar:** Traccar uses `profiles: ["fleet"]` pattern (`docker-compose.yml:65-77`)

### Phone Assignment Model
New `VehiclePhoneAssignment` model in `app/transit/models.py` — lives in transit feature (owns the write pipeline). FKs to vehicles and drivers tables. Admin CRUD endpoints in `app/transit/routes.py`.

## Test Landscape

- **Template:** `app/transit/tests/test_train_ws_listener.py` — tests message parsing, Redis pipeline writes, Pub/Sub, DB history writes, task lifecycle (start/stop/cancel)
- **Redis mock pattern:** `MagicMock()` for pipeline (not `AsyncMock`), only `execute()` is async. `mock_redis.publish = AsyncMock()`
- **DB mock pattern:** `AsyncMock()` context manager — `mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)`, factory returns ctx
- **Settings mock:** `MagicMock()` with attr stubs (`settings.redis_vehicle_ttl_seconds = 120`)
- **Task lifecycle:** `AsyncMock(spec=asyncio.Task)` with `.cancel = MagicMock()`, module-level `_listener_task` state
- **Existing fixtures:** `make_eticket_*` in transit conftest (not reusable). Global `test_db_session` fixture available.
- **Security convention tests:** `app/tests/test_security.py` checks all endpoints require auth

## Type Check Baseline

- **Pyright:** 0 errors across 47 source files in `app/transit/`
- **Mypy:** 0 errors across 47 source files in `app/transit/`

Target: maintain 0 errors after implementation.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/transit/owntracks_listener.py` | MQTT listener — subscribe, parse, normalize, write to Redis/TimescaleDB/Pub/Sub |
| CREATE | `alembic/versions/xxx_add_vehicle_phone_assignments.py` | Migration for phone assignment table |
| CREATE | `app/transit/tests/test_owntracks_listener.py` | Unit tests for MQTT listener |
| CREATE | `app/transit/tests/test_phone_assignment_routes.py` | Unit tests for admin endpoints |
| UPDATE | `app/transit/models.py` | Add `VehiclePhoneAssignment` model |
| UPDATE | `app/transit/schemas.py` | Add phone assignment request/response schemas |
| UPDATE | `app/transit/routes.py` | Add 3 admin phone-assignment endpoints |
| UPDATE | `app/core/config.py` | Add OwnTracks/MQTT settings |
| UPDATE | `app/main.py` | Start/stop MQTT listener in lifespan + shutdown coordinator |
| UPDATE | `docker-compose.yml` | Add Mosquitto service with `mqtt` profile |
| UPDATE | `.env.example` | Document new MQTT env vars |

## Implementation Steps

### Step 1: Config settings
**File:** `app/core/config.py`
**Action:** Add after `train_ws_reconnect_max_seconds` (line 122):
```python
# OwnTracks MQTT listener (LV-3.1)
owntracks_mqtt_enabled: bool = False
owntracks_mqtt_broker_url: str = "mqtt://localhost:1883"
owntracks_mqtt_username: str | None = None
owntracks_mqtt_password: str | None = None
owntracks_mqtt_topic_filter: str = "owntracks/+/+"
owntracks_mqtt_reconnect_max_seconds: int = 60
```
**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Phone assignment model
**File:** `app/transit/models.py`
**Action:** Add `VehiclePhoneAssignment` model after `VehiclePositionRecord`:
```python
class VehiclePhoneAssignment(Base, TimestampMixin):
    """Maps a phone (OwnTracks device) to a vehicle, route, and driver."""
    __tablename__ = "vehicle_phone_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_identifier: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, ForeignKey("vehicles.id"), nullable=False)
    route_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("routes.id"), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("drivers.id"), nullable=True)
    assigned_by: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
```
**Validation:** `uv run ruff check app/transit/models.py && uv run pyright app/transit/models.py`

### Step 3: Alembic migration
**File:** `alembic/versions/xxx_add_vehicle_phone_assignments.py`
**Action:** `make db-revision m="add vehicle_phone_assignments table (LV-3.1)"` then verify the auto-generated migration creates the table with FKs and the unique constraint on `phone_identifier`.
**Validation:** `make db-migrate` (requires Docker DB running)

### Step 4: Phone assignment schemas
**File:** `app/transit/schemas.py`
**Action:** Add Pydantic schemas for phone assignment CRUD:
```python
class PhoneAssignmentCreate(BaseModel):
    phone_identifier: str = Field(..., max_length=100, pattern=r"^[\w\-.:]+$")
    vehicle_id: int
    route_id: int | None = None
    driver_id: int | None = None

class PhoneAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    phone_identifier: str
    vehicle_id: int
    route_id: int | None
    driver_id: int | None
    assigned_by: str
    active: bool
    created_at: datetime
    updated_at: datetime
```
**Validation:** `uv run ruff check app/transit/schemas.py && uv run pyright app/transit/schemas.py`

### Step 5: Phone assignment admin endpoints
**File:** `app/transit/routes.py`
**Action:** Add 3 admin endpoints:
- `POST /api/v1/transit/phone-assignments` — create assignment (admin/dispatcher only)
- `GET /api/v1/transit/phone-assignments` — list active assignments (admin/dispatcher only)
- `DELETE /api/v1/transit/phone-assignments/{id}` — deactivate assignment (admin only)

Each endpoint: `@limiter.limit("30/minute")`, `Depends(require_role(["admin", "dispatcher"]))`, proper logging.
**Validation:** `uv run ruff check app/transit/routes.py && uv run pyright app/transit/routes.py`

### Step 6: OwnTracks MQTT listener
**File:** `app/transit/owntracks_listener.py`
**Action:** Create following `train_ws_listener.py` pattern exactly:
- `pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false` header
- Constants: `FEED_ID = "owntracks"`, `OPERATOR_NAME = "OwnTracks"`, `ROUTE_TYPE = 3` (bus)
- Module-level `_listener_task: asyncio.Task[None] | None = None`
- `_process_message(topic: str, payload: bytes, redis_client, db_session_factory, settings)`:
  - Parse JSON from payload
  - Skip if `_type != "location"`
  - Extract `lat`, `lon`, `vel` (km/h → speed_kmh), `bearing`/`cog`, `tst` (POSIX timestamp)
  - Extract phone_identifier from MQTT topic: `owntracks/{user}/{device}` → `"{user}_{device}"`
  - Lookup phone → vehicle assignment from DB (cache in memory with TTL)
  - If no assignment found: log warning, skip
  - Build enriched vehicle dict (same structure as train_ws_listener)
  - Write to Redis pipeline (same pattern)
  - Write to TimescaleDB with `source="owntracks"` (non-blocking)
  - Publish to Pub/Sub channel `transit:vehicles:owntracks`
- `_listen_loop(settings, *, _shutdown_event=None)`:
  - Use `aiomqtt.Client` (asyncio MQTT client)
  - Connect with username/password from settings
  - Subscribe to `settings.owntracks_mqtt_topic_filter`
  - Exponential backoff reconnection (same as train_ws_listener)
  - Handle `CancelledError` for clean shutdown
- `start_owntracks_listener(settings) -> asyncio.Task[None]`
- `stop_owntracks_listener() -> None`

**Dependencies:** Add `aiomqtt>=2.0` to `pyproject.toml`
**Validation:** `uv run ruff check app/transit/owntracks_listener.py && uv run pyright app/transit/owntracks_listener.py`

### Step 7: Assignment cache in listener
**Action:** Inside `owntracks_listener.py`, implement a simple in-memory cache for phone assignments to avoid DB query on every message:
```python
_assignment_cache: dict[str, tuple[VehiclePhoneAssignment, float]] = {}
_CACHE_TTL = 60.0  # seconds

async def _get_assignment(phone_id: str, db_factory) -> VehiclePhoneAssignment | None:
    cached = _assignment_cache.get(phone_id)
    if cached and (time.monotonic() - cached[1]) < _CACHE_TTL:
        return cached[0]
    # Query DB
    async with db_factory() as db:
        result = await db.execute(
            select(VehiclePhoneAssignment).where(
                VehiclePhoneAssignment.phone_identifier == phone_id,
                VehiclePhoneAssignment.active.is_(True),
            )
        )
        assignment = result.scalar_one_or_none()
    if assignment:
        _assignment_cache[phone_id] = (assignment, time.monotonic())
    return assignment
```
**Validation:** `uv run ruff check app/transit/owntracks_listener.py && uv run pyright app/transit/owntracks_listener.py`

### Step 8: Wire into app lifespan
**File:** `app/main.py`
**Action:** Add after train WS listener startup block (line 167):
```python
# Start OwnTracks MQTT listener (LV-3.1)
if settings.owntracks_mqtt_enabled:
    from app.transit.owntracks_listener import start_owntracks_listener
    await start_owntracks_listener(settings)
```
Add shutdown registration after train WS block (after line 270):
```python
if settings.owntracks_mqtt_enabled:
    from app.transit.owntracks_listener import stop_owntracks_listener
    coordinator.register(
        ShutdownTask(
            name="owntracks_listener",
            drain_timeout_s=5.0,
            drain=stop_owntracks_listener,
        )
    )
```
**Validation:** `uv run ruff check app/main.py && uv run pyright app/main.py`

### Step 9: Docker Mosquitto sidecar
**File:** `docker-compose.yml`
**Action:** Add Mosquitto service with `mqtt` profile:
```yaml
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: vtv-mosquitto
    restart: unless-stopped
    profiles:
      - mqtt
    ports:
      - "1883:1883"
    volumes:
      - mosquitto_data:/mosquitto/data
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - ./mosquitto/passwd:/mosquitto/config/passwd:ro
    healthcheck:
      test: ["CMD", "mosquitto_sub", "-t", "$$SYS/#", "-C", "1", "-i", "healthcheck", "-W", "3"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 128M
```
Add `mosquitto_data:` to volumes. Create `mosquitto/mosquitto.conf` with listener + password_file + persistence.
**Validation:** `docker compose config --quiet`

### Step 10: Add `aiomqtt` dependency
**File:** `pyproject.toml`
**Action:** Add `"aiomqtt>=2.0,<3.0"` to `[project.dependencies]`
**Validation:** `uv lock && uv sync`

### Step 11: Update .env.example
**File:** `.env.example`
**Action:** Add MQTT settings block:
```bash
# OwnTracks MQTT (LV-3.1) — enable with `docker compose --profile mqtt up`
OWNTRACKS_MQTT_ENABLED=false
OWNTRACKS_MQTT_BROKER_URL=mqtt://mosquitto:1883
OWNTRACKS_MQTT_USERNAME=vtv
OWNTRACKS_MQTT_PASSWORD=changeme
OWNTRACKS_MQTT_TOPIC_FILTER=owntracks/+/+
```
**Validation:** N/A

### Step 12: Unit tests — MQTT listener
**File:** `app/transit/tests/test_owntracks_listener.py`
**Action:** Following `test_train_ws_listener.py` patterns:
1. `test_process_message_valid_location` — valid OwnTracks JSON → Redis pipeline called with enriched vehicle
2. `test_process_message_non_location_skipped` — `_type: "transition"` → no Redis write
3. `test_process_message_missing_coords_skipped` — missing lat/lon → no Redis write
4. `test_process_message_no_assignment_skipped` — unknown phone → warning logged, no write
5. `test_process_message_writes_timescaledb` — `position_history_enabled=True` → `batch_insert_positions` called with `source="owntracks"`
6. `test_process_message_db_failure_nonfatal` — DB write raises → Redis write still succeeds
7. `test_process_message_publishes_pubsub` — `redis_client.publish` called with correct channel
8. `test_speed_conversion` — OwnTracks `vel` (km/h) mapped to `speed_kmh` correctly
9. `test_phone_id_from_topic` — `owntracks/user1/phone` → `"user1_phone"`
10. `test_start_creates_task` — returns `asyncio.Task`
11. `test_stop_cancels_task` — cancels and sets module-level task to None
12. `test_assignment_cache_hit` — second call within TTL doesn't query DB

**Validation:** `uv run pytest app/transit/tests/test_owntracks_listener.py -v`

### Step 13: Unit tests — phone assignment endpoints
**File:** `app/transit/tests/test_phone_assignment_routes.py`
**Action:**
1. `test_create_assignment_admin` — admin creates assignment → 201
2. `test_create_assignment_dispatcher` — dispatcher creates → 201
3. `test_create_assignment_viewer_forbidden` — viewer → 403
4. `test_create_assignment_no_auth` — no token → 401/403
5. `test_list_assignments` — returns active assignments
6. `test_delete_assignment_admin` — admin deactivates → 200
7. `test_delete_assignment_dispatcher_forbidden` — dispatcher → 403 (delete is admin-only)
8. `test_create_duplicate_phone_rejected` — duplicate phone_identifier → 409/422

**Validation:** `uv run pytest app/transit/tests/test_phone_assignment_routes.py -v`

### Step 14: Full validation
**Action:** Run complete quality suite:
```bash
make lint && make types && make test
```

## Preflight Warnings

- `app/transit/routes.py` already has 7+ endpoints — adding 3 more is fine but keep the file organized (group phone-assignment endpoints together with a comment block)
- `app/transit/models.py` currently imports `Base` from `app.core.database` but NOT `ForeignKey` — need to add `ForeignKey` import
- The `aiomqtt` library is untyped — will need mypy `[[overrides]]` entry + pyright file-level directives (anti-pattern #12)
- Redis pipeline: `MagicMock()` not `AsyncMock()` for pipeline object — only `execute()` is async (anti-pattern #35)

## Security Checklist

For every new/modified endpoint:
- [ ] `require_role(["admin", "dispatcher"])` on create/list, `require_role(["admin"])` on delete
- [ ] `@limiter.limit("30/minute")` rate limiting on all 3 endpoints
- [ ] Input validation via `PhoneAssignmentCreate` Pydantic schema with `max_length` + `pattern`
- [ ] Error responses use `AppError` hierarchy (no internal type leakage)
- [ ] `escape_like()` not needed (no ILIKE queries)
- [ ] MQTT credentials via env vars, never hardcoded (CTX-INFRA)
- [ ] MQTT broker port 1883 only exposed in `mqtt` profile, not in default compose
- [ ] OwnTracks message coordinates validated within Latvia bounding box (55.5-58.1 lat, 20.5-28.3 lon)
- [ ] Never log MQTT password — use `_redact_url()` pattern for broker URL

## Verification

- [ ] `make lint` passes (ruff format + ruff check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `make test` passes (all unit tests including 20 new tests)
- [ ] Pyright errors ≤ 0 (baseline: 0 errors)
- [ ] `make security-audit-quick` passes
- [ ] New endpoints have auth + rate limiting
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
- [ ] `docker compose --profile mqtt config --quiet` validates
- [ ] OwnTracks listener disabled by default (`owntracks_mqtt_enabled=False`)
