# Plan: Analytics Dashboard Page

## Feature Metadata
**Feature Type**: New Page
**Estimated Complexity**: High
**Route**: `/[locale]/(dashboard)/analytics`
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer

## Feature Description

The Analytics page provides planners and administrators with operational intelligence across four domains: fleet utilization, driver shift coverage, on-time performance, and maintenance/compliance alerts. It consumes four new backend endpoints under `/api/v1/analytics/` (fleet-summary, driver-summary, on-time-performance, overview) that aggregate data from existing vehicle, driver, and GTFS-RT sources.

The page loads the combined overview endpoint on mount (single request for all KPIs), then allows drill-down into each domain via tabs. Each tab renders charts (bar charts, donut charts) and data tables using `@tremor/react` for chart components. KPI summary cards at the top provide at-a-glance metrics: active vehicles, on-duty drivers, network on-time percentage, and urgent alerts count.

All data is point-in-time (no historical time-series yet). The overview endpoint refreshes every 60 seconds via SWR. Individual tab data can be manually refreshed. The on-time performance tab supports optional date and time-window filters for peak-period analysis.

## Design System

### Master Rules (from MASTER.md)
- Border radius: `0` on all components (sharp corners). Exception: avatars, switches, scrollbar thumbs, status dots
- Typography: Lexend (headings), Source Sans 3 (body)
- Spacing: use `--spacing-*` tokens via `p-(--spacing-card)`, `gap-(--spacing-grid)` etc.
- Shadows: `--shadow-sm` for subtle lift, `--shadow-md` for cards
- No emojis as icons, no rounded corners, no low contrast, no motion effects

### Page Override
- None exists in `cms/design-system/vtv/pages/` -- generate during execution using ui-ux-pro-max skill if needed, otherwise follow MASTER.md defaults

### Tokens Used
- `bg-surface`, `bg-card-bg`, `border-card-border` -- card backgrounds
- `text-foreground`, `text-foreground-muted`, `text-foreground-subtle` -- text hierarchy
- `bg-status-ontime`, `text-status-ontime` -- on-time metrics (green)
- `bg-status-delayed`, `text-status-delayed` -- delayed metrics (amber)
- `bg-status-critical`, `text-status-critical` -- critical alerts (red)
- `bg-transport-bus`, `bg-transport-trolleybus`, `bg-transport-tram` -- vehicle type colors
- `border-border` -- card/section borders
- `bg-interactive`, `text-interactive` -- active tab, links
- `--spacing-page`, `--spacing-section`, `--spacing-card`, `--spacing-grid`, `--spacing-inline`

## Components Needed

### Existing (shadcn/ui)
- `Card` -- KPI metric cards wrapper
- `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` -- domain tabs (Fleet / Drivers / Performance)
- `Table`, `TableHeader`, `TableRow`, `TableHead`, `TableBody`, `TableCell` -- route performance table
- `Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem` -- date/time filters
- `Badge` -- status badges for alerts
- `Skeleton` -- loading states
- `Button` -- refresh button
- `Input` -- date input for performance filter
- `Progress` -- inline on-time percentage bars in table

### New npm Package to Install
- `@tremor/react` -- chart components (BarChart, DonutChart). Built on Recharts.
  - **Compatibility note:** `@tremor/react` v3 was built for Tailwind v3. VTV uses Tailwind v4. The executor MUST verify the package installs and builds successfully in Task 1. If Tremor has peer dependency or styling conflicts, fall back to `recharts` (v2.15+) directly and build simple chart wrappers using VTV semantic tokens. The chart component interfaces should remain the same regardless of underlying library.

### Custom Components to Create
- `analytics/analytics-content.tsx` -- Main client component (SWR data fetching, tab layout, KPI cards)
- `analytics/fleet-overview.tsx` -- Fleet tab: vehicle type bar chart, status donut, maintenance alerts
- `analytics/driver-overview.tsx` -- Driver tab: shift coverage bar chart, status donut, expiry alerts
- `analytics/performance-overview.tsx` -- Performance tab: route table with on-time bars, filters

