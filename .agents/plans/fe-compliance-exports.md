# Plan: EU Compliance Exports on GTFS Page

## Feature Metadata
**Feature Type**: Enhancement (new tab on existing GTFS page)
**Estimated Complexity**: Medium
**Route**: `/[locale]/(dashboard)/gtfs` (existing — adding 4th tab)
**Auth Required**: Yes
**Allowed Roles**: admin, editor (same as existing GTFS page)

## Feature Description

The backend already exposes 4 EU compliance endpoints (`/api/v1/compliance/*`) for NeTEx XML export, SIRI Vehicle Monitoring, SIRI Stop Monitoring, and export status metadata. However, there is no frontend UI to access these — operators must use the API directly.

This enhancement adds a "Compliance" tab to the existing GTFS Data Management page. The tab provides three download cards (NeTEx XML, SIRI-VM XML, SIRI-SM XML) with relevant filters (agency for NeTEx, route/feed for SIRI-VM, stop name/feed for SIRI-SM), a status section showing entity counts and metadata from the `/compliance/status` endpoint, and toast notifications for download success/failure.

The design follows the same patterns as the existing "Export" tab (agency filter + download button + info note) but extends it with three distinct export formats, each with their own parameters. All downloads trigger browser file saves using the same `authFetch` + blob pattern used by `exportGTFS()`.

## Design System

### Master Rules (from MASTER.md)
- Border radius: 0 (sharp corners on all components)
- Typography: Lexend headings, Source Sans 3 body
- Spacing: dashboard-density tokens (`--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight`)
- Colors: semantic tokens only, no Tailwind primitives
- Transitions: 150-300ms on interactive elements
- Touch targets: 44x44px minimum
- Cursor: `cursor-pointer` on all clickable elements

### Page Override
- None — no page override exists in `design-system/vtv/pages/`. The GTFS page follows MASTER.md rules.

### Tokens Used
- `--spacing-card` (12px) — card internal padding
- `--spacing-grid` (12px) — gap between cards
- `--spacing-inline` (6px) — icon-to-text gap
- `--spacing-tight` (4px) — micro gaps (badges, labels)
- `text-foreground` — primary text
- `text-foreground-muted` — labels, descriptions
- `text-foreground-subtle` — tertiary text
- `bg-surface` — card backgrounds
- `border-border` — card borders
- `text-status-ontime` — success state (export complete)
- `text-status-delayed` — in-progress state
- `text-error` — error state
- `bg-interactive` — primary download buttons
- `text-interactive-foreground` — button text on interactive bg

## Components Needed

### Existing (shadcn/ui — already installed)
- `Button` — download actions
- `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue` — agency/feed filters
- `Input` — stop name text input (for SIRI-SM)
- `Label` — form field labels
- `Badge` — format version badges
- `Separator` — visual dividers between sections
- `Skeleton` — loading state for status section
- `Card`, `CardContent`, `CardHeader`, `CardTitle` — export format cards (already installed but verify usage)

### New shadcn/ui to Install
- None — all needed components are already installed

### Custom Components to Create
- `ComplianceExports` at `cms/apps/web/src/components/gtfs/compliance-exports.tsx` — main compliance tab content with three export cards and status section

## i18n Keys

