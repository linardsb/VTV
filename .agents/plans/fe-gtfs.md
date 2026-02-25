# Plan: GTFS Data Management Page

## Feature Metadata
**Feature Type**: New Page
**Estimated Complexity**: Medium
**Route**: `/[locale]/(dashboard)/gtfs`
**Auth Required**: Yes
**Allowed Roles**: admin, editor

## Feature Description

The GTFS Data Management page is a centralized hub for managing General Transit Feed Specification data flows — both static (schedules, routes, stops) and real-time (GTFS-RT vehicle feeds). It provides three core capabilities: an overview of imported data with live feed status, GTFS ZIP import (reusing the existing GTFSImport component from the Schedules page), and GTFS ZIP export with optional agency filtering.

This page fills a gap in the CMS: while the Schedules page embeds GTFS import as one of its tabs, there is no dedicated view for understanding the overall state of GTFS data in the system, no UI for the GTFS export endpoint (`GET /api/v1/schedules/export`), and no visibility into GTFS-RT feed status (`GET /api/v1/transit/feeds`). The GTFS page brings all three together in a focused workflow.

The page is restricted to admin and editor roles (matching the existing middleware RBAC config) since it involves bulk data operations that affect the entire schedule dataset.

## Design System

### Master Rules (from MASTER.md)
- Typography: Lexend headings, Source Sans 3 body, `--font-size-heading: 1.125rem`
- Spacing: Dashboard-density tokens (`--spacing-page`, `--spacing-card`, `--spacing-grid`, `--spacing-inline`)
- Colors: oklch semantic tokens — never primitive Tailwind colors
- Cards: `border-border`, `bg-card-bg`, `rounded-lg`, `--shadow-md`
- Focus rings: 3px, `--color-focus-ring` for WCAG AAA
- Transitions: 150-300ms on interactive elements

### Page Override
None — generate during execution using existing MASTER.md rules. No page-specific overrides needed for a data management page.

### Tokens Used
- `bg-surface`, `bg-surface-raised`, `bg-background` — surface hierarchy
- `text-foreground`, `text-foreground-muted` — text hierarchy
- `border-border` — card/section borders
- `bg-interactive`, `text-interactive-foreground` — primary buttons
- `text-status-ontime`, `text-status-critical`, `text-status-delayed` — feed status indicators
- `--spacing-page`, `--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight` — layout

## Components Needed

### Existing (shadcn/ui)
- `Button` — import/export actions, download trigger
- `Card` — stats cards, feed status cards
- `Badge` — entity counts, feed status indicators
- `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` — three-tab layout (Overview/Import/Export)
- `Select` — agency filter for export
- `Separator` — section dividers
- `Skeleton` — loading placeholders
- `Progress` — already used by GTFSImport

### New shadcn/ui to Install
None — all required components already installed.

### Custom Components to Create
- `DataOverview` at `cms/apps/web/src/components/gtfs/data-overview.tsx` — stats cards + RT feed status
- `GTFSExport` at `cms/apps/web/src/components/gtfs/gtfs-export.tsx` — export with agency filter + download

### Existing Components to Reuse
- `GTFSImport` from `cms/apps/web/src/components/schedules/gtfs-import.tsx` — drag-and-drop ZIP import + validation

## i18n Keys

