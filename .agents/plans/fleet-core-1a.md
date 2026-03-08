# Plan: Fleet Core Phase 1A — Infrastructure + Device Management + Telemetry Ingestion

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `app/fleet/` (new), `app/vehicles/` (extension), `app/core/config.py`, `docker-compose.yml`, `app/main.py`

## Feature Description

Phase 1A establishes the foundational infrastructure for hardware GPS tracking in VTV. This adds a new `app/fleet/` vertical slice that manages Traccar GPS tracking devices, links them to existing VTV vehicles, ingests real-time telemetry data via Traccar webhooks, parses OBD-II diagnostic parameters, and stores enriched position data in the existing `vehicle_positions` TimescaleDB hypertable.

The Traccar GPS protocol gateway runs as a Docker sidecar, handling binary protocol parsing (Teltonika Codec 8/8E) and forwarding normalized position updates to VTV via HTTP webhooks. VTV's fleet service receives these webhooks, enriches positions with vehicle metadata, writes to Redis for real-time map display, stores in TimescaleDB for historical analysis, and publishes via Redis Pub/Sub for WebSocket push to CMS clients.

This is the self-contained MVP: after implementation, hardware GPS devices can be registered, linked to fleet vehicles, and their positions tracked in real-time using the same infrastructure already proven for GTFS-RT feeds.

## User Story

As a fleet administrator
I want to register GPS tracking devices, link them to vehicles, and see live hardware positions on the map
So that I can track actual vehicle locations independent of GTFS-RT feeds

## Security Contexts

**Active contexts:**
- **CTX-RBAC**: New REST endpoints for device CRUD and telemetry webhook require role-based access
- **CTX-INPUT**: Device IMEI validation, webhook payload validation, search/filter parameters
- **CTX-INFRA**: New Docker service (Traccar), new environment variables, webhook endpoint security

**Not applicable:**
- CTX-AUTH: No changes to auth flow itself
- CTX-FILE: No file uploads
- CTX-AGENT: No agent tools in this phase

## Solution Approach

We extend VTV's proven real-time tracking architecture (Redis cache + Pub/Sub + TimescaleDB + WebSocket) to support hardware GPS devices alongside GTFS-RT feeds. The key design decisions:

1. **Shared `vehicle_positions` hypertable** — Add a `source` column to distinguish `"gtfs-rt"` from `"hardware"` origins. This preserves the single compression/retention policy and allows unified map rendering.

2. **Traccar as protocol gateway only** — Traccar handles 200+ GPS device protocols (Teltonika, Queclink, etc.) but we don't use its database or API. Instead, Traccar forwards events via HTTP webhook to our `/api/v1/fleet/webhook/traccar` endpoint, which we parse and normalize into VTV's data model.

3. **TrackedDevice model** — New model linking IMEI → Vehicle with device metadata (SIM number, firmware, protocol type). Foreign key to `vehicles.id` with nullable (device can exist before being linked).

4. **OBD-II as JSONB** — Store OBD-II parameters (speed, RPM, fuel, temp, odometer, engine load) as a JSONB column on `vehicle_positions` rather than separate columns. This avoids schema changes for each new parameter and handles the variable nature of OBD data across device types.

**Approach Decision:**
We chose the webhook bridge pattern because:
- Decouples VTV from Traccar's internal schema — Traccar upgrades won't break us
- Single ingestion pipeline for all device protocols — VTV normalizes everything
- Reuses proven Redis+TimescaleDB+WebSocket stack — no new infrastructure for real-time push

