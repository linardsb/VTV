# Plan: WebSocket Hook for Real-Time Vehicle Positions

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: N/A (hook replacement + minor UI indicator, no new route)
**Auth Required**: Yes (JWT token for WebSocket connection)
**Allowed Roles**: All authenticated users (existing Routes page RBAC unchanged)

## Feature Description

Replace the HTTP polling-based `useVehiclePositions` hook with a WebSocket-based implementation
that connects to the backend's `/ws/transit/vehicles` endpoint for real-time push updates. The
backend WebSocket infrastructure is already fully implemented (Redis Pub/Sub fan-out, ConnectionManager,
JWT auth via query parameter, heartbeat/pong protocol).

The current hook uses SWR with a 10-second `refreshInterval` to poll `GET /api/v1/transit/vehicles`.
This introduces 10–15 seconds of end-to-end latency for vehicle position updates. The WebSocket
replacement will reduce this to ~100ms by receiving push updates from the server whenever the
poller publishes new data to Redis Pub/Sub.

Three enhancements beyond the basic WS swap:

1. **Periodic WS retry** — After falling back to HTTP polling (3 failed WS attempts), retry
   WebSocket every 60 seconds. If a retry succeeds, switch back to WS and stop polling.

2. **Visible connection status indicator** — A small badge on the route map showing "Live" (WS
   active, green dot) vs "Polling" (HTTP fallback, amber dot). Helps operators know their data
   freshness at a glance.

3. **Server-side route filter** — When a specific route is selected in the table, push a
   `route_id` filter to the WebSocket so the server only sends that route's vehicles. Reduces
   wire traffic. When deselected, reverts to all vehicles. The existing client-side `typeFilter`
   continues to work for transport-type filtering (bus/tram/trolleybus).

## Design System

### Master Rules (from MASTER.md)
- Status indicator uses semantic tokens: `bg-status-ontime` (green, WS active), `bg-status-delayed` (amber, polling)
- Typography: body font, `text-xs` for badge label
- Transitions: 200ms ease for badge state changes

### Page Override
- None — no page-level design override exists

### Tokens Used
- `bg-status-ontime` — green dot for WS connected
- `bg-status-delayed` — amber dot for polling fallback
- `bg-surface/90` — badge background (matches existing map overlay style)
- `text-foreground` — badge text
- `text-foreground-muted` — secondary badge text

## Components Needed

### Existing (shadcn/ui)
- None needed for the badge (plain div with semantic tokens, matching existing map overlay pattern)

### New shadcn/ui to Install
- None

### Custom Components to Create
- None (badge is inline in `RouteMap`, matching the existing vehicle count overlay pattern)

## i18n Keys

### Latvian (`lv.json`)
Add inside `routes.map` after `"minutes": "min"`:
```json
"liveStream": "Reāllaiks",
"pollingFallback": "Atjaunināšana",
"wsConnecting": "Savienojas..."
```

### English (`en.json`)
Add inside `routes.map` after `"minutes": "min"`:
```json
"liveStream": "Live",
"pollingFallback": "Polling",
"wsConnecting": "Connecting..."
```

## Data Fetching

### WebSocket Protocol (backend already implemented)

**Endpoint:** `ws://host/ws/transit/vehicles?token=JWT`

**Authentication:** JWT access token passed as `?token=` query parameter (browser WebSocket API
does not support custom headers). Token obtained via `getToken()` from `src/lib/auth-fetch.ts`.

**Client → Server messages:**
- `{"action": "subscribe", "route_id": "22", "feed_id": "riga"}` — subscribe with optional filters
- `{"action": "unsubscribe"}` — clear filters (receive all)
- `{"action": "pong"}` — keepalive response to server ping

**Server → Client messages:**
- `{"type": "vehicle_update", "feed_id": "riga", "count": 42, "vehicles": [...], "timestamp": "..."}` — push update
- `{"type": "ack", "action": "connected|subscribe|unsubscribe", "filters": {...}}` — acknowledgement
- `{"type": "ping"}` — keepalive, client must respond with `{"action": "pong"}`
- `{"type": "error", "code": "...", "message": "..."}` — error

