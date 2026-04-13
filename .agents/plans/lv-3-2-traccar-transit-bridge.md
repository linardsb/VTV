# Plan: LV-3.2 Traccar Hardware GPS Bridge Extension

## Context

Extend `app/fleet/bridge.py` so Traccar-tracked fleet devices assigned to transit routes also appear on the transit map alongside GTFS-RT and OwnTracks sources. Hardware GPS devices (Teltonika FMB920) currently write to `vehicle_positions` with `source="hardware"` but always set `route_id=""` and publish only to the generic `vehicle_positions` channel. After this change, route-assigned devices will populate `route_id`/`route_short_name` and publish to the transit Pub/Sub channel `transit:vehicles:fleet`, making them visible on `/map`.

**No new infrastructure needed** — Traccar webhook, Redis cache, TimescaleDB, and GTFS-RT publisher already support hardware sources.

## Security Context Assessment

**Active contexts:** CTX-RBAC, CTX-INPUT

- **CTX-RBAC:** Existing fleet webhook uses bearer token auth (`traccar_webhook_token`). New route assignment CRUD on TrackedDevice uses existing `require_role()`. No new endpoints added — route_id is set via existing device update endpoint.
- **CTX-INPUT:** Route assignment validated via FK constraint. No new user-facing search/filter params.

## Research Summary

### Current Data Flow (bridge.py)
1. Webhook → `TraccarBridge.process_webhook()` (line 117)
2. Device lookup via `fleet_repo.get_by_traccar_id()` (line 133)
3. `normalize_webhook()` builds position dict — **route_id always ""** (line 89)
4. Redis: `SET vehicle:fleet:{vid}` + `PUBLISH vehicle_positions` (lines 151-156)
5. TimescaleDB: insert VehiclePositionRecord with source="hardware" (lines 160-175)

### Target Pattern (owntracks_listener.py)
- Looks up `VehiclePhoneAssignment` for route_id (line 130-138)
- Populates `route_id` + `route_short_name` in position dict
- Redis: `SET vehicle:owntracks:{vid}` + `SADD feed:owntracks:vehicles` + `PUBLISH transit:vehicles:owntracks`
- Same TimescaleDB write pattern

### Key Gap
- `TrackedDevice` model has `vehicle_id` FK but **no `route_id`** FK
- Bridge publishes to `vehicle_positions` channel, not `transit:vehicles:fleet`
- Bridge doesn't add to `feed:fleet:vehicles` SET (needed for redis_reader aggregation)

### Design Decision: Route Assignment

**Option A:** Add `route_id` FK to `TrackedDevice` model — simplest, 1 device = 1 route at a time.
**Option B:** Reuse `VehiclePhoneAssignment` — wrong semantics (phone ≠ hardware device).
**Option C:** New `VehicleTransitAssignment` junction table — over-engineered for this use case.

**Choice: Option A.** TrackedDevice already has `vehicle_id` FK. Adding `route_id` FK follows the same pattern. One device serves one route at a time. The existing device PATCH endpoint already handles field updates.

## Test Landscape

**Existing fleet tests:** `app/fleet/tests/test_bridge.py` (159 lines, 9 tests) — TestParseOBDAttributes, TestNormalizeWebhook, TestProcessWebhook
**Fleet conftest:** `app/fleet/tests/conftest.py` — `mock_db`, `sample_tracked_device`, `sample_webhook_payload`
**OwnTracks tests (template):** `app/transit/tests/test_owntracks_listener.py` (376 lines, 14 tests) — assignment lookup, cache hit, Pub/Sub publish, TimescaleDB write
**Redis mock pattern:** `pipeline()` is sync MagicMock, `.execute()` is AsyncMock, `.publish()` is AsyncMock

## Type Check Baseline

