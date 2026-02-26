# Plan: Stop Management Page

## Feature Metadata
**Feature Type**: New Page
**Estimated Complexity**: High
**Route**: `/[locale]/(dashboard)/stops`
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer (viewer is read-only)

## Feature Description

The Stop Management page provides a CMS interface for managing transit stops and stations. It combines a filterable, paginated data table with an interactive Leaflet map showing stop locations. Users can create, edit, and delete stops through Sheet-based forms, view stop details in a side panel, and visually place stops on the map.

Data comes from the existing backend API at `/api/v1/stops/` (6 endpoints: list, nearby, get, create, update, delete). The page follows the same layout pattern as the Routes page — a ResizablePanelGroup with table on the left and map on the right (desktop), switching to a Tab layout on mobile.

Viewers see a read-only table and map. Admins, dispatchers, and editors can create, edit, and delete stops. The GTFS Stop ID field is readonly during editing to prevent accidental corruption of GTFS references.

## Design System

### Master Rules (from MASTER.md)
- Typography: Lexend headings, Source Sans 3 body, JetBrains Mono for GTFS IDs
- Colors: Navy primary (#0F172A), Blue CTA (#0369A1), Slate background (#F8FAFC)
- Spacing: Use compact dashboard tokens (--spacing-page, --spacing-grid, --spacing-card)
- Shadows: Cards use --shadow-md, modals --shadow-xl
- No hardcoded colors — all via semantic tokens from tokens.css
- 8px border-radius on inputs, 12px on cards
- WCAG compliant: 4.5:1 contrast, visible focus states, 44x44px touch targets
- No emojis as icons — use Lucide React

### Page Override
None exists. No override needed — this page follows the Routes page pattern closely.

### Tokens Used
- `text-foreground`, `text-foreground-muted` — text colors
- `bg-surface`, `bg-background` — backgrounds
- `border-border`, `border-border-subtle` — borders
- `text-status-ontime` — active badge (green)
- `text-status-delayed` — inactive badge (amber)
- `text-status-critical` — delete button/badge (red)
- `bg-selected-bg` — selected table row highlight
- `bg-filter-active-bg`, `text-filter-active-text` — active filter toggle state
- `p-(--spacing-page)` — 16px page padding
- `gap-(--spacing-grid)` — 12px grid gaps
- `p-(--spacing-card)` — 12px card internal padding
- `gap-(--spacing-inline)` — 6px icon-to-text gaps
- `gap-(--spacing-tight)` — 4px micro gaps

## Components Needed

### Existing (shadcn/ui — already installed)
- `Button` — create/edit/delete actions
- `Table` — stop data table
- `Sheet` — detail panel + form panel + mobile filter sheet
- `Dialog` — delete confirmation
- `Input` — text and number inputs in form
- `Label` — form field labels
- `Textarea` — description field
- `Select` — location_type, wheelchair_boarding dropdowns
- `Switch` — is_active toggle (edit mode only)
- `Badge` — status, location type, wheelchair indicators
- `Tabs` — mobile table/map toggle
- `Pagination` — table pagination
- `Skeleton` — map loading placeholder
- `ScrollArea` — detail panel content
- `Separator` — visual dividers
- `Tooltip` — action button hints
- Resizable panels — `ResizablePanelGroup`, `ResizablePanel`, `ResizableHandle`

### New shadcn/ui to Install
None — all needed components are already installed.

### Custom Components to Create
- `StopFilters` at `cms/apps/web/src/components/stops/stop-filters.tsx` — search + status + type filters
- `StopTable` at `cms/apps/web/src/components/stops/stop-table.tsx` — paginated data table
- `StopDetail` at `cms/apps/web/src/components/stops/stop-detail.tsx` — read-only detail sheet
- `StopForm` at `cms/apps/web/src/components/stops/stop-form.tsx` — create/edit form sheet
- `DeleteStopDialog` at `cms/apps/web/src/components/stops/delete-stop-dialog.tsx` — confirmation dialog
- `StopMap` at `cms/apps/web/src/components/stops/stop-map.tsx` — Leaflet map with stop markers

### New Utility Files
- `cms/apps/web/src/types/stop.ts` — TypeScript interfaces
- `cms/apps/web/src/lib/stops-client.ts` — API client functions

## i18n Keys

The `nav.stops` key already exists in both locales ("Stops" / "Pieturas"). Add a `stops` section for page-specific keys.

### English (`en.json`) — add `"stops"` section
```json
{
  "stops": {
    "title": "Stop Management",
    "description": "Manage transit stops and stations",
    "search": "Search stops...",
    "filters": {
      "allStatuses": "All Statuses",
      "active": "Active",
      "inactive": "Inactive",
      "allTypes": "All Types",
      "stop": "Stop",
      "station": "Station",
      "status": "Status",
      "locationType": "Location Type"
    },
    "table": {
      "name": "Name",
      "gtfsId": "GTFS ID",
      "location": "Location",
      "type": "Type",
      "wheelchair": "Wheelchair",
      "status": "Status",
      "actions": "Actions",
      "noResults": "No stops found",
      "noResultsDescription": "Create your first stop to get started.",
      "showing": "Showing {from}-{to} of {total}"
    },
    "detail": {
      "stopName": "Stop Name",
      "gtfsStopId": "GTFS Stop ID",
      "description": "Description",
      "locationType": "Location Type",
      "coordinates": "Coordinates",
      "latitude": "Latitude",
      "longitude": "Longitude",
      "wheelchairBoarding": "Wheelchair Boarding",
      "parentStation": "Parent Station",
      "isActive": "Active",
      "createdAt": "Created",
      "updatedAt": "Updated"
    },
    "locationTypes": {
      "0": "Stop",
      "1": "Station",
      "2": "Entrance/Exit",
      "3": "Generic Node",
      "4": "Boarding Area"
    },
    "wheelchairOptions": {
      "0": "Unknown",
      "1": "Accessible",
      "2": "Not Accessible"
    },
    "actions": {
      "create": "New Stop",
      "edit": "Edit",
      "delete": "Delete",
      "save": "Save",
      "cancel": "Cancel",
      "close": "Close"
    },
    "form": {
      "createTitle": "Create New Stop",
      "editTitle": "Edit Stop",
      "stopNamePlaceholder": "e.g., Brivibas iela",
      "gtfsStopIdPlaceholder": "e.g., 0001",
      "descriptionPlaceholder": "Stop description...",
      "latitudePlaceholder": "56.9496",
      "longitudePlaceholder": "24.1052",
      "required": "Required field",
      "gtfsIdReadonly": "GTFS ID cannot be changed after creation"
    },
    "delete": {
      "title": "Delete Stop",
      "confirmation": "Are you sure you want to delete stop \"{name}\"?",
      "warning": "This action cannot be undone.",
      "confirm": "Delete",
      "cancel": "Cancel"
    },
    "toast": {
      "created": "Stop created successfully",
      "updated": "Stop updated successfully",
      "deleted": "Stop deleted",
      "createError": "Failed to create stop",
      "updateError": "Failed to update stop",
      "deleteError": "Failed to delete stop"
    },
    "map": {
      "title": "Stop Map",
      "stops": "stops",
      "noData": "No stops to display",
      "clickStop": "Click a stop to view details"
    },
    "mobile": {
      "tableTab": "Table",
      "mapTab": "Map",
      "showFilters": "Filters"
    }
  }
}
```

### Latvian (`lv.json`) — add `"stops"` section
```json
{
  "stops": {
    "title": "Pieturvietu parvaldiba",
    "description": "Parvaldiet tranzita pieturas un stacijas",
    "search": "Meklet pieturas...",
    "filters": {
      "allStatuses": "Visi statusi",
      "active": "Aktivs",
      "inactive": "Neaktivs",
      "allTypes": "Visi veidi",
      "stop": "Pietura",
      "station": "Stacija",
      "status": "Statuss",
      "locationType": "Atrasanas vietas tips"
    },
    "table": {
      "name": "Nosaukums",
      "gtfsId": "GTFS ID",
      "location": "Atrasanas vieta",
      "type": "Tips",
      "wheelchair": "Ratinkresls",
      "status": "Statuss",
      "actions": "Darbibas",
      "noResults": "Pieturas nav atrastas",
      "noResultsDescription": "Izveidojiet pirmo pieturu, lai saktu.",
      "showing": "Rada {from}-{to} no {total}"
    },
    "detail": {
      "stopName": "Pieturas nosaukums",
      "gtfsStopId": "GTFS pieturas ID",
      "description": "Apraksts",
      "locationType": "Atrasanas vietas tips",
      "coordinates": "Koordinatas",
      "latitude": "Platums",
      "longitude": "Garums",
      "wheelchairBoarding": "Ratinkresla piekluve",
      "parentStation": "Vecaka stacija",
      "isActive": "Aktivs",
      "createdAt": "Izveidots",
      "updatedAt": "Atjauninats"
    },
    "locationTypes": {
      "0": "Pietura",
      "1": "Stacija",
      "2": "Ieeja/Izeja",
      "3": "Visparigs mezgls",
      "4": "Iekapsanas zona"
    },
    "wheelchairOptions": {
      "0": "Nezinams",
      "1": "Pieejams",
      "2": "Nav pieejams"
    },
    "actions": {
      "create": "Jauna pietura",
      "edit": "Rediget",
      "delete": "Dzest",
      "save": "Saglabat",
      "cancel": "Atcelt",
      "close": "Aizvert"
    },
    "form": {
      "createTitle": "Izveidot jaunu pieturu",
      "editTitle": "Rediget pieturu",
      "stopNamePlaceholder": "piem., Brivibas iela",
      "gtfsStopIdPlaceholder": "piem., 0001",
      "descriptionPlaceholder": "Pieturas apraksts...",
      "latitudePlaceholder": "56.9496",
      "longitudePlaceholder": "24.1052",
      "required": "Obligats lauks",
      "gtfsIdReadonly": "GTFS ID nevar mainit pec izveidosanas"
    },
    "delete": {
      "title": "Dzest pieturu",
      "confirmation": "Vai tiesam velaties dzest pieturu \"{name}\"?",
      "warning": "Si darbiba ir neatgriezeniska.",
      "confirm": "Dzest",
      "cancel": "Atcelt"
    },
    "toast": {
      "created": "Pietura veiksmigi izveidota",
      "updated": "Pietura veiksmigi atjauninata",
      "deleted": "Pietura dzesta",
      "createError": "Pieturas izveide neizdevas",
      "updateError": "Pieturas atjauninasana neizdevas",
      "deleteError": "Dzesana neizdevas"
    },
    "map": {
      "title": "Pieturvietu karte",
      "stops": "pieturas",
      "noData": "Nav radamo pieturvietu",
      "clickStop": "Noklikskiniet uz pieturas, lai skatitu informaciju"
    },
    "mobile": {
      "tableTab": "Tabula",
      "mapTab": "Karte",
      "showFilters": "Filtri"
    }
  }
}
```

**NOTE on diacritics**: The Latvian translations above use ASCII-safe characters. The executing agent MUST verify and add proper Latvian diacritics (a/e/i/u with macrons, c/g/k/l/n/s/z with cedillas/carons) by comparing with the existing `lv.json` patterns. Key diacritics: pieturvietu parvaldiba -> Pieturvietu p&#257;rvald&#299;ba, Meklet -> Mekl&#275;t, Aktivs -> Akt&#299;vs, etc. Follow the diacritics style established in the existing lv.json file.

## Data Fetching

### API Endpoints (backend already implemented)
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/stops/?page=1&page_size=20&search=&active_only=true` | List stops (paginated) |
| GET | `/api/v1/stops/nearby?latitude=56.9&longitude=24.1&radius_meters=500` | Nearby stops |
| GET | `/api/v1/stops/{id}` | Get single stop |
| POST | `/api/v1/stops/` | Create stop |
| PATCH | `/api/v1/stops/{id}` | Update stop (partial) |
| DELETE | `/api/v1/stops/{id}` | Delete stop (returns 204) |

### Client-Side Data Loading
All data is fetched client-side (same as documents page pattern):
- `fetchStops()` on mount and when filters/page change
- `createStop()`, `updateStop()`, `deleteStop()` with toast feedback
- No server-side data fetching — the page is `"use client"`

### Loading States
- Initial load: "Loading..." text in table area (same as documents page)
- Map: `Skeleton` component while dynamic import loads

## RBAC Integration

### Middleware Matcher
**No change needed.** `/stops` is already in the middleware matcher:
```
"/(lv|en)/(routes|stops|schedules|gtfs|users|chat|documents)/:path*"
```

### Role Permissions
All four roles can access the page. Write operations (create/edit/delete) are hidden from `viewer` role using the `IS_READ_ONLY` guard pattern from the routes page.

## Sidebar Navigation

**No new entry needed.** The stops nav item already exists in `app-sidebar.tsx` but is disabled:
```ts
{ key: "stops", href: "/stops", enabled: false }
```
Change `enabled: false` to `enabled: true`. The `nav.stops` i18n key already exists.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules
- `cms/apps/web/CLAUDE.md` — Frontend-specific rules and React 19 anti-patterns

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Map + table + CRUD layout pattern
- `cms/apps/web/src/components/routes/route-table.tsx` — Table with responsive columns
- `cms/apps/web/src/components/routes/route-filters.tsx` — Filter bar with ToggleGroup
- `cms/apps/web/src/components/routes/route-form.tsx` — CRUD form in Sheet
- `cms/apps/web/src/components/routes/route-detail.tsx` — Detail panel in Sheet
- `cms/apps/web/src/components/routes/route-map.tsx` — Leaflet map with markers
- `cms/apps/web/src/components/routes/delete-route-dialog.tsx` — Delete confirmation
- `cms/apps/web/src/app/[locale]/(dashboard)/documents/page.tsx` — Real API integration pattern
- `cms/apps/web/src/lib/documents-client.ts` — API client pattern

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add Latvian translations
- `cms/apps/web/messages/en.json` — Add English translations
- `cms/apps/web/src/components/app-sidebar.tsx` — Enable stops nav item

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on StopForm to force remount with new state
- **No component definitions inside components** — extract StopFilters, StopTable, StopMap etc. to separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **`const USER_ROLE: string = "admin"`** — must have explicit `string` type annotation (not inferred literal)
- **Hook ordering**: `useMemo`/`useCallback` MUST come AFTER their dependencies in the component body
- **Number input handling**: `parseFloat(value)` can return `NaN` — always guard: `const parsed = parseFloat(v); return isNaN(parsed) ? null : parsed;`
- **Latvian diacritics**: Never use EN DASH (U+2013) in i18n values. Use HYPHEN-MINUS (U+002D). Verify all Latvian text has proper diacritics.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Create TypeScript Types
**File:** `cms/apps/web/src/types/stop.ts` (create)
**Action:** CREATE

Define interfaces matching the backend schemas in `app/stops/schemas.py`:

```ts
export interface Stop {
  id: number;
  stop_name: string;
  gtfs_stop_id: string;
  stop_lat: number | null;
  stop_lon: number | null;
  stop_desc: string | null;
  location_type: number;
  parent_station_id: number | null;
  wheelchair_boarding: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StopCreate {
  stop_name: string;
  gtfs_stop_id: string;
  stop_lat?: number | null;
  stop_lon?: number | null;
  stop_desc?: string | null;
  location_type?: number;
  parent_station_id?: number | null;
  wheelchair_boarding?: number;
}

export interface StopUpdate {
  stop_name?: string;
  gtfs_stop_id?: string;
  stop_lat?: number | null;
  stop_lon?: number | null;
  stop_desc?: string | null;
  location_type?: number;
  parent_station_id?: number | null;
  wheelchair_boarding?: number;
  is_active?: boolean;
}

export interface PaginatedStops {
  items: Stop[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface NearbyParams {
  latitude: number;
  longitude: number;
  radius_meters?: number;
  limit?: number;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: Create API Client
**File:** `cms/apps/web/src/lib/stops-client.ts` (create)
**Action:** CREATE

Follow the `documents-client.ts` pattern. Create functions:
- `fetchStops(params: { page?: number; page_size?: number; search?: string; active_only?: boolean })` -> `PaginatedStops`
- `fetchStop(id: number)` -> `Stop`
- `createStop(data: StopCreate)` -> `Stop`
- `updateStop(id: number, data: StopUpdate)` -> `Stop`
- `deleteStop(id: number)` -> `void`
- `fetchNearbyStops(params: NearbyParams)` -> `Stop[]`

Use `process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123"` as base URL. All functions use `fetch()` with proper error handling (throw on non-ok response). PATCH for update, DELETE returns 204.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 3: Add i18n Keys (English)
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add the complete `"stops"` section from the i18n Keys section above. Insert alphabetically among the existing top-level keys.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 4: Add i18n Keys (Latvian)
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add the complete `"stops"` section with proper Latvian diacritics. Compare with existing Latvian text in the file to match diacritics style. Key corrections from ASCII to proper Latvian:
- parvaldiba -> p&#257;rvald&#299;ba
- Meklet -> Mekl&#275;t
- Aktivs -> Akt&#299;vs
- Atrasanas -> Atra&#353;an&#257;s
- Ratinkresls -> Rati&#326;kr&#275;sls
- Darbibas -> Darb&#299;bas
- Izveidojiet -> (already correct)
- (etc. — match patterns from existing lv.json entries)

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 5: Create StopFilters Component
**File:** `cms/apps/web/src/components/stops/stop-filters.tsx` (create)
**Action:** CREATE

Follow the `route-filters.tsx` pattern. `"use client"` component with props:
- `search: string`, `onSearchChange: (v: string) => void`
- `statusFilter: string`, `onStatusFilterChange: (v: string) => void`
- `locationTypeFilter: string`, `onLocationTypeFilterChange: (v: string) => void`
- `isReadOnly: boolean`
- `onCreateClick: () => void`

Layout: horizontal bar with search Input, ToggleGroup for status (All/Active/Inactive), ToggleGroup for location type (All/Stop/Station), and "New Stop" Button (hidden if isReadOnly). Use `useTranslations("stops")` for labels. Use semantic tokens, not hardcoded colors.

Mobile: wrap in a Sheet triggered by a filter icon button (visible only on small screens).

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: Create StopTable Component
**File:** `cms/apps/web/src/components/stops/stop-table.tsx` (create)
**Action:** CREATE

Follow `route-table.tsx` and `document-table.tsx` patterns. `"use client"` component with props:
- `stops: Stop[]`, `total: number`, `page: number`, `pageSize: number`
- `onPageChange: (page: number) => void`
- `selectedStopId: number | null`, `onSelectStop: (stop: Stop) => void`
- `onEditStop: (stop: Stop) => void`, `onDeleteStop: (stop: Stop) => void`
- `isReadOnly: boolean`, `isLoading: boolean`

Columns: Name (always), GTFS ID (sm+), Location lat/lon (md+), Type badge (lg+), Wheelchair badge (lg+), Status badge (always), Actions dropdown (always, hidden if isReadOnly).

Selected row gets `bg-selected-bg` highlight. Clicking a row calls `onSelectStop`. Empty state with `noResults` message. Loading state with "Loading..." text. Pagination at bottom using the Pagination component.

Format coordinates as `{lat.toFixed(4)}, {lon.toFixed(4)}` or show dash if null.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: Create StopDetail Component
**File:** `cms/apps/web/src/components/stops/stop-detail.tsx` (create)
**Action:** CREATE

Follow `route-detail.tsx` pattern. A Sheet (side="right") showing read-only stop details:
- Stop name as title
- GTFS Stop ID in mono font
- Description (or dash if null)
- Location type badge
- Coordinates (lat, lon) or "Not set"
- Wheelchair boarding badge
- Active status badge
- Parent station ID (or dash)
- Created/updated timestamps formatted with locale-appropriate date format
- Edit and Delete buttons at bottom (hidden if isReadOnly)

Props: `stop: Stop | null`, `open: boolean`, `onOpenChange: (v: boolean) => void`, `onEdit: () => void`, `onDelete: () => void`, `isReadOnly: boolean`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 8: Create StopForm Component
**File:** `cms/apps/web/src/components/stops/stop-form.tsx` (create)
**Action:** CREATE

Follow `route-form.tsx` pattern. A Sheet (side="right") with a form for creating/editing stops.

Props: `mode: "create" | "edit"`, `stop: Stop | null` (for edit pre-fill), `open: boolean`, `onOpenChange: (v: boolean) => void`, `onSubmit: (data: StopCreate | StopUpdate) => void`.

Form fields (from backend StopCreate/StopUpdate schemas):
- `stop_name` — Input, required, max 200
- `gtfs_stop_id` — Input, required, max 50. **Readonly in edit mode** with tooltip explaining why
- `stop_desc` — Textarea, optional, max 500
- `stop_lat` — Input type="number", optional, step="any", range -90 to 90
- `stop_lon` — Input type="number", optional, step="any", range -180 to 180
- `location_type` — Select with options 0-4 (use i18n keys `locationTypes.0` through `locationTypes.4`)
- `parent_station_id` — Input type="number", optional
- `wheelchair_boarding` — Select with options 0-2 (use i18n keys `wheelchairOptions.0` through `wheelchairOptions.2`)
- `is_active` — Switch, **only shown in edit mode** (create always sets true)

Use local state for form fields. Initialize from `stop` prop in create mode vs edit mode. Parse lat/lon with NaN guard: `const parsed = parseFloat(v); return isNaN(parsed) ? null : parsed;`

CRITICAL: Use `key` prop on the Sheet content to reset form state when stop changes — do NOT use useEffect+setState for form reset.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 9: Create DeleteStopDialog Component
**File:** `cms/apps/web/src/components/stops/delete-stop-dialog.tsx` (create)
**Action:** CREATE

Follow `delete-route-dialog.tsx` pattern exactly. Dialog with:
- Title from i18n `stops.delete.title`
- Confirmation message with stop name interpolated
- Warning text
- Cancel + Delete buttons (Delete in destructive variant)

Props: `stop: Stop | null`, `open: boolean`, `onOpenChange: (v: boolean) => void`, `onConfirm: () => void`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Create StopMap Component
**File:** `cms/apps/web/src/components/stops/stop-map.tsx` (create)
**Action:** CREATE

Follow `route-map.tsx` pattern but simplified (no live polling, no vehicle markers). `"use client"` component.

Props: `stops: Stop[]`, `selectedStopId: number | null`, `onSelectStop: (stop: Stop) => void`.

Implementation:
- `MapContainer` centered on Riga `[56.9496, 24.1052]`, zoom 12
- OpenStreetMap `TileLayer`
- `CircleMarker` for each stop with valid lat/lon
  - Default: `fillColor` using CTA blue (#0369A1), radius 6
  - Selected: `fillColor` using primary navy (#0F172A), radius 8
- `Popup` on each marker showing stop name and GTFS ID
- Click handler calls `onSelectStop`
- `useEffect` to fly to selected stop when `selectedStopId` changes (use `map.flyTo`)
- Do NOT use `useEffect` + `setState` — the flyTo is an imperative map action, not state

Must NOT be imported directly in page.tsx — use `dynamic()` with `ssr: false` in the page.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 11: Create Stops Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/stops/page.tsx` (create)
**Action:** CREATE

`"use client"` page component combining all stop components. Follow the Routes page layout pattern with real API data (like Documents page).

**State architecture:**
```
// Data
stops, totalItems, page, isLoading
// Filters
search, statusFilter, locationTypeFilter
// UI
selectedStop, detailOpen, formOpen, formMode, formKey, deleteOpen, deleteTarget
// Auth
USER_ROLE: string = "admin", IS_READ_ONLY
```

**Data loading:** `loadStops()` function called on mount and when page/search/statusFilter/locationTypeFilter change. Uses `fetchStops()` from stops-client. Debounce search input (300ms setTimeout pattern from documents page).

**Layout (desktop):** ResizablePanelGroup horizontal — left panel (60%) has StopFilters + StopTable, right panel (40%) has StopMap loaded via `dynamic()` with `ssr: false`.

**Layout (mobile):** Tabs with "Table" and "Map" tabs, switching between StopFilters+StopTable and StopMap.

**CRUD flow:**
- Create: StopForm(mode="create") -> `createStop()` -> toast.success -> reload
- Edit: StopForm(mode="edit", stop=selectedStop) -> `updateStop()` -> toast.success -> reload
- Delete: DeleteStopDialog -> `deleteStop()` -> toast.success -> reload
- All errors: toast.error with i18n message

**Map integration:**
- Pass loaded stops to StopMap
- `selectedStopId` syncs between table and map
- Clicking a map marker or table row opens StopDetail sheet

**Dynamic import for map (CRITICAL for SSR):**
```tsx
const StopMap = dynamic(
  () => import("@/components/stops/stop-map").then((m) => ({ default: m.StopMap })),
  { ssr: false, loading: () => <Skeleton className="h-full w-full rounded-lg" /> },
);
```

**Mobile detection:** Use the `useIsMobile()` hook from `@/hooks/use-mobile` (already exists).

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 12: Enable Sidebar Nav Entry
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify)
**Action:** UPDATE

Find the stops nav item and change `enabled: false` to `enabled: true`:
```ts
{ key: "stops", href: "/stops", enabled: true },
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web build` passes

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

- [ ] Page renders at `/en/stops` and `/lv/stops`
- [ ] i18n keys present in both lv.json and en.json with proper diacritics
- [ ] Sidebar shows "Stops" / "Pieturas" link (enabled)
- [ ] Middleware already allows all 4 roles
- [ ] Table loads stops from backend API with pagination
- [ ] Search filter works (substring match on stop name)
- [ ] Status filter works (active/inactive/all)
- [ ] Location type filter works
- [ ] Map shows stop markers at correct coordinates
- [ ] Clicking a table row selects stop, highlights on map, opens detail
- [ ] Clicking a map marker selects stop, highlights in table, opens detail
- [ ] Create form opens, validates required fields, calls POST API
- [ ] Edit form pre-fills, GTFS ID is readonly, calls PATCH API
- [ ] Delete dialog shows confirmation, calls DELETE API
- [ ] Viewer role sees no create/edit/delete buttons
- [ ] Toast notifications on success and error
- [ ] Mobile layout uses Tabs for table/map switching
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] All interactive elements have proper focus states and ARIA labels

## Acceptance Criteria

This feature is complete when:
- [ ] Page accessible at `/{locale}/stops`
- [ ] RBAC enforced — viewers see read-only, others see full CRUD
- [ ] Both languages have complete translations with proper diacritics
- [ ] Design system rules followed (MASTER.md tokens and patterns)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages (routes, documents, chat, dashboard)
- [ ] Backend API integration works (list, create, update, delete)
- [ ] Map shows stops with selection sync
- [ ] Ready for `/commit`
