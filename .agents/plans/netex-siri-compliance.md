# Plan: NeTEx/SIRI Compliance Exports

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: schedules, stops, transit, core/config

## Feature Description

NeTEx (Network Timetable Exchange) and SIRI (Service Interface for Real-time Information) are
mandatory CEN European standards for transit data exchange under EU MMTIS Delegated Regulation
2017/1926 (amended by 2024/490). Latvia must publish transit data to its National Access Point
(data.gov.lv) in these formats.

This feature adds a new `compliance` vertical slice that transforms existing VTV data (agencies,
routes, stops, calendars, trips, stop times, real-time vehicle positions) into standards-compliant
XML documents. It produces three export types:

1. **NeTEx Static Export** — A `PublicationDelivery` XML document containing four frames
   (ResourceFrame, SiteFrame, ServiceFrame, TimetableFrame) conforming to the European Passenger
   Information Profile (EPIP). This covers operators, stop places, lines, routes, journey patterns,
   service journeys, and operating calendars.

2. **SIRI-VM (Vehicle Monitoring)** — An XML endpoint returning real-time vehicle positions as
   `VehicleActivity` elements within a `ServiceDelivery` wrapper, fed from the existing Redis-cached
   GTFS-RT data.

3. **SIRI-SM (Stop Monitoring)** — An XML endpoint returning predicted arrivals/departures at a
   specific stop as `MonitoredStopVisit` elements, also sourced from GTFS-RT trip update data.

All exports reuse existing database queries (via ScheduleRepository, StopRepository) and existing
real-time data (via TransitService). No new database tables are required — this is a pure
transformation layer.

## User Story

As a transit administrator
I want to export schedule and real-time data in NeTEx and SIRI XML formats
So that VTV complies with EU MMTIS regulation and can publish data to Latvia's National Access Point

## Solution Approach

We follow the exact same export architecture as the existing GTFS exporter: the service layer
gathers data from repositories, passes it to a dedicated exporter class, and the exporter returns
bytes that the route handler streams as a response.

**Approach Decision:**
We chose `lxml` for XML generation because:
- Mature C-based library with proper XML namespace support (essential for NeTEx/SIRI)
- Handles large documents efficiently via `lxml.etree.SubElement` tree building
- Supports pretty-printing and XML declaration headers required by validators
- Already used extensively in Python transit industry (PyNeTExConv, Entur tools)

**Alternatives Considered:**
- `xsdata` (schema-to-dataclass codegen): Rejected because it requires generating ~500+ Python
  dataclasses from the full NeTEx XSD schema. Over-engineered for export-only (we only write XML,
  never parse NeTEx input). Adds a large maintenance burden for schema updates.
- `xml.etree.ElementTree` (stdlib): Rejected because it has poor namespace handling, no
  pretty-printing, and incomplete XML declaration support.