### Latvian (`lv.json`)
```json
{
  "gtfs": {
    "title": "GTFS datu pārvaldība",
    "description": "Importējiet, eksportējiet un pārvaldiet GTFS tranzīta datus",
    "tabs": {
      "overview": "Pārskats",
      "import": "Imports",
      "export": "Eksports"
    },
    "overview": {
      "dataTitle": "Datu statistika",
      "agencies": "Operatori",
      "routes": "Maršruti",
      "calendars": "Kalendāri",
      "trips": "Reisi",
      "stops": "Pieturas",
      "feedsTitle": "GTFS-RT datu plūsmas",
      "feedEnabled": "Aktīvs",
      "feedDisabled": "Neaktīvs",
      "pollInterval": "Intervāls: {seconds}s",
      "noFeeds": "Nav konfigurētu datu plūsmu",
      "loadError": "Neizdevās ielādēt datus",
      "refreshButton": "Atjaunot"
    },
    "export": {
      "title": "Eksportēt GTFS datus",
      "description": "Lejupielādējiet GTFS datus kā ZIP arhīvu standarta formātā",
      "agencyFilter": "Operators",
      "allAgencies": "Visi operatori",
      "downloadButton": "Lejupielādēt GTFS ZIP",
      "downloading": "Lejupielādē...",
      "downloadSuccess": "GTFS dati veiksmīgi lejupielādēti",
      "downloadError": "GTFS datu lejupielāde neizdevās",
      "includesNote": "Ietver: agency.txt, routes.txt, calendar.txt, calendar_dates.txt, trips.txt, stop_times.txt, stops.txt"
    }
  }
}
```

### English (`en.json`)
```json
{
  "gtfs": {
    "title": "GTFS Data Management",
    "description": "Import, export, and manage GTFS transit data",
    "tabs": {
      "overview": "Overview",
      "import": "Import",
      "export": "Export"
    },
    "overview": {
      "dataTitle": "Data Statistics",
      "agencies": "Agencies",
      "routes": "Routes",
      "calendars": "Calendars",
      "trips": "Trips",
      "stops": "Stops",
      "feedsTitle": "GTFS-RT Data Feeds",
      "feedEnabled": "Active",
      "feedDisabled": "Inactive",
      "pollInterval": "Interval: {seconds}s",
      "noFeeds": "No feeds configured",
      "loadError": "Failed to load data",
      "refreshButton": "Refresh"
    },
    "export": {
      "title": "Export GTFS Data",
      "description": "Download GTFS data as a standard-format ZIP archive",
      "agencyFilter": "Agency",
      "allAgencies": "All Agencies",
      "downloadButton": "Download GTFS ZIP",
      "downloading": "Downloading...",
      "downloadSuccess": "GTFS data downloaded successfully",
      "downloadError": "Failed to download GTFS data",
      "includesNote": "Includes: agency.txt, routes.txt, calendar.txt, calendar_dates.txt, trips.txt, stop_times.txt, stops.txt"
    }
  }
}
```

## Data Fetching

### API Endpoints Used
1. `GET /api/v1/schedules/agencies` — list agencies (for export filter + stats)
2. `GET /api/v1/schedules/routes?page_size=1` — routes total count
3. `GET /api/v1/schedules/calendars?page_size=1` — calendars total count
4. `GET /api/v1/schedules/trips?page_size=1` — trips total count
5. `GET /api/v1/transit/feeds` — GTFS-RT feed status
6. `GET /api/v1/schedules/export?agency_id={id}` — download GTFS ZIP (returns blob)
7. `POST /api/v1/schedules/import` — import GTFS ZIP (existing client function)
8. `POST /api/v1/schedules/validate` — validate schedule data (existing client function)

### New API Client Functions (in `gtfs-client.ts`)
- `fetchGTFSStats()` — calls agencies + routes + calendars + trips endpoints in parallel, returns aggregate counts
- `fetchFeeds()` — calls `/api/v1/transit/feeds`, returns feed config array
- `exportGTFS(agencyId?: number)` — downloads `/api/v1/schedules/export` as Blob, triggers browser download

### Server vs Client
- All data fetching is **client-side** (page is `"use client"` with `useSession` gate)
- Stats and feeds load on mount via `useEffect` gated on `status === "authenticated"`
- Export is triggered by user click (no preloading)
- Import reuses existing GTFSImport component (already client-side)

### Loading States
- Stats cards: `Skeleton` placeholders (5 cards in a row)
- Feed list: `Skeleton` block
- Export: Button disabled state with "Downloading..." text

### Server/Client Boundary
- All API calls use `authFetch` from `src/lib/auth-fetch.ts` (handles dual-context)
- No new server-only imports needed
- For stops count, reuse the existing `fetchStops({ page_size: 1 })` from `stops-client.ts`

