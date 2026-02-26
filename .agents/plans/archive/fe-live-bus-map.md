# Plan: Live Bus Map on Routes Page

## Context
The `/routes` page currently uses a raw flexbox 3-panel layout: filters sidebar (240px fixed `w-60`) + routes table (flex-1). Route detail, form, and delete dialogs are sheet overlays. This plan adds a **live bus location map** as a resizable right panel using Leaflet + OpenStreetMap, with mock bus position data matching the existing mock routes pattern.

## Feature Metadata
**Feature Type**: Enhancement (Routes Page)
**Estimated Complexity**: Medium
**Route**: `/[locale]/(dashboard)/routes` (existing)
**Auth Required**: Yes (existing)
**Allowed Roles**: admin, dispatcher, editor, viewer (existing)

## Feature Description

Add a resizable right panel to the routes page displaying a Leaflet map with OpenStreetMap tiles centered on Riga. The map shows ~30 mock bus markers scattered across Riga's transit corridors, color-coded by route. Clicking a route in the table highlights its buses on the map; clicking a bus marker on the map selects its route in the table.

The layout transforms from `[Filters | Table]` to `[Filters | Table | Handle | Map]` using the existing `ResizablePanelGroup` component (already installed via `react-resizable-panels` v4.6.4). Default split: 60/40 table-to-map.

Data approach: Static mock data only (consistent with MOCK_ROUTES). Real GTFS-RT integration is a follow-up requiring backend REST endpoints.

## Design System

### Master Rules (from MASTER.md)
- Spacing: Use semantic tokens via arbitrary values — `p-(--spacing-card)`, `gap-(--spacing-grid)`
- Typography: Lexend (headings), Source Sans 3 (body)
- Colors: No hardcoded hex — use semantic tokens from tokens.css
- Transitions: 150-300ms for state changes
- Accessibility: Focus rings, ARIA labels, keyboard navigation, 4.5:1 contrast

### Page Override
- None exists at `cms/design-system/vtv/pages/routes.md` — not needed for this enhancement

### Tokens Used
- `--color-status-ontime` (emerald-500) — on-time/early buses
- `--color-status-delayed` (amber-500) — 1-5 min late buses
- `--color-status-critical` (red-600) — >5 min late buses
- `--color-surface` (slate-50) — map container background
- `--color-border` (slate-200) — panel borders
- `--color-foreground-muted` (slate-600) — secondary text in popups
- `--spacing-card` (0.75rem) — map overlay padding
- `--spacing-grid` (0.75rem) — internal gaps
- `--spacing-tight` (0.25rem) — micro gaps in markers

## Components Needed

### Existing (shadcn/ui + project)
- `ResizablePanelGroup`, `ResizablePanel`, `ResizableHandle` from `@/components/ui/resizable` — split layout
- `Badge` from `@/components/ui/badge` — delay status in popup
- `Skeleton` from `@/components/ui/skeleton` — map loading state
- `RouteFilters` from `@/components/routes/route-filters` — unchanged
- `RouteTable` from `@/components/routes/route-table` — unchanged

### New npm Packages to Install
```bash
cd cms && pnpm --filter @vtv/web add leaflet react-leaflet && pnpm --filter @vtv/web add -D @types/leaflet
```

### Custom Components to Create
1. `RouteMap` at `cms/apps/web/src/components/routes/route-map.tsx` — Leaflet map with bus markers
2. `BusMarker` at `cms/apps/web/src/components/routes/bus-marker.tsx` — Individual bus marker + popup

## i18n Keys

### English (`en.json`) — add under `"routes"`
```json
"map": {
  "title": "Live Map",
  "loading": "Loading map...",
  "vehicles": "vehicles",
  "delay": "Delay",
  "onTime": "On time",
  "early": "Early",
  "late": "late",
  "nextStop": "Next stop",
  "noData": "No vehicle data available",
  "minutes": "min"
}
```