**Architecture:**
- New vertical slice: `app/compliance/` with schemas, service, routes, exporters, tests
- NeTEx exporter: `netex_export.py` — pure-function XML builder, no DB access
- SIRI-VM builder: `siri_vm.py` — transforms VehiclePosition data to SIRI XML
- SIRI-SM builder: `siri_sm.py` — transforms trip update data to SIRI XML
- Service layer: orchestrates data gathering from schedules/stops/transit repos
- Config: codespace ID and participant ref added to Settings

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/schedules/gtfs_export.py` (lines 1-228) — **Primary pattern reference.** Shows how to build
  an exporter class that takes model lists, builds lookup maps, and returns bytes. The NeTEx exporter
  follows this same constructor/export pattern.
- `app/schedules/service.py` (lines 835-881) — Shows the export_gtfs flow: gather all entities →
  create exporter → return bytes. The compliance service mirrors this pattern.
- `app/schedules/routes.py` (lines 344-359) — Shows the export endpoint pattern: rate-limited,
  auth-required, returns `Response(content=bytes, media_type=...)`.

### Similar Features (Examples to Follow)
- `app/schedules/models.py` (lines 1-138) — All GTFS entity models. NeTEx export reads these same
  models and transforms them to XML elements.
- `app/stops/models.py` (lines 16-42) — Stop model with PostGIS geom, location_type,
  wheelchair_boarding. Maps to NeTEx `StopPlace` and `ScheduledStopPoint`.
- `app/transit/schemas.py` (lines 12-48) — VehiclePosition schema. Maps to SIRI-VM
  `MonitoredVehicleJourney` elements.
- `app/transit/service.py` (lines 46-77) — Shows how to get vehicle positions from Redis/direct.
  SIRI-VM reuses this data.
- `app/core/exceptions.py` (lines 14-29) — AppError hierarchy for domain exceptions.
- `app/schedules/repository.py` (lines 627-669) — `list_all_*` methods for unpaginated export data.

### Files to Modify
- `app/main.py` — Register compliance_router
- `app/core/config.py` — Add codespace and participant_ref settings
- `pyproject.toml` — Add `lxml` dependency

## Research Documentation

- [NeTEx CEN GitHub](https://github.com/NeTEx-CEN/NeTEx) — XSD schemas and examples
- [NeTEx EPIP Profile](https://github.com/NeTEx-CEN/NeTEx-Profile-EPIP) — EU minimum profile spec
- [SIRI CEN GitHub](https://github.com/SIRI-CEN/SIRI) — SIRI XSD schemas
- [Entur Nordic Profile Examples](https://github.com/entur/profile-examples) — Real NeTEx XML samples
- [EU MMTIS Regulation](https://eur-lex.europa.eu/eli/reg_del/2017/1926/oj/eng) — Legal requirements
- [lxml.etree docs](https://lxml.de/tutorial.html) — XML tree building API

## Implementation Plan

### Phase 1: Foundation
Add `lxml` dependency. Create compliance module skeleton with Pydantic schemas for config and
response metadata. Add codespace/participant settings to core config.

### Phase 2: NeTEx Static Export
Build the NeTEx exporter class that transforms GTFS entities into a `PublicationDelivery` XML
document with four frames. This is the largest component.

### Phase 3: SIRI Real-time Exports
Build SIRI-VM (vehicle monitoring) and SIRI-SM (stop monitoring) XML builders that transform
existing real-time data into SIRI ServiceDelivery documents.

### Phase 4: Service & Routes
Create the compliance service that orchestrates data gathering and the FastAPI routes that expose
the three export endpoints. Register router in main.py.

### Phase 5: Testing & Validation
Unit tests for XML structure, namespace correctness, and data mapping. Integration tests for
endpoint responses.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Add lxml dependency
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Add `lxml` with type stubs to dependencies:
- Add `"lxml>=5.0.0"` to the `[project] dependencies` list
- Add `"lxml-stubs>=0.5.0"` to the `[dependency-groups] dev` list
- Add a mypy overrides section for lxml if needed (lxml-stubs provides types)

Run after editing:
```bash
uv sync
```

**Per-task validation:**
- `uv run python -c "import lxml; print(lxml.__version__)"` prints version
- `uv run ruff format pyproject.toml`
- `uv run ruff check --fix pyproject.toml`

---

### Task 2: Add compliance config settings
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add two new fields to the `Settings` class (place them after the existing transit config block):
```python
# --- NeTEx/SIRI compliance ---
netex_codespace: str = "VTV"
netex_participant_ref: str = "VTV"
```

The codespace is a unique namespace prefix for all NeTEx IDs (e.g., `VTV:StopPlace:12345`).
The participant_ref identifies this system in SIRI ServiceDelivery responses.

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py`
- `uv run mypy app/core/config.py`

---

### Task 3: Create compliance module skeleton
**File:** `app/compliance/__init__.py` (create new)
**Action:** CREATE

Create empty `__init__.py`.

**File:** `app/compliance/tests/__init__.py` (create new)
**Action:** CREATE

Create empty `__init__.py`.

**Per-task validation:**
- Files exist: `ls app/compliance/__init__.py app/compliance/tests/__init__.py`

---

### Task 4: Create compliance exceptions
**File:** `app/compliance/exceptions.py` (create new)
**Action:** CREATE

Define domain exceptions following the pattern in `app/schedules/exceptions.py`:
- `ComplianceError(AppError)` — base for all compliance errors (500)
- `ComplianceExportError(ComplianceError)` — XML generation failures
- `ComplianceValidationError(DomainValidationError)` — invalid parameters (422)

Import `AppError` and `DomainValidationError` from `app.core.exceptions`.

**Per-task validation:**
- `uv run ruff format app/compliance/exceptions.py`
- `uv run ruff check --fix app/compliance/exceptions.py`
- `uv run mypy app/compliance/exceptions.py`

---

### Task 5: Create compliance schemas
**File:** `app/compliance/schemas.py` (create new)
**Action:** CREATE

Define Pydantic response schemas:

```python
from pydantic import BaseModel, ConfigDict

class ExportMetadata(BaseModel):
    """Metadata returned alongside XML export responses."""
    model_config = ConfigDict(strict=True)

    format: str          # "NeTEx" | "SIRI-VM" | "SIRI-SM"
    version: str         # e.g. "1.2" for NeTEx EPIP, "2.0" for SIRI
    codespace: str       # e.g. "VTV"
    generated_at: str    # ISO 8601 timestamp
    entity_counts: dict[str, int]  # e.g. {"operators": 2, "stop_places": 150, ...}
```

Keep schemas minimal — the actual export is XML bytes, not JSON. This schema is only used for
the `/compliance/status` health-check endpoint.

