# Fleet Management & Vehicle Tracking — Implementation Plan

> LocTracker-inspired fleet management extension for VTV
> Research source: `/Users/Berzins/Desktop/TrackingAPI/LocTracker-Research.md`
> Created: 2026-03-08

---

## 1. Overview

Extend VTV from a transit CMS into a **full fleet management platform** with hardware GPS tracking, OBD-II telemetry, tachograph compliance, fuel monitoring, and geofencing. This bridges the gap between VTV's existing GTFS-RT software tracking and hardware-based telematics for vehicles without public transit feeds.

**Target:** Rigas Satiksme (RS) — 1,097 vehicles (buses, trolleybuses, trams, service vans)
**Fleet size at launch:** 300-700 vehicles
**Market:** Latvia (initially)
**Approach:** Monorepo — new vertical slices in existing VTV codebase

### Why This Fits VTV

VTV already has:
- TimescaleDB hypertable for vehicle positions (90-day retention, compression)
- Redis Pub/Sub + WebSocket for real-time position push
- Vehicle management (8 endpoints, fleet CRUD, maintenance tracking)
- Driver management (5 endpoints, shift/availability tracking)
- Alerts system (background evaluator, configurable rules)
- PostGIS spatial queries
- RBAC (4 roles), JWT auth, structured logging

What's missing for full fleet management:
- Hardware GPS device ingestion (Teltonika Codec 8/8E)
- OBD-II/CAN bus telemetry (speed, RPM, fuel, odometer, engine data)
- Tachograph remote download + EU driving hours compliance
- Geofence zone management with entry/exit detection
- Fuel monitoring with refueling/drain detection
- Fleet analytics (distance, drive time, country mileage)
- Public tracking links (LocShare equivalent)

---

## 2. Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      VTV Monorepo                            │
│                                                              │
│  Existing slices:              New slices:                    │
│  ├── app/transit/    (GTFS-RT) ├── app/fleet/     (telemetry)│
│  ├── app/vehicles/   (CRUD)    ├── app/tachograph/ (compliance)│
│  ├── app/drivers/    (HR)      ├── app/geofences/  (zones)   │
│  ├── app/alerts/     (rules)   │                             │
│  ├── app/analytics/  (reports) │                             │
│  └── app/compliance/ (EU)      │                             │
│                                                              │
│  Shared: TimescaleDB, Redis, WebSocket, auth, RBAC, alerts  │
│                                                              │
│  External services (Docker sidecar):                         │
│  ├── Traccar (GPS protocol gateway — Codec 8/8E, 200+ protocols)│
│  └── OSRM (self-hosted routing with Latvia OSM extract)      │
│                                                              │
│  External APIs (fallback):                                   │
│  └── HERE Maps (truck routing, geocoding, toll costs)        │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Teltonika Device (FMB920/FMB640)
    │ TCP (Codec 8/8E)
    ▼
Traccar (Docker sidecar, port 5055)
    │ REST API / WebSocket events
    ▼
app/fleet/ event bridge
    │
    ├──▶ TimescaleDB (vehicle_positions — shared with GTFS-RT)
    ├──▶ Redis (live positions, Pub/Sub broadcast)
    ├──▶ app/geofences/ (entry/exit detection)
    ├──▶ app/alerts/ (threshold evaluation)
    └──▶ WebSocket (push to CMS dashboard)
```

### Shared vehicle_positions Table

The existing `vehicle_positions` TimescaleDB hypertable will be extended with a `source` column to distinguish data origins:

```sql
-- Existing columns
timestamp, vehicle_id, latitude, longitude, bearing, speed, ...