## RBAC Integration

### Middleware Matcher
Already configured — `gtfs` is in the matcher pattern:
```ts
matcher: ["/(lv|en)/(routes|stops|schedules|drivers|gtfs|users|chat|documents)/:path*"]
```

### Role Permissions
Already configured in `middleware.ts`:
```ts
admin: [..., "/gtfs", ...],
editor: [..., "/gtfs", ...],
```
Only `admin` and `editor` can access. `dispatcher` and `viewer` cannot.

**No middleware changes needed.**

## Sidebar Navigation

### Label Key
`nav.gtfs` — already exists in both `lv.json` ("GTFS") and `en.json` ("GTFS")

### Icon
`Database` from lucide-react (represents data management)

### Position
After "Drivers", before "Users" (current position in `navItems` array)

### Change Required
Set `enabled: true` for the `gtfs` entry in `cms/apps/web/src/components/app-sidebar.tsx`:
```ts
{ key: "gtfs", href: "/gtfs", enabled: true },
```

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules
- `cms/apps/web/CLAUDE.md` — Frontend-specific conventions, React 19 anti-patterns

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/schedules/page.tsx` — Tabbed page with session gate, same data domain
- `cms/apps/web/src/components/schedules/gtfs-import.tsx` — Component to reuse for Import tab
- `cms/apps/web/src/lib/schedules-client.ts` — API client pattern to follow
- `cms/apps/web/src/lib/documents-client.ts` — Blob download pattern (see `downloadDocument()`)
- `cms/apps/web/src/lib/auth-fetch.ts` — Authenticated fetch wrapper

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add `gtfs` i18n section
- `cms/apps/web/messages/en.json` — Add `gtfs` i18n section
- `cms/apps/web/src/components/app-sidebar.tsx` — Enable GTFS nav item

### Files to Create
- `cms/apps/web/src/app/[locale]/(dashboard)/gtfs/page.tsx` — Main GTFS page
- `cms/apps/web/src/components/gtfs/data-overview.tsx` — Stats + feeds component
- `cms/apps/web/src/components/gtfs/gtfs-export.tsx` — Export component
- `cms/apps/web/src/lib/gtfs-client.ts` — GTFS-specific API functions
- `cms/apps/web/src/types/gtfs.ts` — GTFS page types

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Common violations and their fixes:

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400`, `text-slate-400` | `text-foreground-subtle` |
| `text-white` (on colored bg) | `text-interactive-foreground` / `text-primary-foreground` |
| `text-blue-*`, `text-red-*`, `text-green-*` | `text-primary`, `text-error`, `text-success` |
| `bg-blue-600`, `bg-blue-500` | `bg-primary` or `bg-interactive` |
| `bg-red-500`, `bg-red-600` | `bg-destructive` |
| `bg-green-500`, `bg-emerald-500` | `bg-success` or `bg-status-ontime` |
| `bg-gray-100`, `bg-slate-100` | `bg-surface` / `bg-muted` |
| `border-gray-200` | `border-border` |

**Full semantic token reference** — check `cms/packages/ui/src/tokens.css`:
- **Surface**: `bg-surface`, `bg-surface-raised`, `bg-background`
- **Interactive**: `bg-interactive`, `text-interactive`, `text-interactive-foreground`
- **Status**: `text-status-ontime`, `text-status-delayed`, `text-status-critical`

Exception: Inline HTML strings (e.g., Leaflet `L.divIcon`) may use hex colors. GTFS route color data values are also acceptable.

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first
- **Session gate pattern** — All `useEffect` data fetches must guard on `status === "authenticated"` before calling API

See `cms/apps/web/CLAUDE.md` → "React 19 Anti-Patterns" for full examples.

## TypeScript Security Rules

- **Never use `as` casts on JWT token claims without runtime validation**
- **Clear `.next` cache when module resolution errors persist after fixing imports** — `rm -rf cms/apps/web/.next`

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

