# Plan: Multi-Feed Support for Routes Live Map

## Feature Metadata
**Feature Type**: Enhancement (existing Routes page)
**Estimated Complexity**: High
**Route**: `/[locale]/(dashboard)/routes` (existing)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer

## Feature Description

The VTV routes page currently displays live vehicle positions from a single GTFS-RT feed (Rigas Satiksme). The backend already supports multi-feed polling, Redis-keyed storage per feed, WebSocket subscription filtering by `feed_id`, and a `GET /api/v1/transit/feeds` endpoint listing all configured feeds. However, the frontend has no UI to select feeds, differentiate vehicles by feed, or monitor feed health.

This enhancement adds three capabilities to the existing routes page:
1. **Feed selector/filter** — A toggle group or multi-select in the filter sidebar letting users choose which feeds to display on the map. The WebSocket subscribe message already accepts `feed_id`; we wire it through.
2. **Cross-feed vehicle differentiation** — Vehicle markers get a colored border ring per feed (keeping route color as fill), so operators can visually distinguish which feed a vehicle belongs to.
3. **Feed health status indicators** — Small status badges on the map overlay (next to the existing connection status dot) showing each feed's name and health (healthy/stale/offline).
4. **Auto-fit map bounds** — When showing vehicles from multiple feeds covering different geographic areas (Riga, Jurmala, Pieriga), the map auto-fits to the bounding box of all visible vehicles instead of being hardcoded to Riga center.

## Design System

### Master Rules (from MASTER.md)
- All components use `border-radius: 0` (sharp corners) except avatars, switches, scrollbars, status dots (size <= 3)
- Typography: Lexend headings, Source Sans 3 body
- Spacing via semantic tokens: `--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight`
- Shadows: `--shadow-sm` for subtle lift, `--shadow-md` for cards
- All colors via semantic tokens — no Tailwind primitives

### Page Override
- None exists — no need to generate one. This is an enhancement to an existing page that already follows MASTER.md rules.

### Tokens Used
- `--color-status-ontime` (feed healthy)
- `--color-status-delayed` (feed stale)
- `--color-status-critical` (feed offline)
- `--color-transport-bus`, `--color-transport-trolleybus`, `--color-transport-tram` (existing)
- `--color-surface`, `--color-surface-raised` (overlays)
- `--color-foreground`, `--color-foreground-muted`, `--color-foreground-subtle` (text)
- `--color-border` (borders)
- `--color-interactive` (active filter)
- `--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight`
- `--color-filter-active-bg`, `--color-filter-active-text` (existing filter toggle tokens)

## Components Needed

### Existing (shadcn/ui) — already installed
- `ToggleGroup` / `ToggleGroupItem` — feed selector (matches existing type filter pattern)
- `Separator` — between filter sections
- `Badge` — feed health indicator labels
- `Tooltip` — hover details on feed health badges

### New shadcn/ui to Install
- None required

### Custom Components to Create
- `FeedHealthOverlay` at `cms/apps/web/src/components/routes/feed-health-overlay.tsx` — map overlay showing per-feed health badges
- No new standalone components for feed filter — it integrates into existing `RouteFilters`

## i18n Keys

### Latvian (`lv.json`) — add under existing `routes` namespace
```json
{
  "routes": {
    "filters": {
      "feed": "Datu avots",
      "allFeeds": "Visi avoti"
    },
    "feed": {
      "healthy": "Aktīvs",
      "stale": "Novecojis",
      "offline": "Bezsaistē",
      "vehicles": "{count, plural, one {# transportlīdzeklis} other {# transportlīdzekļi}}",
      "lastUpdate": "Pēdējais: {time}",
      "noFeeds": "Nav konfigurētu datu avotu"
    }
  }
}
```

### English (`en.json`) — add under existing `routes` namespace
```json
{
  "routes": {
    "filters": {
      "feed": "Data Feed",
      "allFeeds": "All Feeds"
    },
    "feed": {
      "healthy": "Healthy",
      "stale": "Stale",
      "offline": "Offline",
      "vehicles": "{count, plural, one {# vehicle} other {# vehicles}}",
      "lastUpdate": "Last: {time}",
      "noFeeds": "No feeds configured"
    }
  }
}
```

## Data Fetching

