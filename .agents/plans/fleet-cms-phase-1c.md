# Plan: Fleet CMS Frontend — Phase 1C

## Feature Metadata
**Feature Type**: New Capability (4 frontend pages)
**Estimated Complexity**: High
**Primary Systems Affected**: CMS frontend (Next.js), Fleet API, Geofences API, Transit API

## Feature Description

Phase 1C adds 4 CMS frontend pages for fleet management and geofencing — consuming the backend APIs built in Phases 1A (fleet devices) and 1B (geofences). These pages give dispatchers and administrators visibility into GPS-tracked hardware devices, real-time fleet positions on a map, geographic zone monitoring with polygon editing, and OBD-II telemetry dashboards.

The pages follow established VTV patterns: vehicles page structure for CRUD, routes page for Leaflet maps, recharts for time-series telemetry. All pages require i18n (LV/EN), RBAC enforcement, semantic design tokens, and responsive mobile layouts.

**Pages:**
1. **Fleet Devices** (`/fleet`) — CRUD table for TrackedDevice hardware (IMEI, SIM, protocol, vehicle link)
2. **Fleet Map** (`/fleet/map`) — Real-time Leaflet map showing hardware GPS positions with device status overlay
3. **Geofences** (`/geofences`) — Zone CRUD with Leaflet polygon drawing/editing, event timeline, dwell reports
4. **Telemetry** (`/fleet/telemetry`) — OBD-II dashboard with recharts time-series (speed, fuel, RPM, temperature)

## User Story

As a fleet administrator
I want to manage GPS tracking devices, view their real-time positions on a map, define geographic zones with entry/exit alerts, and monitor vehicle telemetry data
So that I can maintain oversight of the entire vehicle fleet from a single CMS interface

## Security Contexts

**Active contexts:**
- **CTX-RBAC**: All 4 pages add new protected routes with role-based UI gating (admin/editor write, viewer/dispatcher read)
- **CTX-INPUT**: Search filters, coordinate inputs for geofence polygons, date range pickers for telemetry/events

**Not applicable:**
- CTX-AUTH: No changes to auth flow
- CTX-FILE: No file uploads
- CTX-AGENT: No AI agent integration
- CTX-INFRA: No Docker/nginx changes

## Solution Approach

Mirror the vehicles page architecture across all 4 pages: page root manages state, child components receive data + callbacks, dialogs for forms/details, authFetch for API calls. Create custom SDK wrappers (not @vtv/sdk generated) since the fleet/geofence endpoints aren't in the OpenAPI spec yet.

**Approach Decision:**
We chose custom SDK wrappers over waiting for SDK regeneration because:
- Backend fleet/geofence endpoints aren't in the generated SDK yet
- Custom wrappers follow the exact same pattern as `vehicles-sdk.ts`
- Can be replaced with generated SDK later without API changes

**Alternatives Considered:**
- Regenerate @vtv/sdk first: Rejected — requires running backend, adds dependency; custom wrappers are equivalent
- Single mega-page with tabs: Rejected — 4 distinct concerns (CRUD, map, zones, telemetry) are better as separate routes for RBAC granularity and code splitting

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, type checking, logging
- `cms/CLAUDE.md` — Frontend conventions, SDK patterns, security
- `cms/design-system/vtv/MASTER.md` — Design tokens, spacing, typography, anti-patterns

### Similar Features (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/vehicles/page.tsx` — **PRIMARY REFERENCE**: Full CRUD page with state management, auth gating, RBAC role checks, filter sidebar, mobile responsive layout, dialog/form patterns
- `cms/apps/web/src/components/vehicles/vehicle-table.tsx` — Table with pagination, status badges, row actions
- `cms/apps/web/src/components/vehicles/vehicle-form.tsx` — Create/edit form in Dialog
- `cms/apps/web/src/components/vehicles/vehicle-detail.tsx` — Detail view with tabs
- `cms/apps/web/src/components/vehicles/vehicle-filters.tsx` — Desktop sidebar + mobile Sheet filter pattern
- `cms/apps/web/src/components/routes/route-map.tsx` — Leaflet MapContainer, TileLayer, FitBounds, vehicle markers
- `cms/apps/web/src/components/stops/stop-map.tsx` — Leaflet with editable markers, click-to-place, popup dialogs
- `cms/apps/web/src/lib/vehicles-sdk.ts` — Custom SDK wrapper with authFetch, error class, typed functions
- `cms/apps/web/src/types/vehicle.ts` — TypeScript interfaces for API response types
- `cms/apps/web/src/hooks/use-mobile.ts` — `useIsMobile()` responsive hook
- `cms/apps/web/src/lib/auth-fetch.ts` — `authFetch` with JWT token caching

