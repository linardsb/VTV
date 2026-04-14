# Plan: FE LV-3.4 LocShare — Shareable Vehicle Tracking Links

## Context

Passengers and operations staff need "where is my bus?" links they can share without VTV accounts. The backend (LV-3.4) provides two endpoints:
- `POST /api/v1/transit/share` — admin/dispatcher creates a share link (returns JWT token, QR code base64, share URL)
- `GET /api/v1/transit/share/{token}` — **public** endpoint resolves token to vehicle position data

The frontend needs:
1. **Public tracking page** at `/[locale]/share/[token]` — no auth, shows single vehicle on a Leaflet map with auto-refresh
2. **Admin management page** at `/[locale]/(dashboard)/share-links` — authenticated, create links + view active links + copy URLs + display QR codes

## Security Context Assessment

| Context | Active | Reason |
|---------|--------|--------|
| CTX-RBAC | **Yes** | Admin page requires admin/dispatcher role; public page needs no auth |
| CTX-INPUT | **Yes** | Token path param from URL, vehicle_id selection for creation |
| CTX-AUTH | No | Public page uses plain fetch (no JWT); admin page uses authFetch |
| CTX-FILE | No | No file uploads |
| CTX-AGENT | No | No agent tools |
| CTX-INFRA | No | No Docker/nginx changes |

## Research Summary

### Reference Patterns
- **Journey Planner page** (`components/journey-planner/`) — split layout (form panel + map), dynamic Leaflet import with SSR disabled, `authFetch`-based SDK wrapper
- **Login page** (`app/[locale]/login/`) — public page outside `(dashboard)` layout group, no sidebar
- **Route Map** (`components/routes/route-map.tsx`) — `BusMarker` component, connection status badge, CARTO tile layer
- **Geofences SDK** (`lib/geofences-sdk.ts`) — `authFetch`-based wrapper pattern with error class

### Key Files
| Area | File | Purpose |
|------|------|---------|
| Map hook | `src/hooks/use-vehicle-positions.ts` | WebSocket + SWR vehicle tracking |
| Bus marker | `src/components/routes/bus-marker.tsx` | Leaflet marker with route color + popup |
| Route map | `src/components/routes/route-map.tsx` | Single-route vehicle map, CARTO tiles |
| Journey page | `src/components/journey-planner/journey-planner-page.tsx` | Split layout pattern |
| Journey SDK | `src/lib/journey-sdk.ts` | `authFetch` SDK wrapper pattern |
| Auth fetch | `src/lib/auth-fetch.ts` | JWT-authenticated fetch wrapper |
| Sidebar | `src/components/app-sidebar.tsx:38-67` | Navigation entries array |
| Middleware | `middleware.ts:5-10` | RBAC permissions, matcher on line 34 |
| Login page | `src/app/[locale]/login/page.tsx` | Public page pattern (no dashboard layout) |

### Public Page Routing
Pages outside `(dashboard)` layout group (like `login/`) have no sidebar. The middleware matcher only covers dashboard routes — `/share/*` is **automatically public** since it won't match the regex at `middleware.ts:34`.

## Test Landscape

- 11 Playwright test files, ~81 tests total
- Auth state reuse: `e2e/auth.setup.ts` saves session to `e2e/.auth/user.json`
- Unauthenticated tests use `*.noauth.spec.ts` pattern with `"no-auth"` project
- No MSW/mock layer — tests hit real backend on port 8123
- No component unit tests — all testing via Playwright e2e
- Shared helpers: `waitForDataOrEmpty()`, `hasDataTable()` in `e2e/helpers.ts`

## Type Check Baseline

| Tool | Errors |
|------|--------|
| `pnpm --filter @vtv/web type-check` | **0** |
| `pnpm --filter @vtv/web lint` | **0** |

Target: 0 new errors after implementation.

## Design System

- **Border radius:** `border-radius: 0` on all components (MASTER.md rule)
- **Colors:** Semantic tokens only — `bg-surface`, `text-foreground`, `bg-primary`, `text-primary-foreground`, `border-border`, `text-foreground-muted`, `text-error`, `bg-error-bg`, `text-status-ontime`, `text-status-delayed`
- **Spacing:** Compact tokens — `p-(--spacing-card)`, `gap-(--spacing-grid)`, `p-(--spacing-page)`
- **Typography:** Lexend (headings), Source Sans 3 (body)
- **Dialog widths:** `sm:max-w-[28rem]` (detail), `sm:max-w-[32rem]` (forms)
- **No named container sizes** — use explicit rem values (`sm:max-w-[32rem]` not `max-w-lg`)

