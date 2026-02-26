# Plan: Dashboard Real Data Integration

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: `/[locale]/` (existing dashboard page — no route change)
**Auth Required**: Yes (all authenticated users)
**Allowed Roles**: admin, dispatcher, editor, viewer

## Feature Description

Replace the hardcoded mock metrics on the VTV dashboard with live data from backend APIs. The dashboard currently imports `MOCK_METRICS` from `mock-dashboard-data.ts` and displays four static metric cards: Active Vehicles (342), On-Time Performance (94.2%), Delayed Routes (3), and Fleet Utilization (87%). All values are hardcoded strings that never change.

This plan connects the metrics section to real backend endpoints:
- **Active Vehicles** — from `GET /api/v1/transit/vehicles` response field `count` (real-time GTFS-RT)
- **On-Time Performance** — derived from the same vehicles response: `% of vehicles with |delay_seconds| <= 300`
- **Delayed Routes** — derived from vehicles response: count of distinct `route_id` where any vehicle has `delay_seconds > 300`
- **Active Routes** — from `GET /api/v1/schedules/routes?is_active=true&page_size=1` response field `total` (replaces "Fleet Utilization" which requires untracked fleet inventory data)

The calendar section retains mock events because no operational events backend exists. The file `mock-dashboard-data.ts` is preserved for calendar use but the `MOCK_METRICS` export is removed.

## Design System

### Master Rules (from MASTER.md)
- Spacing: `--spacing-section` (16px) between sections, `--spacing-grid` (12px) grid gaps, `--spacing-card` (12px) card padding
- Typography: Lexend headings (`font-heading`), Source Sans 3 body (`font-body`)
- Cards: `border-card-border`, `bg-card-bg`, `rounded-lg`, hover shadow transition
- Status colors: `--color-status-ontime` (green), `--color-status-delayed` (amber), `--color-status-critical` (red)

### Page Override
None — no file exists at `cms/design-system/vtv/pages/dashboard.md`. Use MASTER.md rules only.

### Tokens Used
- Surface: `bg-card-bg`, `border-card-border`, `bg-surface`
- Text: `text-foreground`, `text-foreground-muted`
- Status: `bg-status-ontime/10`, `text-status-ontime`, `bg-status-critical/10`, `text-status-critical`
- Spacing: `--spacing-section`, `--spacing-grid`, `--spacing-card`, `--spacing-inline`, `--spacing-tight`

## Components Needed

### Existing (shadcn/ui — already installed)
- `Skeleton` — loading placeholders for metric cards during API fetch
- `Button` — "Manage Routes" link button (existing usage, unchanged)
- `ResizablePanelGroup/Panel/Handle` — metrics/calendar layout (existing, unchanged)