**Per-task validation:**
- `uv run ruff format app/compliance/schemas.py`
- `uv run ruff check --fix app/compliance/schemas.py`
- `uv run mypy app/compliance/schemas.py`

---

### Task 6: Create NeTEx XML namespace constants
**File:** `app/compliance/xml_namespaces.py` (create new)
**Action:** CREATE

Define XML namespace constants shared across all exporters:

```python
"""XML namespace constants for NeTEx and SIRI documents."""

# NeTEx namespace (used in PublicationDelivery and all frames)
NETEX_NS = "http://www.netex.org.uk/netex"

# SIRI namespace (used in ServiceDelivery)
SIRI_NS = "http://www.siri.org.uk/siri"

# GML namespace (used for geographic elements)
GML_NS = "http://www.opengis.net/gml/3.2"

# XSI namespace (for schema instance attributes)
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

# Namespace maps for lxml
NETEX_NSMAP: dict[str | None, str] = {
    None: NETEX_NS,
    "gml": GML_NS,
    "xsi": XSI_NS,
}

SIRI_NSMAP: dict[str | None, str] = {
    None: SIRI_NS,
}
```

**Per-task validation:**
- `uv run ruff format app/compliance/xml_namespaces.py`
- `uv run ruff check --fix app/compliance/xml_namespaces.py`
- `uv run mypy app/compliance/xml_namespaces.py`

---

### Task 7: Create NeTEx exporter — ResourceFrame and SiteFrame
**File:** `app/compliance/netex_export.py` (create new)
**Action:** CREATE

Create `NeTExExporter` class following the exact same pattern as `app/schedules/gtfs_export.py`:

**Constructor** takes the same model lists as GTFSExporter:
```python
def __init__(
    self,
    *,
    agencies: list[Agency],
    routes: list[Route],
    calendars: list[Calendar],
    calendar_dates: list[CalendarDate],
    trips: list[Trip],
    stop_times: list[StopTime],
    stops: list[Stop],
    codespace: str,
) -> None:
```

Build the same `_agency_gtfs`, `_route_gtfs`, etc. lookup maps as GTFSExporter (lines 58-62).

**`export()` method** returns `bytes` containing a complete `PublicationDelivery` XML document:
```python
def export(self) -> bytes:
    root = self._build_publication_delivery()
    return lxml.etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
```

**`_build_publication_delivery()`** creates the root XML structure:
```xml
<PublicationDelivery xmlns="http://www.netex.org.uk/netex" version="1.2">
  <PublicationTimestamp>2026-03-03T12:00:00Z</PublicationTimestamp>
  <ParticipantRef>VTV</ParticipantRef>
  <dataObjects>
    <CompositeFrame id="VTV:CompositeFrame:main" version="1">
      <frames>
        <ResourceFrame>...</ResourceFrame>
        <SiteFrame>...</SiteFrame>
        <ServiceFrame>...</ServiceFrame>
        <TimetableFrame>...</TimetableFrame>
      </frames>
    </CompositeFrame>
  </dataObjects>
</PublicationDelivery>
```

**`_build_resource_frame()`** maps Agency → NeTEx Operator:
- Each Agency becomes an `<Operator>` element with `id="VTV:Operator:{gtfs_agency_id}"`
- Fields: `<Name>`, `<ContactDetails><Url>`, `<Locale><DefaultLanguage>`

**`_build_site_frame()`** maps Stop → NeTEx StopPlace + ScheduledStopPoint:
- Each Stop with `location_type=1` (terminus/station) becomes a `<StopPlace>` with `<Centroid>`
  containing `<Location><Longitude>` and `<Latitude>` in GML namespace
- Each Stop with `location_type=0` becomes a `<ScheduledStopPoint>` with `<Location>`
- `wheelchair_boarding` maps to `<AccessibilityAssessment><MobilityImpairedAccess>`
- Stop names and descriptions preserved as `<Name>` and `<Description>`

All NeTEx element IDs use the format `{codespace}:{ElementType}:{gtfs_id}`.

Use `lxml.etree.Element`, `SubElement`, and the namespace maps from `xml_namespaces.py`.

Add structured logging:
- `logger.info("compliance.netex.export_started", stop_count=len(stops), ...)`

**Per-task validation:**
- `uv run ruff format app/compliance/netex_export.py`
- `uv run ruff check --fix app/compliance/netex_export.py`
- `uv run mypy app/compliance/netex_export.py`
- `uv run pyright app/compliance/netex_export.py`

---

### Task 8: Add NeTEx exporter — ServiceFrame and TimetableFrame
**File:** `app/compliance/netex_export.py` (modify existing)
**Action:** UPDATE

Add the remaining two frame builders to the NeTExExporter class:

**`_build_service_frame()`** maps Routes and Calendars:
- Each Route becomes a `<Line>` element with `id="VTV:Line:{gtfs_route_id}"`
  - `<Name>` from `route_long_name`, `<ShortName>` from `route_short_name`
  - `<TransportMode>` mapped from GTFS `route_type` (3→bus, 0→tram, 11→trolleybus, etc.)
  - `<Presentation><Colour>` from `route_color`, `<TextColour>` from `route_text_color`
  - `<OperatorRef>` referencing the agency
- Each Calendar becomes a `<DayType>` with `<PropertyOfDay><DaysOfWeek>`
  - Map boolean day fields to NeTEx day abbreviations (Monday, Tuesday, etc.)
  - `<OperatingPeriod>` with `<FromDate>` and `<ToDate>` from calendar date range
- CalendarDates become `<DayTypeAssignment>` elements within an `<OperatingDay>` structure

**`_build_timetable_frame()`** maps Trips and StopTimes:
- Each Trip becomes a `<ServiceJourney>` with `id="VTV:ServiceJourney:{gtfs_trip_id}"`
  - `<LineRef>` referencing the route's Line
  - `<DayTypeRef>` referencing the calendar's DayType
  - `<DirectionType>` from `direction_id` (0→outbound, 1→inbound)
  - `<DestinationDisplayRef>` from `trip_headsign`