-- New columns for fleet telemetry
source          TEXT       -- 'gtfs_rt' | 'traccar' | 'owntracks'
device_id       TEXT       -- Teltonika IMEI or Traccar device identifier
obd_speed       FLOAT     -- OBD-reported speed (km/h)
obd_rpm         FLOAT     -- Engine RPM
obd_fuel_level  FLOAT     -- Fuel level (%)
obd_odometer    FLOAT     -- Total odometer (km)
obd_coolant_temp FLOAT    -- Engine coolant temperature (°C)
obd_engine_load FLOAT     -- Engine load (%)
ignition        BOOLEAN   -- Ignition on/off
```

This keeps a single hypertable with shared compression/retention policies while allowing queries filtered by source.

---

## 3. New Vertical Slices

### 3.1 `app/fleet/` — Device Telemetry & Fleet Tracking

**Purpose:** Bridge between Traccar GPS gateway and VTV's data layer. Handles device registration, telemetry ingestion, OBD data parsing, fuel monitoring, and LocShare.

**Files:**
```
app/fleet/
├── __init__.py
├── schemas.py          # DeviceCreate, DeviceResponse, TelemetryRecord, FuelEvent, LocShareCreate
├── models.py           # TrackedDevice (SQLAlchemy), FuelEvent
├── repository.py       # Device CRUD, telemetry queries, fuel event queries
├── service.py          # Device registration, Traccar bridge, fuel detection, LocShare
├── routes.py           # REST endpoints
├── traccar_bridge.py   # Traccar API/WS consumer, position normalization
├── fuel_monitor.py     # Refueling/drain detection algorithms
├── exceptions.py       # DeviceNotFoundError, TraccarConnectionError
└── tests/
    ├── conftest.py
    ├── test_routes.py
    ├── test_service.py
    ├── test_traccar_bridge.py
    └── test_fuel_monitor.py
```

**Models:**

```python
class TrackedDevice(Base, TimestampMixin):
    """GPS tracking device registered in the system."""
    id: Mapped[int]                          # PK
    vehicle_id: Mapped[int | None]           # FK to vehicles.id
    traccar_device_id: Mapped[int | None]    # Traccar internal ID
    imei: Mapped[str]                        # Device IMEI (unique)
    device_model: Mapped[str]                # e.g. "FMB920", "FMB640", "FMM00A"
    sim_number: Mapped[str | None]           # SIM card number
    status: Mapped[str]                      # 'active' | 'inactive' | 'maintenance'
    last_position_at: Mapped[datetime | None]
    firmware_version: Mapped[str | None]

class FuelEvent(Base, TimestampMixin):
    """Detected fuel refueling or drain event."""
    id: Mapped[int]
    vehicle_id: Mapped[int]                  # FK to vehicles.id
    event_type: Mapped[str]                  # 'refueling' | 'drain' | 'consumption'
    fuel_before: Mapped[float]               # Fuel level before event (%)
    fuel_after: Mapped[float]                # Fuel level after event (%)
    fuel_change_liters: Mapped[float | None] # Estimated liters (if tank capacity known)
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    detected_at: Mapped[datetime]
```

**Endpoints (~15):**

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/fleet/devices` | List tracked devices (paginated, filterable) | admin, dispatcher |
| POST | `/api/v1/fleet/devices` | Register new device | admin |
| GET | `/api/v1/fleet/devices/{id}` | Get device details | admin, dispatcher |
| PATCH | `/api/v1/fleet/devices/{id}` | Update device (assign to vehicle, status) | admin |
| DELETE | `/api/v1/fleet/devices/{id}` | Deactivate device | admin |
| GET | `/api/v1/fleet/devices/{id}/telemetry` | Recent telemetry for device | admin, dispatcher |
| GET | `/api/v1/fleet/positions` | All fleet vehicle positions (live) | admin, dispatcher |
| GET | `/api/v1/fleet/positions/{vehicle_id}/history` | Position history (time range) | admin, dispatcher |
| GET | `/api/v1/fleet/fuel/events` | Fuel events (refueling/drain) | admin, dispatcher |
| GET | `/api/v1/fleet/fuel/{vehicle_id}/consumption` | Fuel consumption analytics | admin, dispatcher |
| POST | `/api/v1/fleet/share` | Create LocShare link | admin, dispatcher |
| GET | `/api/v1/fleet/share/{token}` | Get shared vehicle position (public, no auth) | public |
| DELETE | `/api/v1/fleet/share/{token}` | Revoke share link | admin, dispatcher |
| GET | `/api/v1/fleet/traccar/status` | Traccar connection health | admin |
| POST | `/api/v1/fleet/traccar/sync` | Force device sync from Traccar | admin |

