# Plan: ML-5.1 Route Performance Dashboard (CMS)

## Feature Metadata
**Feature Type**: New Page + Backend Endpoints
**Estimated Complexity**: High
**Route**: `/[locale]/(dashboard)/analytics/routes`
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer (inherits from parent `/analytics` middleware matcher)

## Feature Description

A dedicated route performance page at `/analytics/routes` showing per-route ML-derived metrics: on-time %, average delay by stop, passenger load trend, and anomaly counts. Operations managers can select a route from a dropdown (pre-populated from GTFS routes) and choose a time window (7d/14d/30d) to visualize performance trends via 4 Recharts charts.

The existing analytics page at `/analytics` has a "Performance" tab with a table of per-route on-time stats. This new page extends that with **chart-based drill-down** for a single route — time-series on-time %, bar chart of delay by stop, load factor trend area chart, and anomaly count stacked area chart. It does NOT duplicate the existing table view.

The plan covers both backend (3 new API endpoints) and frontend (page component + SDK wrapper + i18n + sidebar nav restructuring).

## Security Contexts

**Active contexts:**
- **CTX-RBAC**: New API endpoints require role-based auth; frontend page scoped to authenticated users via existing middleware matcher
- **CTX-INPUT**: Route selector dropdown + time window filter — user input flows to backend query params. Server-side validation of route_id format and window enum

**Not applicable:** CTX-AUTH (no login flow changes), CTX-FILE (no uploads), CTX-AGENT (no AI-generated content displayed), CTX-INFRA (no Docker/nginx changes)

## Design System

### Master Rules (from MASTER.md)
- **Border radius**: 0 on all components (sharp corporate aesthetic)
- **Typography**: Lexend for headings, Source Sans 3 for body, JetBrains Mono for data
- **Spacing**: Use compact tokens — `--spacing-card` (12px) for chart cards, `--spacing-grid` (12px) for grid gaps, `--spacing-page` (16px) for page padding
- **Colors**: oklch-based semantic tokens only; no hardcoded hex except in Recharts `stroke`/`fill` props (which require CSS strings, not classes — use `var(--color-*)` references)

### Page Override
None exists — generate during execution using ui-ux-pro-max skill if desired, or follow MASTER.md directly.

### Tokens Used
- Surface: `--color-surface`, `--color-surface-raised`, `--color-card-bg`, `--color-card-border`
- Text: `--color-foreground`, `--color-foreground-muted`
- Interactive: `--color-interactive`
- Status: `--color-status-ontime`, `--color-status-delayed`, `--color-status-critical`
- Spacing: `--spacing-page`, `--spacing-section`, `--spacing-card`, `--spacing-grid`, `--spacing-inline`
- Border: `--color-border`

## Components Needed

### Existing (shadcn/ui)
- `Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem` — route selector dropdown
- `Button` — time window toggle buttons
- `Skeleton` — loading state placeholders
- `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` — optional chart grouping

### Existing (custom)
- `MetricCard` from `@/components/dashboard/metric-card` — KPI summary cards

### New shadcn/ui to Install
None required — all needed components are already installed.

### Custom Components to Create
- `RoutePerformanceDashboard` at `cms/apps/web/src/components/analytics/route-performance/route-performance-dashboard.tsx` — main client component with route selector, time window, 4 charts
- `ChartCard` at `cms/apps/web/src/components/analytics/route-performance/chart-card.tsx` — reusable chart wrapper (border + title + value + Recharts container). Pattern from `telemetry-dashboard.tsx`

### Third-party (already installed)
- `recharts` v3.8.0 — `ResponsiveContainer`, `LineChart`, `BarChart`, `AreaChart`, `CartesianGrid`, `XAxis`, `YAxis`, `Tooltip`, `Legend`, `Line`, `Bar`, `Area`
- `lucide-react` — `TrendingUp`, `Clock`, `Users`, `AlertTriangle`, `BarChart3`, `RefreshCw`

## i18n Keys