---

### Task 1: Types
**File:** `cms/apps/web/src/types/gtfs.ts` (create)
**Action:** CREATE

Create type definitions for the GTFS page:

```typescript
/** GTFS data statistics — aggregate counts from multiple endpoints */
export interface GTFSStats {
  agencies: number;
  routes: number;
  calendars: number;
  trips: number;
  stops: number;
}

/** GTFS-RT feed configuration from /api/v1/transit/feeds */
export interface GTFSFeed {
  feed_id: string;
  operator_name: string;
  enabled: boolean;
  poll_interval_seconds: number;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: API Client
**File:** `cms/apps/web/src/lib/gtfs-client.ts` (create)
**Action:** CREATE

Create GTFS-specific API client functions. Follow the pattern from `schedules-client.ts` for error handling and `documents-client.ts` for blob downloads.

```typescript
/**
 * VTV GTFS API Client
 *
 * Functions specific to the GTFS Data Management page:
 * stats aggregation, feed status, and GTFS ZIP export.
 */

import { authFetch } from "@/lib/auth-fetch";
import { fetchAgencies } from "@/lib/schedules-client";
import type { GTFSStats, GTFSFeed } from "@/types/gtfs";
import type { PaginatedResponse } from "@/types/schedule";
import type { Route } from "@/types/route";
import type { Stop } from "@/types/stop";

const BASE_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

/** Error thrown when a GTFS API request fails. */
export class GTFSApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "GTFSApiError";
    this.status = status;
  }
}

/** Fetch aggregate GTFS data statistics by calling multiple endpoints in parallel. */
export async function fetchGTFSStats(): Promise<GTFSStats> {
  const [agencies, routesRes, calendarsRes, tripsRes, stopsRes] =
    await Promise.all([
      fetchAgencies(),
      authFetch(
        `${BASE_URL}/api/v1/schedules/routes?page=1&page_size=1`
      ).then((r) => r.json() as Promise<PaginatedResponse<Route>>),
      authFetch(
        `${BASE_URL}/api/v1/schedules/calendars?page=1&page_size=1`
      ).then((r) => r.json() as Promise<PaginatedResponse<unknown>>),
      authFetch(
        `${BASE_URL}/api/v1/schedules/trips?page=1&page_size=1`
      ).then((r) => r.json() as Promise<PaginatedResponse<unknown>>),
      authFetch(
        `${BASE_URL}/api/v1/stops/?page=1&page_size=1`
      ).then((r) => r.json() as Promise<PaginatedResponse<Stop>>),
    ]);

  return {
    agencies: agencies.length,
    routes: routesRes.total,
    calendars: calendarsRes.total,
    trips: tripsRes.total,
    stops: stopsRes.total,
  };
}

/** Fetch GTFS-RT feed configuration from the transit API. */
export async function fetchFeeds(): Promise<GTFSFeed[]> {
  const response = await authFetch(`${BASE_URL}/api/v1/transit/feeds`);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }
  return response.json() as Promise<GTFSFeed[]>;
}