**Vehicle payload shape:** Same `ApiVehicle` interface as the REST endpoint (snake_case fields:
`vehicle_id`, `route_id`, `route_short_name`, `route_type`, `latitude`, `longitude`, `bearing`,
`speed_kmh`, `delay_seconds`, `current_status`, `next_stop_name`, `current_stop_name`, `timestamp`).

### Strategy

1. **Primary:** WebSocket connection with auto-reconnect (exponential backoff: 1s, 2s, 4s, max 3 attempts)
2. **Fallback:** If WebSocket fails after 3 attempts, fall back to SWR HTTP polling
3. **Periodic retry:** While in fallback, attempt WS reconnect every 60s. On success, switch back to WS
4. **Route filter:** When `routeFilter` option changes, send new subscribe message on existing WS (no reconnect)
5. **Auth:** `getToken()` from `auth-fetch.ts` provides the JWT; re-fetch token on reconnect

### Server/Client Boundary
- The hook is client-only (`"use client"` — same as current hook)
- Uses `getToken()` which handles client-side token caching internally
- No server component involvement

## RBAC Integration

No changes — the Routes page already has RBAC via middleware. The WebSocket endpoint validates
JWT server-side.

## Sidebar Navigation

No changes — no new page.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/apps/web/CLAUDE.md` — Frontend-specific conventions and anti-patterns

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/hooks/use-vehicle-positions.ts` — Current HTTP polling hook (being replaced)
- `cms/apps/web/src/lib/auth-fetch.ts` — Token acquisition (`getToken()` function)
- `cms/apps/web/src/components/routes/route-map.tsx` — Map component (adding status badge)

### Backend Reference (read-only, do not modify)
- `app/transit/ws_routes.py` — WebSocket endpoint (auth, protocol, heartbeat)
- `app/transit/ws_schemas.py` — Message type definitions

### Files to Modify
- `cms/apps/web/src/hooks/use-vehicle-positions.ts` — Replace with WebSocket implementation
- `cms/apps/web/src/components/routes/route-map.tsx` — Add connection status badge
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Wire new hook options + pass connectionMode
- `cms/apps/web/messages/lv.json` — Add i18n keys
- `cms/apps/web/messages/en.json` — Add i18n keys

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping
table in `.claude/commands/_shared/tailwind-token-map.md`. Key mappings for this task:
- Green dot: `bg-status-ontime` (NOT `bg-green-500` or `bg-emerald-500`)
- Amber dot: `bg-status-delayed` (NOT `bg-amber-500` or `bg-yellow-500`)
- Badge bg: `bg-surface/90` (matches existing map overlay)
- Text: `text-foreground`, `text-foreground-muted`

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — exception: WebSocket `onmessage` callbacks that call setState
  are fine because they're async event handlers, not synchronous effect logic. The React 19 rule
  targets synchronous setState during the effect body itself, not in async callbacks.
- **No component definitions inside components** — extract all sub-components to module scope
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — `useState` first
- **`useRef` for WebSocket instance** — store in `useRef` to avoid re-creating on re-render
- **Cleanup in `useEffect` return** — close WebSocket and clear all timers

See `cms/apps/web/CLAUDE.md` → "React 19 Anti-Patterns" for full examples.

## TypeScript Security Rules

- **JWT token in WebSocket URL** — Passed as query parameter. Never log the full URL.
- **Clear `.next` cache** when module resolution errors persist: `rm -rf cms/apps/web/.next`

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add i18n keys (Latvian)
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Inside the `routes.map` object, add these 3 keys after the existing `"minutes": "min"` line:

```json
"liveStream": "Reāllaiks",
"pollingFallback": "Atjaunināšana",
"wsConnecting": "Savienojas..."
```

**Per-task validation:**
- Verify valid JSON (no trailing commas, correct nesting)
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 2: Add i18n keys (English)
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Inside the `routes.map` object, add these 3 keys after the existing `"minutes": "min"` line:

```json
"liveStream": "Live",
"pollingFallback": "Polling",
"wsConnecting": "Connecting..."
```

**Per-task validation:**
- Verify valid JSON
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 3: Rewrite the vehicle positions hook with WebSocket
**File:** `cms/apps/web/src/hooks/use-vehicle-positions.ts` (modify — full rewrite)
**Action:** UPDATE

Replace the entire file content. The new implementation must satisfy all requirements below.

