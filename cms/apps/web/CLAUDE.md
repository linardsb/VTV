# @vtv/web — Next.js CMS Application

Next.js 16 App Router application for VTV transit operations management.

## Tech Stack

- **Next.js 16.1.6** with App Router and React 19
- **Auth.js v5** (next-auth 5.0.0-beta.30) with 4-role RBAC: admin, dispatcher, editor, viewer
- **next-intl** for i18n — Latvian (`lv`) primary, English (`en`) secondary
- **Tailwind CSS v4** with three-tier design tokens
- **shadcn/ui** components with CVA variants

## Directory Layout

```
src/
├── app/[locale]/
│   ├── layout.tsx              # Root locale layout (server component, wraps AppSidebar)
│   ├── (dashboard)/
│   │   ├── page.tsx            # Dashboard (default authenticated page)
│   │   ├── documents/page.tsx  # Document management (upload, table, filters, detail)
│   │   ├── routes/page.tsx     # Route management (real API CRUD, server pagination, search, resizable map, multi-feed support: feed selector, per-feed marker colors, feed health overlay, auto-fit bounds; mobile: tab layout)
│   │   ├── schedules/page.tsx  # Schedule management (calendars with unified dialog + month grid, trips, GTFS import)
│   │   ├── stops/page.tsx      # Stop management (CRUD, Leaflet map with terminus markers, direction display, GTFS copy; mobile: tab layout)
│   │   ├── drivers/page.tsx    # Driver management (CRUD, search, shift/status filters, license tracking)
│   │   ├── gtfs/page.tsx       # GTFS data management (stats overview, RT feed status, ZIP export with agency filter)
│   │   ├── users/page.tsx      # User management (admin-only CRUD, role/status filters, search, reset-password)
│   │   └── {page}/page.tsx     # Future feature pages
│   ├── login/page.tsx          # Login (public)
│   └── unauthorized/page.tsx   # Unauthorized redirect
├── components/
│   ├── ui/                     # shadcn/ui components (button, table, dialog, tabs, switch, etc.)
│   ├── swr-provider.tsx        # Global SWR config (fetcher, dedup, retries, focus revalidation)
│   ├── theme-provider.tsx      # next-themes provider (class-based, system default, no transition flash)
│   ├── theme-toggle.tsx        # Light/Dark/System toggle (radiogroup, sidebar footer)
│   ├── app-sidebar.tsx         # Responsive sidebar (desktop: w-60 aside; mobile: hamburger + Sheet — only remaining Sheet usage)
│   ├── dashboard/              # Dashboard components (metric-card, calendar-grid, calendar-panel, dashboard-content, driver-roster, driver-drop-dialog, goals-form, goal-progress-badge, event-goal-panel, week-view, month-view, three-month-view, year-view, live-timeline)
│   ├── documents/              # Document management (table, filters, upload-form, detail, delete-dialog)
│   ├── routes/                 # Route management (table, filters, form, detail, type-badge, map, bus-marker, feed-health-overlay)
│   ├── schedules/              # Schedule management (calendar-table/dialog/form/detail/month-grid/search/status-badge, trip-table/form/detail/filters/search, gtfs-import, delete dialogs)
│   ├── stops/                  # Stop management (table, filters, form, detail, delete-dialog, map with draggable markers)
│   ├── drivers/                # Driver management (table, filters, form, detail, delete-dialog)
│   ├── users/                  # User management (table, filters, form, detail, delete-dialog, reset-password-dialog)
│   └── gtfs/                   # GTFS data management (data-overview stats+feeds, gtfs-export with agency filter)
├── hooks/
│   ├── use-mobile.ts           # useIsMobile() hook (768px breakpoint)
│   ├── use-vehicle-positions.ts # useVehiclePositions() — WebSocket primary (real-time push, ~100ms latency) with SWR HTTP polling fallback (10s refresh). Route + feed filtering via subscribe message, connection status tracking (live/polling/connecting)
│   ├── use-dashboard-metrics.ts # useDashboardMetrics() — SWR, 30s refresh (vehicles + routes)
│   ├── use-calendar-events.ts  # useCalendarEvents() — SWR via @vtv/sdk, 60s refresh (includes goals data)
│   └── use-drivers-summary.ts  # useDriversSummary() — SWR, 120s refresh (active drivers)
├── types/                      # TypeScript types (route.ts, schedule.ts, dashboard.ts, document.ts, stop.ts, driver.ts, event.ts, gtfs.ts, user.ts)
├── lib/
│   ├── auth-fetch.ts            # JWT-authenticated fetch wrapper (getToken with 60s cache, dual server/client context)
│   ├── swr-fetcher.ts          # SWR fetcher wrapping authFetch (shared across all SWR hooks)
│   ├── utils.ts                # cn() class merge utility
│   ├── sdk.ts                  # @vtv/sdk client configuration (base URL + JWT auth interceptor, side-effect import)
│   ├── agent-sdk.ts            # Agent SDK wrapper (chat streaming via @vtv/sdk)
│   ├── documents-sdk.ts        # Documents SDK wrapper (upload, list, delete, download via @vtv/sdk)
│   ├── drivers-sdk.ts          # Drivers SDK wrapper (CRUD, search, shift/status filters via @vtv/sdk)
│   ├── events-sdk.ts           # Events SDK wrapper (CRUD, driver_id filter via @vtv/sdk)
│   ├── gtfs-sdk.ts             # GTFS SDK wrapper (stats, feed status, ZIP export via @vtv/sdk)
│   ├── schedules-sdk.ts        # Schedules SDK wrapper (22 endpoints: agencies, routes, calendars, trips, import via @vtv/sdk)
│   ├── stops-sdk.ts            # Stops SDK wrapper (CRUD, nearby search via @vtv/sdk)
│   ├── users-sdk.ts            # Users SDK wrapper (admin-only CRUD, search, role/status filters via @vtv/sdk)
│   ├── color-utils.ts          # Hex color conversion (backend "FF7043" ↔ frontend "#FF7043")
│   ├── mock-bus-positions.ts   # Mock bus position data (dev fallback)
│   └── mock-dashboard-data.ts  # Mock dashboard metrics (calendar events now from real API)
└── i18n/
    └── request.ts              # next-intl configuration
```