## i18n Keys

### English (`en.json`)
```json
{
  "nav": {
    "analytics": "Analytics"
  },
  "analytics": {
    "title": "Operations Analytics",
    "refresh": "Refresh",
    "lastUpdated": "Last updated: {time}",
    "noData": "No data available",
    "loading": "Loading analytics...",
    "error": "Failed to load analytics data",
    "kpi": {
      "activeVehicles": "Active Vehicles",
      "activeVehiclesOf": "of {total} total",
      "onDutyDrivers": "Drivers On Duty",
      "onDutyDriversOf": "of {total} total",
      "networkOnTime": "Network On-Time",
      "networkOnTimeTrips": "{count} tracked trips",
      "urgentAlerts": "Urgent Alerts",
      "urgentAlertsDesc": "maintenance & expiry"
    },
    "tabs": {
      "fleet": "Fleet",
      "drivers": "Drivers",
      "performance": "Performance"
    },
    "fleet": {
      "title": "Fleet Utilization",
      "byType": "Vehicles by Type",
      "byStatus": "Status Distribution",
      "bus": "Bus",
      "trolleybus": "Trolleybus",
      "tram": "Tram",
      "active": "Active",
      "inactive": "Inactive",
      "maintenance": "In Maintenance",
      "unassigned": "Unassigned Vehicles",
      "avgMileage": "Average Mileage",
      "alerts": "Fleet Alerts",
      "maintenanceDue": "Maintenance due within 7 days",
      "registrationExpiring": "Registration expiring within 30 days"
    },
    "drivers": {
      "title": "Driver Coverage",
      "byShift": "Drivers by Shift",
      "byStatus": "Status Distribution",
      "morning": "Morning",
      "afternoon": "Afternoon",
      "evening": "Evening",
      "night": "Night",
      "available": "Available",
      "onDuty": "On Duty",
      "onLeave": "On Leave",
      "sick": "Sick",
      "alerts": "Driver Alerts",
      "licenseExpiring": "License expiring within 30 days",
      "medicalExpiring": "Medical cert expiring within 30 days"
    },
    "performance": {
      "title": "On-Time Performance",
      "route": "Route",
      "scheduled": "Scheduled",
      "tracked": "Tracked",
      "onTime": "On Time",
      "late": "Late",
      "early": "Early",
      "onTimePercent": "On-Time %",
      "avgDelay": "Avg Delay",
      "filterDate": "Date",
      "filterTimeFrom": "From",
      "filterTimeUntil": "Until",
      "applyFilters": "Apply",
      "seconds": "{value}s",
      "noRoutes": "No route performance data available",
      "transitUnavailable": "Transit data temporarily unavailable"
    }
  }
}
```