### Files to Modify
- `cms/apps/web/src/components/app-sidebar.tsx` — Add fleet + geofences nav items
- `cms/apps/web/middleware.ts` — Add fleet + geofences routes to RBAC permissions
- `cms/apps/web/messages/en.json` — Add English i18n keys
- `cms/apps/web/messages/lv.json` — Add Latvian i18n keys

## Implementation Plan

### Phase 1: Foundation (Types, SDK wrappers, i18n, nav)
Shared infrastructure all 4 pages need: TypeScript interfaces, API client functions, translation keys, sidebar navigation entries, and RBAC route protection.

### Phase 2: Fleet Devices Page (CRUD table)
Standard CRUD page following vehicles pattern: table, filters, form, detail, delete dialog.

### Phase 3: Fleet Map Page (real-time positions)
Leaflet map showing hardware GPS device positions with status overlay and auto-refresh.

### Phase 4: Geofences Page (polygon editor + events)
Zone CRUD with Leaflet polygon drawing, event timeline tab, dwell report tab.

### Phase 5: Telemetry Page (OBD-II dashboard)
Recharts time-series dashboard for vehicle telemetry data with device/time selectors.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Fleet TypeScript Interfaces
**File:** `cms/apps/web/src/types/fleet.ts` (create new)
**Action:** CREATE

Create TypeScript interfaces matching the backend fleet schemas:

```typescript
export type DeviceProtocolType = "teltonika" | "queclink" | "general" | "osmand" | "other";
export type DeviceStatus = "active" | "inactive" | "offline";

export interface TrackedDevice {
  id: number;
  imei: string;
  device_name: string | null;
  sim_number: string | null;
  protocol_type: DeviceProtocolType;
  firmware_version: string | null;
  notes: string | null;
  vehicle_id: number | null;
  status: DeviceStatus;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TrackedDeviceCreate {
  imei: string;
  device_name?: string | null;
  sim_number?: string | null;
  protocol_type?: DeviceProtocolType;
  firmware_version?: string | null;
  notes?: string | null;
  vehicle_id?: number | null;
}

export interface TrackedDeviceUpdate {
  imei?: string;
  device_name?: string | null;
  sim_number?: string | null;
  protocol_type?: DeviceProtocolType;
  firmware_version?: string | null;
  notes?: string | null;
  vehicle_id?: number | null;
  status?: DeviceStatus;
}

export interface PaginatedDevices {
  items: TrackedDevice[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface OBDTelemetry {
  speed_kmh: number | null;
  rpm: number | null;
  fuel_level_pct: number | null;
  coolant_temp_c: number | null;
  odometer_km: number | null;
  engine_load_pct: number | null;
  battery_voltage: number | null;
}

export interface VehiclePositionWithTelemetry {
  vehicle_id: string;
  latitude: number;
  longitude: number;
  speed_kmh: number | null;
  bearing: number | null;
  recorded_at: string;
  source: "hardware" | "gtfs-rt";
  obd_data: OBDTelemetry | null;
}

export interface TelemetryHistoryPoint {
  recorded_at: string;
  latitude: number;
  longitude: number;
  speed_kmh: number | null;
  obd_data: OBDTelemetry | null;
}
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 2: Geofence TypeScript Interfaces
**File:** `cms/apps/web/src/types/geofence.ts` (create new)
**Action:** CREATE

Create TypeScript interfaces matching the backend geofence schemas:

```typescript
export type ZoneType = "depot" | "terminal" | "restricted" | "customer" | "custom";
export type AlertSeverity = "critical" | "high" | "medium" | "low" | "info";
export type GeofenceEventType = "enter" | "exit" | "dwell_exceeded";