#### 3a. Preserve and extend the public API

Keep existing types and add new fields:

```typescript
/** Connection mode exposed to consumers for UI display. */
export type ConnectionMode = "connecting" | "ws" | "polling";

interface UseVehiclePositionsOptions {
  /** SWR fallback polling interval in ms. Default 10000 (10s). */
  interval?: number;
  /** Route color map: routeId -> hex color. */
  colorMap?: Record<string, string>;
  /** Backend API base URL. Defaults to NEXT_PUBLIC_AGENT_URL env var. */
  apiBase?: string;
  /** Optional GTFS route_id to push as server-side WS filter. null = all routes. */
  routeFilter?: string | null;
}

interface UseVehiclePositionsResult {
  vehicles: BusPosition[];
  isLoading: boolean;
  error: string | null;
  lastFetchedAt: string | null;
  /** Current data delivery mode: "connecting" | "ws" | "polling". */
  connectionMode: ConnectionMode;
}
```

The existing `vehicles`, `isLoading`, `error`, `lastFetchedAt` fields are unchanged so
`routes/page.tsx` continues to destructure them without breakage.

#### 3b. Keep existing helper functions at module scope

Copy these verbatim from the current file (they are unchanged):
- `ApiVehicle` interface
- `ApiResponse` interface
- `STATUS_MAP` constant
- `routeColor()` function
- `mapVehicle()` function

#### 3c. Add WS URL derivation helper

```typescript
function getWsUrl(apiBase: string): string {
  const url = new URL(apiBase);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/transit/vehicles";
  return url.toString();
}
```

#### 3d. Constants

```typescript
const MAX_RECONNECT_ATTEMPTS = 3;
const WS_RETRY_INTERVAL = 60_000; // Retry WS every 60s while in polling fallback
```

#### 3e. State and refs

`useState` (declare in this order — hooks must come before any useMemo/useCallback):
1. `vehicles: BusPosition[]` — mapped vehicle data (initial: `[]`)
2. `lastFetchedAt: string | null` — timestamp from last update (initial: `null`)
3. `error: string | null` — error message (initial: `null`)
4. `isWsConnected: boolean` — whether WS is currently open (initial: `false`)
5. `connectionFailed: boolean` — true when in polling fallback (initial: `false`)

`useRef` (declare after all useState calls):
1. `wsRef: WebSocket | null` — current WebSocket instance
2. `reconnectTimerRef: ReturnType<typeof setTimeout> | null` — reconnect/retry timer
3. `reconnectAttemptRef: number` — current retry count (initial: `0`)
4. `colorMapRef: Record<string, string>` — avoid stale closure on colorMap
5. `rawVehiclesRef: ApiVehicle[]` — raw vehicles for re-mapping when colorMap changes
6. `routeFilterRef: string | null` — current route filter for subscribe messages

#### 3f. colorMap ref sync

A small `useEffect` to keep `colorMapRef.current` in sync:
```typescript
useEffect(() => { colorMapRef.current = colorMap; }, [colorMap]);
```

#### 3g. routeFilter ref sync + re-subscribe on change

A small `useEffect` that updates `routeFilterRef` and sends a new subscribe message on the
existing open WebSocket when `routeFilter` changes (no reconnect needed):

```typescript
useEffect(() => {
  routeFilterRef.current = routeFilter ?? null;
  // Re-subscribe with updated filter on existing connection
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(
      JSON.stringify({
        action: "subscribe",
        route_id: routeFilter ?? undefined,
      }),
    );
  }
}, [routeFilter]);
```

**NOTE:** The `routeFilter` dependency here is the prop value. This effect ONLY sends a subscribe
message — it does NOT reconnect. The WS lifecycle is managed by a separate effect (3h).

#### 3h. WebSocket connection lifecycle (main useEffect)

One `useEffect` with dependency `[apiBase]` manages the full connection lifecycle:

```typescript
useEffect(() => {
  let cancelled = false;

  async function connect() {
    const token = await getToken();
    if (cancelled) return;
    if (!token) {
      setConnectionFailed(true);
      return;
    }

    const wsUrl = getWsUrl(apiBase);
    const fullUrl = `${wsUrl}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(fullUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (cancelled) { ws.close(); return; }
      reconnectAttemptRef.current = 0;
      setIsWsConnected(true);
      setConnectionFailed(false);
      setError(null);
      // Subscribe with current route filter
      ws.send(JSON.stringify({
        action: "subscribe",
        route_id: routeFilterRef.current ?? undefined,
      }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as Record<string, unknown>;
        const msgType = msg.type as string | undefined;

        if (msgType === "vehicle_update") {
          const apiVehicles = (msg.vehicles as ApiVehicle[]) ?? [];
          rawVehiclesRef.current = apiVehicles;
          setVehicles(apiVehicles.map((v) => mapVehicle(v, colorMapRef.current)));
          setLastFetchedAt((msg.timestamp as string) ?? new Date().toISOString());
          setError(null);
        } else if (msgType === "ping") {
          ws.send(JSON.stringify({ action: "pong" }));
        } else if (msgType === "error") {
          setError((msg.message as string) ?? "WebSocket error");
        }
        // "ack" messages are informational — no action needed
      } catch {
        // Malformed message — ignore
      }
    };

    ws.onclose = () => {
      if (cancelled) return;
      wsRef.current = null;
      setIsWsConnected(false);

      if (reconnectAttemptRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptRef.current), 8000);
        reconnectAttemptRef.current += 1;
        reconnectTimerRef.current = setTimeout(() => {
          if (!cancelled) void connect();
        }, delay);
      } else {
        setConnectionFailed(true);
      }
    };

    ws.onerror = () => {
      // Browser fires error before close — close handler manages reconnect
    };
  }

  void connect();

  return () => {
    cancelled = true;
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    if (wsRef.current) {
      wsRef.current.onclose = null; // Prevent reconnect on intentional close
      wsRef.current.close(1000);
      wsRef.current = null;
    }
  };
}, [apiBase]);
```

**IMPORTANT:** Dependency array is `[apiBase]` only. Other values are read via refs to avoid
reconnecting when they change.

#### 3i. Periodic WS retry while in polling fallback

A separate `useEffect` that runs a 60-second interval while `connectionFailed` is true:

```typescript
useEffect(() => {
  if (!connectionFailed) return;

  const retryInterval = setInterval(async () => {
    const token = await getToken();
    if (!token) return;

    // Test WebSocket connectivity
    const wsUrl = getWsUrl(apiBase);
    const testWs = new WebSocket(`${wsUrl}?token=${encodeURIComponent(token)}`);

    testWs.onopen = () => {
      // WS is available again — close test socket and trigger main reconnect
      testWs.close(1000);
      reconnectAttemptRef.current = 0;
      setConnectionFailed(false);
      // The main lifecycle effect won't re-run (apiBase unchanged), so we
      // need to manually trigger a connection. We do this by resetting
      // connectionFailed which causes the main effect's connect() to not
      // be needed — instead we reconnect here directly.
    };

    testWs.onerror = () => {
      // Still failing — stay in polling mode
      testWs.close();
    };
  }, WS_RETRY_INTERVAL);

  return () => clearInterval(retryInterval);
}, [connectionFailed, apiBase]);
```

**WAIT — this approach has a problem.** The main lifecycle effect has `[apiBase]` and runs once.
Setting `connectionFailed = false` won't re-trigger it. We need a different approach.

**Better approach:** Use a `connectTrigger` counter state. Increment it to force a new WS connect
attempt from the main lifecycle effect.

Replace the periodic retry effect with:

```typescript
const [connectTrigger, setConnectTrigger] = useState(0);
```

Add `connectTrigger` to the main lifecycle effect's dependency array: `[apiBase, connectTrigger]`.

The periodic retry effect becomes:
```typescript
useEffect(() => {
  if (!connectionFailed) return;

  const retryTimer = setInterval(() => {
    // Reset reconnect counter and trigger a fresh WS connect attempt
    reconnectAttemptRef.current = 0;
    setConnectionFailed(false);
    setConnectTrigger((n) => n + 1);
  }, WS_RETRY_INTERVAL);

  return () => clearInterval(retryTimer);
}, [connectionFailed]);
```

This cleanly reuses the main connect logic. When the WS retry succeeds, the hook switches
back to WS mode automatically. If it fails again (3 attempts), `connectionFailed` becomes true
again and the 60s retry timer restarts.

**Update the main lifecycle dependency array to: `[apiBase, connectTrigger]`.**

#### 3j. SWR fallback when WebSocket fails

```typescript
const { data: swrData } = useSWR<ApiResponse>(
  connectionFailed ? `${apiBase}/api/v1/transit/vehicles` : null,
  { refreshInterval: interval },
);