**Alternatives Considered:**
- Direct Traccar API polling: Rejected — adds latency, couples to Traccar schema, wasteful polling
- Traccar database sharing: Rejected — tight coupling, migration conflicts, schema drift
- Custom protocol parsing: Rejected — Traccar already handles 200+ protocols with battle-tested parsers

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/config.py` (lines 1-214) — Settings class pattern, environment variable structure
- `app/core/database.py` — Base class, AsyncSession, get_db() / get_db_context()
- `app/core/exceptions.py` — AppError hierarchy (NotFoundError → 404, DomainValidationError → 422)
- `app/shared/models.py` — TimestampMixin definition
- `app/shared/schemas.py` — PaginatedResponse, PaginationParams
- `app/shared/utils.py` — escape_like() for search

### Similar Features (Examples to Follow)
- `app/vehicles/models.py` (lines 1-81) — Vehicle model with CheckConstraint, ForeignKey, Mapped types
- `app/vehicles/schemas.py` — Base/Create/Update/Response schema pattern with Literal types
- `app/vehicles/repository.py` — CRUD repository with list/count/search pattern
- `app/vehicles/service.py` — Service with structured logging, exception handling
- `app/vehicles/routes.py` — Router with RBAC, rate limiting, pagination dependencies
- `app/vehicles/exceptions.py` — Feature-specific exception classes
- `app/transit/poller.py` — Background task pattern with Redis pipeline writes, Pub/Sub publishing, leader election
- `app/transit/models.py` (lines 1-69) — VehiclePositionRecord hypertable model (no TimestampMixin)

### Files to Modify
- `app/main.py` — Register fleet_router, add Traccar bridge start/stop to lifespan
- `app/core/config.py` — Add Traccar and fleet settings
- `docker-compose.yml` — Add Traccar service
- `.env.example` — Add new environment variables

## Implementation Plan

### Phase 1: Foundation
Settings, schemas, models, exceptions, and database migration. These are dependency-free and establish the data layer.

### Phase 2: Core Implementation
Repository, service, webhook handler, Traccar bridge (background telemetry processor), and routes.

### Phase 3: Integration & Validation
Docker Traccar service, router registration, lifespan hooks, tests, final validation.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add Fleet Settings to Configuration
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add fleet/Traccar configuration settings to the `Settings` class, after the `alerts_check_interval_seconds` field (around line 190):

```python
# Fleet management / Traccar GPS gateway
traccar_enabled: bool = False
traccar_base_url: str = "http://traccar:8082"
traccar_webhook_token: str = "vtv-traccar-webhook"  # noqa: S105
fleet_telemetry_source: str = "hardware"
fleet_obd_fields: list[str] = [
    "speed", "rpm", "fuel_level", "coolant_temp",
    "odometer", "engine_load", "battery_voltage",
]
```

Add a model validator to reject default webhook token in production (after the existing `_reject_default_secrets_in_production` validator):

```python
# Inside the existing _reject_default_secrets_in_production method, add:
if self.traccar_enabled and self.traccar_webhook_token == "vtv-traccar-webhook":
    msg = "TRACCAR_WEBHOOK_TOKEN must be overridden when Traccar is enabled in production"
    raise ValueError(msg)
```

Actually — merge this check INTO the existing `_reject_default_secrets_in_production` validator body, not as a separate validator.

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py`
- `uv run mypy app/core/config.py`
- `uv run pyright app/core/config.py`

---

### Task 2: Update .env.example
**File:** `.env.example` (modify existing)
**Action:** UPDATE

Add fleet/Traccar environment variables at the end of the file:

```bash
# Fleet Management / Traccar GPS Gateway
TRACCAR_ENABLED=false
TRACCAR_BASE_URL=http://traccar:8082
TRACCAR_WEBHOOK_TOKEN=vtv-traccar-webhook
FLEET_TELEMETRY_SOURCE=hardware
```

**Per-task validation:**
- File is not Python; no lint needed. Verify file exists and is well-formed.

---

### Task 3: Create Fleet Schemas
**File:** `app/fleet/schemas.py` (create new)
**Action:** CREATE

Also create `app/fleet/__init__.py` (empty file).

Define Pydantic schemas for the fleet feature:

1. **Literal types:**
   - `DeviceStatusType = Literal["active", "inactive", "offline"]`
   - `DeviceProtocolType = Literal["teltonika", "queclink", "general", "osmand", "other"]`
   - `TelemetrySourceType = Literal["hardware", "gtfs-rt"]`

2. **TrackedDeviceBase** — shared fields:
   - `imei: str` — Field(min_length=15, max_length=15, pattern=r"^\d{15}$", description="IMEI number")
   - `device_name: str | None` — Field(None, max_length=100)
   - `sim_number: str | None` — Field(None, max_length=20)
   - `protocol_type: DeviceProtocolType` — Field(default="teltonika")
   - `firmware_version: str | None` — Field(None, max_length=50)
   - `notes: str | None` — Field(None, max_length=2000)

3. **TrackedDeviceCreate(TrackedDeviceBase):**
   - `vehicle_id: int | None` — Field(None, description="Link to existing vehicle")

4. **TrackedDeviceUpdate(BaseModel):**
   - All fields optional (mirrors TrackedDeviceBase + vehicle_id)
   - Include `@model_validator(mode="before")` with `@classmethod` for reject_empty_body (pattern from vehicles)
   - `status: DeviceStatusType | None` — Field(None)

5. **TrackedDeviceResponse(TrackedDeviceBase):**
   - `id: int`
   - `vehicle_id: int | None`
   - `status: DeviceStatusType`
   - `last_seen_at: datetime.datetime | None`
   - `created_at: datetime.datetime`
   - `updated_at: datetime.datetime`
   - `model_config = ConfigDict(from_attributes=True)`

6. **TraccarWebhookPayload(BaseModel):**
   - `id: int`
   - `deviceId: int` — Traccar's internal device ID
   - `protocol: str`
   - `deviceTime: str` — ISO timestamp from device
   - `fixTime: str` — GPS fix timestamp
   - `serverTime: str` — Traccar server timestamp
   - `latitude: float`
   - `longitude: float`
   - `altitude: float | None = None`
   - `speed: float | None = None` — knots from Traccar
   - `course: float | None = None` — heading degrees
   - `accuracy: float | None = None`
   - `attributes: dict[str, Any] = Field(default_factory=dict)` — OBD-II and device-specific data
   - Note: Use `from typing import Any` for attributes dict

7. **OBDTelemetry(BaseModel):**
   - `speed_kmh: float | None = None`
   - `rpm: int | None = None`
   - `fuel_level_pct: float | None = None`
   - `coolant_temp_c: float | None = None`
   - `odometer_km: float | None = None`
   - `engine_load_pct: float | None = None`
   - `battery_voltage: float | None = None`