export interface Geofence {
  id: number;
  name: string;
  zone_type: ZoneType;
  coordinates: number[][];  // [lon, lat] pairs
  color: string | null;
  alert_on_enter: boolean;
  alert_on_exit: boolean;
  alert_on_dwell: boolean;
  dwell_threshold_minutes: number | null;
  alert_severity: AlertSeverity;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface GeofenceCreate {
  name: string;
  zone_type: ZoneType;
  coordinates: number[][];
  color?: string | null;
  alert_on_enter?: boolean;
  alert_on_exit?: boolean;
  alert_on_dwell?: boolean;
  dwell_threshold_minutes?: number | null;
  alert_severity?: AlertSeverity;
  description?: string | null;
}

export interface GeofenceUpdate {
  name?: string;
  zone_type?: ZoneType;
  coordinates?: number[][];
  color?: string | null;
  alert_on_enter?: boolean;
  alert_on_exit?: boolean;
  alert_on_dwell?: boolean;
  dwell_threshold_minutes?: number | null;
  alert_severity?: AlertSeverity;
  description?: string | null;
  is_active?: boolean;
}

export interface PaginatedGeofences {
  items: Geofence[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GeofenceEvent {
  id: number;
  geofence_id: number;
  geofence_name: string;
  vehicle_id: string;
  event_type: GeofenceEventType;
  entered_at: string;
  exited_at: string | null;
  dwell_seconds: number | null;
  latitude: number;
  longitude: number;
  created_at: string;
}

export interface PaginatedGeofenceEvents {
  items: GeofenceEvent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DwellTimeReport {
  geofence_id: number;
  geofence_name: string;
  total_events: number;
  avg_dwell_seconds: number;
  max_dwell_seconds: number;
  vehicles_inside: number;
}
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 3: Fleet SDK Wrapper
**File:** `cms/apps/web/src/lib/fleet-sdk.ts` (create new)
**Action:** CREATE

Create API client functions following `vehicles-sdk.ts` pattern. Use `authFetch` from `@/lib/auth-fetch`. Base URL from `NEXT_PUBLIC_AGENT_URL` env var (default `http://localhost:8123`).

Functions to implement:
- `fetchDevices(params: { page?, page_size?, search?, status?, vehicle_linked? }): Promise<PaginatedDevices>`
- `fetchDevice(deviceId: number): Promise<TrackedDevice>`
- `createDevice(data: TrackedDeviceCreate): Promise<TrackedDevice>`
- `updateDevice(deviceId: number, data: TrackedDeviceUpdate): Promise<TrackedDevice>`
- `deleteDevice(deviceId: number): Promise<void>`
- `fetchFleetPositions(feedId?: string): Promise<VehiclePositionWithTelemetry[]>` — calls `GET /api/v1/transit/vehicles?feed_id=fleet`
- `fetchVehicleHistory(vehicleId: string, fromTime: string, toTime: string, limit?: number): Promise<TelemetryHistoryPoint[]>` — calls `GET /api/v1/transit/vehicles/{vehicleId}/history`

Include `FleetApiError` class with `status` property (mirror `VehiclesApiError`).

Use `URLSearchParams` for query building. All functions async with typed returns.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 4: Geofences SDK Wrapper
**File:** `cms/apps/web/src/lib/geofences-sdk.ts` (create new)
**Action:** CREATE

Create API client functions for geofence endpoints:
- `fetchGeofences(params: { page?, page_size?, search?, zone_type?, is_active? }): Promise<PaginatedGeofences>`
- `fetchGeofence(geofenceId: number): Promise<Geofence>`
- `createGeofence(data: GeofenceCreate): Promise<Geofence>`
- `updateGeofence(geofenceId: number, data: GeofenceUpdate): Promise<Geofence>`
- `deleteGeofence(geofenceId: number): Promise<void>`
- `fetchGeofenceEvents(params: { page?, page_size?, vehicle_id?, event_type?, geofence_id?, start_time?, end_time? }): Promise<PaginatedGeofenceEvents>`
- `fetchZoneEvents(geofenceId: number, params: { page?, page_size?, event_type?, start_time?, end_time? }): Promise<PaginatedGeofenceEvents>`
- `fetchDwellReport(geofenceId: number, params: { start_time?, end_time? }): Promise<DwellTimeReport>`

Include `GeofencesApiError` class.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 5: English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify existing)
**Action:** UPDATE

Add these sections to the JSON (read file first to find insertion point after last feature section):

1. Add nav keys: `"fleet": "Fleet Devices"`, `"fleetMap": "Fleet Map"`, `"geofences": "Geofences"`, `"telemetry": "Telemetry"` inside the `"nav"` object.

2. Add `"fleet"` section with keys for:
   - `title`, `description`, `search`
   - `filters`: `allStatuses`, `active`, `inactive`, `offline`, `allProtocols`, `teltonika`, `queclink`, `general`, `osmand`, `other`, `linkedOnly`, `unlinkedOnly`, `status`, `protocol`
   - `table`: `imei`, `deviceName`, `simNumber`, `protocol`, `status`, `vehicle`, `lastSeen`, `actions`, `noResults`, `unlinked`, `neverSeen`
   - `detail`: `title`, `tabs.info`, `tabs.telemetry`, `imei`, `simNumber`, `protocol`, `firmware`, `vehicle`, `status`, `lastSeen`, `notes`, `createdAt`
   - `form`: `createTitle`, `editTitle`, `imei`, `imeiHelp`, `deviceName`, `simNumber`, `protocol`, `firmware`, `vehicle`, `vehiclePlaceholder`, `notes`
   - `actions`: `create`, `edit`, `delete`, `save`, `cancel`, `refresh`
   - `delete`: `title`, `confirmation`, `warning`
   - `toast`: `created`, `updated`, `deleted`, `loadError`, `createError`, `updateError`, `deleteError`
   - `map`: `title`, `vehicles`, `noData`, `deviceStatus`, `lastUpdate`, `speed`, `noDevices`
   - `telemetry`: `title`, `description`, `selectDevice`, `timeRange`, `last1h`, `last6h`, `last24h`, `speed`, `rpm`, `fuelLevel`, `coolantTemp`, `engineLoad`, `battery`, `noData`, `loadError`

3. Add `"geofences"` section with keys for:
   - `title`, `description`, `search`
   - `filters`: `allTypes`, `depot`, `terminal`, `restricted`, `customer`, `custom`, `activeOnly`, `zoneType`, `status`
   - `table`: `name`, `zoneType`, `alertsEnabled`, `severity`, `status`, `actions`, `noResults`, `active`, `inactive`
   - `detail`: `title`, `tabs.info`, `tabs.events`, `tabs.dwell`, `name`, `zoneType`, `color`, `description`, `alertOnEnter`, `alertOnExit`, `alertOnDwell`, `dwellThreshold`, `severity`, `status`, `createdAt`
   - `form`: `createTitle`, `editTitle`, `name`, `zoneType`, `color`, `description`, `alertOnEnter`, `alertOnExit`, `alertOnDwell`, `dwellThreshold`, `dwellThresholdHelp`, `severity`, `coordinates`, `coordinatesHelp`, `drawOnMap`
   - `actions`: `create`, `edit`, `delete`, `save`, `cancel`
   - `delete`: `title`, `confirmation`, `warning`
   - `toast`: `created`, `updated`, `deleted`, `loadError`, `createError`, `updateError`, `deleteError`
   - `events`: `title`, `vehicleId`, `eventType`, `enteredAt`, `exitedAt`, `dwellTime`, `noEvents`, `enter`, `exit`, `dwellExceeded`
   - `dwell`: `title`, `totalEvents`, `avgDwell`, `maxDwell`, `vehiclesInside`, `minutes`, `noData`
   - `map`: `title`, `drawPolygon`, `editPolygon`, `clearPolygon`, `clickToPlace`, `polygonComplete`

**Per-task validation:**
- Verify JSON is valid: `cd cms && node -e "JSON.parse(require('fs').readFileSync('apps/web/messages/en.json','utf8'))"`

---

### Task 6: Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify existing)
**Action:** UPDATE

Add parallel Latvian translations for all keys added in Task 5. Key translations:
- `nav.fleet` = "Flotes ierīces"
- `nav.fleetMap` = "Flotes karte"
- `nav.geofences` = "Geozonējums"
- `nav.telemetry` = "Telemetrija"
- `fleet.title` = "Flotes ierīces"
- `fleet.description` = "GPS izsekošanas ierīču pārvaldība"
- `geofences.title` = "Geozonējums"
- `geofences.description` = "Ģeogrāfisko zonu pārvaldība un uzraudzība"

Follow the exact same hierarchy as en.json. Translate ALL keys — no English fallbacks.

**Per-task validation:**
- Verify JSON is valid: `cd cms && node -e "JSON.parse(require('fs').readFileSync('apps/web/messages/lv.json','utf8'))"`
- Verify key parity: `cd cms && node -e "const en=Object.keys(JSON.parse(require('fs').readFileSync('apps/web/messages/en.json','utf8')).fleet||{});const lv=Object.keys(JSON.parse(require('fs').readFileSync('apps/web/messages/lv.json','utf8')).fleet||{});console.log('EN fleet keys:',en.length,'LV fleet keys:',lv.length)"`

---

### Task 7: Sidebar Navigation
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify existing)
**Action:** UPDATE

Read file first. Add 4 nav items to the `navItems` array (insert after "vehicles" entry):
```typescript
{ key: "fleet", href: "/fleet", enabled: true },
{ key: "fleetMap", href: "/fleet/map", enabled: true },
{ key: "geofences", href: "/geofences", enabled: true },
{ key: "telemetry", href: "/fleet/telemetry", enabled: true },
```

The nav labels come from `useTranslations("nav")` which already exists — the keys will resolve from the i18n files updated in Tasks 5-6.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 8: RBAC Middleware
**File:** `cms/apps/web/middleware.ts` (modify existing)
**Action:** UPDATE

Read file first. Update `ROLE_PERMISSIONS` to include fleet and geofences routes:
- `admin`: add `"/fleet"`, `"/fleet/map"`, `"/fleet/telemetry"`, `"/geofences"`
- `dispatcher`: add `"/fleet"`, `"/fleet/map"`, `"/fleet/telemetry"`, `"/geofences"` (read access for dispatchers)
- `editor`: add `"/fleet"`, `"/fleet/map"`, `"/fleet/telemetry"`, `"/geofences"`
- `viewer`: add `"/fleet"`, `"/fleet/map"`, `"/fleet/telemetry"`, `"/geofences"` (read-only)

Update the `matcher` regex to include `fleet` and `geofences` routes.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 9: Fleet Devices Table Component
**File:** `cms/apps/web/src/components/fleet/fleet-devices-table.tsx` (create new)
**Action:** CREATE

Follow `vehicle-table.tsx` pattern exactly. Props interface:
```typescript
interface FleetDevicesTableProps {
  devices: TrackedDevice[];
  totalItems: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  selectedDevice: TrackedDevice | null;
  onSelectDevice: (device: TrackedDevice) => void;
  onEditDevice: (device: TrackedDevice) => void;
  onDeleteDevice: (device: TrackedDevice) => void;
  isLoading: boolean;
  isReadOnly: boolean;
  canDelete: boolean;
}
```

Table columns: IMEI, Device Name, Protocol, Status (badge), Vehicle (linked or "—"), Last Seen (relative time), Actions dropdown.

Status badge colors (use semantic tokens):
- `active`: `bg-status-ontime/10 text-status-ontime border-status-ontime/20`
- `inactive`: `bg-surface-secondary text-foreground-muted border-border`
- `offline`: `bg-status-critical/10 text-status-critical border-status-critical/20`

Use `Pagination` component at bottom. Loading skeleton when `isLoading`. Row click opens detail.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 10: Fleet Devices Filters Component
**File:** `cms/apps/web/src/components/fleet/fleet-devices-filters.tsx` (create new)
**Action:** CREATE

Follow `vehicle-filters.tsx` pattern. Filter options:
- Search input (debounced, 300ms)
- Status dropdown: All / Active / Inactive / Offline
- Protocol dropdown: All / Teltonika / Queclink / General / OsmAnd / Other
- Vehicle linked toggle: All / Linked Only / Unlinked Only

Support both desktop sidebar layout and mobile Sheet layout via `asSheet` prop.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 11: Fleet Device Form Component
**File:** `cms/apps/web/src/components/fleet/fleet-device-form.tsx` (create new)
**Action:** CREATE

Follow `vehicle-form.tsx` pattern. Dialog-based create/edit form.

Form fields:
- IMEI (required, 15 digits, regex validation)
- Device Name (optional, max 100 chars)
- SIM Number (optional, max 20 chars)
- Protocol Type (select: teltonika/queclink/general/osmand/other)
- Firmware Version (optional, max 50 chars)
- Vehicle (optional select — needs vehicle list from `fetchVehicles`)
- Notes (optional textarea, max 2000 chars)

Dialog width: `sm:max-w-[32rem]`. Form remount via `key` prop.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 12: Fleet Device Detail Component
**File:** `cms/apps/web/src/components/fleet/fleet-device-detail.tsx` (create new)
**Action:** CREATE

Follow `vehicle-detail.tsx` pattern with tabs: Info | Telemetry.

**Info tab:** Read-only display of all device fields. Show vehicle link as clickable badge if linked.

**Telemetry tab:** Show last known OBD-II data if available (speed, RPM, fuel, coolant temp, engine load, battery voltage) as a grid of stat cards using semantic tokens. If no telemetry data, show empty state message.

Action buttons at bottom: Edit (if CAN_EDIT), Delete (if CAN_DELETE).

Dialog width: `sm:max-w-[28rem]`.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 13: Delete Fleet Device Dialog
**File:** `cms/apps/web/src/components/fleet/delete-fleet-device-dialog.tsx` (create new)
**Action:** CREATE

Follow `delete-vehicle-dialog.tsx` pattern exactly. Confirmation dialog with device IMEI/name in message. Destructive action button. Calls `deleteDevice()` from fleet-sdk.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 14: Fleet Devices Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/fleet/page.tsx` (create new)
**Action:** CREATE

Follow `vehicles/page.tsx` as primary reference. This is the main fleet devices CRUD page.

Key requirements:
- `"use client"` directive
- Auth gating: `if (status !== "authenticated") return;`
- RBAC role constants: `IS_READ_ONLY`, `CAN_EDIT`, `CAN_DELETE` based on `session.user.role`
  - CAN_EDIT: admin, editor
  - CAN_DELETE: admin only
- State management: devices array, pagination (page/totalItems), filters (search/status/protocol/vehicleLinked), UI state (detailOpen/formOpen/deleteOpen/selectedDevice/formMode/formKey)
- `useIsMobile()` for responsive layout
- Debounced search (300ms) with `useEffect` + timeout
- `loadDevices()` callback with `fetchDevices()` from fleet-sdk
- Layout structure:
  ```
  header (title + description + create button)
  content area:
    desktop filter sidebar | table
    mobile filter sheet
  dialogs: detail, form, delete
  ```
- Toast notifications for CRUD operations
- All text via `useTranslations("fleet")`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`
- `cd cms && pnpm --filter @vtv/web lint`

---

### Task 15: Fleet Map Component
**File:** `cms/apps/web/src/components/fleet/fleet-map.tsx` (create new)
**Action:** CREATE

Follow `route-map.tsx` pattern. Leaflet MapContainer centered on Riga (56.9496, 24.1052).

Features:
- Device position markers with status-colored pins (active=green, offline=red, inactive=gray)
- Click marker to show popup with: device name, IMEI, speed, last update time
- Auto-fit bounds to visible markers
- Device count overlay (top-left badge showing "N devices")
- Empty state when no devices have positions

Props:
```typescript
interface FleetMapProps {
  positions: VehiclePositionWithTelemetry[];
  selectedDeviceId: string | null;
  onSelectDevice: (vehicleId: string) => void;
}
```

Use CARTO Voyager tiles (same as routes/stops maps). Import `leaflet/dist/leaflet.css`.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 16: Fleet Map Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/fleet/map/page.tsx` (create new)
**Action:** CREATE

Real-time fleet position map page. Simpler than CRUD pages — primarily a map with a device list sidebar.

Layout:
```
header (title + refresh button)
content:
  device list sidebar (scrollable, filterable by status) | map (flex-1)
```

Data loading:
- `fetchFleetPositions("fleet")` with auto-refresh every 15 seconds via `useEffect` + `setInterval`
- Show connection status (last refresh timestamp)
- Click device in sidebar → highlight on map and fly-to

All text via `useTranslations("fleet.map")`.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`
- `cd cms && pnpm --filter @vtv/web lint`

---

### Task 17: Geofence Map Component
**File:** `cms/apps/web/src/components/geofences/geofence-map.tsx` (create new)
**Action:** CREATE

Leaflet map for displaying and editing geofence polygons. This is the most complex map component.

**Display mode:** Render all geofences as Leaflet Polygon overlays with zone-type-based colors:
- depot: `#0391F2` (blue/interactive)
- terminal: `#06757E` (teal/success)
- restricted: `#DD3039` (red/error)
- customer: `#D4A017` (amber/warning)
- custom: `#60607D` (secondary)

Use `fillOpacity: 0.2`, `weight: 2`. Click polygon to select/show popup with name + type.

**Edit mode (for form):** Accept `editCoordinates` and `onCoordinatesChange` props. When in edit mode:
- Render existing polygon from coordinates
- Allow click-to-place new vertices
- Show vertex markers that can be dragged
- Complete polygon by clicking first vertex (minimum 3 unique points + closing point)

Props:
```typescript
interface GeofenceMapProps {
  geofences: Geofence[];
  selectedGeofenceId: number | null;
  onSelectGeofence: (id: number) => void;
  editMode?: boolean;
  editCoordinates?: number[][];
  onCoordinatesChange?: (coords: number[][]) => void;
}
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 18: Geofences Table Component
**File:** `cms/apps/web/src/components/geofences/geofences-table.tsx` (create new)
**Action:** CREATE

Follow `vehicle-table.tsx` pattern. Table columns: Name, Zone Type (badge), Alerts (icons for enter/exit/dwell), Severity (badge), Status (active/inactive badge), Actions dropdown.

Zone type badge colors:
- depot: `bg-interactive/10 text-interactive border-interactive/20`
- terminal: `bg-status-ontime/10 text-status-ontime border-status-ontime/20`
- restricted: `bg-status-critical/10 text-status-critical border-status-critical/20`
- customer: `bg-status-delayed/10 text-status-delayed border-status-delayed/20`
- custom: `bg-surface-secondary text-foreground-muted border-border`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 19: Geofences Filters Component
**File:** `cms/apps/web/src/components/geofences/geofences-filters.tsx` (create new)
**Action:** CREATE

Filter options:
- Search input (debounced)
- Zone Type dropdown: All / Depot / Terminal / Restricted / Customer / Custom
- Status toggle: All / Active Only / Inactive Only

Desktop sidebar + mobile Sheet support.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 20: Geofence Form Component
**File:** `cms/apps/web/src/components/geofences/geofence-form.tsx` (create new)
**Action:** CREATE

Dialog-based create/edit form. This is wider than standard forms because it includes an embedded map for polygon drawing.

Dialog width: `sm:max-w-[48rem]` (extra wide for map).

Form fields (left column):
- Name (required, max 200 chars)
- Zone Type (required select)
- Color (optional hex input with preview swatch)
- Description (optional textarea, max 1000 chars)
- Alert On Enter (checkbox, default true)
- Alert On Exit (checkbox, default true)
- Alert On Dwell (checkbox, default false)
- Dwell Threshold Minutes (number input, 1-1440, shown only when alert_on_dwell is true)
- Alert Severity (select: critical/high/medium/low/info)

Right side: Embedded `GeofenceMap` in edit mode for polygon drawing/editing. Map takes ~60% of dialog width.

When editing, pre-populate all fields including existing polygon coordinates on map.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 21: Geofence Detail Component
**File:** `cms/apps/web/src/components/geofences/geofence-detail.tsx` (create new)
**Action:** CREATE

Dialog with 3 tabs: Info | Events | Dwell Report.

**Info tab:** Read-only display of all geofence fields. Small embedded map preview showing the polygon.

**Events tab:** Table of recent events for this geofence. Columns: Vehicle ID, Event Type (enter/exit/dwell badge), Entered At, Exited At, Dwell Time. Load via `fetchZoneEvents()`. Paginated (10 per page).

**Dwell tab:** Dwell time report card showing: Total Events, Avg Dwell (formatted as minutes), Max Dwell, Vehicles Currently Inside. Load via `fetchDwellReport()`.

Action buttons: Edit (CAN_EDIT), Delete (CAN_DELETE).

Dialog width: `sm:max-w-[36rem]` (wide for tabs with tables).

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 22: Delete Geofence Dialog
**File:** `cms/apps/web/src/components/geofences/delete-geofence-dialog.tsx` (create new)
**Action:** CREATE

Confirmation dialog showing geofence name. Warning about cascading event deletion. Calls `deleteGeofence()`.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 23: Geofences Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/geofences/page.tsx` (create new)
**Action:** CREATE

Follow `vehicles/page.tsx` as primary reference but with split layout: table on left, map on right.

Layout:
```
header (title + description + create button)
content:
  left panel (filters + table, ~50% width)
  right panel (geofence map showing all zones, ~50% width)
dialogs: detail, form, delete
```

On mobile: stack vertically (map above table) or tab between map/table views.

Click geofence in table → highlight on map. Click polygon on map → select in table + open detail.

State, auth gating, RBAC checks, toast, i18n — all follow vehicles page pattern.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`
- `cd cms && pnpm --filter @vtv/web lint`

---

### Task 24: Telemetry Dashboard Component
**File:** `cms/apps/web/src/components/fleet/telemetry-dashboard.tsx` (create new)
**Action:** CREATE

Recharts-based telemetry visualization. Shows OBD-II data as time-series line charts.

Layout: Grid of chart cards (2 columns on desktop, 1 on mobile):
1. **Speed** (km/h) — `LineChart` with `obd_data.speed_kmh`
2. **RPM** — `LineChart` with `obd_data.rpm`
3. **Fuel Level** (%) — `AreaChart` with `obd_data.fuel_level_pct`
4. **Coolant Temperature** (C) — `LineChart` with `obd_data.coolant_temp_c`
5. **Engine Load** (%) — `AreaChart` with `obd_data.engine_load_pct`
6. **Battery Voltage** (V) — `LineChart` with `obd_data.battery_voltage`

Each chart card:
- Title (from i18n)
- Current value (large number, top-right)
- Time-series line chart (last N hours based on selected range)
- Use semantic tokens for chart colors: `--color-interactive` for primary line, `--color-surface-secondary` for grid

Props:
```typescript
interface TelemetryDashboardProps {
  data: TelemetryHistoryPoint[];
  isLoading: boolean;
}
```

Use `recharts` `ResponsiveContainer` for auto-sizing. Format timestamps on X-axis.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 25: Telemetry Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/fleet/telemetry/page.tsx` (create new)
**Action:** CREATE

Telemetry dashboard page. Top controls: device selector + time range selector.

Layout:
```
header (title + description)
controls bar:
  device selector (dropdown of fleet devices with vehicle link info)
  time range (1h / 6h / 24h toggle buttons)
content:
  TelemetryDashboard component (grid of chart cards)
empty state if no device selected or no data
```

Data loading:
- Load device list via `fetchDevices()` on mount
- When device selected + time range set → `fetchVehicleHistory()` with calculated from/to times
- Show loading skeleton while fetching

All text via `useTranslations("fleet.telemetry")`.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`
- `cd cms && pnpm --filter @vtv/web lint`

---

## Testing Strategy

### Manual Testing Checklist
Since these are frontend pages, testing is primarily manual browser-based:

1. **Fleet Devices Page:**
   - List loads with pagination
   - Search filters by device name
   - Status/protocol filters work
   - Create device form validates IMEI (15 digits)
   - Edit device pre-populates all fields
   - Delete shows confirmation, removes from list
   - Detail dialog shows all fields
   - Mobile responsive (Sheet filters, full-width table)

2. **Fleet Map Page:**
   - Map renders centered on Riga
   - Device markers appear with correct status colors
   - Click marker shows popup
   - Auto-refresh every 15 seconds
   - Empty state when no positions

3. **Geofences Page:**
   - Split layout: table left, map right
   - All geofences render as polygons on map
   - Create form opens with embedded map editor
   - Polygon drawing (click vertices, close ring)
   - Zone type colors match design spec
   - Events tab loads paginated events
   - Dwell report shows stats
   - Mobile responsive (stacked layout)

4. **Telemetry Page:**
   - Device selector loads device list
   - Time range toggle works
   - Charts render with data
   - Empty state when no data
   - Responsive chart grid

### Type Safety
```bash
cd cms && pnpm --filter @vtv/web type-check
```

### Lint
```bash
cd cms && pnpm --filter @vtv/web lint
```

### Build
```bash
cd cms && pnpm --filter @vtv/web build
```

## Acceptance Criteria

This feature is complete when:
- [ ] All 4 pages render without errors
- [ ] Fleet Devices CRUD works end-to-end (create, read, update, delete)
- [ ] Fleet Map shows real-time device positions from backend
- [ ] Geofences page renders polygons on map with correct zone-type colors
- [ ] Geofence form allows polygon drawing/editing
- [ ] Geofence events and dwell reports load in detail dialog
- [ ] Telemetry page shows OBD-II time-series charts
- [ ] All pages have Latvian AND English translations
- [ ] RBAC enforced: admin/editor can write, viewer/dispatcher can read
- [ ] Mobile responsive on all 4 pages
- [ ] TypeScript type-check passes (0 errors)
- [ ] ESLint passes (0 errors)
- [ ] Next.js build succeeds
- [ ] No hardcoded colors (semantic tokens only)
- [ ] No rounded corners (except status dots, avatars, scrollbars)
- [ ] Sidebar navigation includes all 4 pages

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 25 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-3)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (3-Level Frontend Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Type Safety**
```bash
cd cms && pnpm --filter @vtv/web type-check
```

**Level 2: Lint**
```bash
cd cms && pnpm --filter @vtv/web lint
```

**Level 3: Build**
```bash
cd cms && pnpm --filter @vtv/web build
```

**Success definition:** All 3 levels exit code 0, zero errors.

## Dependencies

- **Existing packages (already installed):** `leaflet`, `react-leaflet`, `@types/leaflet`, `recharts`, `@tremor/react`, `sonner`, `next-intl`, `next-auth`
- **Existing components (shadcn/ui):** `Table`, `Dialog`, `Badge`, `Button`, `Input`, `Select`, `Pagination`, `Sheet`, `DropdownMenu`, `Tabs`, `Skeleton`
- **New dependencies:** None required — all needed libraries are already installed
- **New env vars:** None — uses existing `NEXT_PUBLIC_AGENT_URL`

## Known Pitfalls

1. **No hardcoded colors** — Use semantic tokens only (`bg-status-ontime/10`, not `bg-green-100`)
2. **No rounded corners** — `border-radius: 0` on all components except status dots, avatars, switches
3. **Dialog sizing** — Use explicit rem: `sm:max-w-[32rem]` not named sizes like `max-w-md`
4. **React 19** — No setState in useEffect (use key remount), no component defs inside components, no Math.random in render
5. **Auth gating** — Always check `if (status !== "authenticated") return;` before loading data
6. **Leaflet CSS import** — Must import `leaflet/dist/leaflet.css` in every map component file
7. **Leaflet SSR** — Leaflet doesn't work server-side. Map components must be `"use client"` and consider dynamic import with `ssr: false` if build issues arise
8. **GeoJSON coordinate order** — Backend stores [longitude, latitude] pairs. Leaflet uses [latitude, longitude]. Swap when converting coordinates for Leaflet LatLng objects
9. **Debounced search** — Use `setTimeout`/`clearTimeout` pattern (not useDebounce hook — doesn't exist in codebase)
10. **Form reset** — Use `key={formKey}` pattern to remount form component when switching between create/edit modes
11. **i18n key parity** — Both lv.json and en.json must have identical key hierarchies

## Notes

- **SDK migration:** When the backend OpenAPI spec is updated to include fleet/geofence endpoints, run `pnpm --filter @vtv/sdk refresh` and migrate from custom SDK wrappers to generated client
- **Leaflet polygon drawing:** Consider installing `@react-leaflet/draw` if native click-to-place implementation becomes too complex. However, check if it's compatible with react-leaflet v5 first
- **Real-time telemetry:** The current implementation uses polling (15s intervals). Future enhancement: add WebSocket support for real-time telemetry push (fleet devices can use the existing `vehicle_positions` Pub/Sub channel)
- **Geofence coordinate validation:** Frontend should validate minimum 3 unique points and closed ring (first == last point) before sending to API

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the vehicles page state management pattern
- [ ] Understood the route-map Leaflet pattern
- [ ] Confirmed that leaflet, react-leaflet, recharts are installed
- [ ] Clear on task execution order
- [ ] Validation commands are executable in this environment