### Latvian (`lv.json`) — add under `"routes"`
```json
"map": {
  "title": "Tiesraides karte",
  "loading": "Ielade karti...",
  "vehicles": "transportlidzekli",
  "delay": "Kavesanas",
  "onTime": "Laika",
  "early": "Agrak",
  "late": "kavejas",
  "nextStop": "Nakama pietura",
  "noData": "Nav transportlidzeklu datu",
  "minutes": "min"
}
```

**IMPORTANT:** All Latvian strings use ASCII hyphens only. No EN DASH (U+2013) — Ruff RUF001.
**IMPORTANT:** Latvian diacritics (ā, ē, ī, ū, š, ž, ķ, ļ, ņ, č, ģ) are fine — they are standard Latvian, not ambiguous Unicode.

## Data Model

### BusPosition type — add to `cms/apps/web/src/types/route.ts`
```typescript
export interface BusPosition {
  vehicleId: string;
  routeId: string;
  routeShortName: string;
  routeColor: string;
  latitude: number;
  longitude: number;
  bearing: number | null;
  delaySeconds: number;
  currentStatus: "in_transit" | "stopped" | "incoming";
  nextStopName: string | null;
  timestamp: string;
}
```

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules
- `cms/apps/web/CLAUDE.md` — React 19 anti-patterns, frontend-specific rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Current routes page (MODIFY)
- `cms/apps/web/src/components/routes/route-table.tsx` — RouteTable props/selection pattern
- `cms/apps/web/src/components/ui/resizable.tsx` — ResizablePanel API

### Files to Modify
- `cms/apps/web/src/types/route.ts` — Add BusPosition interface
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Add resizable layout + map
- `cms/apps/web/messages/lv.json` — Add `routes.map.*` keys
- `cms/apps/web/messages/en.json` — Add `routes.map.*` keys

### Files to Create
- `cms/apps/web/src/lib/mock-bus-positions.ts` — Mock bus position data
- `cms/apps/web/src/components/routes/bus-marker.tsx` — Bus marker component
- `cms/apps/web/src/components/routes/route-map.tsx` — Leaflet map component

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render; mock data must be static constants
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **No EN DASH in strings** — Ruff RUF001. Use `-` (U+002D) not `–` (U+2013)

See `cms/apps/web/CLAUDE.md` → "React 19 Anti-Patterns" for full examples.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Install Leaflet Dependencies
**Action:** RUN

```bash
cd cms && pnpm --filter @vtv/web add leaflet react-leaflet && pnpm --filter @vtv/web add -D @types/leaflet
```

This adds:
- `leaflet` — map rendering engine
- `react-leaflet` — React bindings for Leaflet
- `@types/leaflet` — TypeScript type definitions (dev dependency)

**Per-task validation:**
- Verify `leaflet`, `react-leaflet` appear in `cms/apps/web/package.json` dependencies
- Verify `@types/leaflet` appears in devDependencies

---

### Task 2: Add BusPosition Type
**File:** `cms/apps/web/src/types/route.ts` (modify)
**Action:** UPDATE

Add the `BusPosition` interface at the END of the file, after the existing `AGENCY_IDS` export:

```typescript
export interface BusPosition {
  vehicleId: string;
  routeId: string;
  routeShortName: string;
  routeColor: string;
  latitude: number;
  longitude: number;
  bearing: number | null;
  delaySeconds: number;
  currentStatus: "in_transit" | "stopped" | "incoming";
  nextStopName: string | null;
  timestamp: string;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Create Mock Bus Position Data
**File:** `cms/apps/web/src/lib/mock-bus-positions.ts` (create)
**Action:** CREATE

Create a static array of ~30 `BusPosition` objects. Requirements:

1. Import `BusPosition` from `@/types/route`
2. Export `const MOCK_BUS_POSITIONS: BusPosition[]`
3. Scatter positions across Riga's transit corridors:
   - Latitude range: 56.925 to 56.975
   - Longitude range: 24.05 to 24.20
4. Assign to existing active mock route IDs and their colors. Use these routes (from `mock-routes-data.ts`):

   | routeId | shortName | color | type |
   |---------|-----------|-------|------|
   | `route-rs-tram-1` | `1` | `#6A1B9A` | Tram |
   | `route-rs-tram-2` | `2` | `#7B1FA2` | Tram |
   | `route-rs-bus-3` | `3` | `#E53935` | Bus |
   | `route-rs-trol-5` | `5` | `#2E7D32` | Trolleybus |
   | `route-rs-tram-5` | `5T` | `#8E24AA` | Tram |
   | `route-atd-7101` | `7101` | `#1E88E5` | Bus |
   | `route-rs-tram-7` | `7` | `#AB47BC` | Tram |
   | `route-rs-trol-11` | `11` | `#388E3C` | Trolleybus |
   | `route-rs-trol-14` | `14` | `#4CAF50` | Trolleybus |
   | `route-rs-bus-15` | `15` | `#43A047` | Bus |
   | `route-rs-bus-22` | `22` | `#FB8C00` | Bus |
   | `route-rs-bus-30` | `30` | `#8E24AA` | Bus |
   | `route-atd-7201` | `7201` | `#43A047` | Bus |

5. Each bus position:
   - `vehicleId`: format `"V-{4-digit-number}"` — use static unique values (e.g., `"V-1001"`, `"V-1002"`, etc.)
   - `delaySeconds`: mix of values: -30 (early), 0 (on time), 60, 120, 180, 300, 420 (various late)
   - `currentStatus`: distribute among `"in_transit"`, `"stopped"`, `"incoming"`
   - `nextStopName`: use real Riga stop names (e.g., `"Centrala stacija"`, `"Brivibas iela"`, `"Jugla"`, `"Imanta"`, `"Zolitude"`, `"Purvciems"`, `"Plavnieki"`, `"Bolderaja"`, `"Agenskalns"`, `"Tornakalns"`)
   - `bearing`: mix of null and numeric values (0-359)
   - `timestamp`: use `"2026-02-18T08:30:00Z"` as a static timestamp for all

6. Distribute ~2-3 buses per route, with some routes having 1 and others having 4
7. Do NOT use `Math.random()` — all values must be hardcoded static constants

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 4: Create BusMarker Component
**File:** `cms/apps/web/src/components/routes/bus-marker.tsx` (create)
**Action:** CREATE

Create a `'use client'` component that renders a single bus marker on the Leaflet map.

**Component specification:**

```typescript
"use client";

import { Marker, Popup } from "react-leaflet";
import L from "leaflet";
import type { BusPosition } from "@/types/route";

interface BusMarkerProps {
  bus: BusPosition;
  isHighlighted: boolean;
  onSelect: (routeId: string) => void;
}
```

**Marker icon:** Use `L.divIcon` to create a custom HTML marker:
- Circular div with the route's color as background
- Shows the route short name inside
- Size: 28x28px when normal, 36x36px when highlighted
- White text, bold, centered
- Border: 2px solid white (gives contrast on map)
- Box shadow for depth
- CSS class for the icon: define inline via `className` and `html` properties of divIcon
- Bearing rotation: if `bus.bearing` is not null, apply `transform: rotate({bearing}deg)` — but only to an arrow indicator, not the circle itself

**Popup content:**
- Route number (bold) + vehicle ID
- Delay status with color coding:
  - `delaySeconds <= 0`: green text "On time" or "Early" — use `text-status-ontime` class
  - `delaySeconds > 0 && delaySeconds <= 300`: amber text showing minutes — use `text-status-delayed` class
  - `delaySeconds > 300`: red text showing minutes — use `text-status-critical` class
- Next stop name (if not null)
- Use `useTranslations("routes.map")` for labels

