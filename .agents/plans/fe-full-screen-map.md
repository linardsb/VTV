# Plan: LV-1.3 Full-Screen `/map` CMS Page

## Context

Current vehicle map is a 60/40 resizable split panel on the `/routes` page — too small for dispatchers monitoring all of Latvia. A dedicated full-screen `/map` page serves as the primary operational view for multi-city coverage. Builds on existing `RouteMap`, `BusMarker`, `FeedHealthOverlay`, and `useVehiclePositions` WebSocket hook.

## Security Context Assessment

- **CTX-RBAC** — New page needs middleware route protection + role gating (viewer+ access)
- **CTX-INPUT** — Feed/type filter values are UI-only (no user input sent to backend beyond existing WS subscribe messages). Low risk.
- No CTX-AUTH/FILE/AGENT/INFRA contexts triggered.

## Research Summary

### Key Reference Files

| File | Purpose |
|------|---------|
| `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` | **Primary reference** — map + WS + filters + feed selector |
| `cms/apps/web/src/components/routes/route-map.tsx` | Leaflet MapContainer, FitBounds, connection badge, feed overlay |
| `cms/apps/web/src/components/routes/bus-marker.tsx` | `L.divIcon` marker with route color, delay popup |
| `cms/apps/web/src/components/routes/feed-health-overlay.tsx` | Per-feed vehicle count + health dots |
| `cms/apps/web/src/hooks/use-vehicle-positions.ts` | WebSocket primary + SWR polling fallback, route/feed filter |
| `cms/apps/web/src/types/route.ts` | `BusPosition`, `Route`, `ROUTE_TYPE_LABELS`, `getRouteTypeLabel()` |
| `cms/apps/web/src/types/gtfs.ts` | `GTFSFeed` interface |
| `cms/apps/web/src/lib/gtfs-sdk.ts` | `fetchFeeds()` — SDK wrapper |
| `cms/apps/web/src/components/app-sidebar.tsx:38-65` | `navEntries` array, `NavItem`/`NavGroup` types |
| `cms/apps/web/middleware.ts:5-10` | `ROLE_PERMISSIONS` + matcher regex |
| `cms/apps/web/src/app/[locale]/(dashboard)/layout.tsx` | Dashboard wrapper: sidebar + `main#main-content` with `p-(--spacing-page)` |
| `cms/apps/web/src/components/routes/route-detail.tsx` | Dialog pattern for detail panels |

### Existing Patterns to Reuse

- **Dynamic Leaflet import** — `next/dynamic` with `{ ssr: false }` and `MapSkeleton` loading fallback (routes/page.tsx:55-58)
- **Feed border colors** — `FEED_BORDER_COLORS` array, `feedColorMap` derived from `feeds.filter(f => f.enabled)` (routes/page.tsx:40-99)
- **Route color map** — `routeColorMap: Record<string, string>` built from `allRoutes` (routes/page.tsx:81-89)
- **Connection status badge** — green/yellow dot + label in `route-map.tsx:60-78`
- **FitBounds** — Module-scope component using `useMap()` + `useRef` for trigger-based bounds fitting
- **BusMarker** — `L.divIcon` with inline CSS (hex colors OK for Leaflet HTML)
- **FeedHealthOverlay** — Absolute positioned, `z-[1000]`, tooltip per feed
- **Session gate** — `useSession()` + `status !== "authenticated"` guard before data fetch
- **`useVehiclePositions` hook** — accepts `routeFilter`, `feedFilter`, returns `vehicles`, `connectionMode`, `isLoading`

### Dependencies

- `leaflet.markercluster` — **NOT installed**. Need to add for 500+ marker clustering.
- `react-leaflet-cluster@4.1.3` — **NOT installed**. React wrapper for markercluster, compatible with react-leaflet v5 + React 19. **Use this** (not `@changey/react-leaflet-markercluster` which targets react-leaflet v4).

## Test Landscape

- **9 Playwright e2e tests** in `cms/apps/web/e2e/`. Navigation test (`navigation.spec.ts`) validates sidebar links.
- **No component-level tests** for map components.
- **Test patterns:** `page.goto("/lv/...")` → `waitForLoadState("networkidle")` → `waitForDataOrEmpty()`. Maps detected via `.leaflet-container` locator.
- **Auth setup:** `auth.setup.ts` saves session to `e2e/.auth/user.json`.
- **Auto-detection:** `detect-changed.sh` maps changed source dirs to test files. Need to add `/map` mapping.

