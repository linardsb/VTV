# Plan: Stops Terminus Markers & Direction Display

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: `/[locale]/(dashboard)/stops` (existing page)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer

## Feature Description

Three improvements to the stops management page:

1. **Terminus stops (Galapunkts) with green markers** — Rename `location_type=1` from "Stacija"/"Station" to "Galapunkts"/"Terminus" everywhere in the UI (filters, table badges, detail panel, form). On the map, terminus stops render as green CircleMarkers instead of the default blue, making them visually distinct as route endpoints.

2. **Direction info in table** — Replace the GTFS ID shown below stop names with the direction/description text (`stop_desc` field, e.g., "Uz centru", "Pretējā puse"). When no description exists, show the location type as a subtle badge instead. This makes the table scannable for dispatchers who need to identify stop direction at a glance.

3. **Copyable GTFS ID** — Add a small copy-to-clipboard button next to the GTFS ID in the table's name column. The ID is still accessible but no longer the primary secondary text. Click copies to clipboard and shows a toast confirmation.

## Design System

### Master Rules (from MASTER.md)
- Touch targets: 44x44px minimum for copy buttons
- Transitions: 150-300ms for hover states
- Focus rings: 3px for WCAG AAA compliance
- No hardcoded colors — use semantic tokens

### Page Override
- None exists — no new page override needed (this is an enhancement, not a new page)

### Tokens Used
- `--color-interactive` (existing) — blue, for regular stop markers
- `--color-status-ontime` / `--color-emerald-500` (existing) — green, basis for terminus token
- `--color-foreground-muted` (existing) — secondary text
- `--color-foreground` (existing) — primary text
- `--color-border` (existing) — borders
- New token: `--color-stop-terminus: var(--color-emerald-500)` — semantic green for terminus markers

### New Semantic Token
Add to `cms/packages/ui/src/tokens.css` in Tier 2 (Semantic), near the transit status tokens:

```css
/* Stop location types */
--color-stop-terminus: var(--color-emerald-500);
```

This follows the same pattern as `--color-transport-bus`, `--color-transport-trolleybus`, etc.

## Components Affected

### Existing (modify)
- `StopMap` at `cms/apps/web/src/components/stops/stop-map.tsx` — green markers for terminus
- `StopTable` at `cms/apps/web/src/components/stops/stop-table.tsx` — direction text + copy ID
- `StopDetail` at `cms/apps/web/src/components/stops/stop-detail.tsx` — already works via i18n rename
- `StopFilters` at `cms/apps/web/src/components/stops/stop-filters.tsx` — already works via i18n rename
- `StopForm` at `cms/apps/web/src/components/stops/stop-form.tsx` — already works via i18n rename

### No New Components Needed
- Copy-to-clipboard is a small inline button, not a separate component

### No New shadcn/ui Installations Needed
- Button, Badge, Tooltip already installed

## i18n Keys

### Latvian (`lv.json`) — Changes

```json
{
  "stops": {
    "locationTypes": {
      "1": "Galapunkts"
    },
    "filters": {
      "station": "Galapunkts"
    },
    "table": {
      "copyGtfsId": "Kopēt GTFS ID",
      "copied": "Nokopēts!"
    }
  }
}
```

Changes:
- `stops.locationTypes.1`: "Stacija" → "Galapunkts"
- `stops.filters.station`: "Stacija" → "Galapunkts"
- NEW `stops.table.copyGtfsId`: "Kopēt GTFS ID" (tooltip for copy button)
- NEW `stops.table.copied`: "Nokopēts!" (toast after copying)

### English (`en.json`) — Changes

```json
{
  "stops": {
    "locationTypes": {
      "1": "Terminus"
    },
    "filters": {
      "station": "Terminus"
    },
    "table": {
      "copyGtfsId": "Copy GTFS ID",
      "copied": "Copied!"
    }
  }
}
```

Changes:
- `stops.locationTypes.1`: "Station" → "Terminus"
- `stops.filters.station`: "Station" → "Terminus"
- NEW `stops.table.copyGtfsId`: "Copy GTFS ID"
- NEW `stops.table.copied`: "Copied!"