### Existing Custom Components
- `MetricCard` at `cms/apps/web/src/components/dashboard/metric-card.tsx` — UPDATE to make delta optional
- `CalendarGrid` at `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — unchanged

### New Custom Components
- `DashboardMetrics` at `cms/apps/web/src/components/dashboard/dashboard-metrics.tsx` — client component that fetches live data and renders 4 MetricCard instances with loading/error states

### No New shadcn/ui Installs Needed

## i18n Keys

### Latvian (`lv.json`) — ADD to existing `dashboard.metrics` object

```json
{
  "dashboard": {
    "metrics": {
      "activeVehicles": "Aktīvi transportlīdzekļi",
      "onTimePerformance": "Savlaicīgums",
      "delayedRoutes": "Kavēti maršruti",
      "fleetUtilization": "Parka izmantojums",
      "comparedToLastMonth": "Salīdzinot ar iepriekšējo mēnesi",
      "activeRoutes": "Aktīvi maršruti",
      "onRoutes": "uz {count} maršrutiem",
      "vehiclesOnTime": "{count} no {total} laikā",
      "ofTotalRoutes": "no {total} maršrutiem",
      "totalInSystem": "no {total} sistēmā",
      "unavailable": "Dati nav pieejami",
      "liveIndicator": "Reāllaiks"
    }
  }
}
```

### English (`en.json`) — ADD to existing `dashboard.metrics` object

```json
{
  "dashboard": {
    "metrics": {
      "activeVehicles": "Active Vehicles",
      "onTimePerformance": "On-Time Performance",
      "delayedRoutes": "Delayed Routes",
      "fleetUtilization": "Fleet Utilization",
      "comparedToLastMonth": "Compared to last month",
      "activeRoutes": "Active Routes",
      "onRoutes": "across {count} routes",
      "vehiclesOnTime": "{count} of {total} on time",
      "ofTotalRoutes": "of {total} routes",
      "totalInSystem": "of {total} in system",
      "unavailable": "Data unavailable",
      "liveIndicator": "Live"
    }
  }
}
```

**Note:** Existing keys (`activeVehicles`, `onTimePerformance`, `delayedRoutes`, `fleetUtilization`, `comparedToLastMonth`) are KEPT as-is. New keys are ADDED alongside them. The 4th metric card label changes from `fleetUtilization` to `activeRoutes` at the component level.

## Data Fetching

### API Endpoints Used
| Endpoint | Purpose | Response Fields Used |
|---|---|---|
| `GET /api/v1/transit/vehicles` | Active vehicle count + delay data | `count`, `vehicles[].delay_seconds`, `vehicles[].route_id` |
| `GET /api/v1/schedules/routes?is_active=true&page_size=1` | Active route count | `total` |
| `GET /api/v1/schedules/routes?page_size=1` | Total route count (for subtitle) | `total` |

### Server vs Client
- **Metrics**: Client-side fetching via `useDashboardMetrics` hook (needs polling for live vehicle data)
- **Calendar**: Server-side static data (mock events, unchanged)

### Polling Strategy
- Vehicle data: Poll every 30 seconds (less aggressive than routes map 10s — dashboard only needs counts)
- Route counts: Fetch once on mount (route counts change rarely)
- On error: Show last known values with "unavailable" indicator, do not crash

### Loading States
- Skeleton placeholders in each MetricCard slot during initial load
- Smooth transition from skeleton → real values using opacity animation

## RBAC Integration

No changes needed. The dashboard is at `/[locale]/` which is the default authenticated page. It is not listed in the middleware matcher (only protected sub-routes like `/routes`, `/stops` etc. are matched). All authenticated users already see the dashboard.

## Sidebar Navigation

No changes needed. The dashboard is already the first nav item in `app-sidebar.tsx`.

## Relevant Files

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/hooks/use-vehicle-positions.ts` — Polling hook pattern with `useCallback`, `useEffect`, `useRef`
- `cms/apps/web/src/components/dashboard/metric-card.tsx` — MetricCard component API
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Current dashboard (server component + client children)

### Files to Modify
- `cms/apps/web/src/types/dashboard.ts` — Make `delta`/`deltaType` optional in `MetricData`
- `cms/apps/web/src/components/dashboard/metric-card.tsx` — Conditionally render delta badge
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Replace MOCK_METRICS with DashboardMetrics component
- `cms/apps/web/src/lib/mock-dashboard-data.ts` — Remove MOCK_METRICS export (keep MOCK_EVENTS)
- `cms/apps/web/messages/lv.json` — Add new metric i18n keys
- `cms/apps/web/messages/en.json` — Add new metric i18n keys