## i18n Keys

```jsonc
// lv.json — add "shareLinks" and "shareView" namespaces
{
  "shareLinks": {
    "title": "Koplietošanas saites",
    "description": "Izveidojiet un pārvaldiet publiskas transportlīdzekļu izsekošanas saites",
    "createLink": "Izveidot saiti",
    "vehicleId": "Transportlīdzekļa ID",
    "routeId": "Maršruts",
    "feedId": "Datu avots",
    "expiryHours": "Derīguma laiks",
    "hours": "{count}h",
    "expiresAt": "Derīgs līdz",
    "createdAt": "Izveidots",
    "views": "Skatījumi",
    "active": "Aktīvs",
    "expired": "Beidzies",
    "qrCode": "QR kods",
    "copyUrl": "Kopēt URL",
    "linkCopied": "Saite nokopēta!",
    "noLinks": "Nav izveidotas koplietošanas saites",
    "confirmDelete": "Vai tiešām vēlaties dzēst šo saiti?",
    "deleteSuccess": "Saite dzēsta",
    "createSuccess": "Saite izveidota"
  },
  "shareView": {
    "title": "Transportlīdzekļa atrašanās vieta",
    "loading": "Ielādē...",
    "expired": "Šī saite ir beigusies",
    "notFound": "Saite nav atrasta",
    "error": "Neizdevās ielādēt datus",
    "lastUpdate": "Pēdējais atjauninājums",
    "delay": "Kavēšanās",
    "onTime": "Laikā",
    "route": "Maršruts",
    "speed": "Ātrums",
    "nextStop": "Nākamā pietura",
    "poweredBy": "VTV — Vienotā Transporta Vadība"
  }
}
```

```jsonc
// en.json — add matching namespaces
{
  "shareLinks": {
    "title": "Share Links",
    "description": "Create and manage public vehicle tracking links",
    "createLink": "Create Link",
    "vehicleId": "Vehicle ID",
    "routeId": "Route",
    "feedId": "Data Source",
    "expiryHours": "Expiry Time",
    "hours": "{count}h",
    "expiresAt": "Expires",
    "createdAt": "Created",
    "views": "Views",
    "active": "Active",
    "expired": "Expired",
    "qrCode": "QR Code",
    "copyUrl": "Copy URL",
    "linkCopied": "Link copied!",
    "noLinks": "No share links created",
    "confirmDelete": "Are you sure you want to delete this link?",
    "deleteSuccess": "Link deleted",
    "createSuccess": "Link created"
  },
  "shareView": {
    "title": "Vehicle Location",
    "loading": "Loading...",
    "expired": "This link has expired",
    "notFound": "Link not found",
    "error": "Failed to load data",
    "lastUpdate": "Last update",
    "delay": "Delay",
    "onTime": "On time",
    "route": "Route",
    "speed": "Speed",
    "nextStop": "Next stop",
    "poweredBy": "VTV — Unified Transit Management"
  }
}
```

## RBAC

- **Middleware matcher:** Add `share-links` to matcher regex and RBAC permissions (admin + dispatcher only)
- **Public `/share/[token]`:** Outside matcher — no auth check needed
- **Sidebar nav:** Add `shareLinks` entry after `chat`, before nothing (end of list), admin/dispatcher visibility only

## Files to Create/Modify

| # | Action | File | Purpose |
|---|--------|------|---------|
| 1 | CREATE | `src/types/share.ts` | TypeScript types matching backend schemas |
| 2 | CREATE | `src/lib/share-sdk.ts` | API client for share link endpoints |
| 3 | CREATE | `src/components/share/share-tracker.tsx` | Public tracking page: single vehicle on Leaflet map with auto-refresh |
| 4 | CREATE | `src/components/share-links/share-links-page.tsx` | Admin page: table + create dialog |
| 5 | CREATE | `src/components/share-links/create-share-link-dialog.tsx` | Form dialog for creating a share link |
| 6 | CREATE | `src/components/share-links/qr-code-display.tsx` | Base64 QR code image display |
| 7 | CREATE | `src/app/[locale]/share/[token]/page.tsx` | Public route page component |
| 8 | CREATE | `src/app/[locale]/(dashboard)/share-links/page.tsx` | Admin route page component |
| 9 | UPDATE | `messages/lv.json` | Add `shareLinks` + `shareView` i18n keys |
| 10 | UPDATE | `messages/en.json` | Add `shareLinks` + `shareView` i18n keys |
| 10b | UPDATE | `messages/ru.json` | Add `shareLinks` + `shareView` i18n keys (copy en.json values) |
| 11 | UPDATE | `src/components/app-sidebar.tsx` | Add `shareLinks` nav entry |
| 12 | UPDATE | `middleware.ts` | Add `share-links` to matcher + RBAC permissions |