- **pyright app/fleet/**: 0 errors, 0 warnings
- **pyright app/transit/**: 0 errors, 0 warnings
- **mypy app/fleet/**: Success (12 source files)
- **mypy app/transit/**: Success (50 source files)

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `alembic/versions/u5v6w7x8y9z0_add_tracked_device_route_id.py` | Add route_id FK to tracked_devices |
| UPDATE | `app/fleet/models.py` | Add `route_id` FK column to TrackedDevice |
| UPDATE | `app/fleet/schemas.py` | Add `route_id` to create/update/response schemas |
| UPDATE | `app/fleet/bridge.py` | Populate route_id/route_short_name, publish to transit channel |
| UPDATE | `app/fleet/repository.py` | Add `get_route_short_name()` helper |
| UPDATE | `app/fleet/tests/conftest.py` | Add route_id to sample_tracked_device fixture |
| UPDATE | `app/fleet/tests/test_bridge.py` | Add transit publish tests (6+ new tests) |

## Implementation Steps

### Step 1: Add route_id to TrackedDevice model
**File:** `app/fleet/models.py`
**Action:** Add nullable FK column after `vehicle_id`:
```python
route_id: Mapped[int | None] = mapped_column(
    Integer, ForeignKey("routes.id", ondelete="SET NULL"), nullable=True, index=True
)
```
**Validation:** `uv run pyright app/fleet/models.py`

### Step 2: Create Alembic migration
**File:** `alembic/versions/u5v6w7x8y9z0_add_tracked_device_route_id.py`
**Action:** `make db-revision m="add route_id to tracked_devices"`
- Adds `route_id INTEGER NULLABLE` column with FK to `routes.id`
- Creates index `ix_tracked_devices_route_id`
**Validation:** Review generated migration

### Step 3: Update fleet schemas
**File:** `app/fleet/schemas.py`
**Action:** Add `route_id: int | None = None` to `TrackedDeviceCreate`, `TrackedDeviceUpdate`, and `TrackedDeviceResponse`
**Validation:** `uv run pyright app/fleet/schemas.py`

### Step 4: Add route_short_name lookup to repository
**File:** `app/fleet/repository.py`
**Action:** Add method to fetch route_short_name by route_id:
```python
async def get_route_short_name(self, route_id: int) -> str:
    """Look up route_short_name from schedules.Route by ID."""
    from app.schedules.models import Route
    result = await self.db.execute(select(Route.route_short_name).where(Route.id == route_id))
    name = result.scalar_one_or_none()
    return name or ""
```
**Validation:** `uv run pyright app/fleet/repository.py`

### Step 5: Extend bridge to populate route and publish to transit channel
**File:** `app/fleet/bridge.py`

**5a.** Update `normalize_webhook()` signature to accept `route_id: str = ""` and `route_short_name: str = ""` params. Set them in the returned dict instead of hardcoded empty strings.

**5b.** Update `process_webhook()`:
1. After device lookup, check `device.route_id is not None`
2. If route assigned, call `self.fleet_repo.get_route_short_name(device.route_id)` to get `route_short_name`
3. Pass `route_id=str(device.route_id)` and `route_short_name` to `normalize_webhook()`
4. In Redis pipeline, add `SADD feed:fleet:vehicles {vehicle_id}` with TTL
5. Change `PUBLISH` from `"vehicle_positions"` to `"transit:vehicles:fleet"` **only when route assigned** (keep existing `"vehicle_positions"` for non-transit fleet telemetry)
6. Publish JSON payload matching transit format: `{"feed_id": "fleet", "count": 1, "vehicles": [...], "timestamp": ...}`

**Key logic:**
```python
# After normalize_webhook:
if device.route_id is not None:
    route_short_name = await self.fleet_repo.get_route_short_name(device.route_id)
    position_data["route_id"] = str(device.route_id)
    position_data["route_short_name"] = route_short_name

# In Redis pipeline:
pipe.set(redis_key, redis_value, ex=120)
pipe.sadd(f"feed:fleet:vehicles", position_data["vehicle_id"])
pipe.expire(f"feed:fleet:vehicles", 120)
pipe.publish("vehicle_positions", redis_value)
if position_data["route_id"]:
    transit_payload = json.dumps({
        "feed_id": "fleet",
        "count": 1,
        "vehicles": [position_data],
        "timestamp": position_data["recorded_at"],
    })
    pipe.publish("transit:vehicles:fleet", transit_payload)
```

**Validation:** `uv run ruff format app/fleet/bridge.py && uv run ruff check --fix app/fleet/bridge.py && uv run pyright app/fleet/bridge.py`

### Step 6: Update test fixtures
**File:** `app/fleet/tests/conftest.py`
**Action:** Add `route_id=None` to `sample_tracked_device` fixture. Add new fixture `sample_tracked_device_with_route` that sets `route_id=101`.
**Validation:** `uv run pyright app/fleet/tests/conftest.py`

### Step 7: Add transit bridge tests
**File:** `app/fleet/tests/test_bridge.py`
**Action:** Add new test class `TestTransitBridgePublish` with 6+ tests:

1. `test_process_webhook_route_assigned_publishes_transit` — Device with route_id → publishes to `transit:vehicles:fleet` + adds to feed SET
2. `test_process_webhook_no_route_skips_transit` — Device without route_id → no transit publish, only `vehicle_positions`
3. `test_normalize_webhook_with_route_id` — route_id/route_short_name populated in position dict
4. `test_normalize_webhook_without_route_id` — route_id/route_short_name empty when no route
5. `test_process_webhook_route_populates_redis_set` — `SADD feed:fleet:vehicles` called with vehicle_id
6. `test_process_webhook_transit_payload_format` — Transit Pub/Sub message has correct `{"feed_id", "count", "vehicles", "timestamp"}` structure

**Mock pattern (from OwnTracks tests):**
```python
mock_pipe = MagicMock()
mock_pipe.execute = AsyncMock()
mock_redis = MagicMock()
mock_redis.pipeline.return_value = mock_pipe
```

**Validation:** `uv run pytest app/fleet/tests/test_bridge.py -v`

### Step 8: Run full validation
```bash
make check  # lint + types + tests
```

## Preflight Warnings

- `test_bridge.py` line 149: `mock_pipe.publish.assert_called_once()` — this assertion will need updating since we now call publish twice (once for `vehicle_positions`, once for `transit:vehicles:fleet`) when route is assigned. Update to `assert_any_call` or check call count.
- `bridge.py` line 155: `pipe.publish("vehicle_positions", redis_value)` — existing publish channel stays for backward compat. Transit publish is **additional**, not a replacement.

## Security Checklist

- [x] Webhook endpoint already uses bearer token auth (no change)
- [x] Device update endpoint already uses `require_role()` (no change)
- [x] route_id validated via FK constraint (DB-level)
- [x] No new user-facing endpoints added
- [x] No ILIKE queries added
- [x] Error responses use existing patterns

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors = 0 (baseline: 0)
- [ ] Mypy errors = 0 (baseline: 0)
- [ ] New tests pass: `uv run pytest app/fleet/tests/test_bridge.py -v`
- [ ] Redis SET `feed:fleet:vehicles` populated for route-assigned devices
- [ ] Transit Pub/Sub channel `transit:vehicles:fleet` receives messages
- [ ] Non-route-assigned devices still work (no transit publish, only fleet telemetry)