### 3.2 `app/geofences/` — Zone Management & Detection

**Purpose:** Create and manage geofence zones (depots, terminals, restricted areas). Detect vehicle entry/exit events. LocPoints-style dwell time tracking.

**Files:**
```
app/geofences/
├── __init__.py
├── schemas.py        # GeofenceCreate, GeofenceResponse, GeofenceEvent, DwellTimeReport
├── models.py         # Geofence (PostGIS Polygon), GeofenceEvent
├── repository.py     # Geofence CRUD, spatial queries, event logging
├── service.py        # Zone evaluation, dwell time calculation
├── evaluator.py      # Background task: check positions against geofences
├── exceptions.py
└── tests/
    ├── conftest.py
    ├── test_routes.py
    ├── test_service.py
    └── test_evaluator.py
```

**Models:**

```python
class Geofence(Base, TimestampMixin):
    """Geographic zone for entry/exit detection."""
    id: Mapped[int]
    name: Mapped[str]
    zone_type: Mapped[str]          # 'depot' | 'terminal' | 'restricted' | 'customer' | 'custom'
    geometry: Mapped[Geometry]       # PostGIS Polygon/MultiPolygon (SRID 4326)
    color: Mapped[str | None]       # Hex color for map display
    alert_on_enter: Mapped[bool]    # default True
    alert_on_exit: Mapped[bool]     # default True
    alert_on_dwell: Mapped[bool]    # default False
    dwell_threshold_minutes: Mapped[int | None]  # Alert if vehicle stays longer than X minutes
    is_active: Mapped[bool]         # default True

class GeofenceEvent(Base):
    """Vehicle entry/exit/dwell event for a geofence."""
    id: Mapped[int]
    geofence_id: Mapped[int]        # FK to geofences.id
    vehicle_id: Mapped[int]         # FK to vehicles.id
    event_type: Mapped[str]         # 'enter' | 'exit' | 'dwell_exceeded'
    entered_at: Mapped[datetime]
    exited_at: Mapped[datetime | None]
    dwell_seconds: Mapped[int | None]
    latitude: Mapped[float]
    longitude: Mapped[float]
```

**Endpoints (~8):**

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/geofences` | List geofences (paginated) | admin, dispatcher |
| POST | `/api/v1/geofences` | Create geofence (GeoJSON polygon) | admin |
| GET | `/api/v1/geofences/{id}` | Get geofence details | admin, dispatcher |
| PATCH | `/api/v1/geofences/{id}` | Update geofence | admin |
| DELETE | `/api/v1/geofences/{id}` | Delete geofence | admin |
| GET | `/api/v1/geofences/{id}/events` | Events for a geofence (time range) | admin, dispatcher |
| GET | `/api/v1/geofences/events` | All geofence events (filterable) | admin, dispatcher |
| GET | `/api/v1/geofences/{id}/dwell-report` | Dwell time analytics (LocPoints) | admin, dispatcher |

### 3.3 `app/tachograph/` — Tachograph & Driving Hours Compliance

**Purpose:** Remote tachograph DDD file download, EU Regulation 561/2006 driving hours tracking, compliance dashboard data, and automated limit alerts.

**Files:**
```
app/tachograph/
├── __init__.py
├── schemas.py          # DDDFile, DriverActivity, DrivingHoursSummary, ComplianceStatus
├── models.py           # TachographFile, DriverActivity, TachographCard
├── repository.py       # DDD file storage, activity queries, compliance queries
├── service.py          # DDD parsing orchestration, hours calculation, compliance checks
├── ddd_parser.py       # Parse DDD binary files into structured data
├── hours_calculator.py # EU 561/2006 driving hours rules engine
├── download_client.py  # Teltonika Web Tacho / flespi integration for remote DDD download
├── exceptions.py
└── tests/
    ├── conftest.py
    ├── test_routes.py
    ├── test_service.py
    ├── test_ddd_parser.py
    ├── test_hours_calculator.py
    └── test_download_client.py