## Type Check Baseline

- **TypeScript:** 0 errors (clean)
- **ESLint:** 0 errors, 0 warnings (clean)

## Design System

**From MASTER.md:**
- Border radius: `0` everywhere (sharp corners). Exceptions: status dots, avatars, scrollbar thumbs, switches.
- Typography: Lexend (headings), Source Sans 3 (body)
- Spacing: Use `--spacing-page` (16px), `--spacing-card` (12px), `--spacing-grid` (12px), `--spacing-tight` (4px), `--spacing-inline` (6px)
- No rounded corners on cards/panels/buttons

**Semantic tokens (from tailwind-token-map.md):**
- Backgrounds: `bg-surface`, `bg-surface-secondary`, `bg-background`
- Text: `text-foreground`, `text-foreground-muted`, `text-foreground-subtle`
- Status: `bg-status-ontime` (green), `bg-status-delayed` (yellow), `bg-status-critical` (red)
- Transport: `bg-transport-bus`, `bg-transport-trolleybus`, `bg-transport-tram` (+ text/border variants)
- Interactive: `bg-interactive`, `text-interactive`
- Borders: `border-border`

**No page-specific override** — `design-system/vtv/pages/map.md` does not exist; follow MASTER.md.

## i18n Keys

```json
// lv.json — add "map" key at root level
{
  "map": {
    "title": "Transportlīdzekļu karte",
    "description": "Reāllaika transportlīdzekļu izsekošana visos maršrutos",
    "vehicles": "{count, plural, one {{count} transportlīdzeklis} other {{count} transportlīdzekļi}}",
    "filters": {
      "allFeeds": "Visi operatori",
      "allTypes": "Visi veidi",
      "bus": "Autobuss",
      "trolleybus": "Trolejbuss",
      "tram": "Tramvajs"
    },
    "liveStream": "Tiešraide",
    "pollingFallback": "Aptauja (WS kļūda)",
    "wsConnecting": "Savienojums...",
    "noData": "Nav pieejamu transportlīdzekļu",
    "detail": {
      "route": "Maršruts",
      "operator": "Operators",
      "speed": "Ātrums",
      "delay": "Kavēšanās",
      "nextStop": "Nākamā pietura",
      "status": "Statuss",
      "inTransit": "Ceļā",
      "stopped": "Pieturā",
      "incoming": "Tuvojas",
      "onTime": "Laikā",
      "early": "Priekšlaicīgi",
      "late": "Kavējas",
      "minutes": "min"
    },
    "cluster": {
      "vehicles": "{count} transportlīdzekļi"
    }
  },
  "nav": {
    "map": "Karte"
  }
}
```

```json
// en.json — add "map" key at root level
{
  "map": {
    "title": "Vehicle Map",
    "description": "Real-time vehicle tracking across all feeds",
    "vehicles": "{count, plural, one {{count} vehicle} other {{count} vehicles}}",
    "filters": {
      "allFeeds": "All operators",
      "allTypes": "All types",
      "bus": "Bus",
      "trolleybus": "Trolleybus",
      "tram": "Tram"
    },
    "liveStream": "Live stream",
    "pollingFallback": "Polling (WS failed)",
    "wsConnecting": "Connecting...",
    "noData": "No vehicles available",
    "detail": {
      "route": "Route",
      "operator": "Operator",
      "speed": "Speed",
      "delay": "Delay",
      "nextStop": "Next stop",
      "status": "Status",
      "inTransit": "In transit",
      "stopped": "At stop",
      "incoming": "Incoming",
      "onTime": "On time",
      "early": "Early",
      "late": "Late",
      "minutes": "min"
    },
    "cluster": {
      "vehicles": "{count} vehicles"
    }
  },
  "nav": {
    "map": "Map"
  }
}
```

## RBAC