### Latvian (`lv.json`)
```json
{
  "gtfs": {
    "tabs": {
      "compliance": "Atbilstiba"
    },
    "compliance": {
      "title": "ES atbilstibas eksporti",
      "description": "Lejupieladet NeTEx un SIRI formata datus atbilstosi ES regulam",
      "netex": {
        "title": "NeTEx XML",
        "description": "Pilns marsrutu un sarakstu eksports NeTEx EPIP 1.2 formata",
        "agencyFilter": "Agentura",
        "allAgencies": "Visas agenturas",
        "downloadButton": "Lejupieladet NeTEx XML",
        "downloading": "Lejupladet...",
        "downloadSuccess": "NeTEx dati veiksmigi lejupieladeti",
        "downloadError": "Neizdevas lejupieladet NeTEx datus",
        "includesNote": "Ietver: marsrutus, grafikus, braucienus, pieturas un operatorus NeTEx EPIP 1.2 formata"
      },
      "siriVm": {
        "title": "SIRI-VM XML",
        "description": "Reala laika transportlidzeklu poziciju dati SIRI 2.0 formata",
        "routeFilter": "Marsruts (neobligats)",
        "routePlaceholder": "Piem., 1, 22, tram_5",
        "feedFilter": "Datu avots (neobligats)",
        "feedPlaceholder": "Piem., riga_buses",
        "downloadButton": "Lejupieladet SIRI-VM XML",
        "downloading": "Lejupladet...",
        "downloadSuccess": "SIRI-VM dati veiksmigi lejupieladeti",
        "downloadError": "Neizdevas lejupieladet SIRI-VM datus"
      },
      "siriSm": {
        "title": "SIRI-SM XML",
        "description": "Pieturu uzraudzibas dati SIRI 2.0 formata",
        "stopName": "Pieturas nosaukums",
        "stopPlaceholder": "Piem., Centraltirgus",
        "feedFilter": "Datu avots (neobligats)",
        "feedPlaceholder": "Piem., riga_buses",
        "downloadButton": "Lejupieladet SIRI-SM XML",
        "downloading": "Lejupladet...",
        "downloadSuccess": "SIRI-SM dati veiksmigi lejupieladeti",
        "downloadError": "Neizdevas lejupieladet SIRI-SM datus",
        "stopRequired": "Pieturas nosaukums ir obligats"
      },
      "status": {
        "title": "Eksporta statuss",
        "format": "Formats",
        "version": "Versija",
        "codespace": "Koda telpa",
        "generatedAt": "Generets",
        "entities": "Entitijas",
        "agencies": "Agenturas",
        "routes": "Marsruti",
        "trips": "Braucieni",
        "stops": "Pieturas",
        "loadError": "Neizdevas ieladet eksporta statusu"
      }
    }
  }
}
```

### English (`en.json`)
```json
{
  "gtfs": {
    "tabs": {
      "compliance": "Compliance"
    },
    "compliance": {
      "title": "EU Compliance Exports",
      "description": "Download NeTEx and SIRI format data compliant with EU regulations",
      "netex": {
        "title": "NeTEx XML",
        "description": "Full routes and schedules export in NeTEx EPIP 1.2 format",
        "agencyFilter": "Agency",
        "allAgencies": "All Agencies",
        "downloadButton": "Download NeTEx XML",
        "downloading": "Downloading...",
        "downloadSuccess": "NeTEx data downloaded successfully",
        "downloadError": "Failed to download NeTEx data",
        "includesNote": "Includes: routes, schedules, trips, stops, and operators in NeTEx EPIP 1.2 format"
      },
      "siriVm": {
        "title": "SIRI-VM XML",
        "description": "Real-time vehicle position data in SIRI 2.0 format",
        "routeFilter": "Route (optional)",
        "routePlaceholder": "e.g., 1, 22, tram_5",
        "feedFilter": "Feed (optional)",
        "feedPlaceholder": "e.g., riga_buses",
        "downloadButton": "Download SIRI-VM XML",
        "downloading": "Downloading...",
        "downloadSuccess": "SIRI-VM data downloaded successfully",
        "downloadError": "Failed to download SIRI-VM data"
      },
      "siriSm": {
        "title": "SIRI-SM XML",
        "description": "Stop monitoring data in SIRI 2.0 format",
        "stopName": "Stop Name",
        "stopPlaceholder": "e.g., Centraltirgus",
        "feedFilter": "Feed (optional)",
        "feedPlaceholder": "e.g., riga_buses",
        "downloadButton": "Download SIRI-SM XML",
        "downloading": "Downloading...",
        "downloadSuccess": "SIRI-SM data downloaded successfully",
        "downloadError": "Failed to download SIRI-SM data",
        "stopRequired": "Stop name is required"
      },
      "status": {
        "title": "Export Status",
        "format": "Format",
        "version": "Version",
        "codespace": "Codespace",
        "generatedAt": "Generated",
        "entities": "Entities",
        "agencies": "Agencies",
        "routes": "Routes",
        "trips": "Trips",
        "stops": "Stops",
        "loadError": "Failed to load export status"
      }
    }
  }
}
```

## Data Fetching

### API Endpoints (direct authFetch — compliance not yet in SDK)
The compliance endpoints are NOT in the generated `@vtv/sdk` OpenAPI spec. Use `authFetch` directly (same pattern as existing `exportGTFS()` in `gtfs-sdk.ts`).