### Files to Create
- `cms/apps/web/src/hooks/use-dashboard-metrics.ts` — Hook to fetch and aggregate metrics
- `cms/apps/web/src/components/dashboard/dashboard-metrics.tsx` — Client component for live metrics

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities.

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400`, `text-slate-400` | `text-foreground-muted` |
| `text-white` (on colored bg) | `text-interactive-foreground` |
| `text-green-*`, `text-emerald-*` | `text-status-ontime` |
| `text-red-*` | `text-status-critical` or `text-error` |
| `text-amber-*` | `text-status-delayed` |
| `bg-green-*/10` | `bg-status-ontime/10` |
| `bg-red-*/10` | `bg-status-critical/10` |
| `bg-gray-100` | `bg-surface` or `bg-muted` |
| `border-gray-200` | `border-border` |

**Full token reference:** Check `cms/packages/ui/src/tokens.css` for all available tokens.

## React 19 Coding Rules

- **No `setState` in `useEffect`** — use `useCallback` + direct state updates as in `use-vehicle-positions.ts`
- **No component definitions inside components** — extract `DashboardMetrics` to its own file
- **No `Math.random()` in render**
- **Hook ordering: `useState` declarations MUST precede `useMemo`/`useCallback` that reference them**
- **Polling pattern**: Follow exact pattern from `use-vehicle-positions.ts` — `useCallback` for fetch, `useEffect` for interval setup with cleanup

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add i18n Keys — Latvian
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add the following keys INSIDE the existing `dashboard.metrics` object, after `comparedToLastMonth`:

```json
"activeRoutes": "Aktīvi maršruti",
"onRoutes": "uz {count} maršrutiem",
"vehiclesOnTime": "{count} no {total} laikā",
"ofTotalRoutes": "no {total} maršrutiem",
"totalInSystem": "no {total} sistēmā",
"unavailable": "Dati nav pieejami",
"liveIndicator": "Reāllaiks"
```

Do NOT remove any existing keys. The `fleetUtilization` and `comparedToLastMonth` keys must remain.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- Verify JSON is valid (no trailing commas, proper nesting)

---

### Task 2: Add i18n Keys — English
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add the following keys INSIDE the existing `dashboard.metrics` object, after `comparedToLastMonth`:

```json
"activeRoutes": "Active Routes",
"onRoutes": "across {count} routes",
"vehiclesOnTime": "{count} of {total} on time",
"ofTotalRoutes": "of {total} routes",
"totalInSystem": "of {total} in system",
"unavailable": "Data unavailable",
"liveIndicator": "Live"
```

Do NOT remove any existing keys.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- Verify JSON is valid

---

### Task 3: Update MetricData Type
**File:** `cms/apps/web/src/types/dashboard.ts` (modify)
**Action:** UPDATE

Make `delta` and `deltaType` optional in the `MetricData` interface:

```typescript
export interface MetricData {
  title: string;
  value: string;
  delta?: string;
  deltaType?: "positive" | "negative" | "neutral";
  subtitle: string;
}
```

This is a backwards-compatible change. Existing code that provides all fields continues to work.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 4: Update MetricCard Component
**File:** `cms/apps/web/src/components/dashboard/metric-card.tsx` (modify)
**Action:** UPDATE

Make `delta` and `deltaType` optional in `MetricCardProps`. Conditionally render the delta badge only when both `delta` and `deltaType` are provided.

Updated interface:
```typescript
interface MetricCardProps {
  icon: ReactNode;
  title: string;
  value: string;
  delta?: string;
  deltaType?: "positive" | "negative" | "neutral";
  subtitle: string;
}
```

In the render, wrap the delta badge in a conditional:
```tsx
{delta && deltaType && (
  <span
    className={cn(
      "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
      deltaStyles[deltaType]
    )}
  >
    {delta}
  </span>
)}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 5: Create useDashboardMetrics Hook
**File:** `cms/apps/web/src/hooks/use-dashboard-metrics.ts` (create)
**Action:** CREATE

Create a client-side hook that fetches and aggregates dashboard metrics from multiple API endpoints.

**Follow the pattern from `cms/apps/web/src/hooks/use-vehicle-positions.ts`** for:
- `useState` for data, loading, error states
- `useCallback` for the fetch function
- `useEffect` with interval for polling + cleanup

**Interface:**
```typescript
interface DashboardMetricsData {
  activeVehicles: number;
  onTimePercentage: number;
  onTimeCount: number;
  totalVehicles: number;
  delayedRoutes: number;
  activeRoutes: number;
  totalRoutes: number;
  distinctRouteCount: number;
}

interface UseDashboardMetricsResult {
  data: DashboardMetricsData | null;
  isLoading: boolean;
  error: string | null;
}
```

**Fetch logic:**

1. Fetch `${apiBase}/api/v1/transit/vehicles` (no query params):
   - `activeVehicles` = `response.count`
   - From `response.vehicles` array:
     - `onTimeCount` = count where `Math.abs(delay_seconds) <= 300`
     - `totalVehicles` = `response.vehicles.length`
     - `onTimePercentage` = `totalVehicles > 0 ? Math.round((onTimeCount / totalVehicles) * 1000) / 10 : 0`
     - `delayedRoutes` = count of distinct `route_id` values where any vehicle has `delay_seconds > 300`
     - `distinctRouteCount` = count of distinct `route_id` values across all vehicles

2. Fetch `${apiBase}/api/v1/schedules/routes?is_active=true&page_size=1`:
   - `activeRoutes` = `response.total`

3. Fetch `${apiBase}/api/v1/schedules/routes?page_size=1`:
   - `totalRoutes` = `response.total`