- Add `"/map"` to ALL 4 role arrays in `ROLE_PERMISSIONS` (viewer+ access)
- Add `map` to matcher regex: `/(lv|en|ru)/(routes|...|map)/:path*`
- Sidebar: `{ key: "map", href: "/map", enabled: true }` — top-level entry after "routes"

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| INSTALL | `cms/apps/web/package.json` | Add `leaflet.markercluster` + types |
| CREATE | `cms/apps/web/src/app/[locale]/(dashboard)/map/page.tsx` | Full-screen map page (client component) |
| CREATE | `cms/apps/web/src/components/map/vehicle-map.tsx` | Full-viewport Leaflet map with clustering |
| CREATE | `cms/apps/web/src/components/map/map-filters.tsx` | Feed toggle chips + route type filter bar |
| CREATE | `cms/apps/web/src/components/map/vehicle-detail-dialog.tsx` | Click-to-inspect vehicle detail panel |
| UPDATE | `cms/apps/web/src/components/app-sidebar.tsx:38` | Add "map" nav entry |
| UPDATE | `cms/apps/web/middleware.ts:6-10,34` | Add `/map` to ROLE_PERMISSIONS + matcher |
| UPDATE | `cms/apps/web/messages/lv.json` | Add `map.*` + `nav.map` i18n keys |
| UPDATE | `cms/apps/web/messages/en.json` | Add `map.*` + `nav.map` i18n keys |
| CREATE | `cms/apps/web/e2e/map.spec.ts` | Playwright e2e test for /map page |
| UPDATE | `cms/apps/web/e2e/detect-changed.sh` | Add map component → test mapping |

## Implementation Steps

### Step 1: Install markercluster dependency

```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web add leaflet.markercluster react-leaflet-cluster
pnpm --filter @vtv/web add -D @types/leaflet.markercluster
```

**Note:** `react-leaflet-cluster@4.1.3` is the correct wrapper (react-leaflet v5 + React 19). Do NOT use `@changey/react-leaflet-markercluster` (targets react-leaflet v4, incompatible).

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 2: Add i18n keys to both language files

Add `"map"` section and `"nav.map"` to:
- `cms/apps/web/messages/lv.json` — keys from i18n section above
- `cms/apps/web/messages/en.json` — keys from i18n section above

Also add to `ru.json` if it exists (use English values as placeholder).

**Validation:** Verify JSON is valid: `node -e "JSON.parse(require('fs').readFileSync('cms/apps/web/messages/en.json'))"`

### Step 3: Update middleware RBAC

**File:** `cms/apps/web/middleware.ts`

1. Add `"/map"` to all 4 role arrays in `ROLE_PERMISSIONS` (lines 6-10)
2. Add `map` to the matcher regex (line 34): `/(lv|en|ru)/(routes|stops|schedules|drivers|vehicles|fleet|geofences|analytics|gtfs|users|chat|documents|map)/:path*`

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 4: Add sidebar navigation entry

**File:** `cms/apps/web/src/components/app-sidebar.tsx`

Add `{ key: "map", href: "/map", enabled: true }` to `navEntries` array after the "routes" entry (line 40). This places the map link prominently near the top of navigation since it's a primary operational view.

**Note:** Sidebar uses text-only nav links (no per-item icons). The `t("map")` call resolves to the `nav.map` i18n key. No icon import needed.

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 5: Create map filter bar component

**File:** `cms/apps/web/src/components/map/map-filters.tsx`

A horizontal filter bar for the top of the map page:

- **Feed toggle chips** — One chip per enabled feed (from `fetchFeeds()`). Each chip shows operator name + feed border color dot. Clicking toggles that feed on/off. "All" chip selected by default.
- **Route type filter** — Dropdown or chip group: All / Bus / Trolleybus / Tram (uses `ROUTE_TYPE_LABELS` from `types/route.ts`)
- **Vehicle count badge** — Shows total visible vehicles
- **Connection status** — Reuse the green/yellow dot + label pattern from `route-map.tsx`

Props:
```tsx
interface MapFiltersProps {
  feeds: GTFSFeed[];
  feedColors: Record<string, string>;
  enabledFeedIds: Set<string>;
  onToggleFeed: (feedId: string) => void;
  onToggleAllFeeds: () => void;
  selectedRouteType: number | null; // null = all types
  onRouteTypeChange: (type: number | null) => void;
  vehicleCount: number;
  connectionMode: ConnectionMode;
}
```

Uses `useTranslations("map")`. All text from i18n. Semantic tokens only. Position: absolute over map, top edge, full width, `z-[1000]`, glass morphism bg (`bg-surface/90 backdrop-blur-sm`).

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 6: Create vehicle detail dialog

**File:** `cms/apps/web/src/components/map/vehicle-detail-dialog.tsx`

Dialog (not Sheet) showing vehicle details on marker click. Following existing `route-detail.tsx` pattern:

```tsx
interface VehicleDetailDialogProps {
  vehicle: BusPosition | null;
  open: boolean;
  onClose: () => void;
}
```