## Implementation Steps

### Step 1: Create TypeScript types

**File:** `cms/apps/web/src/types/share.ts` (CREATE)

Types must exactly match backend `ShareLinkResponse`, `ShareLinkData`, `ShareLinkCreate` schemas from `app/transit/schemas.py:265-299`.

```typescript
/** Expiry options matching backend Literal[1, 2, 4, 6, 12, 24]. */
export type ShareLinkExpiryHours = 1 | 2 | 4 | 6 | 12 | 24;

/** POST body for creating a share link. */
export interface ShareLinkCreateParams {
  vehicle_id: string;
  route_id?: string | null;
  feed_id?: string;  // default "riga"
  expiry_hours?: ShareLinkExpiryHours;  // default 1
}

/** Response from POST /api/v1/transit/share (creation). */
export interface ShareLinkResponse {
  id: number;
  token: string;
  share_url: string;
  qr_code_base64: string;
  vehicle_id: string;
  route_id: string | null;
  feed_id: string;
  expires_at: string;  // ISO datetime
  created_at: string;  // ISO datetime
}

/** Vehicle position data (subset of transit VehiclePosition). */
export interface ShareVehiclePosition {
  vehicle_id: string;
  route_id: string | null;
  route_short_name: string | null;
  route_type: number | null;
  latitude: number;
  longitude: number;
  bearing: number | null;
  speed_kmh: number | null;
  delay_seconds: number | null;
  current_status: string | null;
  next_stop_name: string | null;
  timestamp: string | null;
  feed_id: string;
}

/** Response from GET /api/v1/transit/share/{token} (public resolution). */
export interface ShareLinkData {
  vehicle_id: string;
  route_id: string | null;
  feed_id: string;
  position: ShareVehiclePosition | null;
  expires_at: string;  // ISO datetime
  share_link_id: number;
}
```

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 2: Create SDK wrapper

**File:** `cms/apps/web/src/lib/share-sdk.ts` (CREATE)

Follow the `journey-sdk.ts` pattern. Two functions:
- `createShareLink(params)` — uses `authFetch` (admin/dispatcher only)
- `resolveShareLink(token)` — uses plain `fetch` (public, no auth)

```typescript
import { authFetch } from "@/lib/auth-fetch";
import type { ShareLinkCreateParams, ShareLinkResponse, ShareLinkData } from "@/types/share";

const BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export class ShareApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ShareApiError";
    this.status = status;
  }
}

/** Create a share link (requires admin/dispatcher auth). */
export async function createShareLink(params: ShareLinkCreateParams): Promise<ShareLinkResponse> {
  const res = await authFetch(`${BASE}/api/v1/transit/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new ShareApiError(res.status, "Failed to create share link");
  return res.json() as Promise<ShareLinkResponse>;
}