### Latvian (`lv.json`) — add under `analytics.routePerformance`
```json
{
  "analytics": {
    "routePerformance": {
      "title": "Maršruta veiktspēja",
      "selectRoute": "Izvēlieties maršrutu",
      "noRouteSelected": "Izvēlieties maršrutu, lai skatītu veiktspējas datus",
      "window7d": "7 dienas",
      "window14d": "14 dienas",
      "window30d": "30 dienas",
      "onTimePercent": "Savlaicīgums",
      "avgDelay": "Vidējā aizkave",
      "loadFactor": "Noslodze",
      "anomalyCount": "Anomālijas",
      "onTimeTrend": "Savlaicīguma tendence",
      "delayByStop": "Aizkave pa pieturām",
      "loadTrend": "Noslodzes tendence",
      "anomalyTrend": "Anomāliju tendence",
      "date": "Datums",
      "stop": "Pietura",
      "seconds": "{value}s",
      "percent": "{value}%",
      "trips": "Reisi",
      "passengers": "Pasažieri",
      "offRoute": "Novirzījies",
      "stuck": "Iestrēdzis",
      "gpsGap": "GPS pārtraukums",
      "noData": "Nav datu par šo maršrutu",
      "loadError": "Neizdevās ielādēt veiktspējas datus",
      "refresh": "Atjaunot"
    }
  }
}
```

### English (`en.json`) — add under `analytics.routePerformance`
```json
{
  "analytics": {
    "routePerformance": {
      "title": "Route Performance",
      "selectRoute": "Select a route",
      "noRouteSelected": "Select a route to view performance data",
      "window7d": "7 days",
      "window14d": "14 days",
      "window30d": "30 days",
      "onTimePercent": "On-Time %",
      "avgDelay": "Avg Delay",
      "loadFactor": "Load Factor",
      "anomalyCount": "Anomalies",
      "onTimeTrend": "On-Time Trend",
      "delayByStop": "Delay by Stop",
      "loadTrend": "Load Trend",
      "anomalyTrend": "Anomaly Trend",
      "date": "Date",
      "stop": "Stop",
      "seconds": "{value}s",
      "percent": "{value}%",
      "trips": "Trips",
      "passengers": "Passengers",
      "offRoute": "Off Route",
      "stuck": "Stuck",
      "gpsGap": "GPS Gap",
      "noData": "No data available for this route",
      "loadError": "Failed to load performance data",
      "refresh": "Refresh"
    }
  }
}
```

### Russian (`ru.json`) — add under `analytics.routePerformance`
```json
{
  "analytics": {
    "routePerformance": {
      "title": "Производительность маршрута",
      "selectRoute": "Выберите маршрут",
      "noRouteSelected": "Выберите маршрут для просмотра данных",
      "window7d": "7 дней",
      "window14d": "14 дней",
      "window30d": "30 дней",
      "onTimePercent": "Пунктуальность",
      "avgDelay": "Ср. задержка",
      "loadFactor": "Загруженность",
      "anomalyCount": "Аномалии",
      "onTimeTrend": "Тренд пунктуальности",
      "delayByStop": "Задержка по остановкам",
      "loadTrend": "Тренд загруженности",
      "anomalyTrend": "Тренд аномалий",
      "date": "Дата",
      "stop": "Остановка",
      "seconds": "{value}с",
      "percent": "{value}%",
      "trips": "Рейсы",
      "passengers": "Пассажиры",
      "offRoute": "Отклонение",
      "stuck": "Застрял",
      "gpsGap": "GPS разрыв",
      "noData": "Нет данных по этому маршруту",
      "loadError": "Не удалось загрузить данные",
      "refresh": "Обновить"
    }
  }
}
```

### Sidebar nav keys — add to `nav` section in all 3 locale files
```json
{
  "nav": {
    "analyticsGroup": "Analytics",
    "analyticsOverview": "Overview",
    "routePerformance": "Route Performance"
  }
}
```
Latvian: `"analyticsGroup": "Analītika"`, `"analyticsOverview": "Pārskats"`, `"routePerformance": "Maršrutu veiktspēja"`
Russian: `"analyticsGroup": "Аналитика"`, `"analyticsOverview": "Обзор"`, `"routePerformance": "Производительность маршрутов"`

## Data Fetching

### Backend Endpoints (new — created in this plan)
1. `GET /api/v1/analytics/route-performance?route_id={id}&window={7|14|30}` — daily on-time % time series
2. `GET /api/v1/analytics/route-delay-by-stop?route_id={id}&window={7|14|30}` — avg delay per stop
3. `GET /api/v1/analytics/route-load-trend?route_id={id}&window={7|14|30}` — daily load factor
4. `GET /api/v1/analytics/route-anomalies?route_id={id}&window={7|14|30}` — anomaly counts by type per day