## Data Model

No changes to TypeScript types or backend schemas. The `Stop` interface already has:
- `location_type: number` — 0=stop, 1=terminus (previously "station")
- `stop_desc: string | null` — direction/description text (e.g., "Uz centru")
- `gtfs_stop_id: string` — GTFS identifier (e.g., "7985")

## RBAC Integration

No changes needed — the stops page RBAC is already configured.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/stops/stop-map.tsx` — Current map marker rendering
- `cms/apps/web/src/components/stops/stop-table.tsx` — Current table row rendering
- `cms/apps/web/src/components/stops/stop-detail.tsx` — Detail panel rendering

### Files to Modify
- `cms/apps/web/messages/lv.json` — Rename + add Latvian translations
- `cms/apps/web/messages/en.json` — Rename + add English translations
- `cms/packages/ui/src/tokens.css` — Add terminus color token
- `cms/apps/web/src/components/stops/stop-map.tsx` — Green markers for terminus
- `cms/apps/web/src/components/stops/stop-table.tsx` — Direction text + copy button

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Common violations and their fixes:

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400`, `text-slate-400` | `text-foreground-subtle` |
| `text-white` (on colored bg) | `text-interactive-foreground` / `text-primary-foreground` |
| `text-blue-*`, `text-red-*`, `text-green-*` | `text-primary`, `text-error`, `text-success` |
| `text-amber-*`, `text-emerald-*`, `text-purple-*` | `text-category-*`, `text-transport-*` |
| `bg-blue-600`, `bg-blue-500` | `bg-primary` or `bg-interactive` |
| `bg-red-500`, `bg-red-600` | `bg-destructive` |
| `bg-red-50` | `bg-error-bg` |
| `bg-green-500`, `bg-emerald-500` | `bg-success` or `bg-status-ontime` |
| `bg-amber-400`, `bg-amber-500` | `bg-category-route-change` or `bg-status-delayed` |
| `bg-purple-600` | `bg-transport-tram` |
| `bg-gray-100`, `bg-slate-100` | `bg-surface` / `bg-muted` |
| `border-gray-200` | `border-border` |
| `border-red-200` | `border-error-border` |

**Exception:** Leaflet `CircleMarker` `pathOptions.fillColor` MUST use raw hex strings because Leaflet renders via SVG/Canvas, not CSS. These hex values should correspond to the semantic token's resolved value. The plan provides the correct hex values below.

**Full semantic token reference** (check `cms/packages/ui/src/tokens.css`):
- **Surface**: `bg-surface`, `bg-surface-raised`, `bg-background`
- **Interactive**: `bg-interactive`, `text-interactive`, `text-interactive-foreground`
- **Error**: `bg-error-bg`, `border-error-border`, `text-error`
- **Status**: `text-status-ontime`, `text-status-delayed`, `text-status-critical`
- **Transport**: `bg-transport-bus`, `bg-transport-trolleybus`, `bg-transport-tram`
- **Calendar**: `bg-category-maintenance`, `bg-category-route-change`, `bg-category-driver-shift`, `bg-category-service-alert`
- **Stop types**: `bg-stop-terminus` (NEW — added in Task 3)

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies**
- **No unused imports** — Ruff/ESLint flags them immediately

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Update Latvian Translations
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

**Read the file first**, then make these exact changes:

1. Change `stops.locationTypes.1` from `"Stacija"` to `"Galapunkts"`
2. Change `stops.filters.station` from `"Stacija"` to `"Galapunkts"`
3. Add `stops.table.copyGtfsId` with value `"Kopēt GTFS ID"` (add after existing `showing` key in the `table` object)
4. Add `stops.table.copied` with value `"Nokopēts!"` (add after `copyGtfsId`)

After changes, the relevant sections should look like:

```json
"locationTypes": {
  "0": "Pietura",
  "1": "Galapunkts",
  "2": "Ieeja/Izeja",
  "3": "Vispārīgs mezgls",
  "4": "Iekāpšanas zona"
},
```