/** Resolve a share link token (public, no auth). */
export async function resolveShareLink(token: string): Promise<ShareLinkData> {
  const res = await fetch(`${BASE}/api/v1/transit/share/${encodeURIComponent(token)}`);
  if (res.status === 410) throw new ShareApiError(410, "expired");
  if (!res.ok) throw new ShareApiError(res.status, "not_found");
  return res.json() as Promise<ShareLinkData>;
}
```

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 3: Create QR code display component

**File:** `cms/apps/web/src/components/share-links/qr-code-display.tsx` (CREATE)

Simple component displaying a backend-generated base64 QR code PNG. CSP already allows `img-src data:`.

```typescript
interface QrCodeDisplayProps {
  base64: string;
  alt: string;
  size?: number;  // default 200
}
```

Renders `<img src={`data:image/png;base64,${base64}`} />` with given dimensions. Include a "Download QR" button using an anchor with `download` attribute.

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 4: Create public tracking page component

**File:** `cms/apps/web/src/components/share/share-tracker.tsx` (CREATE, `"use client"`)

This is the core public-facing component. Design:
- Full-screen Leaflet map (no sidebar, no dashboard chrome)
- Single vehicle marker using `BusMarker` pattern (or simplified `L.divIcon`)
- Info panel overlay (bottom or sidebar on mobile) showing: route, delay, speed, next stop, last update
- Auto-refresh every 10s via `setInterval` calling `resolveShareLink(token)`
- Error states: expired (410), not found (404), loading
- VTV branding footer: "VTV — Vienotā Transporta Vadība"

Layout pattern (inspired by journey-planner split but simpler):
- Mobile: full-screen map with bottom info card
- Desktop: full-screen map with info panel overlay

Dynamic Leaflet import (SSR disabled):
```typescript
const ShareMap = dynamic(() => import("./share-map").then(m => ({ default: m.ShareMap })), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center">...</div>,
});
```

**Full URL construction:** The backend returns `share_url: "/share/{token}"` (relative). For QR codes and clipboard, construct the absolute URL: `${window.location.origin}/${locale}/share/${token}`. Store this as `fullShareUrl` state after creation. The public tracker page itself doesn't need this — it's already at the correct URL.

States:
- `loading` — initial fetch, show skeleton
- `data` — vehicle position loaded, show map + info
- `expired` — 410 response, show expiry message with VTV branding
- `notFound` — 404 response, show not-found message
- `error` — network error, show retry button

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 5: Create share map sub-component

**File:** `cms/apps/web/src/components/share/share-map.tsx` (CREATE, `"use client"`)

Leaflet `MapContainer` with:
- CARTO basemap tile layer (same as `route-map.tsx`)
- Single marker at vehicle position with bearing rotation
- Auto-center on vehicle (use `map.setView()` on position update)
- Popup with vehicle info
- Center: vehicle lat/lon (or Riga default `[56.9496, 24.1052]` before data loads)

Props: `{ position: ShareVehiclePosition | null }`

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 6: Create public route page

**File:** `cms/apps/web/src/app/[locale]/share/[token]/page.tsx` (CREATE)

Server component that extracts `token` from params and renders `ShareTracker`.
- Outside `(dashboard)` layout group — no sidebar, no auth
- Uses `useTranslations("shareView")` (needs `"use client"` or pass translations as props)
- Simple: just renders `<ShareTracker token={token} />`

Since this page needs client interactivity (map, polling), make it a client component:
```typescript
"use client";
import { useParams } from "next/navigation";
import { ShareTracker } from "@/components/share/share-tracker";