### API Endpoints Used
- `GET /api/v1/transit/feeds` — list configured feeds (feed_id, operator_name, enabled, poll_interval_seconds). Already used in GTFS page via `fetchFeeds()` from `lib/gtfs-sdk.ts`.
- `GET /api/v1/transit/vehicles?feed_id={id}` — REST fallback with feed filter (existing).
- `WS /ws/transit/vehicles` — subscribe message gains `feed_id` field (backend already supports it).

### Server vs Client
- Feed list: Client-side via SWR (needs periodic refresh to detect config changes, 60s interval)
- Vehicle positions: Client-side via existing WebSocket hook (enhanced with `feedFilter` option)
- All data requires authentication — use `authFetch` / `swrFetcher`

### Loading States
- Feed list: Skeleton placeholder in filter sidebar while loading
- Vehicle positions: Existing map skeleton + "no data" overlay

### CRITICAL — Server/client boundary
- `fetchFeeds()` from `lib/gtfs-sdk.ts` uses `authFetch` which supports dual context. Safe to call from client components.
- No new API wrappers needed — reuse existing `fetchFeeds()`.

## RBAC Integration

### Middleware matcher
- No changes needed — `/routes` is already in the matcher for all roles.

### Role permissions
- No changes — all roles can view routes. Read-only roles (viewer, dispatcher) already cannot CRUD.

## Sidebar Navigation

- No changes — `/routes` nav entry already exists.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules
- `cms/apps/web/CLAUDE.md` — Frontend conventions, React 19 anti-patterns

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/routes/route-filters.tsx` — Filter sidebar pattern with ToggleGroup (lines 36-161 for FilterContent, lines 180-239 for RouteFilters wrapper)
- `cms/apps/web/src/components/routes/route-map.tsx` — Map overlay pattern (connection status badge at lines 28-46)
- `cms/apps/web/src/hooks/use-vehicle-positions.ts` — WebSocket hook with subscribe message (lines 153-164 for routeFilter sync, lines 193-198 for subscribe message)
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Main page wiring (lines 90-93 for hook usage, lines 112-116 for vehicle filtering)

### Files to Modify
- `cms/apps/web/src/hooks/use-vehicle-positions.ts` — Add `feedFilter` option, pass `feed_id` in subscribe, add `feedId`+`operatorName` to mapped vehicles
- `cms/apps/web/src/types/route.ts` — Add `feedId` and `operatorName` to `BusPosition` interface
- `cms/apps/web/src/components/routes/route-filters.tsx` — Add feed filter section
- `cms/apps/web/src/components/routes/route-map.tsx` — Add feed health overlay, auto-fit bounds, pass feed border color to markers
- `cms/apps/web/src/components/routes/bus-marker.tsx` — Add feed border ring to marker
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Wire feed state, pass feed filter to hook, load feeds list
- `cms/apps/web/messages/lv.json` — Add feed i18n keys
- `cms/apps/web/messages/en.json` — Add feed i18n keys

### Files to Create
- `cms/apps/web/src/components/routes/feed-health-overlay.tsx` — Map overlay for feed health badges

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping table and forbidden class list are loaded via `@_shared/tailwind-token-map.md`. Key rules:
- Use the mapping table for all color decisions
- Check `cms/packages/ui/src/tokens.css` for available tokens
- Exception: Inline HTML strings (Leaflet `L.divIcon` html) may use hex colors since Tailwind classes don't work there
- Feed border colors in Leaflet markers MUST use inline hex since they render inside `L.divIcon` HTML strings

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `feedFilter` from `useState`, the `useState` line must appear first in the component body
- **Shared type changes require ripple-effect tasks** — Adding `feedId` and `operatorName` to `BusPosition` requires updating `mapVehicle()` in the hook and the `ApiVehicle` interface

## TypeScript Security Rules

- **Clear `.next` cache when module resolution errors persist after fixing imports** — `rm -rf cms/apps/web/.next` and restart dev server
- No new external data sources beyond what's already validated by backend schemas

## Feed Color Assignment Strategy

Each feed gets a deterministic border color for visual differentiation on the map. Since these render inside Leaflet `L.divIcon` HTML strings, they use hex values (not Tailwind classes). The color is assigned by feed index from a fixed palette:

```typescript
// Module-scope constant — deterministic feed colors
const FEED_BORDER_COLORS: string[] = [
  "#0391F2", // VTV blue (Riga — primary feed)
  "#06757E", // Teal (Jurmala)
  "#8E24AA", // Purple (Pieriga)
  "#FB8C00", // Orange (future)
  "#E53935", // Red (future)
  "#43A047", // Green (future)
];