### Latvian (`lv.json`)
```json
{
  "nav": {
    "analytics": "Analitika"
  },
  "analytics": {
    "title": "Darbibas analitika",
    "refresh": "Atjaunot",
    "lastUpdated": "Pedejo reizi atjaunots: {time}",
    "noData": "Nav datu",
    "loading": "Ielade analitiku...",
    "error": "Neizdevas ieladet analitiku",
    "kpi": {
      "activeVehicles": "Aktivi transportlidzekli",
      "activeVehiclesOf": "no {total} kopuma",
      "onDutyDrivers": "Vadtaji maijna",
      "onDutyDriversOf": "no {total} kopuma",
      "networkOnTime": "Tikla precizitate",
      "networkOnTimeTrips": "{count} izsekoti reisi",
      "urgentAlerts": "Steidzami bridinajumi",
      "urgentAlertsDesc": "apkope un termiini"
    },
    "tabs": {
      "fleet": "Autoparks",
      "drivers": "Vaditaji",
      "performance": "Veiktspeja"
    },
    "fleet": {
      "title": "Autoparka izmantosana",
      "byType": "Transportlidzekli pec tipa",
      "byStatus": "Statusa sadalijums",
      "bus": "Autobuss",
      "trolleybus": "Trolejbuss",
      "tram": "Tramvajs",
      "active": "Aktivs",
      "inactive": "Neaktivs",
      "maintenance": "Apkope",
      "unassigned": "Nepieskirtie",
      "avgMileage": "Videjais nobraukums",
      "alerts": "Autoparka bridinajumi",
      "maintenanceDue": "Apkope nepieciesama 7 dienu laika",
      "registrationExpiring": "Registracija beidzas 30 dienu laika"
    },
    "drivers": {
      "title": "Vaditaju nosegums",
      "byShift": "Vaditaji pec mainas",
      "byStatus": "Statusa sadalijums",
      "morning": "Rita",
      "afternoon": "Pusdienas",
      "evening": "Vakara",
      "night": "Nakts",
      "available": "Pieejams",
      "onDuty": "Maina",
      "onLeave": "Atvalinajums",
      "sick": "Slimibas lapa",
      "alerts": "Vaditaju bridinajumi",
      "licenseExpiring": "Aplieciba beidzas 30 dienu laika",
      "medicalExpiring": "Mediciniska izziia beidzas 30 dienu laika"
    },
    "performance": {
      "title": "Precizitates raditaji",
      "route": "Marsruts",
      "scheduled": "Planotie",
      "tracked": "Izsekotie",
      "onTime": "Laika",
      "late": "Kave",
      "early": "Agrak",
      "onTimePercent": "Laika %",
      "avgDelay": "Vid. kavesanas",
      "filterDate": "Datums",
      "filterTimeFrom": "No",
      "filterTimeUntil": "Lidz",
      "applyFilters": "Piemerot",
      "seconds": "{value}s",
      "noRoutes": "Nav marsrutu veiktspejas datu",
      "transitUnavailable": "Tranzita dati isinlaicigi nav pieejami"
    }
  }
}
```

## Data Fetching

- **Primary endpoint**: `GET /api/v1/analytics/overview` -- returns fleet + drivers + on_time in a single response. Used on initial page load via SWR with 60s refresh.
- **Performance drill-down**: `GET /api/v1/analytics/on-time-performance?date=YYYY-MM-DD&time_from=HH:MM&time_until=HH:MM` -- used when user applies filters in Performance tab.
- **Server vs Client**: All data fetched client-side via SWR (analytics is real-time aggregate data, not suitable for SSR caching).
- **Loading states**: Skeleton components matching KPI card and chart dimensions.

### CRITICAL -- Server/client boundary for API clients:
- `authFetch` (from `src/lib/auth-fetch.ts`) handles dual-context (server/client) via dynamic imports. Use `authFetch` for all analytics API calls.
- The SWR hook uses `swrFetcher` (wraps `authFetch`) for the overview endpoint.
- For the filtered on-time endpoint, use `authFetch` directly in an `async` callback (not SWR, since query params change on user action).
- NEVER statically import `auth()` from `next-auth` in client components.

## RBAC Integration

- **Middleware matcher**: Add `analytics` to the matcher pattern
- **Role permissions**: All four roles (admin, dispatcher, editor, viewer) can access analytics -- it is read-only operational data
- Update `ROLE_PERMISSIONS` in `middleware.ts` to add `"/analytics"` to every role's array

## Sidebar Navigation