- StopTimes become `<Call>` elements (children of the parent ServiceJourney's `<calls>` list):
  - `<ScheduledStopPointRef>` referencing the stop
  - `<Arrival><Time>` and `<Departure><Time>` — convert GTFS HH:MM:SS to ISO time
  - `<Order>` from `stop_sequence`
  - `<RequestStop>` derived from `pickup_type`/`drop_off_type`

Group stop_times by trip_id before building to avoid repeated lookups.

Helper method `_gtfs_route_type_to_netex(route_type: int) -> str` mapping:
- 0 → "tram", 1 → "metro", 2 → "rail", 3 → "bus", 4 → "water",
  5 → "cableway", 6 → "gondola", 7 → "funicular", 11 → "trolleyBus", 12 → "monorail"
- Default → "bus"

Helper method `_gtfs_time_to_iso(time_str: str) -> str`:
- Input: "08:30:00" → Output: "08:30:00"
- Input: "25:10:00" → Output: "25:10:00" (NeTEx supports >24h times in ServiceJourney)

**Per-task validation:**
- `uv run ruff format app/compliance/netex_export.py`
- `uv run ruff check --fix app/compliance/netex_export.py`
- `uv run mypy app/compliance/netex_export.py`
- `uv run pyright app/compliance/netex_export.py`

---

### Task 9: Create SIRI-VM builder
**File:** `app/compliance/siri_vm.py` (create new)
**Action:** CREATE

Create `SiriVehicleMonitoringBuilder` class that transforms `VehiclePosition` objects (from
`app.transit.schemas`) into a SIRI-VM `ServiceDelivery` XML document.

**Constructor:**
```python
def __init__(self, *, participant_ref: str) -> None:
```

**`build(vehicles: list[VehiclePosition], response_timestamp: str) -> bytes`:**

Produces XML:
```xml
<Siri xmlns="http://www.siri.org.uk/siri" version="2.0">
  <ServiceDelivery>
    <ResponseTimestamp>2026-03-03T12:00:00Z</ResponseTimestamp>
    <ProducerRef>VTV</ProducerRef>
    <VehicleMonitoringDelivery version="2.0">
      <ResponseTimestamp>...</ResponseTimestamp>
      <VehicleActivity>
        <RecordedAtTime>...</RecordedAtTime>
        <MonitoredVehicleJourney>
          <LineRef>route_id</LineRef>
          <PublishedLineName>route_short_name</PublishedLineName>
          <VehicleRef>vehicle_id</VehicleRef>
          <VehicleLocation>
            <Longitude>lon</Longitude>
            <Latitude>lat</Latitude>
          </VehicleLocation>
          <Bearing>bearing</Bearing>
          <Delay>PT{delay_seconds}S</Delay>
          <MonitoredCall>
            <StopPointName>next_stop_name</StopPointName>
          </MonitoredCall>
        </MonitoredVehicleJourney>
      </VehicleActivity>
      ...
    </VehicleMonitoringDelivery>
  </ServiceDelivery>
</Siri>
```

Map VehiclePosition fields:
- `delay_seconds` → ISO 8601 duration `PT{abs(seconds)}S` (prefix with `-` if early)
- `timestamp` → `<RecordedAtTime>`
- `current_status` → `<ProgressBetweenStops><LinkDistance>` (optional, skip if not applicable)
- Only include `<Bearing>` and `<MonitoredCall>` when values are non-None

Add `from app.core.logging import get_logger` and log `compliance.siri_vm.build_started/completed`.

**Per-task validation:**
- `uv run ruff format app/compliance/siri_vm.py`
- `uv run ruff check --fix app/compliance/siri_vm.py`
- `uv run mypy app/compliance/siri_vm.py`
- `uv run pyright app/compliance/siri_vm.py`

---

### Task 10: Create SIRI-SM builder
**File:** `app/compliance/siri_sm.py` (create new)
**Action:** CREATE

Create `SiriStopMonitoringBuilder` class that builds SIRI-SM XML from vehicle positions filtered
to a specific stop.

**Constructor:**
```python
def __init__(self, *, participant_ref: str) -> None:
```

**`build(stop_name: str, vehicles: list[VehiclePosition], response_timestamp: str) -> bytes`:**

Filter `vehicles` to those whose `next_stop_name` or `current_stop_name` matches `stop_name`.

Produces XML:
```xml
<Siri xmlns="http://www.siri.org.uk/siri" version="2.0">
  <ServiceDelivery>
    <ResponseTimestamp>...</ResponseTimestamp>
    <ProducerRef>VTV</ProducerRef>
    <StopMonitoringDelivery version="2.0">
      <ResponseTimestamp>...</ResponseTimestamp>
      <MonitoringRef>stop_name</MonitoringRef>
      <MonitoredStopVisit>
        <RecordedAtTime>...</RecordedAtTime>
        <MonitoredVehicleJourney>
          <LineRef>route_id</LineRef>
          <PublishedLineName>route_short_name</PublishedLineName>
          <VehicleRef>vehicle_id</VehicleRef>
          <MonitoredCall>
            <StopPointName>stop_name</StopPointName>
            <ExpectedArrivalTime>...</ExpectedArrivalTime>
          </MonitoredCall>
        </MonitoredVehicleJourney>
      </MonitoredStopVisit>
      ...
    </StopMonitoringDelivery>
  </ServiceDelivery>
</Siri>
```

Add logging: `compliance.siri_sm.build_started/completed`.

**Per-task validation:**
- `uv run ruff format app/compliance/siri_sm.py`
- `uv run ruff check --fix app/compliance/siri_sm.py`
- `uv run mypy app/compliance/siri_sm.py`
- `uv run pyright app/compliance/siri_sm.py`

---

### Task 11: Create compliance service
**File:** `app/compliance/service.py` (create new)
**Action:** CREATE

Create `ComplianceService` that orchestrates data gathering and XML generation. Follow the pattern
of `app/schedules/service.py` lines 835-881 (export_gtfs method).

**Constructor takes:**
```python
def __init__(self, db: AsyncSession, settings: Settings) -> None:
```

**`async def export_netex(self, agency_id: int | None = None) -> bytes`:**
1. Create `ScheduleRepository(self._db)` and `StopRepository(self._db)`
2. Fetch all data using `list_all_*` methods (mirror service.py lines 846-861)
3. If `agency_id` provided, filter routes by agency
4. Create `NeTExExporter(agencies=..., routes=..., ..., codespace=settings.netex_codespace)`
5. Return `exporter.export()`
6. Log `compliance.netex.export_started/completed` with entity counts and duration

**`async def get_siri_vm(self, route_id: str | None = None, feed_id: str | None = None) -> bytes`:**
1. Create `TransitService` (import from `app.transit.service`)
2. Call `transit_service.get_vehicle_positions(route_id, feed_id)`
3. Create `SiriVehicleMonitoringBuilder(participant_ref=settings.netex_participant_ref)`
4. Return `builder.build(vehicles=response.vehicles, response_timestamp=response.fetched_at)`

**`async def get_siri_sm(self, stop_name: str, feed_id: str | None = None) -> bytes`:**
1. Get all vehicle positions via `TransitService`
2. Create `SiriStopMonitoringBuilder(participant_ref=settings.netex_participant_ref)`
3. Return `builder.build(stop_name=stop_name, vehicles=response.vehicles, ...)`

**`async def get_export_status(self) -> ExportMetadata`:**
1. Count entities from repos (agencies, routes, stops, trips)
2. Return `ExportMetadata` with counts and timestamp

Import `get_logger` from `app.core.logging` and add structured logging to each method.

**Per-task validation:**
- `uv run ruff format app/compliance/service.py`
- `uv run ruff check --fix app/compliance/service.py`
- `uv run mypy app/compliance/service.py`
- `uv run pyright app/compliance/service.py`

---

### Task 12: Create compliance routes
**File:** `app/compliance/routes.py` (create new)
**Action:** CREATE

Create FastAPI router with 4 endpoints following the pattern of `app/schedules/routes.py`
lines 344-359:

```python
router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])
```

**Endpoints:**

1. `GET /api/v1/compliance/netex` — Export NeTEx XML
   - Query param: `agency_id: int | None = None`
   - Rate limit: `3/minute` (NeTEx generation is heavier than GTFS)
   - Auth: `get_current_user` (any authenticated user)
   - Returns: `Response(content=xml_bytes, media_type="application/xml",
     headers={"Content-Disposition": "attachment; filename=netex.xml"})`

2. `GET /api/v1/compliance/siri/vm` — SIRI Vehicle Monitoring
   - Query params: `route_id: str | None = None`, `feed_id: str | None = None`
   - Rate limit: `10/minute` (lighter, real-time data)
   - Auth: `get_current_user`
   - Returns: `Response(content=xml_bytes, media_type="application/xml")`

3. `GET /api/v1/compliance/siri/sm` — SIRI Stop Monitoring
   - Query param: `stop_name: str` (required)
   - Rate limit: `10/minute`
   - Auth: `get_current_user`
   - Returns: `Response(content=xml_bytes, media_type="application/xml")`

4. `GET /api/v1/compliance/status` — Export status and entity counts
   - Rate limit: `30/minute`
   - Auth: `get_current_user`
   - Returns: `ExportMetadata` (JSON)

Each endpoint creates a `ComplianceService` instance using `Depends(get_db)` and
`Depends(get_current_user)`. Use the `slowapi` limiter (import from `app.core.rate_limit`).
Use `Request` param + `_ = request` pattern for slowapi (see anti-pattern rule 18).

Add pyright file-level directive: `# pyright: reportMissingTypeStubs=false` if lxml triggers stubs
warnings despite lxml-stubs.

**Per-task validation:**
- `uv run ruff format app/compliance/routes.py`
- `uv run ruff check --fix app/compliance/routes.py`
- `uv run mypy app/compliance/routes.py`
- `uv run pyright app/compliance/routes.py`

---

### Task 13: Register compliance router
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

Add import and router registration, following the existing pattern (e.g., vehicles_router on
line 47 and line 162):

```python
from app.compliance.routes import router as compliance_router
```

Add after the last `include_router()` call:
```python
app.include_router(compliance_router)
```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py`

---

### Task 14: Add mypy/pyright overrides for lxml if needed
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE (conditional)

Only if mypy or pyright reports errors about lxml types after installing lxml-stubs. If lxml-stubs
resolves all type issues, skip this task.

If needed, add:
```toml
[[tool.mypy.overrides]]
module = "lxml.*"
ignore_missing_imports = true
```

Also add `"app/compliance/routes.py" = ["ARG001"]` to `[tool.ruff.lint.per-file-ignores]` for
the slowapi Request parameter.

**Per-task validation:**
- `uv run ruff format pyproject.toml`
- `uv run mypy app/compliance/` passes with 0 errors
- `uv run pyright app/compliance/` passes with 0 errors

---

### Task 15: Create NeTEx export unit tests
**File:** `app/compliance/tests/test_netex_export.py` (create new)
**Action:** CREATE

Test the NeTEx exporter in isolation (no DB, no HTTP). Import the exporter and feed it model
instances directly (construct SQLAlchemy model objects in-memory).

**Test 1: Empty export produces valid XML**
```python
async def test_netex_export_empty():
    exporter = NeTExExporter(agencies=[], routes=[], ..., codespace="TEST")
    xml_bytes = exporter.export()
    root = lxml.etree.fromstring(xml_bytes)
    assert root.tag == "{http://www.netex.org.uk/netex}PublicationDelivery"
    assert root.get("version") == "1.2"
```

**Test 2: Agency maps to Operator**
- Create one Agency model instance
- Export, parse XML, find `<Operator>` element
- Assert `<Name>` matches agency_name

**Test 3: Stop maps to StopPlace**
- Create Stop with location_type=1 (station)
- Assert `<StopPlace>` contains `<Centroid><Location>` with correct lat/lon

**Test 4: Stop maps to ScheduledStopPoint**
- Create Stop with location_type=0
- Assert `<ScheduledStopPoint>` with correct ID format

**Test 5: Route maps to Line with correct TransportMode**
- Create Route with route_type=3 (bus)
- Assert `<Line>` contains `<TransportMode>bus</TransportMode>`

**Test 6: Trip maps to ServiceJourney with Calls**
- Create Trip with 3 StopTimes
- Assert `<ServiceJourney>` contains 3 `<Call>` elements with correct order

**Test 7: Full export with all entity types**
- Create one of each entity type with proper FK relationships
- Export and validate the complete XML structure

**Per-task validation:**
- `uv run ruff format app/compliance/tests/test_netex_export.py`
- `uv run ruff check --fix app/compliance/tests/test_netex_export.py`
- `uv run pytest app/compliance/tests/test_netex_export.py -v` — all tests pass

---

### Task 16: Create SIRI builder unit tests
**File:** `app/compliance/tests/test_siri.py` (create new)
**Action:** CREATE

Test SIRI-VM and SIRI-SM builders in isolation.

**Test 1: SIRI-VM empty produces valid XML**
```python
async def test_siri_vm_empty():
    builder = SiriVehicleMonitoringBuilder(participant_ref="TEST")
    xml_bytes = builder.build(vehicles=[], response_timestamp="2026-03-03T12:00:00Z")
    root = lxml.etree.fromstring(xml_bytes)
    assert root.tag == "{http://www.siri.org.uk/siri}Siri"
```

**Test 2: SIRI-VM vehicle maps to VehicleActivity**
- Create VehiclePosition with all fields populated
- Build, parse, find `<VehicleActivity>`
- Assert `<VehicleRef>`, `<LineRef>`, `<VehicleLocation>` present and correct

**Test 3: SIRI-VM delay formatting**
- Vehicle with delay_seconds=120 → `<Delay>PT120S</Delay>`
- Vehicle with delay_seconds=-30 → `<Delay>-PT30S</Delay>`

**Test 4: SIRI-VM optional fields omitted when None**
- Vehicle with bearing=None → no `<Bearing>` element

**Test 5: SIRI-SM filters by stop name**
- Create 3 vehicles, only 1 with matching next_stop_name
- Build with that stop_name, assert only 1 `<MonitoredStopVisit>`

**Test 6: SIRI-SM empty result when no vehicles at stop**
- Build with non-matching stop_name
- Assert `<StopMonitoringDelivery>` contains `<MonitoringRef>` but no visits

**Per-task validation:**
- `uv run ruff format app/compliance/tests/test_siri.py`
- `uv run ruff check --fix app/compliance/tests/test_siri.py`
- `uv run pytest app/compliance/tests/test_siri.py -v` — all tests pass

---

### Task 17: Create route endpoint tests
**File:** `app/compliance/tests/test_routes.py` (create new)
**Action:** CREATE

Test the FastAPI endpoints using `TestClient`. These are lightweight integration tests that mock
the service layer.

**Test 1: NeTEx export returns XML content type**
- Mock ComplianceService.export_netex to return sample XML bytes
- GET `/api/v1/compliance/netex` with auth header
- Assert status 200, content-type "application/xml"

**Test 2: SIRI-VM returns XML**
- Mock ComplianceService.get_siri_vm
- GET `/api/v1/compliance/siri/vm`
- Assert status 200, content-type "application/xml"

**Test 3: SIRI-SM requires stop_name parameter**
- GET `/api/v1/compliance/siri/sm` without stop_name
- Assert status 422 (missing required param)

**Test 4: Status endpoint returns JSON**
- Mock ComplianceService.get_export_status
- GET `/api/v1/compliance/status`
- Assert status 200, response contains entity_counts

**Test 5: Endpoints require authentication**
- GET each endpoint without auth header
- Assert status 401

Mark DB-dependent tests with `@pytest.mark.integration`. For unit route tests, mock the service
dependency using `app.dependency_overrides` with save/restore fixture (anti-pattern rule 56).

**Per-task validation:**
- `uv run ruff format app/compliance/tests/test_routes.py`
- `uv run ruff check --fix app/compliance/tests/test_routes.py`
- `uv run pytest app/compliance/tests/test_routes.py -v` — all tests pass

---

### Task 18: Create test conftest
**File:** `app/compliance/tests/conftest.py` (create new)
**Action:** CREATE

Create shared test fixtures:
- `sample_agency()` — returns an Agency model instance with test data
- `sample_route(agency)` — returns a Route linked to the agency
- `sample_stop()` — returns a Stop with location data
- `sample_calendar()` — returns a Calendar with weekday service
- `sample_trip(route, calendar)` — returns a Trip
- `sample_stop_time(trip, stop)` — returns a StopTime
- `sample_vehicle_position()` — returns a VehiclePosition schema instance

Each fixture creates in-memory model instances (no DB session needed). Set the `id` field
manually for FK resolution in tests.

**Per-task validation:**
- `uv run ruff format app/compliance/tests/conftest.py`
- `uv run ruff check --fix app/compliance/tests/conftest.py`
- `uv run pytest app/compliance/tests/ -v` — all tests still pass

---

## Migration

No database migration required. This feature is a pure transformation layer over existing data.

## Logging Events

- `compliance.netex.export_started` — When NeTEx export begins (includes entity counts)
- `compliance.netex.export_completed` — When NeTEx XML generation finishes (includes byte size, duration_ms)
- `compliance.netex.export_failed` — On XML generation errors (includes error, error_type)
- `compliance.siri_vm.build_started` — When SIRI-VM build begins (includes vehicle_count)
- `compliance.siri_vm.build_completed` — When SIRI-VM XML is ready (includes byte size, duration_ms)
- `compliance.siri_sm.build_started` — When SIRI-SM build begins (includes stop_name, vehicle_count)
- `compliance.siri_sm.build_completed` — When SIRI-SM XML is ready (includes visit_count, duration_ms)

## Testing Strategy

### Unit Tests
**Location:** `app/compliance/tests/`
- `test_netex_export.py` — NeTEx XML structure, namespace correctness, entity mapping, ID format
- `test_siri.py` — SIRI-VM and SIRI-SM XML structure, delay formatting, stop filtering
- `test_routes.py` — Endpoint responses, auth, content types, parameter validation

### Integration Tests
**Location:** `app/compliance/tests/test_routes.py`
**Mark with:** `@pytest.mark.integration`
- Full NeTEx export with real DB data (if Docker running)
- SIRI-VM with real Redis vehicle data (if available)

### Edge Cases
- Empty database (no agencies, routes, stops) — should produce valid but empty XML
- Agencies with no routes — ResourceFrame has operators but ServiceFrame is empty
- Stops with NULL lat/lon — omit `<Location>` element
- Vehicles with no delay data — `<Delay>` element omitted
- Routes with unknown route_type — default to "bus" TransportMode
- Times > 24:00 (GTFS allows, NeTEx supports in ServiceJourney context)

## Acceptance Criteria

This feature is complete when:
- [ ] `GET /api/v1/compliance/netex` returns valid NeTEx XML with PublicationDelivery root
- [ ] NeTEx XML contains ResourceFrame (Operators), SiteFrame (StopPlaces), ServiceFrame (Lines),
      TimetableFrame (ServiceJourneys)
- [ ] All NeTEx IDs use `{codespace}:{ElementType}:{id}` format
- [ ] `GET /api/v1/compliance/siri/vm` returns valid SIRI XML with VehicleActivity elements
- [ ] `GET /api/v1/compliance/siri/sm?stop_name=X` filters vehicles by stop and returns SIRI XML
- [ ] `GET /api/v1/compliance/status` returns JSON with entity counts
- [ ] All endpoints require authentication
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + integration)
- [ ] Structured logging follows `compliance.component.action_state` pattern
- [ ] No type suppressions added (except lxml-related if needed)
- [ ] Router registered in `app/main.py`
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 18 tasks completed in order
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
uv run pytest app/compliance/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings.

## Dependencies

- Shared utilities used: `get_logger()` from `app.core.logging`, `get_db()` from
  `app.core.database`, `AppError`/`DomainValidationError` from `app.core.exceptions`,
  `get_current_user` from `app.auth.dependencies`
- Core modules used: `app.core.config.Settings`, `app.core.rate_limit.limiter`
- Cross-feature reads: `ScheduleRepository` from `app.schedules.repository`,
  `StopRepository` from `app.stops.repository`, `TransitService` from `app.transit.service`
- New dependencies:
  ```bash
  uv add lxml
  uv add --group dev lxml-stubs
  ```
- New env vars: None required (defaults configured in Settings)

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules loaded via
`@_shared/python-anti-patterns.md`.

**Feature-specific pitfalls:**
- **lxml namespace handling** — Always use `{namespace}tag` or `QName(ns, tag)` format. Bare tag
  names produce elements outside any namespace, which NeTEx validators reject.
- **XML encoding** — Use `encoding="UTF-8"` in `tostring()` to produce `<?xml ... encoding="UTF-8"?>`.
  Without it, lxml defaults to ASCII with character escaping.
- **GTFS times > 24:00** — Valid in both GTFS and NeTEx. Do NOT normalize to 00:xx:xx.
- **Empty elements** — NeTEx validators may reject self-closing tags for certain elements. Use
  `SubElement` with text content rather than empty elements where required.
- **lxml type stubs** — `lxml-stubs` may not cover all APIs. If pyright complains, add
  `# pyright: reportMissingTypeStubs=false` at file level in the affected file only.
- **Anti-pattern rule 18 (ARG001)** — The `request: Request` parameter required by slowapi will
  trigger unused-arg warnings. Add `_ = request` on the first line of each route handler.
- **Anti-pattern rule 55 (HTTPBearer)** — All endpoints use `get_current_user` which already
  handles the 401 pattern correctly.

## Notes

- **Future enhancement:** Add NeTEx validation via `xmlschema` library against the official XSD.
  This is a post-MVP improvement — the current implementation generates structurally correct XML
  but does not self-validate against the schema.
- **Future enhancement:** SIRI-SX (Situation Exchange) for service disruptions. Requires an events
  or alerts system that doesn't exist yet.
- **Performance:** NeTEx export for 80 routes / 2000+ stops generates ~2-5MB XML. The in-memory
  lxml tree building handles this easily. For much larger datasets, consider streaming XML via
  `lxml.etree.xmlfile` context manager.
- **Latvia NAP:** The codespace "VTV" and participant_ref "VTV" are configurable via Settings.
  When deploying for Rigas Satiksme, change to "RS" or the NAP-assigned codespace.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed research documentation (NeTEx EPIP profile, SIRI spec)
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order (1-18)
- [ ] Validation commands are executable in this environment