```

**EU 561/2006 Rules Engine:**

```python
# Driving hour limits
DAILY_DRIVE_LIMIT = timedelta(hours=9)         # Can extend to 10h twice/week
DAILY_DRIVE_EXTENDED = timedelta(hours=10)      # Max 2x per week
WEEKLY_DRIVE_LIMIT = timedelta(hours=56)
BIWEEKLY_DRIVE_LIMIT = timedelta(hours=90)
MONTHLY_DRIVE_LIMIT = timedelta(hours=160)      # RS-specific

# Break requirements
CONTINUOUS_DRIVE_MAX = timedelta(hours=4, minutes=30)
BREAK_MINIMUM = timedelta(minutes=45)           # Can split: 15min + 30min
DAILY_REST_MIN = timedelta(hours=11)            # Can reduce to 9h 3x/week
WEEKLY_REST_MIN = timedelta(hours=45)           # Can reduce to 24h every 2 weeks

# Alert thresholds (configurable via alert rules)
WARNING_THRESHOLD = 0.80   # 80% of limit
CRITICAL_THRESHOLD = 0.95  # 95% of limit
```

**Models:**

```python
class TachographCard(Base, TimestampMixin):
    """Driver's tachograph smart card."""
    id: Mapped[int]
    driver_id: Mapped[int]           # FK to drivers.id
    card_number: Mapped[str]         # Unique tachograph card number
    card_type: Mapped[str]           # 'driver' | 'company' | 'workshop'
    issuing_country: Mapped[str]     # ISO 3166-1 alpha-2
    valid_from: Mapped[date]
    valid_until: Mapped[date]

class TachographFile(Base, TimestampMixin):
    """Downloaded DDD file from tachograph device."""
    id: Mapped[int]
    vehicle_id: Mapped[int | None]   # FK to vehicles.id
    driver_id: Mapped[int | None]    # FK to drivers.id
    card_number: Mapped[str | None]
    file_path: Mapped[str]           # Path to stored DDD file
    file_hash: Mapped[str]           # SHA-256 for dedup
    download_source: Mapped[str]     # 'web_tacho' | 'flespi' | 'manual_upload'
    period_start: Mapped[datetime]
    period_end: Mapped[datetime]
    parsed: Mapped[bool]             # Whether activities have been extracted

class DriverActivity(Base):
    """Parsed driving activity from tachograph data."""
    id: Mapped[int]
    driver_id: Mapped[int]           # FK to drivers.id
    tachograph_file_id: Mapped[int]  # FK to tachograph_files.id
    activity_type: Mapped[str]       # 'driving' | 'work' | 'availability' | 'rest' | 'break'
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime]
    duration_seconds: Mapped[int]
    vehicle_id: Mapped[int | None]
```

**Endpoints (~10):**

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/tachograph/cards` | List tachograph cards | admin |
| POST | `/api/v1/tachograph/cards` | Register tachograph card | admin |
| GET | `/api/v1/tachograph/files` | List DDD files (filterable) | admin |
| POST | `/api/v1/tachograph/files/upload` | Manual DDD file upload | admin |
| POST | `/api/v1/tachograph/files/download/{vehicle_id}` | Trigger remote DDD download | admin |
| GET | `/api/v1/tachograph/drivers/{driver_id}/hours` | Driving hours summary (daily/weekly/monthly) | admin, dispatcher |
| GET | `/api/v1/tachograph/drivers/{driver_id}/activities` | Activity timeline (time range) | admin, dispatcher |
| GET | `/api/v1/tachograph/compliance` | Fleet compliance overview (all drivers) | admin, dispatcher |
| GET | `/api/v1/tachograph/compliance/{driver_id}` | Individual driver compliance status | admin, dispatcher |
| GET | `/api/v1/tachograph/infringements` | Detected violations (time range) | admin |

---

## 4. Extensions to Existing Slices

### 4.1 `app/vehicles/` Extensions