```json
"filters": {
  "allStatuses": "Visi statusi",
  "active": "Aktīvs",
  "inactive": "Neaktīvs",
  "allTypes": "Visi veidi",
  "stop": "Pietura",
  "station": "Galapunkts",
  "status": "Statuss",
  "locationType": "Atrašanās vietas tips"
},
```

```json
"table": {
  "name": "Nosaukums",
  "gtfsId": "GTFS ID",
  "location": "Atrašanās vieta",
  "type": "Tips",
  "wheelchair": "Ratiņkrēsls",
  "status": "Statuss",
  "actions": "Darbības",
  "noResults": "Pieturas nav atrastas",
  "noResultsDescription": "Izveidojiet pirmo pieturu, lai sāktu.",
  "showing": "Rāda {from}-{to} no {total}",
  "copyGtfsId": "Kopēt GTFS ID",
  "copied": "Nokopēts!"
},
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- Verify JSON is valid (no trailing commas, no syntax errors)

---

### Task 2: Update English Translations
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

**Read the file first**, then make these exact changes:

1. Change `stops.locationTypes.1` from `"Station"` to `"Terminus"`
2. Change `stops.filters.station` from `"Station"` to `"Terminus"`
3. Add `stops.table.copyGtfsId` with value `"Copy GTFS ID"` (after `showing`)
4. Add `stops.table.copied` with value `"Copied!"` (after `copyGtfsId`)

After changes, the relevant sections should look like:

```json
"locationTypes": {
  "0": "Stop",
  "1": "Terminus",
  "2": "Entrance/Exit",
  "3": "Generic Node",
  "4": "Boarding Area"
},
```

```json
"filters": {
  "allStatuses": "All Statuses",
  "active": "Active",
  "inactive": "Inactive",
  "allTypes": "All Types",
  "stop": "Stop",
  "station": "Terminus",
  "status": "Status",
  "locationType": "Location Type"
},
```

```json
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
  "showing": "Showing {from}-{to} of {total}",
  "copyGtfsId": "Copy GTFS ID",
  "copied": "Copied!"
},
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- Verify JSON is valid

---

### Task 3: Add Terminus Semantic Token
**File:** `cms/packages/ui/src/tokens.css` (modify)
**Action:** UPDATE

**Read the file first**, then add the terminus token in the Tier 2 semantic tokens section (the `@theme inline` block), after the existing "Route transport types" group and before "Error state":

```css
/* Stop location types */
--color-stop-terminus: var(--color-emerald-500);
```

The insertion point is after line `--color-transport-tram: var(--color-purple-600);` and before `/* Error state */`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web build` passes (ensures CSS is valid)

---

### Task 4: Update Map Markers for Terminus Stops
**File:** `cms/apps/web/src/components/stops/stop-map.tsx` (modify)
**Action:** UPDATE

**Read the file first**, then make these changes:

#### 4a. Define hex constants for marker colors at module scope

Add these constants at the top of the file, after the imports and before the `createEditingIcon` function:

```typescript
/**
 * Marker hex colors — must use raw hex because Leaflet renders via SVG/Canvas.
 * These correspond to semantic tokens in tokens.css:
 * - MARKER_BLUE = --color-interactive = --color-blue-600
 * - MARKER_GREEN = --color-stop-terminus = --color-emerald-500
 * - MARKER_DARK = --color-brand = --color-navy-800
 */