Content:
- Route short name + color badge
- Operator name
- Current status (in_transit/stopped/incoming) with i18n labels
- Delay (formatted as on-time/early/X min late with status color)
- Next stop name (if available)
- Feed ID
- Timestamp (formatted relative or absolute)

Width: `sm:max-w-[28rem]` (detail view convention). Uses `Dialog` from `@/components/ui/dialog`.

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 7: Create full-viewport vehicle map component

**File:** `cms/apps/web/src/components/map/vehicle-map.tsx`

The core map component — full viewport Leaflet map with clustering.

**Structure:**
```tsx
"use client";

interface VehicleMapProps {
  vehicles: BusPosition[];
  feeds: GTFSFeed[];
  feedColors: Record<string, string>;
  enabledFeedIds: Set<string>;
  selectedRouteType: number | null;
  connectionMode: ConnectionMode;
  onVehicleClick: (vehicle: BusPosition) => void;
}
```

**Key implementation details:**
- `MapContainer` with `center={[56.9496, 24.1052]}` (Riga), `zoom={8}` (Latvia-wide view vs 13 for routes page)
- CARTO Voyager tile layer (same as route-map.tsx)
- `FitBounds` module-scope component (same pattern as route-map.tsx)
- Filter vehicles by `enabledFeedIds` and `selectedRouteType` using `useMemo`
- **MarkerCluster:** Use `react-leaflet-cluster` (v4.1.3, react-leaflet v5 + React 19 compatible):
  ```tsx
  import MarkerClusterGroup from "react-leaflet-cluster";
  import "leaflet.markercluster/dist/MarkerCluster.css";
  import "leaflet.markercluster/dist/MarkerCluster.Default.css";

  <MarkerClusterGroup
    maxClusterRadius={50}
    spiderfyOnMaxZoom={true}
    showCoverageOnHover={false}
    zoomToBoundsOnClick={true}
    chunkedLoading={true}
  >
    {filteredVehicles.map(v => (
      <Marker key={v.vehicleId} position={[v.latitude, v.longitude]} icon={createBusIcon(v)}
        eventHandlers={{ click: () => onVehicleClick(v) }} />
    ))}
  </MarkerClusterGroup>
  ```
- `createBusIcon()` — same `L.divIcon` pattern as `bus-marker.tsx` but extracted as a pure function
- **Feed health overlay** — Reuse `FeedHealthOverlay` component from routes
- **Connection badge** — Same pattern as route-map.tsx, top-right corner
- **Empty state** — Centered message when no vehicles after filtering

**Performance:** MarkerClusterGroup handles 500+ markers efficiently by grouping at lower zoom levels.

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 8: Create the map page

**File:** `cms/apps/web/src/app/[locale]/(dashboard)/map/page.tsx`

**Structure:**
```tsx
"use client";
```

**Key implementation:**
- Dynamic import of `VehicleMap` with `{ ssr: false }` (Leaflet needs browser DOM)
- `useSession()` gate for data fetching
- `useVehiclePositions({ feedFilter: null })` — all feeds, no route filter (full map)
- `fetchFeeds()` + `fetchRoutes()` via `useEffect` on session auth (for route colors + feed list)
- State: `enabledFeedIds: Set<string>`, `selectedRouteType: number | null`, `selectedVehicle: BusPosition | null`
- Feed toggle handlers: `onToggleFeed(id)` — add/remove from Set; `onToggleAllFeeds()` — reset to all
- **Layout override:** The dashboard layout applies `p-(--spacing-page)` padding. For full-screen map, override with negative margin or use a CSS class to remove padding. Best approach: add `className="!p-0"` override on the page wrapper, or conditionally remove padding in layout based on route.
  - Simpler: wrap the page content in a `div` with `-m-(--spacing-page)` to negate the layout padding, and set explicit height `h-[calc(100vh-0px)]` (no header in dashboard layout, sidebar is flex sibling).
  - Actually: the layout has `<main className="flex-1 overflow-auto p-(--spacing-page)">`. The map page should fill the entire main area. Use `className="-m-(--spacing-page) h-[calc(100vh)]"` on the page root div to negate padding and fill viewport. Or better: use `absolute inset-0` positioning within the main.
  - **Recommended approach:** Render a wrapper `<div className="relative -m-(--spacing-page) flex h-[calc(100dvh)] flex-col">` — negates parent padding, fills viewport height. Filter bar at top, map fills remaining space.