**Event handling:**
- On marker click: call `onSelect(bus.routeId)` to sync with table selection
- On popup open: Leaflet handles this automatically

**Opacity:**
- When a route IS selected (`isHighlighted` could be true or false for different markers):
  - If `isHighlighted === true`: full opacity (1.0)
  - If `isHighlighted === false` AND some route is selected: dimmed (opacity 0.4)
- When NO route is selected: all markers at full opacity (1.0)
- The parent `RouteMap` will handle the logic of whether any route is selected; `BusMarker` just uses `isHighlighted` and an `isDimmed` prop or similar approach

Wait — simplify: use TWO props instead:
```typescript
interface BusMarkerProps {
  bus: BusPosition;
  isHighlighted: boolean;  // true = this bus's route is selected
  isDimmed: boolean;        // true = another route is selected (not this one)
  onSelect: (routeId: string) => void;
}
```

- `isHighlighted && !isDimmed`: large marker, full opacity
- `!isHighlighted && isDimmed`: small marker, 0.4 opacity
- `!isHighlighted && !isDimmed`: normal marker, full opacity (no selection active)

**CRITICAL — Leaflet divIcon pattern:**
The `L.divIcon` `html` property must be a string of HTML, not JSX. Build the HTML string manually:

```typescript
const size = isHighlighted ? 36 : 28;
const icon = L.divIcon({
  className: "", // empty to avoid default leaflet-div-icon styling
  iconSize: [size, size],
  iconAnchor: [size / 2, size / 2],
  popupAnchor: [0, -size / 2],
  html: `<div style="
    width: ${size}px;
    height: ${size}px;
    border-radius: 50%;
    background-color: ${bus.routeColor};
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: ${isHighlighted ? 13 : 11}px;
    font-weight: 700;
    border: 2px solid white;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    opacity: ${isDimmed ? 0.4 : 1};
    transition: all 200ms ease;
    font-family: 'Source Sans 3', system-ui, sans-serif;
  ">${bus.routeShortName}</div>`,
});
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 5: Create RouteMap Component
**File:** `cms/apps/web/src/components/routes/route-map.tsx` (create)
**Action:** CREATE

Create a `'use client'` component that renders the Leaflet map with all bus markers.

**Component specification:**

```typescript
"use client";

import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer } from "react-leaflet";
import { useTranslations } from "next-intl";
import type { BusPosition } from "@/types/route";
import { BusMarker } from "./bus-marker";

interface RouteMapProps {
  buses: BusPosition[];
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
}

export function RouteMap({ buses, selectedRouteId, onSelectRoute }: RouteMapProps) {
  const t = useTranslations("routes.map");
  const hasSelection = selectedRouteId !== null;

  return (
    <div className="relative h-full w-full bg-surface">
      {/* Map title overlay */}
      <div className="absolute left-3 top-3 z-[1000] rounded-md bg-surface-raised/90 px-3 py-1.5 text-sm font-medium shadow-sm backdrop-blur-sm">
        {t("title")} · {buses.length} {t("vehicles")}
      </div>

      <MapContainer
        center={[56.9496, 24.1052]}
        zoom={13}
        className="h-full w-full"
        zoomControl={true}
        attributionControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {buses.map((bus) => (
          <BusMarker
            key={bus.vehicleId}
            bus={bus}
            isHighlighted={selectedRouteId === bus.routeId}
            isDimmed={hasSelection && selectedRouteId !== bus.routeId}
            onSelect={onSelectRoute}
          />
        ))}
      </MapContainer>

      {/* Empty state */}
      {buses.length === 0 && (
        <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-surface/80">
          <p className="text-foreground-muted">{t("noData")}</p>
        </div>
      )}
    </div>
  );
}
```

