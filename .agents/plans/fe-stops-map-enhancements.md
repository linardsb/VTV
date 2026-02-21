# Plan: Stop Map — Interactive Placement & Edit Enhancements

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: `/[locale]/(dashboard)/stops` (existing page)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer (existing — no changes)

## Feature Description

The stops page already has a Leaflet map (`StopMap`) with basic draggable markers and click-to-place. This enhancement adds three capabilities:

1. **Live map-form coordinate sync**: When the form Sheet is open (create or edit), dragging the marker on the map updates the form's lat/lon fields in real-time. Typing coordinates in the form moves the marker on the map. This creates a bidirectional link between map and form.

2. **Persistent editing marker**: When creating a new stop, after clicking the map to place, a draggable "editing marker" remains visible while the form is open — letting the user fine-tune position before saving. When editing an existing stop, the map auto-highlights that stop's marker as the "editing marker".

3. **High-zoom precision**: The map auto-zooms to street level (zoom 18) when entering create or edit mode. The `MapContainer` `maxZoom` is raised to 19 (OpenStreetMap max). When exiting edit mode, the map returns to the previous zoom level.

No new pages, routes, middleware, or sidebar entries. No new packages. This modifies 3 existing files only.

## Design System

### Master Rules (from MASTER.md)
- All colors via semantic tokens from `tokens.css`
- No hardcoded colors in component code (hex in Leaflet `L.divIcon` HTML strings is the one exception since Tailwind classes don't work in raw HTML strings)
- Spacing uses design token scale (`--spacing-*`)
- Transitions: 150-300ms ease

### Page Override
- None exists — no override needed for this enhancement

### Tokens Used
- `--color-foreground`, `--color-foreground-muted` — text
- `--spacing-tight`, `--spacing-grid`, `--spacing-card`, `--spacing-inline` — spacing
- `bg-surface`, `bg-primary`, `text-primary-foreground` — map overlays
- `border-border` — borders

## Components Needed

### Existing (shadcn/ui) — no new installs
- `Sheet` — stop form container (already used)
- `Input` — coordinate fields (already used)
- `Button` — actions (already used)
- `Label` — form labels (already used)

### New shadcn/ui to Install
None.

### Custom Components to Create
None — all changes are modifications to existing components.

## i18n Keys

### Latvian (`lv.json`)
```json
{
  "stops": {
    "map": {
      "zoomHint": "Tuviniet precīzai novietošanai"
    }
  }
}
```

### English (`en.json`)
```json
{
  "stops": {
    "map": {
      "zoomHint": "Zoom in for precise placement"
    }
  }
}
```

## Data Fetching

No changes. The existing `fetchStops`, `createStop`, `updateStop` API calls remain unchanged. The only behavioral change is that drag-while-editing updates form state locally instead of calling the API immediately — the API is called when the form is submitted.

## RBAC Integration

No changes. Existing middleware and role checks remain.

## Sidebar Navigation

No changes. The stops nav entry already exists.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/routes/route-map.tsx` — Reference for map layout style (the user wants the stops map to look like this)
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Reference for how the routes page wires up its map

### Files to Modify
- `cms/apps/web/src/components/stops/stop-map.tsx` — Add editing marker, high zoom, bidirectional coord sync
- `cms/apps/web/src/components/stops/stop-form.tsx` — Accept live coordinate updates from map drag
- `cms/apps/web/src/app/[locale]/(dashboard)/stops/page.tsx` — Wire up map-form coordinate sync
- `cms/apps/web/messages/lv.json` — Add 1 new i18n key
- `cms/apps/web/messages/en.json` — Add 1 new i18n key

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Common violations and their fixes:

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400`, `text-slate-400` | `text-foreground-subtle` |
| `text-white` (on colored bg) | `text-primary-foreground` / `text-destructive-foreground` |
| `bg-blue-600`, `bg-blue-500` | `bg-primary` |
| `bg-red-500` | `bg-destructive` |
| `bg-green-500` | `bg-success` |
| `bg-gray-100`, `bg-slate-100` | `bg-surface-secondary` / `bg-muted` |
| `border-gray-200` | `border-border` |

If unsure, check `cms/packages/ui/src/tokens.css` for the correct semantic token.
Exception: Inline HTML strings (e.g., Leaflet `L.divIcon`) may use hex colors since Tailwind classes don't work there.

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first in the component body.
- **Shared type changes require ripple-effect tasks** — When adding a field to a shared interface, the plan MUST include tasks to update ALL files that construct objects of that type.

See `cms/apps/web/CLAUDE.md` → "React 19 Anti-Patterns" for full examples.

---

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add i18n Keys

**Files:**
- `cms/apps/web/messages/en.json` (modify)
- `cms/apps/web/messages/lv.json` (modify)

**Action:** UPDATE both translation files

In `en.json`, inside `"stops" > "map"`, add after the existing `"dragHint"` key:
```json
"zoomHint": "Zoom in for precise placement"
```

In `lv.json`, inside `"stops" > "map"`, add after the existing `"dragHint"` key:
```json
"zoomHint": "Tuviniet precīzai novietošanai"
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 2: Enhance StopMap Component

**File:** `cms/apps/web/src/components/stops/stop-map.tsx` (modify)
**Action:** UPDATE

Read the full current file before making changes.

#### 2a. Update the `StopMapProps` interface

Add these new props to the existing interface:
```typescript
interface StopMapProps {
  stops: Stop[];
  selectedStopId: number | null;
  onSelectStop: (stop: Stop) => void;
  editable?: boolean;
  onStopMoved?: (stopId: number, lat: number, lon: number) => void;
  placementMode?: boolean;
  onMapClick?: (lat: number, lon: number) => void;
  // NEW props for map-form sync:
  editingStopId?: number | null;        // ID of the stop currently being edited in the form
  editingCoords?: { lat: number; lon: number } | null;  // Live coords from form (for new stop or editing)
  onEditingCoordsChange?: (lat: number, lon: number) => void;  // Fires when editing marker is dragged
}
```

#### 2b. Create a new `ZoomToEditing` helper component

Place this at MODULE scope (not inside StopMap). It zooms the map to the editing marker location at street level.

```typescript
/** Imperatively zoom the map to editing coordinates at street level. */
function ZoomToEditing({
  coords,
  editingStopId,
}: {
  coords: { lat: number; lon: number } | null;
  editingStopId: number | null;
}) {
  const map = useMap();
  const hasZoomed = useRef(false);

  useEffect(() => {
    if (coords && !hasZoomed.current) {
      map.flyTo([coords.lat, coords.lon], 18, { duration: 0.8 });
      hasZoomed.current = true;
    }
    // Reset when exiting edit mode
    if (!coords && !editingStopId) {
      hasZoomed.current = false;
    }
  }, [map, coords, editingStopId]);

  return null;
}
```

Add `useRef` to the existing imports from `react` (it's already imported — verify).

#### 2c. Create a new `EditingMarker` helper component

Place this at MODULE scope. It renders a single draggable marker at the form's current coordinates. This is used for BOTH new stop placement (after clicking the map) and editing an existing stop.

```typescript
/** Draggable marker shown while the form is open for create/edit. */
function EditingMarker({
  coords,
  onDragEnd,
}: {
  coords: { lat: number; lon: number };
  onDragEnd: (lat: number, lon: number) => void;
}) {
  const icon = useMemo(
    () =>
      L.divIcon({
        className: "",
        html: `<div style="
          width:24px;height:24px;
          border-radius:50%;
          background:#0369A1;
          border:3px solid white;
          box-shadow:0 0 0 2px #0369A1, 0 4px 12px rgba(0,0,0,0.4);
          cursor:grab;
          animation: pulse 1.5s ease-in-out infinite;
        "></div>
        <style>
          @keyframes pulse {
            0%, 100% { box-shadow: 0 0 0 2px #0369A1, 0 4px 12px rgba(0,0,0,0.4); }
            50% { box-shadow: 0 0 0 6px rgba(3,105,161,0.3), 0 4px 12px rgba(0,0,0,0.4); }
          }
        </style>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      }),
    [],
  );

  return (
    <Marker
      position={[coords.lat, coords.lon]}
      icon={icon}
      draggable={true}
      eventHandlers={{
        dragend: (e) => {
          const marker = e.target as L.Marker;
          const pos = marker.getLatLng();
          onDragEnd(pos.lat, pos.lng);
        },
      }}
    />
  );
}
```

Add `useMemo` to the existing react imports if not already present (it IS already imported — verify).

#### 2d. Update `MapContainer` props

Change the existing `MapContainer` to increase max zoom and default zoom:

```tsx
<MapContainer
  center={[56.9496, 24.1052]}
  zoom={13}
  maxZoom={19}
  className={`h-full w-full ${placementMode ? "cursor-crosshair" : ""}`}
  zoomControl={true}
  attributionControl={true}
>
```

Changes from current: `zoom` from `12` to `13` (matching routes map), add `maxZoom={19}`.

#### 2e. Add `ZoomToEditing` and `EditingMarker` inside MapContainer

Add these children inside the `<MapContainer>`, after the existing `<MapClickHandler>`:

```tsx
{/* Zoom to editing location */}
{editingCoords && (
  <ZoomToEditing coords={editingCoords} editingStopId={editingStopId ?? null} />
)}

{/* Draggable editing marker (visible during form open) */}
{editingCoords && onEditingCoordsChange && (
  <EditingMarker
    coords={editingCoords}
    onDragEnd={onEditingCoordsChange}
  />
)}
```

#### 2f. Skip rendering the regular marker for the stop being edited

In the `.map()` loop that renders stops, add a guard at the top of the callback to skip the stop being edited (it's rendered separately by `EditingMarker`):

```typescript
{stopsWithCoords.map((stop) => {
  // Skip the stop being edited — it's rendered by EditingMarker
  if (editingStopId === stop.id) return null;

  const isSelected = selectedStopId === stop.id;
  // ... rest unchanged
})}
```

#### 2g. Add zoom hint overlay

Add a zoom hint below the placement hint, shown when editing/creating and zoom is below 16. This requires reading the map zoom level. Instead of using state (which would violate React 19 rules), use a simple ref-based approach. Actually, to keep it simple, show the hint whenever `editingCoords` is truthy and `placementMode` is false — the user will naturally zoom in.

Add this right after the existing placement hint `div`:

```tsx
{/* Drag hint when editing */}
{editingCoords && !placementMode && (
  <div className="absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-lg">
    {t("dragHint")}
  </div>
)}
```

#### 2h. Update the component function signature

Destructure the new props in the `StopMap` function:

```typescript
export function StopMap({
  stops,
  selectedStopId,
  onSelectStop,
  editable = false,
  onStopMoved,
  placementMode = false,
  onMapClick,
  editingStopId,
  editingCoords,
  onEditingCoordsChange,
}: StopMapProps) {
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 3: Enhance StopForm for Live Coordinate Updates

**File:** `cms/apps/web/src/components/stops/stop-form.tsx` (modify)
**Action:** UPDATE

Read the full current file before making changes.

#### 3a. Add `onCoordsChange` callback prop

Update the `StopFormProps` interface:

```typescript
interface StopFormProps {
  mode: "create" | "edit";
  stop: Stop | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: StopCreate | StopUpdate) => void;
  defaultCoords?: { lat: number; lon: number } | null;
  onCoordsChange?: (lat: number, lon: number) => void;  // NEW: notify parent of coord changes
}
```

#### 3b. Destructure the new prop

In the `StopForm` function signature, add `onCoordsChange`:

```typescript
export function StopForm({
  mode,
  stop,
  open,
  onOpenChange,
  onSubmit,
  defaultCoords,
  onCoordsChange,
}: StopFormProps) {
```

#### 3c. Add a `useEffect` to notify parent when coordinates change — BUT use a ref-based approach

We need to notify the parent when the form's lat/lon fields change so the map marker moves. However, we cannot use `setState` in a `useEffect`. Instead, call `onCoordsChange` directly from `updateField` when the field is `stop_lat` or `stop_lon`.

Replace the existing `updateField` function with:

```typescript
function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
  setForm((prev) => {
    const next = { ...prev, [key]: value };
    // Notify parent of coordinate changes for map sync
    if (onCoordsChange && (key === "stop_lat" || key === "stop_lon")) {
      const lat = parseFloat(key === "stop_lat" ? String(value) : next.stop_lat);
      const lon = parseFloat(key === "stop_lon" ? String(value) : next.stop_lon);
      if (!isNaN(lat) && !isNaN(lon)) {
        // Use queueMicrotask to avoid calling during render
        queueMicrotask(() => onCoordsChange(lat, lon));
      }
    }
    return next;
  });
}
```

#### 3d. Accept external coordinate updates from map drag

Add a new prop `externalCoords` that, when changed, updates the form's lat/lon fields. This handles the map-to-form direction (user drags marker → form updates).

Update the interface:

```typescript
interface StopFormProps {
  mode: "create" | "edit";
  stop: Stop | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: StopCreate | StopUpdate) => void;
  defaultCoords?: { lat: number; lon: number } | null;
  onCoordsChange?: (lat: number, lon: number) => void;
  externalCoords?: { lat: number; lon: number } | null;  // NEW: coords from map drag
}
```

Destructure `externalCoords` in the function signature.

Add a `useEffect` that updates the form when `externalCoords` changes. **Note:** This is updating form input fields from an external source (map drag), which is a valid use of `useEffect` for synchronization — it's not "deriving state from props" since the external coords change independently via user interaction on the map:

```typescript
const prevExternalCoords = useRef<{ lat: number; lon: number } | null>(null);

useEffect(() => {
  if (
    externalCoords &&
    (prevExternalCoords.current?.lat !== externalCoords.lat ||
      prevExternalCoords.current?.lon !== externalCoords.lon)
  ) {
    setForm((prev) => ({
      ...prev,
      stop_lat: externalCoords.lat.toFixed(6),
      stop_lon: externalCoords.lon.toFixed(6),
    }));
    prevExternalCoords.current = externalCoords;
  }
}, [externalCoords]);
```

Add `useEffect` and `useRef` to the react imports:

```typescript
import { useState, useEffect, useRef } from "react";
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 4: Wire Up Map-Form Sync in Stops Page

**File:** `cms/apps/web/src/app/[locale]/(dashboard)/stops/page.tsx` (modify)
**Action:** UPDATE

Read the full current file before making changes.

#### 4a. Add editing state variables

Add these state variables after the existing `defaultCoords` state (around line 77):

```typescript
const [editingStopId, setEditingStopId] = useState<number | null>(null);
const [editingCoords, setEditingCoords] = useState<{ lat: number; lon: number } | null>(null);
```

#### 4b. Update `handleCreate`

Replace the existing `handleCreate` callback. The create flow remains: user clicks "New Stop" → `placementMode=true` → user clicks map → `handleMapClick` sets coords and opens form.

No changes needed to `handleCreate` itself — it already sets `placementMode(true)`.

#### 4c. Update `handleMapClick`

Replace the existing `handleMapClick` callback to also set editing state:

```typescript
const handleMapClick = useCallback(
  (lat: number, lon: number) => {
    setDefaultCoords({ lat, lon });
    setEditingCoords({ lat, lon });
    setEditingStopId(null); // New stop, no ID yet
    setPlacementMode(false);
    setFormKey((k) => k + 1);
    setFormOpen(true);
  },
  [],
);
```

#### 4d. Update `handleEdit`

Replace the existing `handleEdit` callback to set editing state and coords:

```typescript
const handleEdit = useCallback(() => {
  if (!selectedStop) return;
  setFormMode("edit");
  setEditingStopId(selectedStop.id);
  setEditingCoords(
    selectedStop.stop_lat !== null && selectedStop.stop_lon !== null
      ? { lat: selectedStop.stop_lat, lon: selectedStop.stop_lon }
      : null,
  );
  setDetailOpen(false);
  setFormKey((k) => k + 1);
  setFormOpen(true);
}, [selectedStop]);
```

#### 4e. Update `handleEditFromTable`

Replace the existing `handleEditFromTable` callback similarly:

```typescript
const handleEditFromTable = useCallback((stop: Stop) => {
  setSelectedStop(stop);
  setFormMode("edit");
  setEditingStopId(stop.id);
  setEditingCoords(
    stop.stop_lat !== null && stop.stop_lon !== null
      ? { lat: stop.stop_lat, lon: stop.stop_lon }
      : null,
  );
  setDetailOpen(false);
  setFormKey((k) => k + 1);
  setFormOpen(true);
}, []);
```

#### 4f. Add `handleEditingCoordsChange` callback

This is called when the user drags the editing marker on the map. Add this new callback after `handleStopMoved`:

```typescript
// Map editing marker dragged — update form coords (NOT the API)
const handleEditingCoordsChange = useCallback(
  (lat: number, lon: number) => {
    setEditingCoords({ lat, lon });
  },
  [],
);
```

#### 4g. Add `handleFormCoordsChange` callback

This is called when the user types coordinates in the form. Add this after `handleEditingCoordsChange`:

```typescript
// Form coordinate fields changed — update map marker
const handleFormCoordsChange = useCallback(
  (lat: number, lon: number) => {
    setEditingCoords({ lat, lon });
  },
  [],
);
```

#### 4h. Clear editing state when form closes

Update the `onOpenChange` callback in the `<StopForm>` JSX. Currently it's:
```tsx
onOpenChange={(open) => {
  setFormOpen(open);
  if (!open) {
    setPlacementMode(false);
    setDefaultCoords(null);
  }
}}
```

Replace with:
```tsx
onOpenChange={(open) => {
  setFormOpen(open);
  if (!open) {
    setPlacementMode(false);
    setDefaultCoords(null);
    setEditingStopId(null);
    setEditingCoords(null);
  }
}}
```

#### 4i. Pass new props to StopMap

In BOTH the desktop (`ResizablePanel`) and mobile (`TabsContent`) `<StopMap>` renders, add the new props:

```tsx
<StopMap
  stops={displayStops}
  selectedStopId={selectedStopId}
  onSelectStop={handleSelectStop}
  editable={!IS_READ_ONLY}
  onStopMoved={handleStopMoved}
  placementMode={placementMode}
  onMapClick={handleMapClick}
  editingStopId={editingStopId}
  editingCoords={editingCoords}
  onEditingCoordsChange={handleEditingCoordsChange}
/>
```

There are TWO `<StopMap>` renders (one in mobile tabs, one in desktop resizable panel). Update BOTH identically.

#### 4j. Pass new props to StopForm

Update the `<StopForm>` render to include the new props:

```tsx
<StopForm
  key={formKey}
  mode={formMode}
  stop={selectedStop}
  open={formOpen}
  onOpenChange={(open) => {
    setFormOpen(open);
    if (!open) {
      setPlacementMode(false);
      setDefaultCoords(null);
      setEditingStopId(null);
      setEditingCoords(null);
    }
  }}
  onSubmit={handleFormSubmit}
  defaultCoords={defaultCoords}
  onCoordsChange={handleFormCoordsChange}
  externalCoords={editingCoords}
/>
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes
- `cd cms && pnpm --filter @vtv/web build` passes

---

### Task 5: Edge Case — Prevent Feedback Loop Between Form and Map

**File:** `cms/apps/web/src/components/stops/stop-form.tsx` (modify)
**Action:** UPDATE

The `onCoordsChange` callback (form → map) and `externalCoords` prop (map → form) could create an infinite loop: form changes → notifies parent → parent updates `editingCoords` → passed back as `externalCoords` → triggers form `useEffect` → notifies parent again.

The `prevExternalCoords` ref in Task 3d already prevents the useEffect from firing when coords haven't actually changed. But we need to make sure `updateField`'s microtask doesn't fire when the change came from `externalCoords`.

Add a ref to track whether the update came from external:

```typescript
const isExternalUpdate = useRef(false);
```

Update the `useEffect` from Task 3d:

```typescript
useEffect(() => {
  if (
    externalCoords &&
    (prevExternalCoords.current?.lat !== externalCoords.lat ||
      prevExternalCoords.current?.lon !== externalCoords.lon)
  ) {
    isExternalUpdate.current = true;
    setForm((prev) => ({
      ...prev,
      stop_lat: externalCoords.lat.toFixed(6),
      stop_lon: externalCoords.lon.toFixed(6),
    }));
    prevExternalCoords.current = externalCoords;
    // Reset after microtask completes
    queueMicrotask(() => {
      isExternalUpdate.current = false;
    });
  }
}, [externalCoords]);
```

Update `updateField` to skip notification when update is external:

```typescript
function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
  setForm((prev) => {
    const next = { ...prev, [key]: value };
    if (
      onCoordsChange &&
      !isExternalUpdate.current &&
      (key === "stop_lat" || key === "stop_lon")
    ) {
      const lat = parseFloat(key === "stop_lat" ? String(value) : next.stop_lat);
      const lon = parseFloat(key === "stop_lon" ? String(value) : next.stop_lon);
      if (!isNaN(lat) && !isNaN(lon)) {
        queueMicrotask(() => onCoordsChange(lat, lon));
      }
    }
    return next;
  });
}
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes
- `cd cms && pnpm --filter @vtv/web build` passes

---

### Task 6: Lint & Build Sweep

**Action:** RUN validation and fix any issues

Run all three validation levels:

```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
cd cms && pnpm --filter @vtv/web build
```

Common issues to watch for:
- Unused imports after refactoring (remove them)
- `useEffect` dependency array warnings (include all dependencies)
- TypeScript errors from new props not passed correctly
- Tailwind primitive color classes (replace with semantic tokens)

Fix any errors before proceeding.

**Per-task validation:**
- All three commands exit 0 with zero errors

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

- [ ] Map zooms to level 18 when editing or creating a stop
- [ ] Dragging the marker on the map updates the form's lat/lon fields in real-time
- [ ] Typing coordinates in the form moves the marker on the map
- [ ] Editing marker has a distinct visual (larger, pulsing, high-contrast)
- [ ] The regular stop marker is hidden while the editing marker is shown
- [ ] When form closes, editing marker disappears and map returns to normal
- [ ] Click-to-place still works (new stop flow)
- [ ] Drag-to-reposition for non-editing stops still works
- [ ] No hardcoded colors — all styling uses semantic tokens (hex in Leaflet divIcon HTML is acceptable)
- [ ] i18n keys present in both lv.json and en.json
- [ ] No feedback loop between map and form coordinate sync
- [ ] maxZoom is 19 on the MapContainer

## Acceptance Criteria

This feature is complete when:
- [ ] Map automatically zooms to street level (18) when entering create or edit mode
- [ ] Bidirectional coordinate sync works between map marker and form fields
- [ ] Editing marker is visually distinct (pulsing, larger) from regular stop markers
- [ ] No regression in existing stop CRUD functionality
- [ ] No regression in existing drag-to-reposition for admin users
- [ ] All validation levels pass (type-check, lint, build)
- [ ] Ready for `/commit`

## Summary of Changes

| File | Action | Changes |
|------|--------|---------|
| `cms/apps/web/messages/en.json` | UPDATE | Add 1 key (`stops.map.zoomHint`) |
| `cms/apps/web/messages/lv.json` | UPDATE | Add 1 key (`stops.map.zoomHint`) |
| `cms/apps/web/src/components/stops/stop-map.tsx` | UPDATE | Add `editingStopId`, `editingCoords`, `onEditingCoordsChange` props; add `ZoomToEditing` and `EditingMarker` helper components; increase `maxZoom` to 19, default zoom to 13; skip regular marker for editing stop |
| `cms/apps/web/src/components/stops/stop-form.tsx` | UPDATE | Add `onCoordsChange` and `externalCoords` props; bidirectional coord sync with feedback loop prevention |
| `cms/apps/web/src/app/[locale]/(dashboard)/stops/page.tsx` | UPDATE | Add `editingStopId` and `editingCoords` state; wire map-form sync callbacks; clear editing state on form close |

**Total: 0 new files, 5 modified files**