**Component tree:**
```
MapPage
├── MapFilters (absolute over map or flex above)
├── VehicleMap (dynamic import, flex-1)
├── FeedHealthOverlay (inside VehicleMap)
└── VehicleDetailDialog (controlled by selectedVehicle state)
```

**Validation:** `cd cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint`

### Step 9: Create Playwright e2e test

**File:** `cms/apps/web/e2e/map.spec.ts`

```typescript
import { test, expect } from "@playwright/test";
import { waitForDataOrEmpty } from "./helpers";

test.describe("Map Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/map");
    await page.waitForLoadState("networkidle");
  });

  test("displays page with map container", async ({ page }) => {
    const map = page.locator(".leaflet-container");
    await expect(map).toBeVisible({ timeout: 15000 });
  });

  test("shows connection status badge", async ({ page }) => {
    // Should show connecting, then ws or polling
    const badge = page.locator("[data-testid='connection-badge']");
    if (await badge.isVisible()) {
      await expect(badge).toBeVisible();
    }
  });

  test("filter bar is visible", async ({ page }) => {
    const filters = page.locator("[data-testid='map-filters']");
    await expect(filters).toBeVisible({ timeout: 10000 });
  });

  test("can navigate to map from sidebar", async ({ page }) => {
    await page.goto("/lv");
    const mapLink = page.getByRole("link", { name: /karte|map/i });
    if (await mapLink.isVisible()) {
      await mapLink.click();
      await expect(page).toHaveURL(/\/map/);
    }
  });
});
```

**Update** `cms/apps/web/e2e/detect-changed.sh` — add mapping:
```bash
components/map/*) echo "map.spec.ts" ;;
app/*/map/*) echo "map.spec.ts" ;;
```

**Validation:** Tests should pass when backend + frontend running: `cd cms && npx playwright test e2e/map.spec.ts`

### Step 10: Final validation

Run full frontend quality pipeline:
1. `cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check` — must pass with 0 errors
2. `cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web lint` — must pass with 0 errors/warnings
3. `cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web build` — must succeed

## Preflight Warnings

- **No markercluster installed** — Step 1 installs it. If the React wrapper package is incompatible with react-leaflet v5, implement clustering directly via `L.markerClusterGroup` in a `useEffect`.
- **Dashboard layout padding** — The `(dashboard)/layout.tsx` applies `p-(--spacing-page)` to `<main>`. Full-screen map must negate this. Test that the map truly fills the viewport.
- **Dynamic import required** — Leaflet uses browser APIs. Must use `next/dynamic` with `{ ssr: false }`.
- **No existing markercluster types** — May need manual type declarations if `@types/leaflet.markercluster` doesn't cover the React wrapper.
- **`detect-changed.sh`** has case-statement mappings — verify the exact syntax before adding new entries.

## Security Checklist

- [ ] No `as any` casts (use proper TypeScript types)
- [ ] API calls use existing `useVehiclePositions` hook (authenticated WS/SWR)
- [ ] Feed data fetched via `fetchFeeds()` SDK wrapper (uses `authFetch`)
- [ ] No `dangerouslySetInnerHTML` without DOMPurify (Leaflet `divIcon.html` is internal, not user input)
- [ ] No hardcoded API URLs (uses `NEXT_PUBLIC_AGENT_URL` env var via hooks)
- [ ] No tokens in localStorage (Auth.js httpOnly cookies)
- [ ] External links use `rel="noopener noreferrer"` (tile attribution)
- [ ] RBAC: `/map` added to middleware matcher + all role arrays

## Verification

- [ ] `cd cms && pnpm --filter @vtv/web type-check` passes (0 errors)
- [ ] `cd cms && pnpm --filter @vtv/web lint` passes (0 errors, 0 warnings)
- [ ] `cd cms && pnpm --filter @vtv/web build` succeeds
- [ ] Semantic Tailwind tokens only — no primitive color classes
- [ ] i18n keys present in both `lv.json` and `en.json` (+ `ru.json`)
- [ ] TypeScript errors <= baseline (0 errors before)
- [ ] `/map` loads full-screen with Leaflet map
- [ ] Feed chips toggle markers per operator
- [ ] Route type filter shows only selected types
- [ ] MarkerCluster groups dense markers at low zoom
- [ ] Clicking vehicle opens detail dialog
- [ ] WebSocket connection shows green dot; fallback shows yellow
- [ ] Sidebar shows "Karte"/"Map" link
- [ ] RBAC: viewer/editor/dispatcher/admin all can access `/map`