| Endpoint | Method | Params | Response | Usage |
|----------|--------|--------|----------|-------|
| `/api/v1/compliance/netex` | GET | `agency_id?: number` | Binary XML | NeTEx download |
| `/api/v1/compliance/siri/vm` | GET | `route_id?: string`, `feed_id?: string` | Binary XML | SIRI-VM download |
| `/api/v1/compliance/siri/sm` | GET | `stop_name: string` (required), `feed_id?: string` | Binary XML | SIRI-SM download |
| `/api/v1/compliance/status` | GET | None | JSON `ExportMetadata` | Status display |

### ExportMetadata Response Shape
```typescript
interface ExportMetadata {
  format: "NeTEx" | "SIRI-VM" | "SIRI-SM";
  version: string;        // "1.2" for NeTEx, "2.0" for SIRI
  codespace: string;      // NeTEx codespace prefix
  generated_at: string;   // ISO 8601 timestamp
  entity_counts: {
    agencies: number;
    routes: number;
    trips: number;
    stops: number;
  };
}
```

### Server vs Client
- All compliance fetching is client-side (`"use client"` component) — user-initiated downloads
- Status endpoint loaded on tab mount (client-side, gated on session auth)
- Downloads use `authFetch` → blob → browser download (same pattern as `exportGTFS`)

### BASE_URL Pattern
```typescript
const BASE_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
```
This is the established pattern from `gtfs-sdk.ts` line 15-16.

## RBAC Integration

No changes needed — the GTFS page route (`/gtfs`) is already in the middleware matcher with access for `admin` and `editor` roles. The compliance tab lives within the existing GTFS page, inheriting its RBAC.

## Sidebar Navigation

No changes needed — the GTFS nav entry already exists in `app-sidebar.tsx`. The compliance feature is a new tab within the existing page, not a new route.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/gtfs/gtfs-export.tsx` (106 lines) — **PRIMARY PATTERN**: Download card with Select filter, Button, toast notifications, `authFetch` blob download. Copy this pattern exactly for each compliance export card.
- `cms/apps/web/src/lib/gtfs-sdk.ts` (87 lines) — **SDK PATTERN**: `exportGTFS()` function showing authFetch → blob → createObjectURL → anchor click → cleanup. Reuse for compliance downloads.
- `cms/apps/web/src/app/[locale]/(dashboard)/gtfs/page.tsx` (111 lines) — **PAGE PATTERN**: Tab structure, session gate, data loading. Will be modified to add 4th tab.
- `cms/apps/web/src/components/gtfs/data-overview.tsx` (185 lines) — StatCard pattern for status display.

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add compliance i18n keys under `gtfs` section
- `cms/apps/web/messages/en.json` — Add compliance i18n keys under `gtfs` section
- `cms/apps/web/src/app/[locale]/(dashboard)/gtfs/page.tsx` — Add 4th tab trigger + content
- `cms/apps/web/src/lib/gtfs-sdk.ts` — Add compliance export/status functions
- `cms/apps/web/src/types/gtfs.ts` — Add ExportMetadata type

### Files to Create
- `cms/apps/web/src/components/gtfs/compliance-exports.tsx` — Compliance tab component

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping table and forbidden class list are loaded via `@_shared/tailwind-token-map.md`. Key rules:
- Use the mapping table for all color decisions
- Check `cms/packages/ui/src/tokens.css` for available tokens
- Exception: Inline HTML strings (Leaflet) may use hex colors. GTFS route color data values are acceptable.

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first in the component body. TypeScript enforces block-scoped variable ordering (TS2448/TS2454). Plan tasks must respect declaration order.
- **Shared type changes require ripple-effect tasks** — When adding a field to a shared interface (e.g., `BusPosition`), the plan MUST include tasks to update ALL files that construct objects of that type (mock data files, test factories, etc.). Search for all usages with `Grep` before finalizing the plan.

See `cms/apps/web/CLAUDE.md` → "React 19 Anti-Patterns" for full examples.

## TypeScript Security Rules

- **Never use `as` casts on JWT token claims without runtime validation** — JWT payloads are untrusted input.
- **Clear `.next` cache when module resolution errors persist after fixing imports** — `rm -rf cms/apps/web/.next` and restart dev server.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

### Task 1: Add ExportMetadata Type
**File:** `cms/apps/web/src/types/gtfs.ts` (modify)
**Action:** UPDATE

Add the `ExportMetadata` interface after the existing `GTFSFeed` interface:

```typescript
/** EU compliance export metadata from /api/v1/compliance/status */
export interface ExportMetadata {
  format: "NeTEx" | "SIRI-VM" | "SIRI-SM";
  version: string;
  codespace: string;
  generated_at: string;
  entity_counts: {
    agencies: number;
    routes: number;
    trips: number;
    stops: number;
  };
}
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 2: Add Compliance SDK Functions
**File:** `cms/apps/web/src/lib/gtfs-sdk.ts` (modify)
**Action:** UPDATE