- **Label key**: `nav.analytics`
- **Icon**: `BarChart3` from lucide-react (bar chart icon, fits analytics context)
- **Position**: After "vehicles", before "gtfs" in the navItems array
- **Role visibility**: All roles (no filtering needed)

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` -- Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` -- Design system master rules
- `cms/apps/web/CLAUDE.md` -- Frontend-specific conventions, React 19 anti-patterns

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` -- Server component delegating to client content component
- `cms/apps/web/src/components/dashboard/dashboard-content.tsx` -- Client component with SWR data fetching, tabs, session gating
- `cms/apps/web/src/components/dashboard/metric-card.tsx` -- KPI card component pattern (semantic tokens, delta badges)
- `cms/apps/web/src/hooks/use-dashboard-metrics.ts` -- SWR hook pattern with session gating

### Files to Modify
- `cms/apps/web/messages/en.json` -- Add English translations
- `cms/apps/web/messages/lv.json` -- Add Latvian translations
- `cms/apps/web/middleware.ts` -- Add route matcher + role permissions
- `cms/apps/web/src/components/app-sidebar.tsx` -- Add analytics nav entry

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping table and forbidden class list are loaded via `@_shared/tailwind-token-map.md`. Key rules:
- Use the mapping table for all color decisions
- Check `cms/packages/ui/src/tokens.css` for available tokens
- Vehicle type badges: `bg-transport-bus`, `bg-transport-trolleybus`, `bg-transport-tram`
- Status colors: `text-status-ontime` (green), `text-status-delayed` (amber), `text-status-critical` (red)
- For Tremor/Recharts chart colors: use CSS variable values from tokens.css (e.g., `var(--color-transport-bus)`) since chart libraries accept CSS color strings, not Tailwind classes

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** -- use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** -- extract all sub-components to module scope or separate files
- **No `Math.random()` in render** -- use `useId()` or generate outside render
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies**
- **Shared type changes require ripple-effect tasks**
- **Const literal narrowing** -- annotate runtime-determined values as `string` to avoid TS2367

## TypeScript Security Rules

- Never use `as` casts on API response data without runtime validation
- Clear `.next` cache when module resolution errors persist: `rm -rf cms/apps/web/.next`

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Install charting library
**Action:** INSTALL

```bash
cd cms && pnpm --filter @vtv/web add @tremor/react
```

After install, run `pnpm --filter @vtv/web build` to verify no build errors. If `@tremor/react` fails due to Tailwind v4 incompatibility or React 19 peer dep conflicts:
1. Remove it: `pnpm --filter @vtv/web remove @tremor/react`
2. Install Recharts directly: `pnpm --filter @vtv/web add recharts`
3. Note the fallback and adapt chart component code in Tasks 9-11 to use Recharts `<BarChart>`, `<PieChart>`, `<Bar>`, `<Pie>`, `<XAxis>`, `<YAxis>`, `<Tooltip>`, `<Cell>`, `<ResponsiveContainer>` instead of Tremor components.

**Per-task validation:**
- `pnpm --filter @vtv/web build` passes (zero errors)

---

### Task 2: Create TypeScript types
**File:** `cms/apps/web/src/types/analytics.ts` (create)
**Action:** CREATE

Define interfaces matching the backend response schemas from `.agents/plans/analytics-endpoints.md`:

```typescript
export interface FleetTypeSummary {
  vehicle_type: "bus" | "trolleybus" | "tram";
  total: number;
  active: number;
  inactive: number;
  in_maintenance: number;
}

export interface FleetSummaryResponse {
  total_vehicles: number;
  active_vehicles: number;
  inactive_vehicles: number;
  in_maintenance: number;
  by_type: FleetTypeSummary[];
  maintenance_due_7d: number;
  registration_expiring_30d: number;
  unassigned_vehicles: number;
  average_mileage_km: number;
  generated_at: string;
}

export interface ShiftCoverageSummary {
  shift: "morning" | "afternoon" | "evening" | "night";
  total: number;
  available: number;
  on_duty: number;
  on_leave: number;
  sick: number;
}

export interface DriverSummaryResponse {
  total_drivers: number;
  available_drivers: number;
  on_duty_drivers: number;
  on_leave_drivers: number;
  sick_drivers: number;
  by_shift: ShiftCoverageSummary[];
  license_expiring_30d: number;
  medical_expiring_30d: number;
  generated_at: string;
}