// Map SWR data when in fallback mode
useEffect(() => {
  if (!connectionFailed || !swrData) return;
  rawVehiclesRef.current = swrData.vehicles;
  setVehicles(swrData.vehicles.map((v) => mapVehicle(v, colorMapRef.current)));
  setLastFetchedAt(swrData.fetched_at);
}, [connectionFailed, swrData]);
```

#### 3k. Derived values and return

```typescript
// Re-map when colorMap changes (for already-received data)
const mappedVehicles = useMemo(
  () => rawVehiclesRef.current.map((v) => mapVehicle(v, colorMap)),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [colorMap, vehicles], // vehicles state change signals new rawVehiclesRef data
);

// Connection mode for UI display
const connectionMode: ConnectionMode = isWsConnected
  ? "ws"
  : connectionFailed
    ? "polling"
    : "connecting";

const isLoading = vehicles.length === 0 && !lastFetchedAt && !error;

return {
  vehicles: mappedVehicles,
  isLoading,
  error,
  lastFetchedAt,
  connectionMode,
};
```

**CRITICAL NOTES for the executor:**
- The `eslint-disable-next-line` comment on `useMemo` is needed because `rawVehiclesRef.current`
  is not a valid React dependency. We track its changes via the `vehicles` state update.
- `ws.onclose = null` in cleanup prevents reconnect logic from firing on intentional close.
- `getToken()` is called inside the effect (not a dependency) — it handles its own 60s cache.
- `routeFilter` is read via `routeFilterRef.current` in the WS lifecycle to avoid reconnects.
- `connectTrigger` is a counter state used solely to re-trigger the main lifecycle effect for
  periodic WS retry. It has no other purpose.
- All `useState` declarations MUST come before all `useRef` declarations which MUST come before
  all `useEffect`/`useMemo` hooks. This is a React 19 hook ordering requirement.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes
- `cd cms && pnpm --filter @vtv/web build` passes

---

### Task 4: Add connection status badge to RouteMap
**File:** `cms/apps/web/src/components/routes/route-map.tsx` (modify)
**Action:** UPDATE

#### 4a. Update imports

Add the `ConnectionMode` type import:

```typescript
import type { ConnectionMode } from "@/hooks/use-vehicle-positions";
```

#### 4b. Update RouteMapProps interface

Add `connectionMode` prop:

```typescript
interface RouteMapProps {
  buses: BusPosition[];
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
  connectionMode?: ConnectionMode;
}
```

The prop is optional (`?`) so any existing callers that don't pass it won't break.

#### 4c. Add status badge

Destructure `connectionMode = "connecting"` in the component params (default for backwards compat).

Add a second overlay `div` positioned at top-right of the map (the existing vehicle count overlay
is at top-left). Place it AFTER the existing top-left overlay and BEFORE `<MapContainer>`:

```tsx
{/* Connection status badge — top right */}
<div className="absolute right-3 top-3 z-[1000] flex items-center gap-(--spacing-tight) rounded-md bg-surface/90 px-2 py-1 text-xs shadow-sm backdrop-blur-sm transition-all duration-200">
  <span
    className={`inline-block size-2 rounded-full ${
      connectionMode === "ws"
        ? "bg-status-ontime"
        : connectionMode === "polling"
          ? "bg-status-delayed"
          : "animate-pulse bg-status-delayed"
    }`}
    aria-hidden="true"
  />
  <span className="font-medium text-foreground">
    {connectionMode === "ws"
      ? t("liveStream")
      : connectionMode === "polling"
        ? t("pollingFallback")
        : t("wsConnecting")}
  </span>
</div>
```

**Design notes:**
- Green dot (`bg-status-ontime`) = WebSocket live
- Amber dot (`bg-status-delayed`) = HTTP polling fallback
- Pulsing amber dot = connecting/reconnecting
- `size-2` = 8px dot (subtle)
- Same `bg-surface/90 backdrop-blur-sm shadow-sm` as the existing vehicle count badge
- `transition-all duration-200` for smooth state changes
- All colors are semantic tokens — no primitives

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 5: Wire new hook options in Routes page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` (modify)
**Action:** UPDATE