- Add `tracked_device_id` FK to Vehicle model (link vehicle ↔ Teltonika device)
- Add `tank_capacity_liters` field for fuel calculations
- Add `tachograph_equipped` boolean

### 4.2 `app/drivers/` Extensions

- Add `tachograph_card_number` field
- Add driving hours summary to driver detail response

### 4.3 `app/alerts/` Extensions

New alert rule types for the background evaluator:

| Rule Type | Description | Threshold |
|-----------|-------------|-----------|
| `geofence_enter` | Vehicle entered a geofence | zone_id |
| `geofence_exit` | Vehicle left a geofence | zone_id |
| `geofence_dwell` | Vehicle stayed too long | minutes |
| `driving_hours_warning` | Approaching driving limit | 80% of limit |
| `driving_hours_critical` | Near driving limit | 95% of limit |
| `fuel_drain` | Sudden fuel level drop | liters threshold |
| `speed_limit` | Vehicle exceeding speed | km/h threshold |
| `idle_time` | Vehicle idling too long | minutes |
| `device_offline` | Device stopped reporting | minutes since last position |

### 4.4 `app/analytics/` Extensions

New analytics endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/analytics/fleet/distance` | Distance per vehicle (daily/weekly/monthly) |
| `GET /api/v1/analytics/fleet/drive-time` | Drive time vs idle time per vehicle |
| `GET /api/v1/analytics/fleet/fuel` | Fuel consumption per vehicle/route |
| `GET /api/v1/analytics/fleet/geofence-visits` | Visit frequency and dwell time per zone |
| `GET /api/v1/analytics/fleet/compliance` | Fleet-wide driving hours compliance % |

---

## 5. Infrastructure Changes

### 5.1 Docker Compose Additions

```yaml
# Added to existing docker-compose.yml

traccar:
  image: traccar/traccar:6-alpine
  ports:
    - "8082:8082"    # Traccar web UI (dev only)
    - "5055:5055"    # Teltonika protocol port (TCP/UDP)
  volumes:
    - ./config/traccar.xml:/opt/traccar/conf/traccar.xml
    - traccar-data:/opt/traccar/data
  depends_on:
    db:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8082/api/server"]
    interval: 30s
    timeout: 10s
    retries: 3

osrm:
  image: osrm/osrm-backend:v5.27.1
  ports:
    - "5000:5000"
  volumes:
    - ./data/osrm:/data
  command: osrm-routed --algorithm mld /data/latvia-latest.osrm
  # Requires pre-processing: download Latvia OSM extract, run osrm-extract + osrm-partition + osrm-customize
```

### 5.2 Traccar Configuration (`config/traccar.xml`)

```xml
<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE properties SYSTEM 'http://java.sun.com/dtd/properties.dtd'>
<properties>
    <!-- Use VTV's PostgreSQL -->
    <entry key='database.driver'>org.postgresql.Driver</entry>
    <entry key='database.url'>jdbc:postgresql://db:5432/vtv</entry>
    <entry key='database.user'>vtv</entry>
    <entry key='database.password'>${DB_PASSWORD}</entry>

    <!-- Enable Teltonika protocol on port 5055 -->
    <entry key='teltonika.port'>5055</entry>

    <!-- Forward events to VTV via webhook -->
    <entry key='forward.enable'>true</entry>
    <entry key='forward.url'>http://app:8123/api/v1/fleet/traccar/webhook</entry>
    <entry key='forward.json'>true</entry>

    <!-- Disable Traccar's built-in web UI in production -->
    <entry key='web.port'>8082</entry>