**Key details:**
- Import `leaflet/dist/leaflet.css` at the TOP of this file — Leaflet needs its CSS
- Map center: Riga `[56.9496, 24.1052]`, zoom 13
- Tile provider: OpenStreetMap (free, no API key)
- z-index `1000` for overlays — Leaflet uses z-indexes up to 999
- Title overlay shows bus count
- No `useEffect`, no `useState` — pure rendering component
- The `MapContainer` props `center` and `zoom` are initial values only (Leaflet caches internally)

**CRITICAL — Leaflet default icon fix:**
Leaflet's default marker icon has broken image paths in webpack/Next.js. Since we use custom `divIcon` in BusMarker, this is NOT an issue. Do NOT import or configure `L.Icon.Default` — it's unnecessary.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: Add i18n Keys — English
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add a `"map"` object inside the existing `"routes"` section. Place it after the last existing key in the `"routes"` object (after `"agencies"`):

```json
"map": {
  "title": "Live Map",
  "loading": "Loading map...",
  "vehicles": "vehicles",
  "delay": "Delay",
  "onTime": "On time",
  "early": "Early",
  "late": "late",
  "nextStop": "Next stop",
  "noData": "No vehicle data available",
  "minutes": "min"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 7: Add i18n Keys — Latvian
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add a matching `"map"` object inside the existing `"routes"` section, same position as English:

```json
"map": {
  "title": "Tiešraides karte",
  "loading": "Ielādē karti...",
  "vehicles": "transportlīdzekļi",
  "delay": "Kavēšanās",
  "onTime": "Laikā",
  "early": "Agrāk",
  "late": "kavējas",
  "nextStop": "Nākamā pietura",
  "noData": "Nav transportlīdzekļu datu",
  "minutes": "min"
}
```

**IMPORTANT:** Latvian diacritics (š, ā, ē, ī, ū, ņ) are correct Unicode for Latvian text — NOT ambiguous. RUF001 only flags EN DASH and similar.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 8: Update Routes Page Layout
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` (modify)
**Action:** UPDATE

This is the most complex task. Read the file first, then make these changes:

#### 8a. Add imports at the top of the file

Add these imports alongside the existing ones:

```typescript
import dynamic from "next/dynamic";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { Skeleton } from "@/components/ui/skeleton";
import { MOCK_BUS_POSITIONS } from "@/lib/mock-bus-positions";
```

#### 8b. Add dynamic map import (BELOW the regular imports, ABOVE the component)

```typescript
function MapSkeleton() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-surface">
      <div className="flex flex-col items-center gap-2">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-4 w-24" />
      </div>
    </div>
  );
}

const RouteMap = dynamic(
  () => import("@/components/routes/route-map").then((m) => ({ default: m.RouteMap })),
  { ssr: false, loading: () => <MapSkeleton /> }
);
```

**CRITICAL:** `MapSkeleton` is defined at MODULE SCOPE (not inside RoutesPage). This avoids the React 19 anti-pattern of component definitions inside components. The `dynamic()` call is also at module scope.

#### 8c. Transform the 3-panel layout to resizable panels

Find this JSX block (the content area container, approximately lines 170-193):

```tsx
<div className="flex min-h-0 flex-1 overflow-hidden rounded-lg border border-border">
  <RouteFilters
    search={search}
    onSearchChange={setSearch}
    typeFilter={typeFilter}
    onTypeFilterChange={setTypeFilter}
    statusFilter={statusFilter}
    onStatusFilterChange={setStatusFilter}
    resultCount={filtered.length}
  />

  <RouteTable
    routes={filtered}
    selectedRouteId={selectedRouteId}
    onSelectRoute={handleSelectRoute}
    onEditRoute={handleEdit}
    onDeleteRoute={handleDeleteRequest}
    onDuplicateRoute={handleDuplicate}
    isReadOnly={IS_READ_ONLY}
  />
</div>
```

Replace with:

```tsx
<ResizablePanelGroup
  direction="horizontal"
  className="min-h-0 flex-1 overflow-hidden rounded-lg border border-border"
>
  <ResizablePanel defaultSize={60} minSize={40}>
    <div className="flex h-full">
      <RouteFilters
        search={search}
        onSearchChange={setSearch}
        typeFilter={typeFilter}
        onTypeFilterChange={setTypeFilter}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        resultCount={filtered.length}
      />

      <RouteTable
        routes={filtered}
        selectedRouteId={selectedRouteId}
        onSelectRoute={handleSelectRoute}
        onEditRoute={handleEdit}
        onDeleteRoute={handleDeleteRequest}
        onDuplicateRoute={handleDuplicate}
        isReadOnly={IS_READ_ONLY}
      />
    </div>
  </ResizablePanel>

  <ResizableHandle withHandle />

  <ResizablePanel defaultSize={40} minSize={25}>
    <RouteMap
      buses={MOCK_BUS_POSITIONS}
      selectedRouteId={selectedRouteId}
      onSelectRoute={handleSelectRoute}
    />
  </ResizablePanel>
</ResizablePanelGroup>
```

**Key details:**
- `defaultSize={60}` / `defaultSize={40}` — 60/40 split (table dominant)
- `minSize={40}` on left panel — table never smaller than 40%
- `minSize={25}` on right panel — map never smaller than 25%
- `withHandle` on ResizableHandle — shows the drag grip icon
- `MOCK_BUS_POSITIONS` imported from mock data file
- `selectedRouteId` and `handleSelectRoute` are REUSED from existing state — route selection syncs bidirectionally between table and map
- The existing `<div className="flex h-full">` wrapping Filters+Table ensures they remain in a horizontal flex inside the left panel

#### 8d. Do NOT change any other part of the page

- Sheet overlays (RouteDetail, RouteForm, DeleteRouteDialog) remain unchanged
- Header section remains unchanged
- State management remains unchanged — `selectedRouteId` + `handleSelectRoute` already exist and work for the map too
- RBAC logic remains unchanged

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 9: Fix Leaflet CSS for Next.js (if needed)
**File:** `cms/apps/web/next.config.ts` (modify — ONLY if build fails)
**Action:** CONDITIONAL UPDATE

If the build in Task 8 fails with CSS import errors from `leaflet/dist/leaflet.css`, add Leaflet to `transpilePackages` in `next.config.ts`:

```typescript
const nextConfig: NextConfig = {
  transpilePackages: ["leaflet", "react-leaflet"],
};
```

This is only needed if Next.js can't resolve the CSS from node_modules. The `dynamic()` with `ssr: false` should handle most cases.

**If build passes in Task 8, skip this task entirely.**

---

## Final Validation (3-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: TypeScript**
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

## Post-Implementation Checks

- [ ] Map renders on the right side of the routes page at `/lv/routes`
- [ ] ~30 bus markers visible on the map, scattered across Riga
- [ ] Markers are colored circles with route short names inside
- [ ] Resize handle between table and map drags smoothly
- [ ] Clicking a route row in the table highlights its buses on the map (other buses dim to 0.4 opacity)
- [ ] Clicking a bus marker on the map selects its route in the table
- [ ] Clicking the same route again deselects (all markers return to full opacity)
- [ ] Map popup shows route number, vehicle ID, delay status, and next stop
- [ ] Delay colors: green (on-time/early), amber (1-5 min late), red (>5 min late)
- [ ] i18n: Map title shows "Live Map" in English, "Tiešraides karte" in Latvian
- [ ] No hardcoded colors — status colors use semantic tokens
- [ ] No SSR errors — map loads client-side only via dynamic import
- [ ] Existing route table functionality unchanged (filters, sorting, pagination, CRUD sheets)

## Acceptance Criteria

This feature is complete when:
- [ ] Resizable map panel visible on routes page with mock bus data
- [ ] Bidirectional route selection sync between table and map
- [ ] Both languages have complete translations
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing routes page functionality
- [ ] Ready for `/commit`