### Frontend Data Fetching
- **Route list**: Use existing `fetchRoutes` from `schedules-sdk.ts` with `page_size=500` to populate the dropdown
- **Performance data**: Use `authFetch` directly (like `fleet-sdk.ts` pattern) since these are new endpoints not yet in `@vtv/sdk`. Wrap in `route-performance-sdk.ts`
- **Session gate**: `useSession()` + `status === "authenticated"` guard on data loading
- **Loading states**: `Skeleton` placeholders for each chart card (matching telemetry dashboard pattern)

### Server/Client Boundary
- Page component (`page.tsx`): **server component** — thin wrapper passing `locale` to client component
- `RoutePerformanceDashboard`: **client component** (`"use client"`) — handles interactivity, data fetching, charts
- SDK wrapper (`route-performance-sdk.ts`): uses `authFetch` from `@/lib/auth-fetch` (dual-context safe)

## RBAC Integration

**No middleware change needed.** The existing middleware matcher already includes:
```
/(lv|en|ru)/(routes|stops|schedules|drivers|vehicles|fleet|geofences|analytics|gtfs|users|chat|documents)/:path*
```
The `:path*` suffix covers `/analytics/routes`. The RBAC permissions for `/analytics` grant access to all 4 roles (admin, dispatcher, editor, viewer).

**Backend endpoints**: All 4 new endpoints use `Depends(get_current_user)` (matching existing analytics endpoints).

## Sidebar Navigation

**Action**: Convert the flat `analytics` nav entry to a `NavGroup` (matching the `fleetGroup` pattern).

**Before:**
```ts
{ key: "analytics", href: "/analytics", enabled: true },
```

**After:**
```ts
{
  key: "analyticsGroup",
  children: [
    { key: "analyticsOverview", href: "/analytics", enabled: true },
    { key: "routePerformance", href: "/analytics/routes", enabled: true },
  ],
},
```

**Icon**: No icons in sidebar (current pattern uses text-only nav links)
**Position**: Same position in nav list (between geofences group and gtfs)

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules
- `cms/apps/web/CLAUDE.md` — React 19 anti-patterns, conventions, data fetching

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/analytics/page.tsx` — Server component thin wrapper pattern
- `cms/apps/web/src/components/analytics/analytics-content.tsx` — Client analytics component with SWR, KPI cards, tabs
- `cms/apps/web/src/components/fleet/telemetry-dashboard.tsx` — Recharts pattern: ChartCard wrapper, LineChart/AreaChart, CSS variable colors, responsive grid
- `cms/apps/web/src/components/analytics/performance-overview.tsx` — Existing route performance table with filter controls, `authFetch` pattern
- `cms/apps/web/src/lib/fleet-sdk.ts` — SDK wrapper using `authFetch` with URLSearchParams (pattern for new endpoints)
- `cms/apps/web/src/hooks/use-analytics.ts` — SWR hook with session gate pattern
- `cms/apps/web/src/components/app-sidebar.tsx` — NavGroup pattern (see `fleetGroup`)

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add Latvian translations (routePerformance + nav keys)
- `cms/apps/web/messages/en.json` — Add English translations
- `cms/apps/web/messages/ru.json` — Add Russian translations
- `cms/apps/web/src/components/app-sidebar.tsx` — Convert analytics to NavGroup
- `cms/apps/web/src/types/analytics.ts` — Add route performance response types

### Files to Create
- `app/analytics/schemas.py` — Add 4 new Pydantic response models (extend existing file)
- `app/analytics/routes.py` — Add 4 new endpoints (extend existing file)
- `app/analytics/service.py` — Add 4 new service methods (extend existing file)
- `cms/apps/web/src/app/[locale]/(dashboard)/analytics/routes/page.tsx` — Page component
- `cms/apps/web/src/components/analytics/route-performance/route-performance-dashboard.tsx` — Main dashboard component
- `cms/apps/web/src/components/analytics/route-performance/chart-card.tsx` — Reusable chart wrapper
- `cms/apps/web/src/lib/route-performance-sdk.ts` — API wrapper functions
- `app/analytics/tests/test_route_performance.py` — Backend tests

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities (no `text-gray-*`, `bg-blue-*`, etc.). Full mapping in `.claude/commands/_shared/tailwind-token-map.md`.

**Recharts exception:** Recharts `stroke`/`fill` props accept CSS strings, not Tailwind classes. Use CSS variable references:
```tsx
const lineColor = "var(--color-interactive)";
const gridColor = "var(--color-border)";
const ontimeColor = "var(--color-status-ontime)";
const delayedColor = "var(--color-status-delayed)";
const criticalColor = "var(--color-status-critical)";
```
This ensures dark mode works correctly. Do NOT hardcode hex values.

## React 19 Coding Rules

- **No `setState` in `useEffect`** — use `key` prop on components to force remount
- **No component definitions inside components** — extract `ChartCard` to its own file
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — declare `useState` hooks first, then derived `useMemo`/`useCallback`
- **Named container sizes forbidden** — use `sm:max-w-[32rem]` not `max-w-lg`

## TypeScript Security Rules

- Backend: validate `route_id` format and `window` enum at the API level (Pydantic `Literal` types)
- Frontend: route_id comes from the route dropdown (pre-validated GTFS data), window from button group (hardcoded values) — low injection risk but use enum-style types

---

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Backend — Add Pydantic response schemas
**File:** `app/analytics/schemas.py` (modify)
**Action:** UPDATE

Read the existing file first. Add these models after the existing `OnTimePerformanceResponse`:

```python
class DailyOnTimePoint(BaseModel):
    """Single day's on-time performance for a route."""
    date: str
    on_time_percentage: float
    tracked_trips: int
    model_config = ConfigDict(from_attributes=True)