/** Export GTFS data as a ZIP file. Triggers a browser download. */
export async function exportGTFS(agencyId?: number): Promise<void> {
  const params = new URLSearchParams();
  if (agencyId !== undefined) {
    params.set("agency_id", String(agencyId));
  }
  const url = `${BASE_URL}/api/v1/schedules/export${params.toString() ? `?${params.toString()}` : ""}`;

  const response = await authFetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = "gtfs.zip";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(downloadUrl);
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 3: Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add the `gtfs` section AFTER the existing `drivers` section (before the closing `}`). Use the exact keys from the i18n Keys section above.

**Per-task validation:**
- Verify JSON is valid (no trailing commas, properly nested)

---

### Task 4: English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add the `gtfs` section AFTER the existing `drivers` section (before the closing `}`). Use the exact keys from the i18n Keys section above. Ensure key structure matches `lv.json` exactly.

**Per-task validation:**
- Verify JSON is valid
- Verify key structure matches `lv.json`

---

### Task 5: DataOverview Component
**File:** `cms/apps/web/src/components/gtfs/data-overview.tsx` (create)
**Action:** CREATE

Create a component showing GTFS data statistics as cards and GTFS-RT feed status.

**Layout:**
- Top section: 5 stat cards in a responsive grid (`grid-cols-2 sm:grid-cols-3 lg:grid-cols-5`)
- Bottom section: Feed list with status indicators

**Component structure:**
```
DataOverview (props: { stats, feeds, isLoading, onRefresh })
  -> StatCard (module-scope helper, NOT inside DataOverview)
  -> FeedCard (module-scope helper, NOT inside DataOverview)
```

**CRITICAL:** Define `StatCard` and `FeedCard` as **module-scope functions** outside `DataOverview`. React 19 lint forbids component definitions inside other components.

**Implementation details:**

```typescript
"use client";

import { useTranslations } from "next-intl";
import { Database, MapPin, Calendar, Route, Building2, Radio, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { GTFSStats, GTFSFeed } from "@/types/gtfs";

// ... (import cn from lib/utils)
```

StatCard: Use `rounded-lg border border-border p-(--spacing-card)` container. Display icon + count + label. Count in `text-2xl font-bold font-heading`. Label in `text-xs text-foreground-muted`.

FeedCard: Use `rounded-lg border border-border p-(--spacing-card) flex items-center justify-between`. Show feed_id + operator_name on left. Status badge on right: `text-status-ontime` for enabled, `text-foreground-muted` for disabled. Poll interval in `text-xs text-foreground-muted`.

**Skeleton states:** When `isLoading` is true, render 5 `Skeleton` rectangles for stats and 1 for feeds.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: GTFSExport Component
**File:** `cms/apps/web/src/components/gtfs/gtfs-export.tsx` (create)
**Action:** CREATE

Create a component for downloading GTFS data as a ZIP file with optional agency filtering.

**Props:**
```typescript
interface GTFSExportProps {
  agencies: Array<{ id: number; agency_name: string }>;
}
```

**Layout:**
- Title + description text
- Agency filter dropdown (`Select` component with "All Agencies" default)
- Download button (full width)
- Info note listing included files

**Implementation details:**
- State: `selectedAgency: number | null`, `isDownloading: boolean`
- On download click: call `exportGTFS(selectedAgency ?? undefined)` from `gtfs-client.ts`
- Show `toast.success` on success, `toast.error` on failure
- Button disabled while downloading, text changes to "Downloading..."
- Uses `Download` icon from lucide-react on the button
- The info note about included files uses `text-xs text-foreground-muted`

**Semantic tokens only:**
- Container: `space-y-(--spacing-card) p-(--spacing-card)`
- Section headings: `text-sm font-semibold text-foreground`
- Description: `text-xs text-foreground-muted`
- Select border: `border-border`
- Button: default variant (primary), `cursor-pointer`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: GTFS Page Component
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/gtfs/page.tsx` (create)
**Action:** CREATE

Create the main GTFS page following the Schedules page pattern (tabbed layout with session gate).

**Component: `GTFSPage` (default export)**

**State:**
```typescript
const t = useTranslations("gtfs");
const { status } = useSession();

const [stats, setStats] = useState<GTFSStats | null>(null);
const [feeds, setFeeds] = useState<GTFSFeed[]>([]);
const [agencies, setAgencies] = useState<Agency[]>([]);
const [isLoading, setIsLoading] = useState(true);
```

**Data loading:**
- `loadData` callback: calls `fetchGTFSStats()`, `fetchFeeds()`, `fetchAgencies()` in parallel via `Promise.all`
- `useEffect` gated on `status === "authenticated"` (session gate pattern)
- On error: set empty defaults, log warning to console

**Layout:**
```
<div className="flex h-[calc(100vh-var(--spacing-page)*2)] flex-col gap-(--spacing-grid)">
  {/* Header */}
  <div>
    <h1 className="font-heading text-heading font-semibold text-foreground">{t("title")}</h1>
    <p className="hidden sm:block text-sm text-foreground-muted">{t("description")}</p>
  </div>

  {/* Tabs */}
  <Tabs defaultValue="overview" className="flex min-h-0 flex-1 flex-col">
    <TabsList>
      <TabsTrigger value="overview">{t("tabs.overview")}</TabsTrigger>
      <TabsTrigger value="import">{t("tabs.import")}</TabsTrigger>
      <TabsTrigger value="export">{t("tabs.export")}</TabsTrigger>
    </TabsList>

    <TabsContent value="overview" ...>
      <DataOverview stats={stats} feeds={feeds} isLoading={isLoading} onRefresh={loadData} />
    </TabsContent>

    <TabsContent value="import" ...>
      <GTFSImport onImportComplete={handleImportComplete} />
    </TabsContent>

    <TabsContent value="export" ...>
      <GTFSExport agencies={agencies} />
    </TabsContent>
  </Tabs>
</div>
```

**`handleImportComplete` callback:** Calls `loadData()` to refresh stats after import.

**Imports:**
```typescript
"use client";
import { useState, useCallback, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataOverview } from "@/components/gtfs/data-overview";
import { GTFSExport } from "@/components/gtfs/gtfs-export";
import { GTFSImport } from "@/components/schedules/gtfs-import";
import { fetchGTFSStats, fetchFeeds } from "@/lib/gtfs-client";
import { fetchAgencies } from "@/lib/schedules-client";
import type { GTFSStats, GTFSFeed } from "@/types/gtfs";
import type { Agency } from "@/types/schedule";
```

**TabsContent styling:** Each tab content uses `className="flex-1 overflow-auto rounded-lg border border-border mt-(--spacing-tight)"` — matching the Schedules page pattern.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 8: Enable Sidebar Nav
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify)
**Action:** UPDATE

Change the `gtfs` entry in the `navItems` array from `enabled: false` to `enabled: true`:

```typescript
// BEFORE:
{ key: "gtfs", href: "/gtfs", enabled: false },

// AFTER:
{ key: "gtfs", href: "/gtfs", enabled: true },
```

That is the ONLY change in this file. Do not modify any other nav items or component logic.

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

- [ ] Page renders at `/lv/gtfs` and `/en/gtfs`
- [ ] i18n keys present in both `lv.json` and `en.json` under `gtfs.*`
- [ ] Sidebar shows "GTFS" as an enabled, clickable link
- [ ] Middleware already handles `/gtfs` route (admin + editor only)
- [ ] Overview tab shows 5 stat cards and feed status
- [ ] Import tab shows GTFSImport component (drag-and-drop ZIP upload + validation)
- [ ] Export tab shows agency filter + download button
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] Accessibility: all interactive elements have labels, focus states visible
- [ ] Session gate: data loads only after `status === "authenticated"`

## Security Checklist

- [x] Redirects preserve user's current locale (handled by existing middleware)
- [x] No hardcoded credentials
- [x] Auth tokens via httpOnly cookies (Auth.js, no localStorage)
- [x] File uploads validate type AND size client-side (GTFSImport already does this — 100MB max, .zip only)
- [x] No `dangerouslySetInnerHTML`
- [x] User input displayed via React JSX (auto-escaped)
- [ ] Export download uses `authFetch` with Bearer token (not unauthenticated fetch)
- [ ] Blob URL created with `URL.createObjectURL` and revoked with `URL.revokeObjectURL` after download

## Acceptance Criteria

This feature is complete when:
- [ ] Page accessible at `/lv/gtfs` and `/en/gtfs`
- [ ] RBAC enforced — only admin and editor roles can access (dispatcher and viewer get redirected)
- [ ] Both languages have complete translations
- [ ] Design system rules followed (MASTER.md, semantic tokens only)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages (Schedules page still works, GTFSImport component reused without modification)
- [ ] Ready for `/commit`