export default function SharePage() {
  const params = useParams<{ token: string }>();
  return <ShareTracker token={params.token} />;
}
```

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 7: Create admin page components

**File:** `cms/apps/web/src/components/share-links/share-links-page.tsx` (CREATE, `"use client"`)

Admin page with:
- Header: title + "Create Link" button
- Table of active share links: vehicle_id, route_id, feed_id, expires_at, views, actions (copy URL, view QR, delete)
- Create dialog (Step 8)
- QR code dialog/popover on click

Data fetching: `useSession()` gate, then load share links from a list endpoint. **Note:** The backend plan only defines POST (create) and GET (resolve). If no list endpoint exists, the admin page shows only the most recently created link, or we need to add a list endpoint to the backend. For now, design the UI as a "create and view" flow — user creates a link, sees the result with QR code, and can copy the URL.

Simplified flow:
1. User fills create form (vehicle_id, route_id, feed_id, expiry)
2. POST to backend → receive `ShareLinkResponse` with token, QR, URL
3. Display result: share URL (copy button), QR code (display + download), expiry countdown
4. No persistent table (backend has no list endpoint in current plan)

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 8: Create share link dialog

**File:** `cms/apps/web/src/components/share-links/create-share-link-dialog.tsx` (CREATE, `"use client"`)

Form fields matching `ShareLinkCreate`:
- `vehicle_id` — text input, required, pattern `^[\w\-.:]+$`
- `route_id` — text input, optional
- `feed_id` — text input, default "riga"
- `expiry_hours` — select dropdown: 1h, 2h, 4h, 6h, 12h, 24h

On submit: call `createShareLink()`, on success show the result with QR code and copy URL button.

**Full URL for QR + clipboard:** Build absolute URL from `window.location.origin` + `/${locale}/share/${response.token}`. The backend's `share_url` is relative — use the constructed absolute URL for QR code content and the "Copy URL" button. Pass `locale` from `useLocale()`.

Dialog width: `sm:max-w-[32rem]` (form pattern).

Uses `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription` from shadcn/ui.
Uses `Button`, `Input`, `Label`, `Select` from shadcn/ui.

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 9: Create admin route page

**File:** `cms/apps/web/src/app/[locale]/(dashboard)/share-links/page.tsx` (CREATE)

Simple wrapper:
```typescript
import { ShareLinksPage } from "@/components/share-links/share-links-page";
export default function Page() {
  return <ShareLinksPage />;
}
```

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 10: Add i18n keys

**File:** `cms/apps/web/messages/lv.json` — add `shareLinks` and `shareView` objects (see i18n Keys section above)
**File:** `cms/apps/web/messages/en.json` — add matching keys
**File:** `cms/apps/web/messages/ru.json` — add matching keys (copy en.json values; ru locale is in middleware matcher)

Add `nav.shareLinks` key to all three files:
- lv: `"shareLinks": "Koplietošanas saites"`
- en: `"shareLinks": "Share Links"`
- ru: `"shareLinks": "Share Links"` (English fallback)

**Validation:** Verify all files parse as valid JSON: `node -e "JSON.parse(require('fs').readFileSync('cms/apps/web/messages/lv.json'))"`

### Step 11: Update sidebar navigation

**File:** `cms/apps/web/src/components/app-sidebar.tsx`

Add nav entry at line ~67 (after `chat`):
```typescript
{ key: "shareLinks", href: "/share-links", enabled: true },
```

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

### Step 12: Update middleware RBAC

**File:** `cms/apps/web/middleware.ts`

1. Add `/share-links` to `admin` and `dispatcher` permission arrays (lines 6-7)
2. Add `share-links` to the matcher regex (line 34)

The `/share/[token]` route is NOT added to the matcher — it remains public.

**Validation:** `cd cms && pnpm --filter @vtv/web type-check`

## Preflight Warnings

- **No backend list endpoint:** Backend plan only defines POST (create) and GET by token (resolve). The admin page cannot display a table of all links without a list endpoint. Design as "create → view result" flow.
- **Leaflet SSR:** All Leaflet components must be dynamically imported with `ssr: false`
- **`import datetime as dt`:** Backend convention — irrelevant for frontend but keep in mind for API response field names (`expires_at`, `created_at` are ISO strings)
- **Named container sizes:** Never use `max-w-lg` etc. — use `sm:max-w-[32rem]`
- **React 19 rules:** No `setState` in `useEffect`, no component defs inside components, no `Math.random()` in render
- **Public fetch:** The `resolveShareLink()` function uses plain `fetch()` (not `authFetch`) since it's a public endpoint
- **QR code base64:** Backend returns raw base64 string (not data URI) — frontend must prepend `data:image/png;base64,`
- **`ShareVehiclePosition` vs `BusPosition`:** `BusPosition` (in `types/route.ts`) uses camelCase (transformed by `useVehiclePositions` hook). The public page uses raw `fetch()` returning snake_case, so `ShareVehiclePosition` is a separate type matching the raw API response. This is intentional.
- **Full URL for QR codes:** Backend returns relative `share_url: "/share/{token}"`. Must construct absolute URL using `window.location.origin` + locale prefix for QR codes and clipboard copy

## Security Checklist

- [ ] No `as any` casts
- [ ] Public page uses plain `fetch()` (not `authFetch`) — no token leakage
- [ ] Admin page uses `authFetch` for authenticated operations
- [ ] No `dangerouslySetInnerHTML`
- [ ] No hardcoded API URLs (uses `NEXT_PUBLIC_AGENT_URL` env var)
- [ ] No tokens in localStorage
- [ ] Token from URL params is passed to backend as-is (no client-side JWT decoding)
- [ ] External links use `rel="noopener noreferrer"`
- [ ] QR code displayed as `<img>` with `alt` text (accessible)
- [ ] Admin page protected by middleware RBAC (admin + dispatcher only)
- [ ] Public page has no session/auth dependency

## Verification

- [ ] `cd cms && pnpm --filter @vtv/web type-check` — 0 errors (baseline: 0)
- [ ] `cd cms && pnpm --filter @vtv/web lint` — 0 errors, 0 warnings (baseline: 0)
- [ ] `cd cms && pnpm --filter @vtv/web build` — builds successfully
- [ ] Semantic Tailwind tokens only (no primitive color classes)
- [ ] i18n keys in both `lv.json` and `en.json`
- [ ] All user-visible text uses `useTranslations()`
- [ ] `border-radius: 0` on all components (no `rounded-*` except avatars/switches)
- [ ] Dialog widths use explicit rem values
- [ ] Public page loads without authentication
- [ ] Admin page redirects to login when unauthenticated
- [ ] QR code renders and is downloadable
- [ ] Map auto-refreshes vehicle position every 10s