const MARKER_BLUE = "#0369A1";
const MARKER_GREEN = "#16a34a";
const MARKER_DARK = "#0F172A";
```

#### 4b. Update the CircleMarker rendering to use terminus-aware coloring

In the `stopsWithCoords.map()` callback, replace the existing `pathOptions` object. Currently:

```typescript
pathOptions={{
  fillColor: isSelected ? "#0F172A" : "#0369A1",
  color: "#FFFFFF",
  weight: 2,
  opacity: 1,
  fillOpacity: 0.9,
}}
```

Replace with terminus-aware logic:

```typescript
pathOptions={{
  fillColor: isSelected
    ? MARKER_DARK
    : stop.location_type === 1
      ? MARKER_GREEN
      : MARKER_BLUE,
  color: "#FFFFFF",
  weight: 2,
  opacity: 1,
  fillOpacity: 0.9,
}}
```

#### 4c. Add direction info to the Popup

In the `<Popup>` content, add the direction text between the stop name and the GTFS ID. Currently:

```tsx
<Popup>
  <div className="text-sm">
    <p className="font-semibold">{stop.stop_name}</p>
    <p className="font-mono text-xs text-foreground-muted">
      {stop.gtfs_stop_id}
    </p>
    {onEditStop && (
```

Replace with:

```tsx
<Popup>
  <div className="text-sm">
    <p className="font-semibold">{stop.stop_name}</p>
    {stop.stop_desc && (
      <p className="text-xs text-foreground-muted">{stop.stop_desc}</p>
    )}
    <p className="font-mono text-xs text-foreground-muted">
      {stop.gtfs_stop_id}
    </p>
    {onEditStop && (
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 5: Update Table to Show Direction and Copyable GTFS ID
**File:** `cms/apps/web/src/components/stops/stop-table.tsx` (modify)
**Action:** UPDATE

**Read the file first**, then make these changes:

#### 5a. Add imports

Add `Copy, Check` to the lucide-react import and `toast` from sonner. Add `useCallback, useState` from react:

Current import:
```typescript
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
```

Replace with:
```typescript
import { Copy, Check, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
```

Add at the top of the file with other imports:
```typescript
import { useCallback, useState } from "react";
import { toast } from "sonner";
```

#### 5b. Create a CopyGtfsButton component at MODULE SCOPE

Add this component OUTSIDE of StopTable, after the imports and before the `StopTable` function. This avoids the React 19 "no component definitions inside components" rule:

```tsx
function CopyGtfsButton({ gtfsId, label, copiedLabel }: { gtfsId: string; label: string; copiedLabel: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      void navigator.clipboard.writeText(gtfsId).then(() => {
        setCopied(true);
        toast.success(copiedLabel);
        setTimeout(() => setCopied(false), 2000);
      });
    },
    [gtfsId, copiedLabel],
  );

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1 rounded px-1 py-0.5 font-mono text-xs text-foreground-muted transition-colors hover:bg-surface hover:text-foreground"
      title={label}
      aria-label={`${label}: ${gtfsId}`}
    >
      {gtfsId}
      {copied ? (
        <Check className="size-3 text-status-ontime" />
      ) : (
        <Copy className="size-3 opacity-0 transition-opacity group-hover/row:opacity-100" />
      )}
    </button>
  );
}
```

#### 5c. Update the TableRow to support group hover

In the `<TableRow>` element, add `group/row` to the className for hover-based copy icon reveal:

Current:
```tsx
<TableRow
  key={stop.id}
  className={cn(
    "cursor-pointer transition-colors",
    selectedStopId === stop.id && "bg-selected-bg",
  )}
  onClick={() => onSelectStop(stop)}
>
```

Replace with:
```tsx
<TableRow
  key={stop.id}
  className={cn(
    "group/row cursor-pointer transition-colors",
    selectedStopId === stop.id && "bg-selected-bg",
  )}
  onClick={() => onSelectStop(stop)}
>
```

#### 5d. Update the name column cell

Replace the current name cell content. Currently:

```tsx
<TableCell>
  <div className="flex flex-col">
    <span className="font-medium">{stop.stop_name}</span>
    <span className="text-xs text-foreground-muted">
      {stop.stop_desc || stop.gtfs_stop_id}
    </span>
  </div>
</TableCell>
```

Replace with:

```tsx
<TableCell>
  <div className="flex flex-col gap-0.5">
    <span className="font-medium">{stop.stop_name}</span>
    {stop.stop_desc && (
      <span className="text-xs text-foreground-muted">
        {stop.stop_desc}
      </span>
    )}
    <CopyGtfsButton
      gtfsId={stop.gtfs_stop_id}
      label={t("table.copyGtfsId")}
      copiedLabel={t("table.copied")}
    />
  </div>
</TableCell>
```

This renders:
1. **Stop name** (bold) — e.g., "1.trolejbusu parks"
2. **Direction** (muted, only when available) — e.g., "Uz centru"
3. **Copyable GTFS ID** (monospace, copy icon appears on row hover) — e.g., "7985" with clipboard icon

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 6: Final Validation & Design System Compliance Scan
**Action:** VALIDATE

Run the full 3-level validation pyramid and scan for design system violations.

#### 6a. TypeScript Check
```bash
cd cms && pnpm --filter @vtv/web type-check
```

#### 6b. Lint Check
```bash
cd cms && pnpm --filter @vtv/web lint
```

#### 6c. Build Check
```bash
cd cms && pnpm --filter @vtv/web build
```

#### 6d. Design System Compliance Scan

Scan all modified files for forbidden Tailwind primitive color classes. Run Grep on each file for patterns like `text-gray-`, `bg-blue-`, `text-white`, `text-green-`, `bg-green-`, `text-emerald-`, `bg-emerald-`, `text-red-`, `bg-red-`, `text-amber-`, `bg-amber-`, `text-purple-`, `bg-purple-`, `border-gray-`, `border-red-`, `border-blue-`.

Files to scan:
- `cms/apps/web/src/components/stops/stop-map.tsx`
- `cms/apps/web/src/components/stops/stop-table.tsx`

**Exception:** Hex values in Leaflet `pathOptions` (e.g., `fillColor: "#0369A1"`) are acceptable because Leaflet renders via SVG/Canvas, not CSS classes.

If any violations found, fix them before marking complete.

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

- [ ] Terminus stops (location_type=1) render as green CircleMarkers on the map
- [ ] Regular stops (location_type=0) remain blue CircleMarkers
- [ ] Selected stop of any type shows dark navy marker
- [ ] Filter sidebar shows "Galapunkts" (lv) / "Terminus" (en) instead of "Stacija"/"Station"
- [ ] Location type badges in table and detail panel show "Galapunkts"/"Terminus"
- [ ] Table shows direction text below stop name when `stop_desc` is available
- [ ] GTFS ID shown as small copyable monospace text with clipboard icon on row hover
- [ ] Clicking copy button copies GTFS ID to clipboard and shows toast
- [ ] Map popup shows direction text when available
- [ ] No hardcoded colors in component code (only hex in Leaflet pathOptions)
- [ ] New `--color-stop-terminus` token exists in tokens.css
- [ ] i18n keys present in both lv.json and en.json
- [ ] All validation levels pass (type-check, lint, build)

## Acceptance Criteria

This feature is complete when:
- [ ] Terminus stops visually distinguished with green markers on map
- [ ] "Stacija" renamed to "Galapunkts" / "Station" renamed to "Terminus" everywhere
- [ ] Direction info visible in table rows and map popups
- [ ] GTFS ID copyable with one click
- [ ] Design system tokens used (no primitive color classes)
- [ ] All 3 validation levels pass with 0 errors
- [ ] No regressions in existing stops functionality (CRUD, map interactions, filters)
- [ ] Ready for `/commit`

## Summary of Changes

| File | Action | Description |
|------|--------|-------------|
| `cms/apps/web/messages/lv.json` | MODIFY | Rename Stacija→Galapunkts, add copy i18n keys |
| `cms/apps/web/messages/en.json` | MODIFY | Rename Station→Terminus, add copy i18n keys |
| `cms/packages/ui/src/tokens.css` | MODIFY | Add `--color-stop-terminus` semantic token |
| `cms/apps/web/src/components/stops/stop-map.tsx` | MODIFY | Green markers for terminus, direction in popup |
| `cms/apps/web/src/components/stops/stop-table.tsx` | MODIFY | Direction text, copyable GTFS ID button |

**Total: 0 new files, 5 modified files**