**Polling:** Refresh vehicle data every 30 seconds. Route counts fetch once on mount only (use a `useRef` flag to avoid re-fetching).

**Error handling:** If any fetch fails, set `error` state but keep previously fetched data visible. Use `try/catch` around each fetch independently so one failure doesn't block the others.

**API base URL:** `const apiBase = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123"` (same pattern as `use-vehicle-positions.ts`).

**API response types** (define at top of file, not exported):
```typescript
interface VehicleApiResponse {
  count: number;
  vehicles: Array<{
    vehicle_id: string;
    route_id: string;
    delay_seconds: number;
  }>;
  fetched_at: string;
}

interface PaginatedApiResponse {
  items: unknown[];
  total: number;
  page: number;
  page_size: number;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: Create DashboardMetrics Component
**File:** `cms/apps/web/src/components/dashboard/dashboard-metrics.tsx` (create)
**Action:** CREATE

Create a `"use client"` component that renders the 4 metric cards with live data.

**Imports:**
```typescript
"use client";

import { Bus, Clock, AlertTriangle, MapPin } from "lucide-react";
import { useTranslations } from "next-intl";
import { useDashboardMetrics } from "@/hooks/use-dashboard-metrics";
import { MetricCard } from "./metric-card";
import { Skeleton } from "@/components/ui/skeleton";
```

**Note:** The 4th icon changes from `Gauge` to `MapPin` since the metric changes from Fleet Utilization to Active Routes.

**Component logic:**
1. Call `useDashboardMetrics()` to get `{ data, isLoading, error }`
2. Call `useTranslations("dashboard")` for labels

**Loading state:** Show 4 Skeleton placeholders matching MetricCard dimensions:
```tsx
if (isLoading) {
  return (
    <div className="grid grid-cols-1 gap-(--spacing-grid) sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-24 rounded-lg" />
      ))}
    </div>
  );
}
```

**Data state:** Render 4 MetricCard instances:

| # | Icon | Title key | Value | Subtitle key + params |
|---|------|-----------|-------|-----------------------|
| 1 | `Bus` | `metrics.activeVehicles` | `data.activeVehicles` (number as string) | `metrics.onRoutes` with `count: data.distinctRouteCount` |
| 2 | `Clock` | `metrics.onTimePerformance` | `data.onTimePercentage + "%"` | `metrics.vehiclesOnTime` with `count: data.onTimeCount, total: data.totalVehicles` |
| 3 | `AlertTriangle` | `metrics.delayedRoutes` | `data.delayedRoutes` (number as string) | `metrics.ofTotalRoutes` with `total: data.distinctRouteCount` |
| 4 | `MapPin` | `metrics.activeRoutes` | `data.activeRoutes` (number as string) | `metrics.totalInSystem` with `total: data.totalRoutes` |

**Error/no-data state:** When `data` is null and not loading, show the grid with "—" values and `metrics.unavailable` subtitle.

**Omit delta/deltaType** from all MetricCard calls (no historical comparison data available).

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 7: Update Dashboard Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` (modify)
**Action:** UPDATE

**Changes:**

1. **Remove** the import of `MOCK_METRICS` from `@/lib/mock-dashboard-data`:
   ```typescript
   // REMOVE this:
   import { MOCK_METRICS, MOCK_EVENTS } from "@/lib/mock-dashboard-data";
   // REPLACE with:
   import { MOCK_EVENTS } from "@/lib/mock-dashboard-data";
   ```

2. **Add** import for the new component:
   ```typescript
   import { DashboardMetrics } from "@/components/dashboard/dashboard-metrics";
   ```

3. **Remove** the `METRIC_ICONS` and `METRIC_KEYS` constants (lines 17-27). These are no longer needed — `DashboardMetrics` handles icons and labels internally.

4. **Remove** the unused icon imports that were only used by METRIC_ICONS. Keep `ArrowRight` (used by the Manage Routes button). Check which icons are still needed:
   - `Bus`, `Clock`, `AlertTriangle`, `Gauge` — REMOVE (now imported inside DashboardMetrics)
   - `ArrowRight` — KEEP