Use `import datetime` (not `from datetime import datetime`) to avoid shadowing with field names (anti-pattern rule 39).

**Per-task validation:**
- `uv run ruff format app/fleet/schemas.py`
- `uv run ruff check --fix app/fleet/schemas.py`
- `uv run mypy app/fleet/schemas.py`

---

### Task 4: Create Fleet Models
**File:** `app/fleet/models.py` (create new)
**Action:** CREATE

Define SQLAlchemy models:

1. **TrackedDevice(Base, TimestampMixin):**
   - `__tablename__ = "tracked_devices"`
   - `__table_args__` with:
     - `CheckConstraint("status IN ('active', 'inactive', 'offline')", name="ck_tracked_devices_status")`
     - `CheckConstraint("protocol_type IN ('teltonika', 'queclink', 'general', 'osmand', 'other')", name="ck_tracked_devices_protocol")`
   - Fields:
     - `id: Mapped[int]` — primary_key, index
     - `imei: Mapped[str]` — String(15), unique, nullable=False, index
     - `device_name: Mapped[str | None]` — String(100)
     - `sim_number: Mapped[str | None]` — String(20)
     - `protocol_type: Mapped[str]` — String(20), nullable=False, default="teltonika"
     - `firmware_version: Mapped[str | None]` — String(50)
     - `vehicle_id: Mapped[int | None]` — ForeignKey("vehicles.id", ondelete="SET NULL"), index
     - `status: Mapped[str]` — String(20), nullable=False, default="active"
     - `last_seen_at: Mapped[datetime.datetime | None]` — DateTime(timezone=True)
     - `traccar_device_id: Mapped[int | None]` — Integer, nullable=True (Traccar's internal ID for webhook correlation)
     - `notes: Mapped[str | None]` — Text

Import: `from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text`
Import: `from app.core.database import Base` and `from app.shared.models import TimestampMixin`

**Per-task validation:**
- `uv run ruff format app/fleet/models.py`
- `uv run ruff check --fix app/fleet/models.py`
- `uv run mypy app/fleet/models.py`

---

### Task 5: Create Fleet Exceptions
**File:** `app/fleet/exceptions.py` (create new)
**Action:** CREATE

Define feature-specific exceptions:

```python
"""Fleet-specific exceptions.

Exception → HTTP mapping:
- DeviceNotFoundError → 404
- DeviceAlreadyExistsError → 422
- DeviceValidationError → 422
- FleetError → 500
- WebhookAuthError → 401
"""

from app.core.exceptions import AppError, DomainValidationError, NotFoundError


class FleetError(AppError):
    """Base exception for fleet operations."""


class DeviceNotFoundError(NotFoundError):
    """Raised when tracked device not found by ID or IMEI."""

    def __init__(self, identifier: int | str) -> None:
        super().__init__(f"Tracked device '{identifier}' not found")


class DeviceAlreadyExistsError(DomainValidationError):
    """Raised when IMEI already registered."""

    def __init__(self, imei: str) -> None:
        super().__init__(f"Device with IMEI '{imei}' already exists")


class DeviceValidationError(DomainValidationError):
    """Raised on business logic validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class WebhookAuthError(AppError):
    """Raised when webhook token is invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid webhook authentication token")
```

**Per-task validation:**
- `uv run ruff format app/fleet/exceptions.py`
- `uv run ruff check --fix app/fleet/exceptions.py`
- `uv run mypy app/fleet/exceptions.py`

---

### Task 6: Create Fleet Repository
**File:** `app/fleet/repository.py` (create new)
**Action:** CREATE

Implement `FleetRepository` following `app/vehicles/repository.py` pattern:

- `__init__(self, db: AsyncSession) -> None`
- `async def get(self, device_id: int) -> TrackedDevice | None`
- `async def get_by_imei(self, imei: str) -> TrackedDevice | None`
- `async def get_by_traccar_id(self, traccar_device_id: int) -> TrackedDevice | None`
- `async def get_by_vehicle_id(self, vehicle_id: int) -> TrackedDevice | None`
- `async def list(self, *, offset: int = 0, limit: int = 20, search: str | None = None, status: str | None = None, vehicle_linked: bool | None = None) -> list[TrackedDevice]`
  - Search on `imei`, `device_name`, `sim_number` using `escape_like()`
  - Filter by status if provided
  - Filter by `vehicle_linked`: True = vehicle_id IS NOT NULL, False = vehicle_id IS NULL
  - Order by `id`
- `async def count(self, *, search: str | None = None, status: str | None = None, vehicle_linked: bool | None = None) -> int` — mirrors list filters
- `async def create(self, data: TrackedDeviceCreate) -> TrackedDevice`
- `async def update(self, device: TrackedDevice, data: TrackedDeviceUpdate) -> TrackedDevice` — uses `exclude_unset=True`
- `async def delete(self, device: TrackedDevice) -> None`
- `async def update_last_seen(self, device: TrackedDevice, seen_at: datetime.datetime) -> None` — lightweight update for webhook telemetry

Imports: `from collections.abc import Sequence` (if needed), `from sqlalchemy import func, or_, select`, `from sqlalchemy.ext.asyncio import AsyncSession`, `from app.shared.utils import escape_like`

**Per-task validation:**
- `uv run ruff format app/fleet/repository.py`
- `uv run ruff check --fix app/fleet/repository.py`
- `uv run mypy app/fleet/repository.py`

---

### Task 7: Create Fleet Service
**File:** `app/fleet/service.py` (create new)
**Action:** CREATE

Implement `FleetService` following `app/vehicles/service.py` pattern:

- `__init__(self, db: AsyncSession) -> None` — creates `FleetRepository` and `VehicleRepository` (cross-feature read)
- `async def get_device(self, device_id: int) -> TrackedDeviceResponse` — 404 if not found
- `async def list_devices(self, pagination: PaginationParams, *, search: str | None = None, status: str | None = None, vehicle_linked: bool | None = None) -> PaginatedResponse[TrackedDeviceResponse]`
- `async def create_device(self, data: TrackedDeviceCreate) -> TrackedDeviceResponse`
  - Check IMEI uniqueness → `DeviceAlreadyExistsError`
  - If `vehicle_id` provided, verify vehicle exists via `VehicleRepository.get()` → `DeviceValidationError` if not found
  - Check no other device is already linked to that vehicle → `DeviceValidationError`
- `async def update_device(self, device_id: int, data: TrackedDeviceUpdate) -> TrackedDeviceResponse`
  - 404 if not found
  - If IMEI changed, check uniqueness
  - If vehicle_id changed, verify vehicle exists and no conflict
- `async def delete_device(self, device_id: int) -> None` — 404 if not found

Import `VehicleRepository` from `app.vehicles.repository` (cross-feature read is allowed per CLAUDE.md).

Logging pattern: `"fleet.device.{action}_{state}"` with structured kwargs.

**Per-task validation:**
- `uv run ruff format app/fleet/service.py`
- `uv run ruff check --fix app/fleet/service.py`
- `uv run mypy app/fleet/service.py`

---

### Task 8: Create Traccar Bridge (Webhook Handler + Telemetry Processor)
**File:** `app/fleet/bridge.py` (create new)
**Action:** CREATE

This is the core telemetry ingestion module. It receives Traccar webhook payloads, normalizes them, and writes to Redis + TimescaleDB + Pub/Sub.

1. **`parse_obd_attributes(attributes: dict[str, Any]) -> OBDTelemetry`**
   - Extract OBD-II parameters from Traccar's `attributes` dict
   - Traccar keys: `speed` (km/h), `rpm`, `fuel` (%), `coolantTemp` (C), `odometer` (m → km), `engineLoad` (%), `batteryLevel` (V)
   - Convert units where needed (odometer: meters → km)
   - Return `OBDTelemetry` schema with None for missing values

2. **`normalize_webhook(payload: TraccarWebhookPayload, device: TrackedDevice) -> dict[str, Any]`**
   - Convert Traccar payload to VTV's vehicle position format (matching GTFS-RT structure)
   - Map fields: `latitude`, `longitude`, `speed` (knots → km/h: multiply by 1.852), `course` → `bearing`
   - Set `source: "hardware"`, `feed_id: "fleet"`, `vehicle_id` from linked vehicle's fleet_number
   - Parse OBD attributes
   - Return dict ready for Redis SET and TimescaleDB insert

3. **`class TraccarBridge`**
   - `__init__(self, settings: Settings, db_session_factory: Callable | None = None) -> None`
   - `async def process_webhook(self, payload: TraccarWebhookPayload, redis_client: Redis) -> bool`
     - Look up device by `payload.deviceId` (traccar_device_id)
     - If device not found or not linked to a vehicle, log warning and return False
     - Normalize the payload
     - Write to Redis with same key pattern as transit poller: `vehicle:{feed_id}:{vehicle_id}`
     - Write to TimescaleDB via `VehiclePositionRecord` (using db_session_factory)
     - Publish to Redis Pub/Sub channel `vehicle_positions` (same as transit poller)
     - Update device `last_seen_at`
     - Return True

Import the Redis type from `redis.asyncio import Redis`.
Import `get_db_context` from `app.core.database` for standalone DB access.
Import `VehiclePositionRecord` from `app.transit.models` (cross-feature read — writing to shared hypertable).

Logging: `"fleet.bridge.{action}_{state}"` — `webhook_received`, `position_stored`, `device_unknown`, `storage_failed`

Note on writing to `vehicle_positions`: This is an intentional cross-feature write to the shared hypertable. The `source` column distinguishes hardware from GTFS-RT data. This is justified because the hypertable is shared infrastructure, not owned by a single feature.

**Per-task validation:**
- `uv run ruff format app/fleet/bridge.py`
- `uv run ruff check --fix app/fleet/bridge.py`
- `uv run mypy app/fleet/bridge.py`

---

### Task 9: Create Fleet Routes
**File:** `app/fleet/routes.py` (create new)
**Action:** CREATE

Implement the FastAPI router with two sections: device CRUD and webhook endpoint.

**Router:** `APIRouter(prefix="/api/v1/fleet", tags=["fleet"])`

**Device CRUD endpoints (RBAC: admin/editor for write, all authenticated for read):**

1. `GET /devices` — list devices with pagination, search, status filter, vehicle_linked filter
   - Rate limit: 30/minute
   - Auth: `get_current_user`
   - Query params: `search: str | None = Query(None, max_length=200)`, `status: str | None = Query(None)`, `vehicle_linked: bool | None = Query(None)`

2. `GET /devices/{device_id}` — get device by ID
   - Rate limit: 30/minute
   - Auth: `get_current_user`

3. `POST /devices` — create device
   - Rate limit: 10/minute
   - Auth: `require_role("admin", "editor")`
   - Status: 201

4. `PATCH /devices/{device_id}` — update device
   - Rate limit: 10/minute
   - Auth: `require_role("admin", "editor")`

5. `DELETE /devices/{device_id}` — delete device
   - Rate limit: 10/minute
   - Auth: `require_role("admin")`
   - Status: 204

**Webhook endpoint (token-authenticated, no RBAC):**

6. `POST /webhook/traccar` — receive Traccar position events
   - Rate limit: 120/minute (high volume — one per device per poll interval)
   - Auth: **Token-based** — `Authorization: Bearer {TRACCAR_WEBHOOK_TOKEN}` header
   - Validate token against `settings.traccar_webhook_token`
   - If invalid, return 401 (do NOT use `get_current_user` — Traccar is not a VTV user)
   - On success, call `TraccarBridge.process_webhook()`
   - Return `{"status": "ok", "processed": True/False}`

**Important:** The webhook endpoint must be added to the security test allowlist. Add the path to the public endpoints exception list. The webhook uses token auth, not JWT — it needs its own auth check.

For webhook auth, create a dependency:
```python
async def verify_webhook_token(
    authorization: str | None = Header(None),  # noqa: B008
) -> None:
    """Verify Traccar webhook bearer token."""
    settings = get_settings()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing webhook token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.traccar_webhook_token:
        raise HTTPException(status_code=401, detail="Invalid webhook token")
```

**Per-task validation:**
- `uv run ruff format app/fleet/routes.py`
- `uv run ruff check --fix app/fleet/routes.py`
- `uv run mypy app/fleet/routes.py`

---

### Task 10: Add `source` and `obd_data` Columns to vehicle_positions
**File:** `alembic/versions/d1e2f3a4b5c6_add_fleet_tracking_columns.py` (create new)
**Action:** CREATE

Create a NEW migration (do NOT use --autogenerate since the tracked_devices table needs to be created too):

- `revision = "d1e2f3a4b5c6"`
- `down_revision = "c8d9e0f1a2b3"` (shapes migration — current HEAD)
- `branch_labels = None`
- `depends_on = None`

**Upgrade operations:**
1. Create `tracked_devices` table:
   - `id` — Integer, primary key, autoincrement
   - `imei` — String(15), unique, not null, indexed
   - `device_name` — String(100), nullable
   - `sim_number` — String(20), nullable
   - `protocol_type` — String(20), not null, server_default="teltonika"
   - `firmware_version` — String(50), nullable
   - `vehicle_id` — Integer, ForeignKey("vehicles.id", ondelete="SET NULL"), nullable, indexed
   - `status` — String(20), not null, server_default="active"
   - `last_seen_at` — DateTime(timezone=True), nullable
   - `traccar_device_id` — Integer, nullable
   - `notes` — Text, nullable
   - `created_at` — DateTime(timezone=True), not null, server_default=func.now()
   - `updated_at` — DateTime(timezone=True), not null, server_default=func.now()
   - CHECK constraints for `status` and `protocol_type` (same values as model)

2. Add columns to `vehicle_positions`:
   - `source` — String(20), not null, server_default="gtfs-rt"
   - `obd_data` — JSONB, nullable (use `sa.dialects.postgresql.JSONB`)
   - Add index: `ix_vehicle_positions_source` on `source` column

**Downgrade operations:**
1. Drop columns from `vehicle_positions`: `source`, `obd_data` and the index
2. Drop `tracked_devices` table

Import: `import sqlalchemy as sa`, `from alembic import op`, `from sqlalchemy.dialects.postgresql import JSONB`

**Per-task validation:**
- `uv run ruff format alembic/versions/d1e2f3a4b5c6_add_fleet_tracking_columns.py`
- `uv run ruff check --fix alembic/versions/d1e2f3a4b5c6_add_fleet_tracking_columns.py`
- `uv run mypy alembic/versions/d1e2f3a4b5c6_add_fleet_tracking_columns.py`

---

### Task 11: Update VehiclePositionRecord Model
**File:** `app/transit/models.py` (modify existing)
**Action:** UPDATE

Add the two new columns to `VehiclePositionRecord`:

```python
source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="gtfs-rt")
obd_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
```

Add imports: `from typing import Any` and `from sqlalchemy.dialects.postgresql import JSONB`

Add a new index to `__table_args__`:
```python
Index("ix_vehicle_positions_source", "source"),
```

**Per-task validation:**
- `uv run ruff format app/transit/models.py`
- `uv run ruff check --fix app/transit/models.py`
- `uv run mypy app/transit/models.py`

---

### Task 12: Add Traccar Service to Docker Compose
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

Add a Traccar service definition. Insert AFTER the `redis` service:

```yaml
  traccar:
    image: traccar/traccar:6-alpine
    container_name: vtv-traccar
    restart: unless-stopped
    profiles:
      - fleet
    ports:
      - "8082:8082"    # Traccar web UI (dev only)
      - "5027:5027"    # Teltonika protocol
      - "5023:5023"    # Queclink protocol
    volumes:
      - traccar_data:/opt/traccar/data
      - ./traccar/traccar.xml:/opt/traccar/conf/traccar.xml:ro
    environment:
      - JAVA_OPTS=-Xmx256m
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8082/api/server"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
```

Add `traccar_data` to the `volumes` section at the bottom:
```yaml
  traccar_data:
```

IMPORTANT: Traccar uses the `fleet` profile — it won't start with `docker compose up` unless explicitly activated with `--profile fleet` or `COMPOSE_PROFILES=fleet`. This keeps the default dev experience unchanged.

**Per-task validation:**
- `docker compose config --quiet` — validates compose file syntax

---

### Task 13: Create Traccar Configuration File
**File:** `traccar/traccar.xml` (create new)
**Action:** CREATE

Create the Traccar config that enables webhook forwarding to VTV:

```xml
<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE properties SYSTEM 'http://java.sun.com/dtd/properties.dtd'>
<properties>
    <!-- Database: use H2 embedded (Traccar is gateway-only, VTV owns the data) -->
    <entry key='database.driver'>org.h2.Driver</entry>
    <entry key='database.url'>jdbc:h2:/opt/traccar/data/database</entry>
    <entry key='database.user'>sa</entry>
    <entry key='database.password'></entry>

    <!-- Forward all events to VTV webhook -->
    <entry key='forward.enable'>true</entry>
    <entry key='forward.url'>http://app:8123/api/v1/fleet/webhook/traccar</entry>
    <entry key='forward.header.Authorization'>Bearer ${TRACCAR_WEBHOOK_TOKEN:-vtv-traccar-webhook}</entry>
    <entry key='forward.json'>true</entry>

    <!-- Enable protocols (Teltonika + Queclink + OsmAnd for testing) -->
    <entry key='teltonika.port'>5027</entry>
    <entry key='queclink.port'>5023</entry>
    <entry key='osmand.port'>5055</entry>

    <!-- Logging -->
    <entry key='logger.enable'>true</entry>
    <entry key='logger.level'>info</entry>
</properties>
```

**Per-task validation:**
- Verify XML is well-formed: file exists and is parseable

---

### Task 14: Create Fleet Tests
**File:** `app/fleet/tests/__init__.py` (create new, empty)
**File:** `app/fleet/tests/conftest.py` (create new)
**File:** `app/fleet/tests/test_service.py` (create new)
**File:** `app/fleet/tests/test_bridge.py` (create new)
**Action:** CREATE

**conftest.py:**
- Import `pytest` and `AsyncMock`, `MagicMock` from `unittest.mock`
- Create fixtures for mock `AsyncSession`, mock `FleetRepository`, sample `TrackedDeviceCreate`, sample `TraccarWebhookPayload`

**test_service.py** — Unit tests for FleetService:

1. `test_create_device_success` — creates device, verifies response fields
2. `test_create_device_duplicate_imei` — raises DeviceAlreadyExistsError
3. `test_create_device_invalid_vehicle` — vehicle_id provided but vehicle doesn't exist → DeviceValidationError
4. `test_create_device_vehicle_already_linked` — another device linked to same vehicle → DeviceValidationError
5. `test_get_device_not_found` — raises DeviceNotFoundError
6. `test_update_device_success` — updates fields, verifies response
7. `test_delete_device_success` — deletes device
8. `test_list_devices_pagination` — verifies PaginatedResponse structure

**test_bridge.py** — Unit tests for TraccarBridge:

1. `test_parse_obd_attributes_full` — all OBD fields present, verify conversion
2. `test_parse_obd_attributes_partial` — some fields missing → None
3. `test_parse_obd_attributes_empty` — empty dict → all None
4. `test_normalize_webhook_speed_conversion` — knots → km/h conversion (1 knot = 1.852 km/h)
5. `test_normalize_webhook_odometer_conversion` — meters → km
6. `test_process_webhook_unknown_device` — device not found → returns False
7. `test_process_webhook_unlinked_device` — device has no vehicle → returns False
8. `test_process_webhook_success` — full pipeline, verify Redis SET and Pub/Sub publish called

Use `MagicMock` for Redis (not `AsyncMock` — redis pipeline is sync, only `execute()` is async per anti-pattern rule 35).
Use `AsyncMock` for `execute()` on the pipeline.

All test functions annotated with `-> None`. Test helpers have return type annotations.

**Per-task validation:**
- `uv run ruff format app/fleet/tests/`
- `uv run ruff check --fix app/fleet/tests/`
- `uv run pytest app/fleet/tests/ -v`

---

### Task 15: Update Security Test Allowlist
**File:** `app/tests/test_security.py` (modify existing)
**Action:** UPDATE

Find the set/list of public endpoint paths that are exempted from the `TestAllEndpointsRequireAuth` check. Add the webhook endpoint:

- `/api/v1/fleet/webhook/traccar` — uses token auth, not JWT (webhook from Traccar service)

Read the file first to find the exact variable name and format used for the allowlist, then add the path.

**Per-task validation:**
- `uv run ruff format app/tests/test_security.py`
- `uv run ruff check --fix app/tests/test_security.py`
- `uv run pytest app/tests/test_security.py -v`

---

### Task 16: Register Router and Lifespan Hooks
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

1. Add import at the top (with other router imports):
   ```python
   from app.fleet.routes import router as fleet_router
   ```

2. Add router registration (after `alerts_router`):
   ```python
   app.include_router(fleet_router)
   ```

3. No lifespan changes needed in this phase — the bridge is invoked on-demand via webhook, not as a background task. Background polling of Traccar is deferred to Phase 1B (if needed).

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py`

---

## Migration

**Migration file:** Created manually in Task 10 at `alembic/versions/d1e2f3a4b5c6_add_fleet_tracking_columns.py`

**If database is running:**
```bash
uv run alembic upgrade head
```

**If database is NOT running:** The migration file is self-contained and will run on next `docker compose up` via the `migrate` service.

**Column specifications (for manual migration):**
- `tracked_devices.id`: Integer, PK, autoincrement
- `tracked_devices.imei`: String(15), unique, not null, indexed
- `tracked_devices.device_name`: String(100), nullable
- `tracked_devices.sim_number`: String(20), nullable
- `tracked_devices.protocol_type`: String(20), not null, server_default="teltonika"
- `tracked_devices.firmware_version`: String(50), nullable
- `tracked_devices.vehicle_id`: Integer, FK(vehicles.id), SET NULL, nullable, indexed
- `tracked_devices.status`: String(20), not null, server_default="active"
- `tracked_devices.last_seen_at`: DateTime(tz), nullable
- `tracked_devices.traccar_device_id`: Integer, nullable
- `tracked_devices.notes`: Text, nullable
- `tracked_devices.created_at`: DateTime(tz), not null, server_default=now()
- `tracked_devices.updated_at`: DateTime(tz), not null, server_default=now()
- `vehicle_positions.source`: String(20), not null, server_default="gtfs-rt"
- `vehicle_positions.obd_data`: JSONB, nullable

## Logging Events

- `fleet.device.create_started` — device registration initiated (imei)
- `fleet.device.create_completed` — device registered (device_id, imei)
- `fleet.device.create_failed` — registration failed (imei, reason)
- `fleet.device.update_started` — device update initiated (device_id)
- `fleet.device.update_completed` — device updated (device_id)
- `fleet.device.delete_started` — device deletion initiated (device_id)
- `fleet.device.delete_completed` — device deleted (device_id)
- `fleet.device.list_started` — device listing initiated (page, search)
- `fleet.device.list_completed` — listing completed (result_count, total)
- `fleet.bridge.webhook_received` — Traccar webhook received (traccar_device_id)
- `fleet.bridge.position_stored` — position written to Redis + DB (vehicle_id, lat, lon)
- `fleet.bridge.device_unknown` — webhook for unregistered device (traccar_device_id)
- `fleet.bridge.device_unlinked` — webhook for device not linked to vehicle (imei)
- `fleet.bridge.storage_failed` — DB/Redis write failed (error, error_type)

## Testing Strategy

### Unit Tests
**Location:** `app/fleet/tests/test_service.py`
- FleetService CRUD — happy paths and error cases
- IMEI uniqueness validation
- Vehicle linking validation (vehicle exists, no double-link)

**Location:** `app/fleet/tests/test_bridge.py`
- OBD-II attribute parsing (full, partial, empty)
- Speed/odometer unit conversions
- Webhook processing pipeline (device lookup, normalization, storage)
- Unknown/unlinked device handling

### Integration Tests
**Location:** `app/fleet/tests/test_routes.py` (deferred to Phase 1B — requires running DB)
**Mark with:** `@pytest.mark.integration`
- Full HTTP request cycle through device CRUD endpoints
- Webhook endpoint with valid/invalid tokens

### Edge Cases
- Device with all-zero IMEI — should pass regex validation (15 digits)
- Webhook with no OBD attributes — should produce empty OBDTelemetry
- Speed of 0 knots — should convert to 0 km/h (not None)
- Negative altitude from GPS — valid, should be stored
- Device linked to deleted vehicle — FK SET NULL, device remains but unlinked
- Concurrent webhooks for same device — idempotent (last write wins)

## Acceptance Criteria

This feature is complete when:
- [ ] `TrackedDevice` model with IMEI uniqueness, vehicle FK, status constraints
- [ ] Device CRUD endpoints (5) with RBAC (admin/editor write, authenticated read)
- [ ] Traccar webhook endpoint with token authentication
- [ ] OBD-II attribute parsing from Traccar's `attributes` dict
- [ ] Position data written to Redis cache, TimescaleDB, and Pub/Sub
- [ ] `source` column added to `vehicle_positions` (distinguishes hardware from GTFS-RT)
- [ ] `obd_data` JSONB column added to `vehicle_positions`
- [ ] Traccar Docker service configured with `fleet` profile
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + integration)
- [ ] Structured logging follows `fleet.component.action_state` pattern
- [ ] No type suppressions added (except documented exceptions)
- [ ] Router registered in `app/main.py`
- [ ] No regressions in existing tests (879+)
- [ ] Security: webhook token validated, IMEI input validated, CTX-RBAC on all endpoints

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 16 tasks completed in order
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
uv run pytest app/fleet/tests/ -v
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

- **Shared utilities used:** `TimestampMixin` (app/shared/models), `PaginatedResponse` + `PaginationParams` (app/shared/schemas), `escape_like` (app/shared/utils), `get_logger` (app/core/logging), `get_db` + `get_db_context` (app/core/database), `AppError` hierarchy (app/core/exceptions), `get_current_user` + `require_role` (app/auth/dependencies), `limiter` (app/core/rate_limit)
- **Core modules used:** `app/core/config.py` (Settings), `app/core/redis.py` (Redis client)
- **Cross-feature reads:** `app/vehicles/repository.py` (verify vehicle exists), `app/transit/models.py` (VehiclePositionRecord for shared hypertable writes)
- **New dependencies:** None — all libraries already in pyproject.toml (SQLAlchemy, Redis, httpx, Pydantic)
- **New env vars:** `TRACCAR_ENABLED`, `TRACCAR_BASE_URL`, `TRACCAR_WEBHOOK_TOKEN`, `FLEET_TELEMETRY_SOURCE`

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules loaded via `@_shared/python-anti-patterns.md`. Key rules for this feature:

- **Rule 1:** No `assert` in production — use `if not device:` not `assert device`
- **Rule 5:** No unused imports — only import what's used
- **Rule 9:** Pydantic AI `ctx` — N/A (no agent tools), but ARG001 applies to unused params like `request` in routes (use `_ = request`)
- **Rule 11:** Schema field additions — adding `source`/`obd_data` to VehiclePositionRecord affects transit poller writes
- **Rule 18:** ARG001 — suppress with `_ = param_name` for FastAPI `request` params needed by limiter
- **Rule 35:** Redis pipeline is SYNC — mock with `MagicMock()`, only `execute()` is async
- **Rule 39:** `import datetime` not `from datetime import datetime` (field name conflicts)
- **Rule 41:** ILIKE search — use `escape_like()` from `app.shared.utils`
- **Rule 46:** Docker creds — use `${VAR:-default}` interpolation
- **Rule 48:** Unique constraints — IMEI uniqueness via `unique=True` on model column
- **Rule 52:** Empty PATCH bodies — `@model_validator(mode="before")` with `@classmethod`
- **Rule 54:** Constrained strings — use `Literal[...]` for status, protocol_type

**Transit poller impact:** Adding `source` and `obd_data` columns to `VehiclePositionRecord` requires checking that the transit poller's `batch_insert_positions` function still works. The new columns have `server_default` values, so existing GTFS-RT writes won't need code changes — they'll get `source="gtfs-rt"` and `obd_data=NULL` automatically. Verify this by running `uv run pytest app/transit/tests/ -v` after Task 11.

## Notes

- **Traccar profile isolation:** Traccar uses Docker Compose profiles (`--profile fleet`). Default `docker compose up` won't start Traccar, preserving the current dev experience. Use `docker compose --profile fleet up` when testing fleet features.
- **OBD-II as JSONB:** Storing OBD parameters as JSONB avoids schema changes per parameter and handles device variability. Indexing individual OBD fields (if needed for analytics queries) can be added later via GIN index or generated columns.
- **Webhook vs polling:** This design uses Traccar's event forwarding (push) rather than polling Traccar's API. Push is lower latency and avoids coupling to Traccar's API schema. If Traccar webhook delivery proves unreliable, a fallback polling bridge can be added in Phase 1B.
- **Source column backfill:** Existing `vehicle_positions` rows will get `source="gtfs-rt"` via `server_default`. No data migration needed.
- **Future Phase 1B scope:** Geofencing (PostGIS Polygon zones), fleet analytics aggregation, CMS device management page, extended live map with hardware markers.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the VehiclePositionRecord hypertable structure
- [ ] Understood the Vehicle model and its fleet_number field
- [ ] Understood the transit poller's Redis write pattern (key format, TTL, Pub/Sub channel)
- [ ] Understood the authentication dependency pattern (get_current_user, require_role)
- [ ] Verified current migration HEAD is c8d9e0f1a2b3
- [ ] Clear on task execution order (1-16)
- [ ] Validation commands are executable in this environment