#### 5a. Update the useVehiclePositions call

The current call at approximately line 80 is:
```typescript
const { vehicles: liveVehicles } = useVehiclePositions({
  colorMap: routeColorMap,
});
```

Replace with:
```typescript
const { vehicles: liveVehicles, connectionMode } = useVehiclePositions({
  colorMap: routeColorMap,
  routeFilter: selectedGtfsRouteId,
});
```

This destructures the new `connectionMode` and passes `selectedGtfsRouteId` as the WS filter.
When a route is selected in the table, only that route's vehicles come over the WebSocket.
When no route is selected (`null`), all vehicles are received.

**NOTE:** `selectedGtfsRouteId` is already defined at approximately line 123-127. It derives the
GTFS route ID string from the selected numeric route ID. It is `null` when no route is selected.

#### 5b. Pass connectionMode to RouteMap components

There are two `<RouteMap>` instances in the file:

1. **Mobile tab** (inside `<TabsContent value="map">`): Add `connectionMode={connectionMode}`
2. **Desktop resizable panel** (inside `<ResizablePanel defaultSize={40}>`): Add `connectionMode={connectionMode}`

Both RouteMap calls currently look like:
```tsx
<RouteMap
  buses={filteredVehicles}
  selectedRouteId={selectedGtfsRouteId}
  onSelectRoute={...}
/>
```

Add `connectionMode={connectionMode}` to both.

#### 5c. Behavior change documentation

When `routeFilter` (= `selectedGtfsRouteId`) is set:
- The WebSocket sends a subscribe with `route_id`, so the server only pushes that route's vehicles
- The map shows only the selected route's vehicles (not all vehicles with one highlighted)
- The `typeFilter` client-side filtering still applies on top of this

When `routeFilter` is null (no route selected):
- All vehicles are received via WebSocket (or polling fallback)
- Client-side `typeFilter` still applies
- This is the same as current behavior

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes
- `cd cms && pnpm --filter @vtv/web build` passes

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

- [ ] Hook compiles with zero TypeScript errors
- [ ] Routes page passes `routeFilter` and destructures `connectionMode`
- [ ] `RouteMap` displays connection status badge (green=WS, amber=polling, pulsing=connecting)
- [ ] `BusPosition` type is unchanged in `types/route.ts`
- [ ] WebSocket connects using JWT from `getToken()`
- [ ] Heartbeat/pong protocol implemented (responds to `{"type": "ping"}` with `{"action": "pong"}`)
- [ ] Auto-reconnect with exponential backoff (1s → 2s → 4s, max 3 attempts)
- [ ] Falls back to SWR HTTP polling after 3 failed WebSocket attempts
- [ ] Periodic WS retry every 60s while in polling fallback
- [ ] When WS retry succeeds, switches back to WS mode (badge turns green)
- [ ] `routeFilter` sends subscribe with `route_id` to WS (no reconnect)
- [ ] Changing route selection sends new subscribe message (not a reconnect)
- [ ] `colorMap` option still works (colors update without reconnecting WS)
- [ ] Cleanup closes WebSocket on unmount and clears all timers
- [ ] i18n keys present in both `lv.json` and `en.json`
- [ ] No hardcoded colors — badge uses `bg-status-ontime` and `bg-status-delayed`
- [ ] No hardcoded URLs — uses `NEXT_PUBLIC_AGENT_URL` env var
- [ ] No security violations (token not logged, not in localStorage)

## Acceptance Criteria

This feature is complete when:
- [ ] `useVehiclePositions` connects via WebSocket to `/ws/transit/vehicles`
- [ ] Vehicle positions update in real-time (~100ms latency vs previous 10s polling)
- [ ] Connection status badge visible on route map (Live / Polling / Connecting)
- [ ] Graceful fallback to HTTP polling when WebSocket unavailable
- [ ] Periodic WS retry (60s) while in polling fallback — auto-recovers
- [ ] Route selection pushes `route_id` filter to WebSocket (server-side filtering)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`