5. **Replace** the metrics grid in the first `ResizablePanel` with the new component:
   ```tsx
   {/* REMOVE this: */}
   <div className="grid grid-cols-1 gap-(--spacing-grid) sm:grid-cols-2 lg:grid-cols-4">
     {MOCK_METRICS.map((metric, i) => (
       <MetricCard
         key={METRIC_KEYS[i]}
         icon={METRIC_ICONS[i]}
         title={t(`metrics.${METRIC_KEYS[i]}`)}
         value={metric.value}
         delta={metric.delta}
         deltaType={metric.deltaType}
         subtitle={t("metrics.comparedToLastMonth")}
       />
     ))}
   </div>

   {/* REPLACE with: */}
   <DashboardMetrics />
   ```

6. **Remove** the unused `MetricCard` import (now imported inside DashboardMetrics).

7. **Update** `revalidate` comment:
   ```typescript
   export const revalidate = 3600; // 1 hour — calendar uses mock data, metrics are client-side
   ```

**Final page.tsx should have these imports:**
```typescript
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DashboardMetrics } from "@/components/dashboard/dashboard-metrics";
import { CalendarGrid } from "@/components/dashboard/calendar-grid";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { MOCK_EVENTS } from "@/lib/mock-dashboard-data";
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 8: Clean Up Mock Data File
**File:** `cms/apps/web/src/lib/mock-dashboard-data.ts` (modify)
**Action:** UPDATE

1. **Remove** the entire `MOCK_METRICS` array and its export (lines 3-32)
2. **Remove** the `MetricData` type import if it was only used by MOCK_METRICS:
   - Check: `import type { CalendarEvent, MetricData } from "@/types/dashboard";`
   - If `MetricData` is no longer used in this file, remove it from the import:
     ```typescript
     import type { CalendarEvent } from "@/types/dashboard";
     ```
3. **Keep** `MOCK_EVENTS`, `getWeekDay()`, and `setTime()` — these are still used by the calendar

**After cleanup the file should:**
- Export only `MOCK_EVENTS`
- Import only `CalendarEvent` from types
- Keep the helper functions `getWeekDay` and `setTime`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes
- **Verify no other file imports `MOCK_METRICS`**: Run `grep -r "MOCK_METRICS" cms/apps/web/src/` — should return 0 matches

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

**Recovery rule:** If any level fails, fix the issue, then re-run ALL checks from Level 1 (not just the failing level). Code fixes can introduce regressions at lower levels.

**Success definition:** All 3 levels exit code 0, zero errors, zero warnings.

## Post-Implementation Checks

- [ ] Dashboard renders at `/lv/` and `/en/`
- [ ] Metric cards show loading skeletons on initial page load
- [ ] Metric values update when backend is running (not static 342/94.2%/3/87%)
- [ ] Metric cards show "—" with "Data unavailable" when backend is unreachable
- [ ] i18n: Metric labels display in both Latvian and English
- [ ] i18n: Subtitles use ICU message format with interpolated counts
- [ ] Calendar section still renders mock events (unchanged)
- [ ] "Manage Routes" button still navigates to routes page
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] Resizable panels still work (drag handle between metrics and calendar)
- [ ] No console errors in browser DevTools
- [ ] Page loads without flash of unstyled content

## Acceptance Criteria

This feature is complete when:
- [ ] Dashboard metrics show real-time data from backend APIs
- [ ] Active Vehicles shows actual GTFS-RT vehicle count
- [ ] On-Time Performance shows computed percentage from live delay data
- [ ] Delayed Routes shows count of routes with delayed vehicles
- [ ] Active Routes shows database route count (replacing Fleet Utilization)
- [ ] Loading and error states handle gracefully (skeletons, fallback text)
- [ ] Both lv.json and en.json have all new keys with proper translations
- [ ] Vehicle metrics auto-refresh every 30 seconds without page reload
- [ ] All 3 validation levels pass (type-check, lint, build)
- [ ] No regressions in calendar section or page layout
- [ ] Ready for `/commit`

## Security Checklist

- [x] No new routes added — no auth/RBAC changes needed
- [x] No user input rendered — metrics are read-only server data
- [x] No `dangerouslySetInnerHTML` — all content via React JSX
- [x] API calls use `process.env.NEXT_PUBLIC_AGENT_URL` — no hardcoded URLs
- [x] No credentials in client code — API endpoints are public within the network
- [x] No localStorage usage — metrics are fetched fresh on each mount
- [x] External links (if any) would use `rel="noopener noreferrer"` — N/A for this change