Read the existing file first. Add the `ExportMetadata` type import and 4 new functions at the end of the file. Follow the exact same pattern as `exportGTFS()` for binary downloads.

Add import at top (update existing type import line):
```typescript
import type { GTFSStats, GTFSFeed, ExportMetadata } from "@/types/gtfs";
```

Add these functions after `exportGTFS()`:

```typescript
/** Download NeTEx XML export. Triggers a browser download. */
export async function exportNeTEx(agencyId?: number): Promise<void> {
  const params = new URLSearchParams();
  if (agencyId !== undefined) {
    params.set("agency_id", String(agencyId));
  }
  const query = params.toString();
  const url = `${BASE_URL}/api/v1/compliance/netex${query ? `?${query}` : ""}`;

  const response = await authFetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = "netex-export.xml";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(downloadUrl);
}

/** Download SIRI Vehicle Monitoring XML. Triggers a browser download. */
export async function exportSiriVM(routeId?: string, feedId?: string): Promise<void> {
  const params = new URLSearchParams();
  if (routeId) params.set("route_id", routeId);
  if (feedId) params.set("feed_id", feedId);
  const query = params.toString();
  const url = `${BASE_URL}/api/v1/compliance/siri/vm${query ? `?${query}` : ""}`;

  const response = await authFetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = "siri-vm.xml";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(downloadUrl);
}

/** Download SIRI Stop Monitoring XML. Triggers a browser download. */
export async function exportSiriSM(stopName: string, feedId?: string): Promise<void> {
  const params = new URLSearchParams();
  params.set("stop_name", stopName);
  if (feedId) params.set("feed_id", feedId);
  const query = params.toString();
  const url = `${BASE_URL}/api/v1/compliance/siri/sm?${query}`;

  const response = await authFetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }

  const blob = await response.blob();
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = "siri-sm.xml";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(downloadUrl);
}

/** Fetch compliance export status metadata. */
export async function fetchComplianceStatus(): Promise<ExportMetadata> {
  const url = `${BASE_URL}/api/v1/compliance/status`;
  const response = await authFetch(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new GTFSApiError(response.status, detail);
  }
  return response.json() as Promise<ExportMetadata>;
}
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 3: Add Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Read the file first. Locate the existing `"gtfs"` section. Inside `"gtfs"."tabs"`, add:
```json
"compliance": "Atbilstiba"
```

After the existing `"export"` block (but still inside `"gtfs"`), add the full `"compliance"` block as specified in the i18n Keys section above.

**Per-task validation:**
- Verify JSON is valid: `cd cms/apps/web && node -e "JSON.parse(require('fs').readFileSync('messages/lv.json','utf8'))"`

---

### Task 4: Add English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Read the file first. Same structure as Task 3 but with English values as specified in the i18n Keys section above.

**Per-task validation:**
- Verify JSON is valid: `cd cms/apps/web && node -e "JSON.parse(require('fs').readFileSync('messages/en.json','utf8'))"`

---

### Task 5: Create ComplianceExports Component
**File:** `cms/apps/web/src/components/gtfs/compliance-exports.tsx` (create)
**Action:** CREATE

Create the main compliance tab component. This is the most complex task. Follow the `gtfs-export.tsx` pattern closely.

**Component structure:**

```
ComplianceExports (client component)
  Props: { agencies: Array<{ id: number; agency_name: string }> }

  State:
    - netexAgency: string (default "all")
    - siriVmRoute: string (default "")
    - siriVmFeed: string (default "")
    - siriSmStop: string (default "")
    - siriSmFeed: string (default "")
    - downloadingNetex: boolean
    - downloadingSiriVm: boolean
    - downloadingSiriSm: boolean
    - status: ExportMetadata | null
    - statusLoading: boolean

  Effects:
    - On mount: fetch compliance status via fetchComplianceStatus()

  Layout (vertical stack with spacing-grid gap):
    1. Header: title + description
    2. Three export cards in a responsive grid (1 col mobile, 3 col lg):
       a. NeTEx Card: agency Select filter + download button + includes note
       b. SIRI-VM Card: route Input (optional) + feed Input (optional) + download button
       c. SIRI-SM Card: stop name Input (required) + feed Input (optional) + download button
    3. Separator
    4. Status section: format badge, version, codespace, generated_at, entity counts grid