export interface RoutePerformanceSummary {
  route_id: string;
  route_short_name: string;
  scheduled_trips: number;
  tracked_trips: number;
  on_time_count: number;
  late_count: number;
  early_count: number;
  on_time_percentage: number;
  average_delay_seconds: number;
}

export interface OnTimePerformanceResponse {
  service_date: string;
  service_type: string;
  time_from: string | null;
  time_until: string | null;
  total_routes: number;
  network_on_time_percentage: number;
  network_average_delay_seconds: number;
  routes: RoutePerformanceSummary[];
  generated_at: string;
}

export interface AnalyticsOverviewResponse {
  fleet: FleetSummaryResponse;
  drivers: DriverSummaryResponse;
  on_time: OnTimePerformanceResponse;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Create analytics SWR hook
**File:** `cms/apps/web/src/hooks/use-analytics.ts` (create)
**Action:** CREATE

Follow the pattern from `use-dashboard-metrics.ts`. Use SWR with `swrFetcher` for the overview endpoint:

```typescript
"use client";

import useSWR from "swr";
import { useSession } from "next-auth/react";
import type { AnalyticsOverviewResponse } from "@/types/analytics";

const API_BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export function useAnalyticsOverview() {
  const { status } = useSession();

  const swrKey =
    status === "authenticated"
      ? `${API_BASE}/api/v1/analytics/overview`
      : null;

  const { data, error, isLoading, mutate } = useSWR<AnalyticsOverviewResponse>(
    swrKey,
    { refreshInterval: 60_000 }
  );

  return {
    data,
    isLoading,
    error: error instanceof Error ? error.message : null,
    refresh: mutate,
  };
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 4: Add i18n keys -- English
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add `"analytics"` key to `nav` section (after `"vehicles"` entry).
Add complete `"analytics"` section as specified in i18n Keys above.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 5: Add i18n keys -- Latvian
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add `"analytics"` key to `nav` section (after `"vehicles"` entry, matching en.json structure).
Add complete `"analytics"` section as specified in i18n Keys above.

IMPORTANT: Verify both files have exactly the same key structure. Every key in en.json must exist in lv.json and vice versa.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 6: Create Fleet Overview component
**File:** `cms/apps/web/src/components/analytics/fleet-overview.tsx` (create)
**Action:** CREATE

Client component displaying fleet utilization data from `FleetSummaryResponse`.

Layout:
- Two-column grid on desktop (single column on mobile): left = bar chart (vehicles by type), right = donut chart (status distribution)
- Below charts: stats row with unassigned count and average mileage
- Below stats: alerts section (maintenance due 7d, registration expiring 30d) using Badge components with status colors

**Chart: Vehicles by Type (Bar Chart)**
- If using Tremor: `<BarChart data={byTypeData} index="type" categories={["active", "inactive", "in_maintenance"]} colors={[...]}>`
- If using Recharts: `<ResponsiveContainer><BarChart data={byTypeData}><XAxis dataKey="type" /><Bar dataKey="active" stackId="a" /><Bar dataKey="inactive" stackId="a" /><Bar dataKey="in_maintenance" stackId="a" /></BarChart></ResponsiveContainer>`
- Chart colors: Use CSS variables `var(--color-status-ontime)` for active, `var(--color-foreground-muted)` for inactive, `var(--color-status-delayed)` for maintenance
- Map type labels through `useTranslations("analytics.fleet")`

**Chart: Status Distribution (Donut)**
- Show active / inactive / maintenance as donut segments
- Center label: total vehicle count

**Alerts section:**
- If `maintenance_due_7d > 0`: render Badge with `bg-status-delayed/10 text-status-delayed` showing count + translated label
- If `registration_expiring_30d > 0`: render Badge with `bg-status-critical/10 text-status-critical` showing count + translated label

Props: `{ data: FleetSummaryResponse }`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: Create Driver Overview component
**File:** `cms/apps/web/src/components/analytics/driver-overview.tsx` (create)
**Action:** CREATE

Client component displaying driver coverage data from `DriverSummaryResponse`.

Layout (mirrors fleet-overview structure):
- Two-column grid: left = bar chart (drivers by shift), right = donut chart (status distribution)
- Below: alerts section (license expiring 30d, medical cert expiring 30d)

**Chart: Drivers by Shift (Bar Chart)**
- Data from `by_shift` array, grouped bars for available/on_duty/on_leave/sick per shift
- Shift labels from translations: morning/afternoon/evening/night
- Colors: `var(--color-status-ontime)` available, `var(--color-interactive)` on_duty, `var(--color-status-delayed)` on_leave, `var(--color-status-critical)` sick

**Chart: Status Distribution (Donut)**
- available / on_duty / on_leave / sick segments
- Center label: total driver count

**Alerts section:**
- Same pattern as fleet alerts with license and medical expiry counts

Props: `{ data: DriverSummaryResponse }`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 8: Create Performance Overview component
**File:** `cms/apps/web/src/components/analytics/performance-overview.tsx` (create)
**Action:** CREATE

Client component displaying on-time performance from `OnTimePerformanceResponse`.

Layout:
- Top: filter bar with date input, time_from input, time_until input, Apply button
- Network summary: large on-time percentage display with average delay
- Table: route performance ranked by worst on-time percentage

**Filter bar:**
- `<Input type="date">` for date filter (default: today)
- `<Input type="time">` for time_from and time_until (optional, empty = full day)
- `<Button>` to apply filters
- On apply: call `authFetch` with query params to `GET /api/v1/analytics/on-time-performance?date=...&time_from=...&time_until=...`
- Store filtered result in local state (separate from SWR overview data)

**Network summary row:**
- Large text: `{network_on_time_percentage}%` with color based on value (>=90 = status-ontime, >=75 = status-delayed, <75 = status-critical)
- Subtitle: service_date, service_type, total_routes count

**Route performance table:**
- Columns: Route | Scheduled | Tracked | On Time | Late | Early | On-Time % | Avg Delay
- On-Time % column: show number + inline `<Progress>` bar colored by threshold
- Avg Delay column: show `{value}s` formatted
- Sort by worst on-time percentage (data comes pre-sorted from backend)
- If `routes` is empty: show translated "noRoutes" message
- Wrap in `<div className="overflow-x-auto">` for mobile

**Transit unavailable fallback:**
- If on_time data fetch fails, show translated "transitUnavailable" message with `text-foreground-muted`

Props: `{ data: OnTimePerformanceResponse }`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 9: Create Analytics Content component
**File:** `cms/apps/web/src/components/analytics/analytics-content.tsx` (create)
**Action:** CREATE

Main client component that orchestrates the entire analytics page. Follow the `dashboard-content.tsx` pattern.

```typescript
"use client";
// imports: useTranslations, useSession, Tabs components, Skeleton,
// useAnalyticsOverview, MetricCard (reuse from dashboard), lucide icons,
// FleetOverview, DriverOverview, PerformanceOverview
```

**KPI Cards row (4 cards in responsive grid):**
- `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-(--spacing-grid)`
- Card 1: Active Vehicles -- value=`fleet.active_vehicles`, subtitle=`of {total} total`, icon=`<Truck />`
- Card 2: Drivers On Duty -- value=`drivers.on_duty_drivers`, subtitle=`of {total} total`, icon=`<Users />`
- Card 3: Network On-Time -- value=`on_time.network_on_time_percentage + "%"`, subtitle=`{count} tracked trips`, icon=`<Clock />`
  - deltaType based on percentage: >=90 positive, >=75 neutral, <75 negative
- Card 4: Urgent Alerts -- value=sum of maintenance_due_7d + registration_expiring_30d + license_expiring_30d + medical_expiring_30d, subtitle="maintenance & expiry", icon=`<AlertTriangle />`
  - deltaType: >0 negative, 0 positive

**Tabs section below KPI cards:**
- `<Tabs defaultValue="fleet">` with `TabsList` containing Fleet / Drivers / Performance triggers
- Each `TabsContent` renders the corresponding overview component
- Pass the relevant slice of data: `data.fleet`, `data.drivers`, `data.on_time`

**Loading state:**
- When `isLoading`: render 4 Skeleton cards + Skeleton placeholder for chart area
- When `error`: render error message with retry button calling `refresh()`

**Session gating:**
- Use `useSession()` status check -- the SWR hook already gates on authenticated status

Reuse `MetricCard` from `@/components/dashboard/metric-card` for KPI cards (same interface: icon, title, value, delta, deltaType, subtitle).

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Create page component
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/analytics/page.tsx` (create)
**Action:** CREATE

Server component following the dashboard page pattern exactly:

```typescript
import { AnalyticsContent } from "@/components/analytics/analytics-content";

export default async function AnalyticsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return <AnalyticsContent locale={locale} />;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 11: Update middleware for RBAC
**File:** `cms/apps/web/middleware.ts` (modify)
**Action:** UPDATE

1. Add `"/analytics"` to ALL four role arrays in `ROLE_PERMISSIONS`:
   - `admin: [..., "/analytics"]`
   - `dispatcher: [..., "/analytics"]`
   - `editor: [..., "/analytics"]`
   - `viewer: [..., "/analytics"]`

2. Add `analytics` to the matcher pattern:
   ```typescript
   matcher: ["/(lv|en)/(routes|stops|schedules|drivers|vehicles|analytics|gtfs|users|chat|documents)/:path*"],
   ```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 12: Update sidebar navigation
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify)
**Action:** UPDATE

1. Add `{ key: "analytics", href: "/analytics", enabled: true }` to `navItems` array, positioned after `vehicles` and before `gtfs` (line ~28).

The `navItems` array should be:
```typescript
const navItems = [
  { key: "dashboard", href: "", enabled: true },
  { key: "routes", href: "/routes", enabled: true },
  { key: "stops", href: "/stops", enabled: true },
  { key: "schedules", href: "/schedules", enabled: true },
  { key: "drivers", href: "/drivers", enabled: true },
  { key: "vehicles", href: "/vehicles", enabled: true },
  { key: "analytics", href: "/analytics", enabled: true },
  { key: "gtfs", href: "/gtfs", enabled: true },
  { key: "users", href: "/users", enabled: true },
  { key: "documents", href: "/documents", enabled: true },
  { key: "chat", href: "/chat", enabled: true },
] as const;
```

No icon changes needed -- the sidebar uses text-only nav items (no icons in current implementation).

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

## Final Validation (3-Level Pyramid)

Run each level in order -- every one must pass with 0 errors:

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

- [ ] Page renders at `/lv/analytics` and `/en/analytics`
- [ ] i18n keys present in both lv.json and en.json (all keys match)
- [ ] Middleware updated -- all 4 roles can access `/analytics`
- [ ] Sidebar nav link appears between Vehicles and GTFS
- [ ] KPI cards show loading skeletons then data from overview endpoint
- [ ] Fleet tab shows vehicle type bar chart and status donut
- [ ] Driver tab shows shift coverage bar chart and status donut
- [ ] Performance tab shows route table with on-time bars
- [ ] Performance filters (date, time) trigger new API call
- [ ] No hardcoded colors -- all styling uses semantic tokens
- [ ] Chart colors use CSS variables from tokens.css
- [ ] Accessibility: all interactive elements have labels, charts have aria-labels
- [ ] Mobile responsive: cards stack, charts resize, table scrolls horizontally

## Acceptance Criteria

This feature is complete when:
- [ ] Page accessible at `/{locale}/analytics`
- [ ] RBAC enforced -- all roles can access (read-only)
- [ ] Both languages have complete translations
- [ ] Design system rules followed (MASTER.md: sharp corners, semantic tokens, spacing tokens)
- [ ] Charts render with VTV design system colors (transport-*, status-*)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`