## Adding a New Page

Use `/fe-create-page {name}` or manually:

1. Create `src/app/[locale]/(dashboard)/{name}/page.tsx` — server component with `useTranslations`
2. Add i18n keys to `messages/lv.json` and `messages/en.json`
3. Add sidebar nav link in `src/components/app-sidebar.tsx`
4. Add route matcher in `middleware.ts` with role permissions

## Key Files

- `middleware.ts` — RBAC route protection, role-based access control
- `messages/lv.json` / `en.json` — Translation strings
- `auth.ts` — Auth.js configuration, provider setup, login brute-force protection (5 attempts = 15min lockout)
- `next.config.ts` — Security headers (CSP, HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff)
- `src/app/[locale]/layout.tsx` — Root locale layout (server component)
- `src/components/app-sidebar.tsx` — Responsive sidebar navigation (desktop aside + mobile hamburger)

## Data Fetching Patterns

### SWR Hooks (Dashboard)

Dashboard data fetching uses SWR with a global `SWRProvider` (in root layout) and `swrFetcher` (wraps `authFetch`). Benefits: request deduplication, stale-while-revalidate, focus revalidation, automatic error retry.

```tsx
// SWR key is null when not authenticated (disables fetching)
const { data, error, isLoading } = useSWR<ApiResponse>(
  status === "authenticated" ? "/api/v1/endpoint" : null,
  { refreshInterval: 30_000 }
);
```

**Client-side token caching:** `getToken()` in `auth-fetch.ts` caches the JWT for 60s to avoid redundant `/api/auth/session` round trips. Both `authFetch` and the SDK client share this cache.

**Applied to:** `use-dashboard-metrics`, `use-calendar-events`, `use-vehicle-positions`, `use-drivers-summary`.

### Session Gate (Page-level)

Page-level data fetching that uses raw `useEffect` (not SWR) **must** gate on session status:

```tsx
const { data: session, status } = useSession();

useEffect(() => {
  if (status !== "authenticated") return;
  void loadData();
}, [loadData, status]);
```

**Applied to:** Routes, Stops, Schedules, Drivers, Documents pages.

## Conventions

- Use semantic tokens (`var(--color-surface-primary)`) not hardcoded colors
- **Never use Tailwind primitive color classes** — use semantic alternatives:
  - `text-gray-*` / `text-slate-*` → `text-foreground`, `text-foreground-muted`, `text-foreground-subtle`
  - `bg-blue-*` / `bg-red-*` / `bg-green-*` → `bg-primary`, `bg-destructive`, `bg-success`
  - `text-white` (on colored bg) → `text-primary-foreground`, `text-destructive-foreground`
  - `border-gray-*` → `border-border`
  - `bg-gray-*` → `bg-surface`, `bg-surface-secondary`, `bg-muted`
  - Check `cms/packages/ui/src/tokens.css` when unsure
- Server components by default; `'use client'` only for forms/interactivity
- All text via `useTranslations()` — never hardcode user-visible strings
- `cn()` from `lib/utils.ts` for conditional Tailwind class merging
- **Dialog for all modals** — All detail views, create/edit forms, and upload panels use centered `Dialog` (not side-sliding `Sheet`). Sheet is only used for the mobile sidebar. Dialog widths use explicit rem values: `sm:max-w-[28rem]` (detail), `sm:max-w-[32rem]` (forms, default), `sm:max-w-[36rem]` (wide content with tables)
- Accessibility: ARIA labels, alt text, skip links, focus management

## React 19 Anti-Patterns (MUST AVOID)

These patterns trigger lint errors under React 19 strict rules. Write correct code on the first pass:

1. **No `setState` inside `useEffect`** — `react-hooks/set-state-in-effect` forbids synchronous setState in effects. Instead of resetting form state in an effect, use the React `key` prop pattern to remount the component with fresh initial state.
   ```tsx
   // BAD — lint error
   useEffect(() => { setForm(initialData); }, [isOpen]);

   // GOOD — parent passes key to force remount
   <MyForm key={formKey} initialData={data} />
   ```