```

**Key implementation details:**

- `"use client"` directive at top
- Import `useTranslations("gtfs.compliance")` — all text via `t()`
- Each download handler follows the `handleDownload` pattern from `gtfs-export.tsx`:
  - Set downloading state → call SDK function → toast.success → catch → toast.error → finally reset state
- SIRI-SM download must validate stop name is non-empty before calling API (show `toast.error(t("siriSm.stopRequired"))` if empty)
- Use `useCallback` for all three download handlers
- Sub-components (`ExportCard` wrapping each format) should be defined at **module scope** (React 19 rule — no component definitions inside components)
- Status section shows a `Skeleton` while loading, then the metadata once loaded
- Entity counts displayed as a 2x2 or 4-col grid of small stat items (label + count)
- All interactive elements have `cursor-pointer`
- All icons use `aria-hidden="true"`
- Form labels use `<Label>` with proper `htmlFor` linking
- Use semantic tokens: `text-foreground`, `text-foreground-muted`, `bg-surface`, `border-border`
- Badge for format version: `<Badge variant="outline">{status.version}</Badge>`

**Module-scope sub-components to extract:**

1. `StatusSection` — receives `status: ExportMetadata | null` and `isLoading: boolean`, renders the status metadata display
2. Keep the three export cards inline (they're simple enough and share parent state via callbacks)

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 6: Add Compliance Tab to GTFS Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/gtfs/page.tsx` (modify)
**Action:** UPDATE

Read the file first. Make these changes:

1. Add import at top:
```typescript
import { ComplianceExports } from "@/components/gtfs/compliance-exports";
```

2. Add a 4th `TabsTrigger` after the "export" trigger:
```tsx
<TabsTrigger value="compliance">{t("tabs.compliance")}</TabsTrigger>
```

3. Add a 4th `TabsContent` after the "export" content:
```tsx
<TabsContent value="compliance" className="flex-1 overflow-y-auto">
  <ComplianceExports agencies={agencies} />
</TabsContent>
```

No other changes needed — the `agencies` prop is already loaded in the page's `loadData()` function.

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

- [ ] Compliance tab renders on GTFS page when clicked
- [ ] i18n keys present in both lv.json and en.json (all nested keys under `gtfs.compliance`)
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] No hardcoded user-visible strings — all text via `useTranslations()`
- [ ] Accessibility: all inputs have labels, icons have `aria-hidden`, buttons have text content
- [ ] NeTEx download triggers with optional agency filter
- [ ] SIRI-VM download triggers with optional route and feed filters
- [ ] SIRI-SM download validates stop name is required, triggers with feed filter
- [ ] Status section loads and displays export metadata
- [ ] Toast notifications on download success and failure
- [ ] Loading/disabled states on download buttons during download
- [ ] Design tokens from tokens.css used (not arbitrary Tailwind values)
- [ ] No `rounded-*` classes (sharp corners per MASTER.md)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Sub-components defined at module scope (not inside component body)

## Acceptance Criteria

This feature is complete when:
- [ ] Compliance tab accessible on the GTFS page at `/{locale}/gtfs`
- [ ] All three export formats download successfully (NeTEx, SIRI-VM, SIRI-SM)
- [ ] Export status metadata displays correctly
- [ ] Both languages have complete translations
- [ ] Design system rules followed (MASTER.md)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing GTFS tabs (overview, import, export)
- [ ] Ready for `/commit`

## Security Checklist

- [ ] No hardcoded API URLs — uses `NEXT_PUBLIC_AGENT_URL` env var with localhost fallback
- [ ] Auth tokens via `authFetch` (httpOnly cookies) — no localStorage
- [ ] No `dangerouslySetInnerHTML`
- [ ] File downloads use blob URL pattern (no direct URL exposure)
- [ ] User input (stop name) passed as URL query parameter (backend validates/sanitizes)
- [ ] No hardcoded credentials