function getFeedColor(feedId: string, feedIds: string[]): string {
  const idx = feedIds.indexOf(feedId);
  return FEED_BORDER_COLORS[idx >= 0 ? idx % FEED_BORDER_COLORS.length : 0];
}
```

This palette is used in two places:
1. `bus-marker.tsx` — border ring on vehicle markers
2. `feed-health-overlay.tsx` — colored dot next to feed name

## Auto-Fit Bounds Strategy

When vehicles from multiple feeds are visible, the map should auto-fit to show all vehicles. Use `react-leaflet`'s `useMap()` hook with `map.fitBounds()`:

```typescript
// Inside RouteMap, after the MapContainer renders:
// Compute bounds from all visible vehicles
const bounds = useMemo(() => {
  if (buses.length === 0) return null;
  const lats = buses.map(b => b.latitude);
  const lngs = buses.map(b => b.longitude);
  return L.latLngBounds(
    [Math.min(...lats), Math.min(...lngs)],
    [Math.max(...lats), Math.max(...lngs)]
  );
}, [buses]);

// Apply bounds via a child component (MapContainer doesn't accept bounds changes after mount)
function FitBounds({ bounds }: { bounds: L.LatLngBounds | null }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [map, bounds]);
  return null;
}
```

IMPORTANT: `FitBounds` must be defined at module scope (not inside `RouteMap`) per React 19 rules. It should only run when the feed selection changes, NOT on every vehicle update (that would cause jarring viewport jumps). Track a `feedSelectionKey` derived from the active feed IDs.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add i18n Keys (Latvian)
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Read the file first. Add these keys INSIDE the existing `"routes"` object, merging with existing keys:

Under `routes.filters`, add:
```json
"feed": "Datu avots",
"allFeeds": "Visi avoti"
```

Under `routes`, add new `"feed"` block:
```json
"feed": {
  "healthy": "Aktīvs",
  "stale": "Novecojis",
  "offline": "Bezsaistē",
  "vehicles": "{count, plural, one {# transportlīdzeklis} other {# transportlīdzekļi}}",
  "lastUpdate": "Pēdējais: {time}",
  "noFeeds": "Nav konfigurētu datu avotu"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: Add i18n Keys (English)
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Read the file first. Add matching keys INSIDE the existing `"routes"` object:

Under `routes.filters`, add:
```json
"feed": "Data Feed",
"allFeeds": "All Feeds"
```

Under `routes`, add new `"feed"` block:
```json
"feed": {
  "healthy": "Healthy",
  "stale": "Stale",
  "offline": "Offline",
  "vehicles": "{count, plural, one {# vehicle} other {# vehicles}}",
  "lastUpdate": "Last: {time}",
  "noFeeds": "No feeds configured"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Extend BusPosition Type with Feed Fields
**File:** `cms/apps/web/src/types/route.ts` (modify)
**Action:** UPDATE

Read the file first. Add two fields to the `BusPosition` interface (after `timestamp`):

```typescript
export interface BusPosition {
  // ... existing fields unchanged ...
  timestamp: string;
  /** GTFS-RT feed source identifier (e.g., "riga", "jurmala") */
  feedId: string;
  /** Human-readable operator name (e.g., "Rigas Satiksme") */
  operatorName: string;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` — will show errors in files constructing BusPosition objects (use-vehicle-positions.ts, mock-bus-positions.ts). These are expected and will be fixed in subsequent tasks.

---

### Task 4: Update Vehicle Positions Hook for Multi-Feed
**File:** `cms/apps/web/src/hooks/use-vehicle-positions.ts` (modify)
**Action:** UPDATE

Read the file first. Make these changes:

1. **Add `feed_id` and `operator_name` to `ApiVehicle` interface** (after `current_stop_name`):
```typescript
feed_id: string;
operator_name: string;
```

2. **Add `feedFilter` to `UseVehiclePositionsOptions`** (after `routeFilter`):
```typescript
/** Optional feed_id to push as server-side WS filter. null = all feeds. */
feedFilter?: string | null;
```

3. **Update `mapVehicle()` function** to include feed fields:
```typescript
function mapVehicle(v: ApiVehicle, colorMap: Record<string, string>): BusPosition {
  return {
    // ... existing fields unchanged ...
    timestamp: v.timestamp,
    feedId: v.feed_id ?? "",
    operatorName: v.operator_name ?? "",
  };
}
```

4. **Add `feedFilter` to destructuring** in the hook (after `routeFilter`):
```typescript
const { ..., routeFilter, feedFilter } = options;
```

5. **Add feedFilterRef** (after `routeFilterRef`):
```typescript
const feedFilterRef = useRef<string | null>(feedFilter ?? null);
```

6. **Add feedFilter sync effect** (after the routeFilter sync effect). Follow the same pattern — sync ref and re-subscribe:
```typescript
useEffect(() => {
  feedFilterRef.current = feedFilter ?? null;
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(
      JSON.stringify({
        action: "subscribe",
        route_id: routeFilterRef.current ?? undefined,
        feed_id: feedFilter ?? undefined,
      }),
    );
  }
}, [feedFilter]);
```

7. **Update ALL `subscribe` messages** to include `feed_id`:
- In the `routeFilter` sync effect (existing): add `feed_id: feedFilterRef.current ?? undefined`
- In `ws.onopen` handler: add `feed_id: feedFilterRef.current ?? undefined`

8. **Update SWR fallback URL** to include feed_id when in polling mode:
```typescript
const swrUrl = connectionFailed
  ? `${apiBase}/api/v1/transit/vehicles${feedFilterRef.current ? `?feed_id=${feedFilterRef.current}` : ""}`
  : null;
```
Use `swrUrl` as the SWR key instead of the inline expression.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 5: Update Mock Bus Positions (if exists)
**File:** `cms/apps/web/src/lib/mock-bus-positions.ts` (modify, if it exists)
**Action:** UPDATE

Read the file first. If it constructs `BusPosition` objects, add `feedId: "riga"` and `operatorName: "Rigas Satiksme"` to each mock object. If the file doesn't construct BusPosition objects directly, skip this task.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 6: Add Feed Filter Section to RouteFilters
**File:** `cms/apps/web/src/components/routes/route-filters.tsx` (modify)
**Action:** UPDATE

Read the file first. Make these changes:

1. **Import `GTFSFeed` type** at the top:
```typescript
import type { GTFSFeed } from "@/types/gtfs";
```

2. **Add feed props to `FilterContentProps`** (after `resultCount`):
```typescript
feeds: GTFSFeed[];
feedFilter: string | null;
onFeedFilterChange: (feedId: string | null) => void;
```

3. **Add feed props to `RouteFiltersProps`** (same three props, after `resultCount`).

4. **Add Feed Filter section to `FilterContent`** — insert BEFORE the Type Filter section (after the Search section and its Separator). Follow the exact same pattern as the Type Filter toggle group:

```tsx
{/* Feed Filter */}
{feeds.length > 0 && (
  <>
    <div className="space-y-(--spacing-tight)">
      <p className="text-xs font-medium text-label-text uppercase tracking-wide">
        {t("filters.feed")}
      </p>
      <ToggleGroup
        type="single"
        spacing={1}
        value={feedFilter ?? "all"}
        onValueChange={(value) => {
          onFeedFilterChange(value === "all" || value === "" ? null : value);
        }}
        className="flex flex-col gap-1"
      >
        <ToggleGroupItem value="all" className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold">
          {t("filters.allFeeds")}
        </ToggleGroupItem>
        {feeds.filter(f => f.enabled).map((feed) => (
          <ToggleGroupItem
            key={feed.feed_id}
            value={feed.feed_id}
            className="w-full justify-start rounded-md text-sm data-[state=on]:bg-filter-active-bg data-[state=on]:text-filter-active-text data-[state=on]:font-semibold"
          >
            {feed.operator_name}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
    <Separator />
  </>
)}
```

5. **Thread the new props** through `FilterContent` calls in both the `aside` (desktop) and `Sheet` (mobile) branches of `RouteFilters`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` — will fail because routes/page.tsx doesn't pass the new props yet. That's expected.
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: Create Feed Health Overlay Component
**File:** `cms/apps/web/src/components/routes/feed-health-overlay.tsx` (create)
**Action:** CREATE

Create a client component that renders feed health badges as a map overlay. It sits in the top-left area of the map, below the existing vehicle count badge.

```typescript
"use client";

import { useTranslations } from "next-intl";
import type { GTFSFeed } from "@/types/gtfs";
import type { BusPosition } from "@/types/route";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
```

**Props:**
```typescript
interface FeedHealthOverlayProps {
  feeds: GTFSFeed[];
  vehicles: BusPosition[];
  feedColors: Record<string, string>;  // feedId -> hex color
}
```

**Logic:**
- For each enabled feed, count vehicles with matching `feedId`
- Determine health: `count > 0` = healthy, `count === 0 && feed.enabled` = stale/offline
- Display as a vertical list of small badges, each with:
  - Colored dot (using `feedColors[feed.feed_id]` as inline `style={{ backgroundColor }}` since these are deterministic hex values for Leaflet consistency)
  - Feed operator name (abbreviated if > 12 chars)
  - Vehicle count
  - Status dot: `bg-status-ontime` (healthy), `bg-status-delayed` (stale — 0 vehicles but enabled), `bg-status-critical` (disabled)
- Wrap each badge in a `Tooltip` showing full operator name and vehicle count

**Positioning:** `absolute left-3 top-14 z-[1000]` (below the existing vehicle count overlay which is at `top-3`). Use `bg-surface/90 backdrop-blur-sm shadow-sm` for the container. Match the existing overlay styling pattern from `route-map.tsx` lines 23-25.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 8: Update Bus Marker with Feed Border Ring
**File:** `cms/apps/web/src/components/routes/bus-marker.tsx` (modify)
**Action:** UPDATE

Read the file first. Make these changes:

1. **Add `feedBorderColor` prop** to the marker's props interface:
```typescript
/** Hex color for feed differentiation border ring. */
feedBorderColor?: string;
```

2. **Update the Leaflet `divIcon` HTML** to include a 2px border ring when `feedBorderColor` is provided. The marker currently renders a colored circle with the route short name. Add a `border: 2px solid {feedBorderColor}` to the outer div's inline style. If no `feedBorderColor` is provided, keep current behavior (no border or transparent border).

Since Leaflet `divIcon` uses raw HTML strings, inline hex colors are acceptable here (this is the documented exception in the design system rules).

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 9: Update RouteMap with Auto-Fit Bounds, Feed Overlay, and Feed Border Colors
**File:** `cms/apps/web/src/components/routes/route-map.tsx` (modify)
**Action:** UPDATE

Read the file first. Make these changes:

1. **Add imports:**
```typescript
import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import { useMap } from "react-leaflet";
import type { GTFSFeed } from "@/types/gtfs";
import { FeedHealthOverlay } from "./feed-health-overlay";
```

2. **Add new props to `RouteMapProps`:**
```typescript
feeds?: GTFSFeed[];
feedColors?: Record<string, string>;  // feedId -> hex color
feedSelectionKey?: string;  // changes when feed selection changes, triggers re-fit
```

3. **Create `FitBounds` component at MODULE SCOPE** (not inside RouteMap — React 19 rule):
```typescript
function FitBounds({ bounds, trigger }: { bounds: L.LatLngBounds | null; trigger: string }) {
  const map = useMap();
  const prevTriggerRef = useRef(trigger);

  useEffect(() => {
    // Only fit bounds when feed selection changes, not on every vehicle update
    if (trigger !== prevTriggerRef.current && bounds && bounds.isValid()) {
      prevTriggerRef.current = trigger;
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [map, bounds, trigger]);

  return null;
}
```

4. **Compute bounds inside RouteMap** (as a `useMemo`):
```typescript
const bounds = useMemo(() => {
  if (buses.length === 0) return null;
  const lats = buses.map(b => b.latitude);
  const lngs = buses.map(b => b.longitude);
  return L.latLngBounds(
    [Math.min(...lats), Math.min(...lngs)],
    [Math.max(...lats), Math.max(...lngs)]
  );
}, [buses]);
```

5. **Add `FitBounds` as a child of `MapContainer`:**
```tsx
<FitBounds bounds={bounds} trigger={feedSelectionKey ?? ""} />
```

6. **Add `FeedHealthOverlay`** below the connection status badge (inside the `relative` container, outside `MapContainer`):
```tsx
{feeds && feeds.length > 0 && (
  <FeedHealthOverlay
    feeds={feeds}
    vehicles={buses}
    feedColors={feedColors ?? {}}
  />
)}
```

7. **Pass `feedBorderColor` to BusMarker:**
```tsx
<BusMarker
  key={bus.vehicleId}
  bus={bus}
  isHighlighted={selectedRouteId === bus.routeId}
  isDimmed={false}
  onSelect={onSelectRoute}
  feedBorderColor={feedColors?.[bus.feedId]}
/>
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Wire Everything in the Routes Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` (modify)
**Action:** UPDATE

Read the file first. This is the largest change — it wires all the new pieces together.

1. **Add imports:**
```typescript
import { fetchFeeds } from "@/lib/gtfs-sdk";
import type { GTFSFeed } from "@/types/gtfs";
```

2. **Add feed state** (with the other `useState` calls near the top):
```typescript
const [feeds, setFeeds] = useState<GTFSFeed[]>([]);
const [feedFilter, setFeedFilter] = useState<string | null>(null);
```

3. **Create feed color map** (as `useMemo`, AFTER `feeds` state since it depends on it):
```typescript
// Deterministic feed border colors for map markers
const FEED_BORDER_COLORS = [
  "#0391F2", "#06757E", "#8E24AA", "#FB8C00", "#E53935", "#43A047",
];

const feedColorMap = useMemo(() => {
  const enabledFeeds = feeds.filter(f => f.enabled);
  const map: Record<string, string> = {};
  enabledFeeds.forEach((feed, idx) => {
    map[feed.feed_id] = FEED_BORDER_COLORS[idx % FEED_BORDER_COLORS.length];
  });
  return map;
}, [feeds]);
```

NOTE: `FEED_BORDER_COLORS` should be a module-scope `const` (outside the component), not inside the component body.

4. **Create feedSelectionKey** for auto-fit bounds triggering:
```typescript
const feedSelectionKey = useMemo(() => feedFilter ?? "all", [feedFilter]);
```

5. **Pass `feedFilter` to `useVehiclePositions` hook:**
```typescript
const { vehicles: liveVehicles, connectionMode } = useVehiclePositions({
  colorMap: routeColorMap,
  routeFilter: selectedGtfsRouteId,
  feedFilter,
});
```

6. **Load feeds on mount** — add to the existing `loadAgencies` effect or create a new `loadFeeds` callback:
```typescript
const loadFeeds = useCallback(async () => {
  try {
    const data = await fetchFeeds();
    setFeeds(data);
  } catch (e) {
    console.warn("[routes] Failed to load feeds:", e);
  }
}, []);
```

Add `void loadFeeds();` to the existing mount effect (the one that calls `loadAgencies` and `loadAllRoutes`), and add `loadFeeds` to its dependency array.

7. **Pass feed props to `RouteFilters`** — add to BOTH desktop and mobile filter instances:
```typescript
feeds={feeds}
feedFilter={feedFilter}
onFeedFilterChange={setFeedFilter}
```

8. **Pass feed props to `RouteMap`** — add to BOTH mobile tab and desktop panel instances:
```typescript
feeds={feeds}
feedColors={feedColorMap}
feedSelectionKey={feedSelectionKey}
```

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

- [ ] Feed filter appears in route filters sidebar (desktop) and sheet (mobile)
- [ ] Selecting a specific feed sends `feed_id` in WebSocket subscribe message
- [ ] Selecting "All Feeds" sends no `feed_id` (receives all feeds)
- [ ] Vehicle markers show colored border ring matching their feed
- [ ] Feed health overlay shows on map with per-feed vehicle counts
- [ ] Health status dots: green (has vehicles), amber (enabled but 0 vehicles), red (disabled)
- [ ] Map auto-fits bounds when feed selection changes
- [ ] Map does NOT auto-fit on every vehicle position update (only on feed change)
- [ ] i18n keys present in both lv.json and en.json
- [ ] No hardcoded colors — all styling uses semantic tokens (except Leaflet divIcon inline HTML)
- [ ] No new `rounded-*` classes (except status dots size <= 3)
- [ ] Accessibility: feed filter has proper labels, tooltips have aria descriptions

## Acceptance Criteria

This feature is complete when:
- [ ] Feed selector works in routes page filter sidebar
- [ ] WebSocket subscription correctly filters by feed_id
- [ ] Vehicle markers visually distinguish feed source via border color
- [ ] Feed health overlay shows real-time per-feed status
- [ ] Map auto-fits to visible vehicle bounds on feed change
- [ ] Both languages have complete translations
- [ ] Design system rules followed (MASTER.md, semantic tokens only)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing routes page functionality
- [ ] SWR polling fallback also respects feed_id filter
- [ ] Ready for `/commit`