2. **No component definitions inside components** — `react-hooks/static-components` forbids defining components within render. Components declared inside another component are recreated every render, resetting their state. Move them outside or extract to separate files.
   ```tsx
   // BAD — lint error: "Cannot create components during render"
   function ParentComponent() {
     function ChildComponent({ text }: { text: string }) { return <p>{text}</p>; }
     return <ChildComponent text="hello" />;
   }

   // GOOD — defined outside
   function ChildComponent({ text }: { text: string }) { return <p>{text}</p>; }
   function ParentComponent() { return <ChildComponent text="hello" />; }
   ```

3. **No `Math.random()` in render** — React 19 purity rules forbid impure expressions during render. Generate random values outside render or use `useId()`.

4. **No named Tailwind container sizes** — In Tailwind v4, `max-w-sm`, `max-w-md`, `max-w-lg`, `max-w-xl`, `max-w-2xl` generate `max-width: var(--container-lg)` etc. The project's `@theme inline` block in `globals.css` does NOT define `--container-*` CSS variables (only `--container-3xl` is defined from shadcn). This causes elements to collapse to near-zero width. Always use explicit rem values:
   ```tsx
   // BAD — renders as ~50px wide (CSS variable undefined)
   className="sm:max-w-lg"

   // GOOD — explicit value that doesn't depend on CSS variables
   className="sm:max-w-[32rem]"
   ```
   **Size mapping:** `sm` = `24rem`, `md` = `28rem`, `lg` = `32rem`, `xl` = `36rem`, `2xl` = `42rem`, `3xl` = `48rem` (3xl works because it IS defined)

5. **No narrowing const literals for role checks** — TypeScript infers `const role = "admin"` as literal type `"admin"`, making `role === "viewer"` a TS2367 error. Use explicit `string` annotation when the value is a placeholder for runtime data:
   ```tsx
   // BAD — TS2367: comparison is unintentional
   const USER_ROLE = "admin";
   const readOnly = USER_ROLE === "viewer";

   // GOOD — annotate as string since it's a stand-in for runtime value
   const USER_ROLE: string = "admin";
   const readOnly = USER_ROLE === "viewer";
   ```

## E2E Testing (Playwright)

81 tests across 10 files in `e2e/` including CRUD flows for routes, stops, schedules, drivers, and documents. CRUD tests conditionally skip (`test.skip`) when prerequisites (e.g., create button, prerequisite data) are missing. Requires backend (port 8123) + frontend (port 3000) running. CI runs tests via GitHub Actions (`e2e-tests` job with docker-compose).

```bash
npx playwright test                    # All tests (headless)
npx playwright test e2e/routes.spec.ts # Single feature
npx playwright test -g "dashboard"     # By test name
npx playwright test --ui               # Interactive UI mode
```

**Test structure:**
- `e2e/auth.setup.ts` — Login + save session (runs before authenticated tests)
- `e2e/helpers.ts` — Shared test utilities (`waitForDataOrEmpty`, `hasDataTable`)
- `e2e/*.spec.ts` — Authenticated tests (dashboard, routes, stops, schedules, documents, drivers, navigation, smoke) including CRUD flows
- `e2e/*.noauth.spec.ts` — Unauthenticated tests (login form, redirects)
- `e2e/detect-changed.sh` — Auto-detects which features changed and runs only those tests

**Auto-detection:** `make e2e` uses `detect-changed.sh` to map git-changed source files → test files. Shared code changes (ui/, lib/, hooks/, messages/) run all tests.

**Adding tests for a new feature:** Create `e2e/{feature}.spec.ts`, add path mappings in `detect-changed.sh`.

## Security Practices

- **No hardcoded credentials** — demo passwords come from env vars, never in source code
- **Auth tokens via httpOnly cookies** — Auth.js handles token storage, never use localStorage for auth tokens
- **File uploads** — client-side size validation (50MB limit) before sending to backend
- **Security headers** — `next.config.ts` sets CSP, HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff
- **XSS prevention** — avoid `dangerouslySetInnerHTML`, sanitize user input before rendering
- **External links** — always use `rel="noopener noreferrer"` on `target="_blank"` links

## Zero-Warning Policy

**Lint must be fully clean** — zero errors AND zero warnings. Do not tolerate "pre-existing" lint issues.

- Before committing: `pnpm --filter @vtv/web lint` must exit 0 with no output
- If lint reports warnings in files you didn't touch, fix them anyway — broken windows accumulate
- Common traps to avoid:
  - Unused imports/variables after refactoring (remove them)
  - `Math.random()` in React render paths (React 19 purity rules forbid this)
  - Variables only used as types (use `type` keyword directly instead of `const ... as const`)
  - Hardcoded strings in components (must go through `useTranslations()`)
  - `setState` inside `useEffect` — use key-based remount instead (see anti-patterns above)
  - Component functions defined inside other components (see anti-patterns above)

<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 19, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #16350 | 8:56 PM | 🔵 | Frontend Environment Configuration Files Located | ~209 |
</claude-mem-context>