</properties>
```

### 5.3 Database Migrations

```
alembic/versions/
├── xxxx_add_fleet_device_table.py           # TrackedDevice model
├── xxxx_add_source_to_vehicle_positions.py  # source, device_id, OBD columns
├── xxxx_add_geofence_tables.py              # Geofence (PostGIS Polygon), GeofenceEvent
├── xxxx_add_tachograph_tables.py            # TachographCard, TachographFile, DriverActivity
├── xxxx_add_fuel_event_table.py             # FuelEvent model
├── xxxx_extend_vehicles_for_fleet.py        # tank_capacity_liters, tachograph_equipped
└── xxxx_extend_drivers_for_tachograph.py    # tachograph_card_number
```

---

## 6. Phase Breakdown

### Phase 1: GPS Telemetry + Live Tracking (Weeks 1-6) — MVP

**Goal:** Vehicles tracked via Teltonika hardware appear on VTV's live map alongside GTFS-RT vehicles.

| # | Task | Slice | Est | Depends |
|---|------|-------|-----|---------|
| 1.1 | Add Traccar to docker-compose.yml with Teltonika protocol enabled | infra | 1d | — |
| 1.2 | Create `config/traccar.xml` with PostgreSQL + webhook forwarding | infra | 1d | 1.1 |
| 1.3 | Create `app/fleet/` vertical slice scaffold (schemas, models, repository, service, routes, tests) | `fleet/` | 1d | — |
| 1.4 | TrackedDevice model + migration | `fleet/` | 1d | 1.3 |
| 1.5 | Add `source`, `device_id`, OBD columns to `vehicle_positions` + migration | migration | 1d | — |
| 1.6 | Traccar event bridge (`traccar_bridge.py`) — consume webhook events, normalize to VTV position format | `fleet/` | 3d | 1.2, 1.5 |
| 1.7 | Write normalized positions to TimescaleDB + Redis (same dual-write as GTFS-RT poller) | `fleet/` | 2d | 1.6 |
| 1.8 | Broadcast fleet positions via existing WebSocket Pub/Sub | `fleet/` | 1d | 1.7 |
| 1.9 | Device management REST endpoints (CRUD, status, telemetry) | `fleet/` | 2d | 1.4 |
| 1.10 | OBD-II/CAN parameter parsing from Teltonika AVL data (speed, RPM, fuel, odometer) | `fleet/` | 3d | 1.6 |
| 1.11 | Create `app/geofences/` vertical slice scaffold | `geofences/` | 1d | — |
| 1.12 | Geofence model with PostGIS Polygon + migration | `geofences/` | 1d | 1.11 |
| 1.13 | Geofence CRUD endpoints (create/edit zones with GeoJSON) | `geofences/` | 2d | 1.12 |
| 1.14 | Geofence evaluator — background task checking positions against zones | `geofences/` | 3d | 1.12, 1.7 |
| 1.15 | GeofenceEvent model + entry/exit event logging | `geofences/` | 2d | 1.14 |
| 1.16 | Integrate geofence alerts with existing alerts module | `alerts/` | 1d | 1.15 |
| 1.17 | CMS: Fleet devices management page | `cms/` | 3d | 1.9 |
| 1.18 | CMS: Extend live map to show fleet vehicles (distinct markers for GTFS-RT vs Traccar) | `cms/` | 2d | 1.8 |
| 1.19 | CMS: Geofence management page (draw/edit polygons on map) | `cms/` | 3d | 1.13 |
| 1.20 | CMS: Vehicle telemetry panel (OBD gauges: speed, RPM, fuel, temp) | `cms/` | 2d | 1.10 |
| 1.21 | Unit tests for all Phase 1 features (~60 tests target) | all | 3d | all |

**Phase 1 total: ~34 person-days (~7 weeks at 5d/week)**

### Phase 2: Fuel + Analytics + LocShare (Weeks 7-10)

**Goal:** Fuel monitoring, fleet analytics, public sharing links.

| # | Task | Slice | Est | Depends |
|---|------|-------|-----|---------|
| 2.1 | FuelEvent model + migration | `fleet/` | 1d | P1 |
| 2.2 | Fuel monitoring algorithm (refueling/drain detection from OBD fuel level changes) | `fleet/` | 3d | 2.1 |
| 2.3 | Fuel consumption analytics (per km, per route, per vehicle) | `analytics/` | 2d | 2.2 |
| 2.4 | Fleet distance/drive time analytics (aggregate from vehicle_positions) | `analytics/` | 2d | P1 |
| 2.5 | Idle time detection and reporting | `analytics/` | 1d | P1 |
| 2.6 | Geofence dwell time reports (LocPoints equivalent) | `geofences/` | 2d | P1 |
| 2.7 | LocShare — JWT-based expiring public tracking links | `fleet/` | 2d | P1 |
| 2.8 | Report export (PDF/CSV) for analytics | `analytics/` | 3d | 2.3, 2.4 |
| 2.9 | Speed alert rule type in alerts evaluator | `alerts/` | 1d | P1 |
| 2.10 | Device offline alert rule type | `alerts/` | 1d | P1 |
| 2.11 | CMS: Fuel monitoring dashboard | `cms/` | 3d | 2.2, 2.3 |
| 2.12 | CMS: Fleet analytics pages (distance, drive time, reports) | `cms/` | 3d | 2.4, 2.8 |
| 2.13 | CMS: LocShare management + public share page | `cms/` | 2d | 2.7 |
| 2.14 | Unit tests for Phase 2 (~40 tests target) | all | 2d | all |

**Phase 2 total: ~27 person-days (~5.5 weeks)**

### Phase 3: Tachograph + Driving Hours Compliance (Weeks 11-15)

**Goal:** Remote tachograph data download, EU 561/2006 compliance tracking, driver hours dashboard.

| # | Task | Slice | Est | Depends |
|---|------|-------|-----|---------|
| 3.1 | Create `app/tachograph/` vertical slice scaffold | `tachograph/` | 1d | — |
| 3.2 | TachographCard, TachographFile, DriverActivity models + migration | `tachograph/` | 2d | 3.1 |
| 3.3 | DDD file binary parser (`ddd_parser.py`) — extract activities from tachograph data | `tachograph/` | 5d | 3.2 |
| 3.4 | Manual DDD file upload endpoint with parsing | `tachograph/` | 2d | 3.3 |
| 3.5 | Teltonika Web Tacho / flespi integration for remote DDD download | `tachograph/` | 5d | 3.2 |
| 3.6 | EU 561/2006 driving hours calculator (`hours_calculator.py`) | `tachograph/` | 4d | 3.3 |
| 3.7 | Compliance status endpoints (per-driver, fleet overview) | `tachograph/` | 2d | 3.6 |
| 3.8 | Driving hours warning/critical alerts integration | `alerts/` | 2d | 3.6 |
| 3.9 | Infringement detection and logging | `tachograph/` | 2d | 3.6 |
| 3.10 | Extend driver model with tachograph_card_number | `drivers/` | 1d | 3.2 |
| 3.11 | CMS: Tachograph dashboard (driver hours table, compliance % bars) | `cms/` | 3d | 3.7 |
| 3.12 | CMS: Driver activity timeline view | `cms/` | 2d | 3.7 |
| 3.13 | CMS: DDD file management page (upload, download history) | `cms/` | 2d | 3.4, 3.5 |
| 3.14 | CMS: Infringement/violation reports | `cms/` | 2d | 3.9 |
| 3.15 | Unit tests for Phase 3 (~50 tests target) | all | 3d | all |

**Phase 3 total: ~36 person-days (~7 weeks)**

### Phase 4: Routing + Maps Fallback (Weeks 16-18)

**Goal:** Self-hosted routing with HERE fallback for truck-aware navigation.

| # | Task | Slice | Est | Depends |
|---|------|-------|-----|---------|
| 4.1 | Download Latvia OSM extract, pre-process for OSRM | infra | 1d | — |
| 4.2 | Add OSRM to docker-compose.yml | infra | 1d | 4.1 |
| 4.3 | Routing service with OSRM primary + HERE fallback | `fleet/` | 3d | 4.2 |
| 4.4 | HERE Fleet Telematics API integration (geocoding, routing) | `fleet/` | 2d | — |
| 4.5 | Route optimization for service vehicles (non-fixed routes) | `fleet/` | 3d | 4.3 |
| 4.6 | CMS: Route planning UI with map waypoints | `cms/` | 4d | 4.3 |
| 4.7 | Unit tests | all | 1d | all |

**Phase 4 total: ~15 person-days (~3 weeks)**

### Phase 5: Driver Mobile App + Messaging (Weeks 19-24)

**Goal:** Driver-facing mobile app with dispatcher messaging and task assignment.

| # | Task | Slice | Est | Depends |
|---|------|-------|-----|---------|
| 5.1 | Create `app/messaging/` vertical slice | `messaging/` | 1d | — |
| 5.2 | Message and Conversation models | `messaging/` | 1d | 5.1 |
| 5.3 | Dispatcher↔driver messaging endpoints (send, list, mark read) | `messaging/` | 3d | 5.2 |
| 5.4 | Task assignment system (create, assign, complete, cancel) | `messaging/` | 3d | 5.2 |
| 5.5 | WebSocket channel for real-time message delivery | `messaging/` | 2d | 5.3 |
| 5.6 | Push notification service (FCM/APNs) | `messaging/` | 2d | 5.3 |
| 5.7 | React Native mobile app — live map | `mobile/` | 5d | P1 |
| 5.8 | Mobile app — alerts and notifications | `mobile/` | 3d | 5.6 |
| 5.9 | Mobile app — messaging UI | `mobile/` | 3d | 5.5 |
| 5.10 | Mobile app — task management UI | `mobile/` | 3d | 5.4 |
| 5.11 | Unit tests | all | 2d | all |

**Phase 5 total: ~28 person-days (~6 weeks)**

---

## 7. Total Effort Summary

| Phase | Description | Est (days) | Est (weeks) |
|-------|-------------|------------|-------------|
| 1 | GPS Telemetry + Live Tracking (MVP) | 34 | 7 |
| 2 | Fuel + Analytics + LocShare | 27 | 5.5 |
| 3 | Tachograph + Driving Hours | 36 | 7 |
| 4 | Routing + Maps Fallback | 15 | 3 |
| 5 | Driver Mobile App + Messaging | 28 | 6 |
| **Total** | | **140** | **~28 weeks** |

---

## 8. Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| GPS protocol gateway | Traccar (Docker sidecar) | 200+ protocols, battle-tested, avoid re-implementing Codec 8/8E |
| Position storage | Shared `vehicle_positions` hypertable | Single table with `source` column, shared compression/retention |
| Geofence storage | PostGIS Polygon with GIST index | Already using PostGIS for stops, consistent spatial stack |
| Routing (primary) | OSRM self-hosted | Free, fast, Latvia OSM extract ~50MB |
| Routing (fallback) | HERE Fleet Telematics API | Truck-aware routing, toll costs, 250K free/month |
| Tachograph download | Teltonika Web Tacho + flespi fallback | Primary: Teltonika native. Fallback: flespi for wider device support |
| DDD file parsing | Custom Python parser | Open DDD format spec available, no good Python libraries exist |
| Real-time transport | Redis Pub/Sub + WebSocket (existing) | Already proven at VTV scale, sufficient for 300-700 vehicles |
| Mobile app | React Native | Shared TypeScript ecosystem with CMS, single codebase iOS+Android |
| Fuel detection | Custom algorithm | No standard library; detect sudden level changes with configurable thresholds |

---

## 9. Open Questions & Future Considerations

- [ ] **Hardware procurement** — When to order Teltonika test devices? (FMB920 for basic, FMB640 for tachograph)
- [ ] **Traccar vs direct** — Re-evaluate after Phase 1 if Traccar webhook latency is acceptable (<500ms)
- [ ] **Multi-tenancy** — Not needed for RS-only, but consider if expanding to other operators
- [ ] **Toll calculation** — Deferred. HERE Toll Cost API available when needed
- [ ] **Refrigeration monitoring** — Deferred. Requires Carrier/Thermo King OEM partnership
- [ ] **SIM management** — Who provides SIM cards for Teltonika devices? RS or VTV?
- [ ] **Data retention** — 90-day retention (matching GDPR policy) or longer for fleet analytics?
- [ ] **Monetization** — Per-vehicle SaaS, license, or included in RS contract?
