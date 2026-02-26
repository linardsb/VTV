# Plan: Filter Live Map Vehicles by Transport Type

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Low
**Route**: `/[locale]/(dashboard)/routes` (existing page)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer

## Feature Description

When a user clicks a transport type filter (Autobuss, Trolejbuss, or Tramvajs) in the route sidebar filters, only the route table is currently filtered. The live map continues showing ALL vehicles regardless of the selected transport type.

This enhancement connects the existing `typeFilter` state to the live map so that when a transport type is selected, only vehicles belonging to routes of that type are shown on the map. When no type filter is selected (null), all vehicles are shown as before.

The approach is client-side filtering: we build a lookup from `routeId → RouteType` using the existing `routes` state (which contains `MOCK_ROUTES` with type info), then filter `liveVehicles` before passing them to `RouteMap`. This requires no backend changes.

## Design System

### Master Rules (from MASTER.md)
- No new design changes needed — this is purely a data-flow fix
- Existing map component and filter components are unchanged visually

### Page Override
- None needed — no visual changes

### Tokens Used
- No new tokens required

## Components Needed

### Existing (no changes needed)
- `RouteFilters` — already manages `typeFilter` state, no changes
- `RouteMap` — already receives `buses` prop, will just receive fewer buses when filtered
- `BusMarker` — no changes

### New shadcn/ui to Install
- None

### Custom Components to Create
- None

## i18n Keys

No new i18n keys needed. The map already shows a vehicle count overlay (`{buses.length}`) which will automatically reflect the filtered count.

## Data Fetching

- No changes to data fetching
- `useVehiclePositions` hook continues polling all vehicles every 10s
- Filtering happens client-side in a `useMemo` before passing to `RouteMap`

## RBAC Integration

- No changes — existing route permissions apply

## Sidebar Navigation

- No changes — existing nav entry for routes page

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — The file being modified (read for full context)

### Files to Modify
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Add vehicle filtering by type before passing to RouteMap

### Files to Read (Context Only)
- `cms/apps/web/src/types/route.ts` — RouteType definition, BusPosition interface
- `cms/apps/web/src/components/routes/route-map.tsx` — Understand RouteMap props (no changes needed)
- `cms/apps/web/src/hooks/use-vehicle-positions.ts` — Understand vehicle data shape (no changes needed)

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367

See `cms/apps/web/CLAUDE.md` -> "React 19 Anti-Patterns" for full examples.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

### Task 1: Add vehicle type filtering to routes page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` (modify)
**Action:** UPDATE

Add a `useMemo` that builds a `routeId -> RouteType` lookup from the `routes` state, then uses it to filter `liveVehicles` when `typeFilter` is set.

**Step 1a:** After the existing `routeColorMap` useMemo (lines 53-59), add a new `routeTypeMap` useMemo:

```tsx
// Build route type lookup for filtering live vehicles by transport type
const routeTypeMap = useMemo(() => {
  const map: Record<string, RouteType> = {};
  for (const r of routes) {
    map[r.id] = r.type;
  }
  return map;
}, [routes]);
```

**Step 1b:** After the `useVehiclePositions` hook call (lines 62-64), add a `filteredVehicles` useMemo:

```tsx
// Filter live vehicles by transport type when a type filter is active
const filteredVehicles = useMemo(() => {
  if (typeFilter === null) return liveVehicles;
  return liveVehicles.filter((v) => routeTypeMap[v.routeId] === typeFilter);
}, [liveVehicles, typeFilter, routeTypeMap]);
```

**Step 1c:** Replace ALL occurrences of `buses={liveVehicles}` with `buses={filteredVehicles}` in the JSX. There are exactly 2 occurrences:

1. **Mobile tab layout** (around line 266):
   ```tsx
   // BEFORE:
   <RouteMap buses={liveVehicles} selectedRouteId={selectedRouteId} onSelectRoute={handleSelectRoute} />
   // AFTER:
   <RouteMap buses={filteredVehicles} selectedRouteId={selectedRouteId} onSelectRoute={handleSelectRoute} />
   ```

2. **Desktop resizable panel** (around line 302):
   ```tsx
   // BEFORE:
   <RouteMap buses={liveVehicles} selectedRouteId={selectedRouteId} onSelectRoute={handleSelectRoute} />
   // AFTER:
   <RouteMap buses={filteredVehicles} selectedRouteId={selectedRouteId} onSelectRoute={handleSelectRoute} />
   ```

**Important:** The `RouteType` import already exists on line 23. No new imports needed.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
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

- [ ] When no type filter selected: map shows ALL vehicles (same as current behavior)
- [ ] When "Autobuss" selected: map shows only bus vehicles (route_type 3)
- [ ] When "Trolejbuss" selected: map shows only trolleybus vehicles (route_type 11)
- [ ] When "Tramvajs" selected: map shows only tram vehicles (route_type 0)
- [ ] Vehicle count overlay updates to reflect filtered count
- [ ] Clearing the type filter restores all vehicles on map
- [ ] Route selection (highlighting) still works correctly after filtering
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] No new lint warnings or type errors

## Acceptance Criteria

This feature is complete when:
- [ ] Transport type filter affects both the route table AND the live map
- [ ] Unselecting a filter restores all vehicles on the map
- [ ] Vehicle count in map overlay reflects the filtered count
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing functionality
- [ ] Ready for `/commit`