class StopDelayPoint(BaseModel):
    """Average delay at a single stop."""
    stop_id: str
    stop_name: str
    average_delay_seconds: float
    sample_count: int
    model_config = ConfigDict(from_attributes=True)

class DailyLoadPoint(BaseModel):
    """Single day's load factor for a route."""
    date: str
    load_factor: float  # 0.0–1.0
    estimated_passengers: int
    model_config = ConfigDict(from_attributes=True)

class DailyAnomalyPoint(BaseModel):
    """Single day's anomaly counts by type for a route."""
    date: str
    off_route: int
    stuck: int
    gps_gap: int
    model_config = ConfigDict(from_attributes=True)

WindowLiteral = Literal["7", "14", "30"]

class RoutePerformanceResponse(BaseModel):
    """Time-series on-time performance for a single route."""
    route_id: str
    route_short_name: str
    window_days: int
    overall_on_time_percentage: float
    overall_average_delay_seconds: float
    data: list[DailyOnTimePoint]
    generated_at: str
    model_config = ConfigDict(from_attributes=True)

class RouteDelayByStopResponse(BaseModel):
    """Average delay per stop for a route."""
    route_id: str
    route_short_name: str
    window_days: int
    stops: list[StopDelayPoint]
    generated_at: str
    model_config = ConfigDict(from_attributes=True)

class RouteLoadTrendResponse(BaseModel):
    """Daily load factor trend for a route."""
    route_id: str
    route_short_name: str
    window_days: int
    data: list[DailyLoadPoint]
    generated_at: str
    model_config = ConfigDict(from_attributes=True)

class RouteAnomalyResponse(BaseModel):
    """Daily anomaly counts by type for a route."""
    route_id: str
    route_short_name: str
    window_days: int
    total_anomalies: int
    data: list[DailyAnomalyPoint]
    generated_at: str
    model_config = ConfigDict(from_attributes=True)
```

Add `Literal` to the `typing` imports if not already present.

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV && python -m py_compile app/analytics/schemas.py
```

---

### Task 2: Backend — Add service methods
**File:** `app/analytics/service.py` (modify)
**Action:** UPDATE

Read the existing file first. Add 4 new async methods to `AnalyticsService`:

1. `get_route_performance(route_id: str, window: int) -> RoutePerformanceResponse` — queries `DailyAdherenceReport` model for historical on-time % by date, filtered by `route_id`. Falls back to GTFS-RT live computation if no stored reports exist.
2. `get_route_delay_by_stop(route_id: str, window: int) -> RouteDelayByStopResponse` — computes average delay per stop from trip_updates feed, using the same `_compute_route_adherence()` pattern but decomposed per stop.
3. `get_route_load_trend(route_id: str, window: int) -> RouteLoadTrendResponse` — queries stored load factor data if available, otherwise returns empty/placeholder data (ML load model may not be deployed yet — graceful degradation).
4. `get_route_anomalies(route_id: str, window: int) -> RouteAnomalyResponse` — queries anomaly alerts for the route from the `alerts` table, grouped by type (off_route, stuck, gps_gap) and date.

Import the new schema models. Use structured logging: `analytics.route_performance.{started|completed|failed}`.

For methods where ML data may not exist yet, return empty `data: []` arrays with a log warning — do NOT raise exceptions. The frontend handles empty states gracefully.

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV && python -m mypy app/analytics/service.py --no-error-summary
```

---

### Task 3: Backend — Add API endpoints
**File:** `app/analytics/routes.py` (modify)
**Action:** UPDATE

Read the existing file first. Add 4 new endpoints after the existing ones:

```python
@router.get("/route-performance", response_model=RoutePerformanceResponse)
@limiter.limit("30/minute", key_func=_analytics_key)
async def get_route_performance(
    request: Request,
    route_id: str = Query(..., max_length=50, pattern=r"^[A-Za-z0-9_-]+$"),
    window: Literal["7", "14", "30"] = Query("7"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> RoutePerformanceResponse:
    service = AnalyticsService(db)
    return await service.get_route_performance(route_id, int(window))

@router.get("/route-delay-by-stop", response_model=RouteDelayByStopResponse)
@limiter.limit("30/minute", key_func=_analytics_key)
async def get_route_delay_by_stop(
    request: Request,
    route_id: str = Query(..., max_length=50, pattern=r"^[A-Za-z0-9_-]+$"),
    window: Literal["7", "14", "30"] = Query("7"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> RouteDelayByStopResponse:
    service = AnalyticsService(db)
    return await service.get_route_delay_by_stop(route_id, int(window))

@router.get("/route-load-trend", response_model=RouteLoadTrendResponse)
@limiter.limit("30/minute", key_func=_analytics_key)
async def get_route_load_trend(
    request: Request,
    route_id: str = Query(..., max_length=50, pattern=r"^[A-Za-z0-9_-]+$"),
    window: Literal["7", "14", "30"] = Query("7"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> RouteLoadTrendResponse:
    service = AnalyticsService(db)
    return await service.get_route_load_trend(route_id, int(window))

@router.get("/route-anomalies", response_model=RouteAnomalyResponse)
@limiter.limit("30/minute", key_func=_analytics_key)
async def get_route_anomalies(
    request: Request,
    route_id: str = Query(..., max_length=50, pattern=r"^[A-Za-z0-9_-]+$"),
    window: Literal["7", "14", "30"] = Query("7"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> RouteAnomalyResponse:
    service = AnalyticsService(db)
    return await service.get_route_anomalies(route_id, int(window))
```

Import the new schema models and `Literal` from `typing`. Follow the existing `_analytics_key` rate limit key function pattern. All endpoints use `get_current_user` (all authenticated roles allowed).

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV && python -m mypy app/analytics/routes.py --no-error-summary
```

---

### Task 4: Backend — Add unit tests
**File:** `app/analytics/tests/test_route_performance.py` (create)
**Action:** CREATE

Create test file with 10+ tests covering:
- Schema model instantiation for all 4 response types
- Service method returns valid responses (mock DB/GTFS data)
- Service method handles missing data gracefully (empty arrays, no exceptions)
- Endpoint returns 401 without auth
- Endpoint validates `route_id` format (rejects `../etc/passwd`)
- Endpoint validates `window` enum (rejects `999`)
- Rate limiting key function returns expected format

Follow existing test patterns in `app/analytics/tests/`. Use `@pytest.mark.asyncio` for async tests, `AsyncMock` for service mocking.

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV && python -m pytest app/analytics/tests/test_route_performance.py -v --tb=short 2>&1 | head -50
```

---

### Task 5: Frontend — Add TypeScript types
**File:** `cms/apps/web/src/types/analytics.ts` (modify)
**Action:** UPDATE

Read the existing file first. Add these interfaces after the existing types:

```typescript
export interface DailyOnTimePoint {
  date: string;
  on_time_percentage: number;
  tracked_trips: number;
}

export interface StopDelayPoint {
  stop_id: string;
  stop_name: string;
  average_delay_seconds: number;
  sample_count: number;
}

export interface DailyLoadPoint {
  date: string;
  load_factor: number;
  estimated_passengers: number;
}

export interface DailyAnomalyPoint {
  date: string;
  off_route: number;
  stuck: number;
  gps_gap: number;
}

export interface RoutePerformanceResponse {
  route_id: string;
  route_short_name: string;
  window_days: number;
  overall_on_time_percentage: number;
  overall_average_delay_seconds: number;
  data: DailyOnTimePoint[];
  generated_at: string;
}

export interface RouteDelayByStopResponse {
  route_id: string;
  route_short_name: string;
  window_days: number;
  stops: StopDelayPoint[];
  generated_at: string;
}

export interface RouteLoadTrendResponse {
  route_id: string;
  route_short_name: string;
  window_days: number;
  data: DailyLoadPoint[];
  generated_at: string;
}

export interface RouteAnomalyResponse {
  route_id: string;
  route_short_name: string;
  window_days: number;
  total_anomalies: number;
  data: DailyAnomalyPoint[];
  generated_at: string;
}
```

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
```

---

### Task 6: Frontend — Create SDK wrapper
**File:** `cms/apps/web/src/lib/route-performance-sdk.ts` (create)
**Action:** CREATE

Follow the `fleet-sdk.ts` pattern — use `authFetch` with `URLSearchParams`:

```typescript
import { authFetch } from "@/lib/auth-fetch";
import type {
  RoutePerformanceResponse,
  RouteDelayByStopResponse,
  RouteLoadTrendResponse,
  RouteAnomalyResponse,
} from "@/types/analytics";

const BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

class RoutePerformanceApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "RoutePerformanceApiError";
  }
}

export async function fetchRoutePerformance(
  routeId: string,
  window: "7" | "14" | "30" = "7",
): Promise<RoutePerformanceResponse> {
  const query = new URLSearchParams({ route_id: routeId, window });
  const res = await authFetch(`${BASE}/api/v1/analytics/route-performance?${query.toString()}`);
  if (!res.ok) throw new RoutePerformanceApiError(res.status, "Failed to fetch route performance");
  return res.json() as Promise<RoutePerformanceResponse>;
}

export async function fetchRouteDelayByStop(
  routeId: string,
  window: "7" | "14" | "30" = "7",
): Promise<RouteDelayByStopResponse> {
  const query = new URLSearchParams({ route_id: routeId, window });
  const res = await authFetch(`${BASE}/api/v1/analytics/route-delay-by-stop?${query.toString()}`);
  if (!res.ok) throw new RoutePerformanceApiError(res.status, "Failed to fetch delay by stop");
  return res.json() as Promise<RouteDelayByStopResponse>;
}

export async function fetchRouteLoadTrend(
  routeId: string,
  window: "7" | "14" | "30" = "7",
): Promise<RouteLoadTrendResponse> {
  const query = new URLSearchParams({ route_id: routeId, window });
  const res = await authFetch(`${BASE}/api/v1/analytics/route-load-trend?${query.toString()}`);
  if (!res.ok) throw new RoutePerformanceApiError(res.status, "Failed to fetch load trend");
  return res.json() as Promise<RouteLoadTrendResponse>;
}

export async function fetchRouteAnomalies(
  routeId: string,
  window: "7" | "14" | "30" = "7",
): Promise<RouteAnomalyResponse> {
  const query = new URLSearchParams({ route_id: routeId, window });
  const res = await authFetch(`${BASE}/api/v1/analytics/route-anomalies?${query.toString()}`);
  if (!res.ok) throw new RoutePerformanceApiError(res.status, "Failed to fetch anomalies");
  return res.json() as Promise<RouteAnomalyResponse>;
}
```

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
```

---

### Task 7: Frontend — Add i18n keys (all 3 locales)
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Read the file. Add the `routePerformance` object inside the existing `analytics` section (after `performance`). Also add the nav keys `analyticsGroup`, `analyticsOverview`, `routePerformance` to the `nav` section. Use the exact keys from the i18n section above.

**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Same structure, Latvian values from i18n section above.

**File:** `cms/apps/web/messages/ru.json` (modify)
**Action:** UPDATE

Same structure, Russian values from i18n section above.

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && node -e "const en=require('./apps/web/messages/en.json'); const lv=require('./apps/web/messages/lv.json'); const ru=require('./apps/web/messages/ru.json'); console.log('EN routePerformance keys:', Object.keys(en.analytics.routePerformance).length); console.log('LV routePerformance keys:', Object.keys(lv.analytics.routePerformance).length); console.log('RU routePerformance keys:', Object.keys(ru.analytics.routePerformance).length); console.log('EN nav analyticsGroup:', en.nav.analyticsGroup); console.log('LV nav analyticsGroup:', lv.nav.analyticsGroup); console.log('RU nav analyticsGroup:', ru.nav.analyticsGroup);"
```

---

### Task 8: Frontend — Create ChartCard component
**File:** `cms/apps/web/src/components/analytics/route-performance/chart-card.tsx` (create)
**Action:** CREATE

Extract from the telemetry dashboard pattern. This is a reusable wrapper for each Recharts chart:

```tsx
interface ChartCardProps {
  title: string;
  currentValue?: string;
  children: React.ReactNode;
}

export function ChartCard({ title, currentValue, children }: ChartCardProps) {
  return (
    <div className="border border-card-border bg-card-bg p-(--spacing-card)">
      <div className="mb-(--spacing-card) flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-foreground-muted">
          {title}
        </p>
        {currentValue && (
          <p className="font-heading text-lg font-semibold text-foreground">
            {currentValue}
          </p>
        )}
      </div>
      <div className="h-[220px]">{children}</div>
    </div>
  );
}
```

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint
```

---

### Task 9: Frontend — Create RoutePerformanceDashboard component
**File:** `cms/apps/web/src/components/analytics/route-performance/route-performance-dashboard.tsx` (create)
**Action:** CREATE

This is the main client component. Follow these patterns exactly:

**Structure:**
1. `"use client"` directive
2. Imports: React hooks, next-intl, next-auth, Recharts components, shadcn Select/Button/Skeleton, ChartCard, SDK functions, types
3. `type TimeWindow = "7" | "14" | "30"` — local type
4. Component with props `{ locale: string }` (void locale — needed by server component wrapper)

**State:**
- `selectedRouteId: string` — from route selector dropdown
- `timeWindow: TimeWindow` — from button group (default `"7"`)
- `routes: Route[]` — populated from `fetchRoutes()` on mount
- `perfData: RoutePerformanceResponse | null`
- `delayData: RouteDelayByStopResponse | null`
- `loadData: RouteLoadTrendResponse | null`
- `anomalyData: RouteAnomalyResponse | null`
- `isLoading: boolean`

**Data Loading:**
- `useSession()` for auth gate
- Route list loads once on mount (session-gated `useEffect`)
- Performance data loads when `selectedRouteId` or `timeWindow` changes (via `useCallback` + `useEffect`)
- All 4 API calls fire in parallel via `Promise.allSettled()` — partial data is acceptable
- `toast.error()` on failure (using sonner)

**Layout:**
```
┌──────────────────────────────────────────────┐
│ Title               [Route Selector ▼] [7d|14d|30d] │
├──────────────────────────────────────────────┤
│ MetricCard  MetricCard  MetricCard  MetricCard │  ← 4 KPIs (optional, from perfData summary)
├──────────────────────────────────────────────┤
│ On-Time Trend (LineChart) │ Delay by Stop (BarChart) │  ← 2x2 chart grid
│ Load Trend (AreaChart)    │ Anomaly Trend (AreaChart) │
└──────────────────────────────────────────────┘
```

**Chart specifications:**

1. **On-Time Trend** — `LineChart` with `perfData.data`
   - X: `date`, Y: `on_time_percentage` (0–100)
   - Line stroke: `var(--color-interactive)`
   - Reference line at 90% (target threshold) — dashed, `var(--color-status-ontime)`

2. **Delay by Stop** — `BarChart` with `delayData.stops`
   - X: `stop_name`, Y: `average_delay_seconds`
   - Bar fill: `var(--color-status-delayed)`
   - Positive = late, show seconds

3. **Load Trend** — `AreaChart` with `loadData.data`
   - X: `date`, Y: `load_factor` (0–1, formatted as %)
   - Area stroke: `var(--color-interactive)`, fill at 0.1 opacity

4. **Anomaly Trend** — `AreaChart` (stacked) with `anomalyData.data`
   - X: `date`, Y: stacked `off_route`, `stuck`, `gps_gap`
   - Colors: `var(--color-status-critical)`, `var(--color-status-delayed)`, `var(--color-foreground-muted)`
   - `stackId="anomalies"`

**All charts share:**
- `ResponsiveContainer` with `width="100%" height="100%"`
- `CartesianGrid` with `strokeDasharray="3 3" stroke="var(--color-border)"`
- `XAxis`/`YAxis` with `tick={{ fontSize: 10 }}`, `axisLine={false}`, `tickLine={false}`
- `Tooltip` with `contentStyle={{ borderRadius: 0, border: "1px solid var(--color-border)", fontSize: 12 }}`

**Empty state:** When no route is selected, show a centered message: `t("noRouteSelected")`
**Loading state:** When `isLoading`, show 4 `Skeleton` components in the chart grid
**Error state:** When all data is null after loading, show `t("noData")` with refresh button

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint
```

---

### Task 10: Frontend — Create page component
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/analytics/routes/page.tsx` (create)
**Action:** CREATE

Thin server component wrapper (matching existing `analytics/page.tsx` pattern):

```tsx
import { RoutePerformanceDashboard } from "@/components/analytics/route-performance/route-performance-dashboard";

export default async function RoutePerformancePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return <RoutePerformanceDashboard locale={locale} />;
}
```

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint
```

---

### Task 11: Frontend — Update sidebar navigation
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify)
**Action:** UPDATE

Read the file. Find the line:
```ts
{ key: "analytics", href: "/analytics", enabled: true },
```

Replace with:
```ts
{
  key: "analyticsGroup",
  children: [
    { key: "analyticsOverview", href: "/analytics", enabled: true },
    { key: "routePerformance", href: "/analytics/routes", enabled: true },
  ],
},
```

This converts the flat `analytics` entry into a collapsible group, matching the `fleetGroup` pattern already in the file.

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint
```

---

### Task 12: Frontend — Verify build
**Action:** Run full validation pyramid

```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint && pnpm --filter @vtv/web build
```

If build fails due to `.next` cache issues after import changes:
```bash
rm -rf cms/apps/web/.next && cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web build
```

---

## Final Validation (3-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: TypeScript**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
```

**Level 2: Lint**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web lint
```

**Level 3: Build**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web build
```

**Backend validation:**
```bash
cd /Users/Berzins/Desktop/VTV && make lint && python -m mypy app/analytics/ --no-error-summary
```

**Success definition:** All levels exit code 0, zero errors.

## Post-Implementation Checks

- [ ] Page renders at `/lv/analytics/routes` and `/en/analytics/routes`
- [ ] i18n keys present in all 3 locale files (lv, en, ru) with matching key structure
- [ ] No middleware changes needed (existing matcher covers `/analytics/:path*`)
- [ ] Sidebar shows "Analytics" as collapsible group with "Overview" and "Route Performance" children
- [ ] Analytics Overview page (`/analytics`) still works correctly after nav restructuring
- [ ] No hardcoded colors — all styling uses semantic tokens; Recharts uses `var(--color-*)` references
- [ ] Charts render correctly in dark mode (CSS variable references adapt automatically)
- [ ] Route selector dropdown populates from GTFS route data
- [ ] Time window buttons toggle between 7/14/30 day views
- [ ] Empty states display correctly when no route is selected or no data exists
- [ ] Loading skeletons display during data fetch
- [ ] All 4 backend endpoints return valid responses and handle missing data gracefully

## Acceptance Criteria

This feature is complete when:
- [ ] Page accessible at `/{locale}/analytics/routes`
- [ ] RBAC enforced — unauthenticated users redirected to login
- [ ] All 3 languages have complete translations (26 routePerformance keys + 3 nav keys each)
- [ ] Design system rules followed (MASTER.md — sharp corners, semantic tokens, compact spacing)
- [ ] All validation levels pass (type-check, lint, build for frontend; lint, mypy for backend)
- [ ] Backend tests pass (10+ tests covering schemas, service, endpoints, validation)
- [ ] No regressions in existing analytics page
- [ ] Ready for `/commit`
