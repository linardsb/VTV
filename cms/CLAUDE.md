# CMS Frontend Monorepo

Turborepo monorepo for the VTV transit operations CMS. Uses pnpm workspaces.

## Workspace Structure

```
cms/
├── apps/web/               # @vtv/web — Next.js 16 application (port 3000)
├── packages/ui/            # @vtv/ui — Design tokens (tokens.css) and shared UI exports
├── packages/sdk/           # @vtv/sdk — OpenAPI TypeScript client (generated from FastAPI)
├── packages/typescript-config/  # Shared tsconfig base and Next.js presets
├── design-system/vtv/      # Design system documentation (MASTER.md + page overrides)
├── turbo.json              # Turborepo pipeline configuration
├── pnpm-workspace.yaml     # Workspace definition
└── package.json            # Root scripts and workspace config
```

## Essential Commands

```bash
# Install all workspace dependencies
pnpm install

# Run commands scoped to the web app
pnpm --filter @vtv/web dev          # Dev server (port 3000)
pnpm --filter @vtv/web build        # Production build
pnpm --filter @vtv/web type-check   # TypeScript strict check
pnpm --filter @vtv/web lint         # ESLint

# E2E testing (Playwright — requires backend + frontend running)
pnpm --filter @vtv/web e2e          # Run all 81 tests (headless, CRUD tests conditionally skip)
pnpm --filter @vtv/web e2e:ui       # Interactive Playwright UI
pnpm --filter @vtv/web e2e:headed   # Visible browser
pnpm --filter @vtv/web e2e:report   # View HTML test report

# Generate SDK client (requires FastAPI running on port 8123)
pnpm --filter @vtv/sdk generate-sdk   # Regenerate from local openapi.json
pnpm --filter @vtv/sdk refresh        # Fetch fresh schema from backend + regenerate
```

## Design System

Three-tier token architecture in `packages/ui/src/tokens.css`:
- **Primitive tokens**: Raw values (`--color-blue-500`, `--spacing-4`)
- **Semantic tokens**: Contextual meaning (`--color-surface-primary`, `--color-text-secondary`)
- **Component tokens**: Component-specific (`--button-bg`, `--input-border`)
- **Dark mode**: `.dark` class overrides on semantic/component tokens. Managed by `next-themes` (class attribute, system default). Toggle in sidebar footer.

Design rules live in `design-system/vtv/MASTER.md`. Page-specific overrides go in `design-system/vtv/pages/{page}.md`.

## Frontend Slash Commands

| Command | Purpose |
|---------|---------|
| `/fe-prime` | Load frontend context into session |
| `/fe-planning` | Plan a frontend page/feature |
| `/fe-create-page` | Scaffold a new page |
| `/fe-execute` | Execute a frontend plan |
| `/fe-validate` | Run all frontend quality checks |
| `/e2e` | Run Playwright e2e tests (auto-detects changed features) |

Workflow: `/fe-prime` → `/fe-planning` → `/fe-execute` → `/fe-validate` → `/e2e` → `/commit`

## Implemented Pages

| Page | Route | Status | Data Source |
|------|-------|--------|-------------|
| Dashboard | `/[locale]/` | Live | Real API metrics (vehicles + routes, 30s polling) + real calendar events with goal tracking (`/api/v1/events`, 60s polling, goal progress badges, goal completion panel) |
| Routes | `/[locale]/routes` | Live | Backend `/api/v1/schedules/routes` (CRUD, server pagination, search) + GTFS-RT live vehicle positions (WebSocket real-time push with HTTP polling fallback) on Leaflet map. Multi-feed support: feed selector filter, per-feed marker border colors, feed health overlay with vehicle counts, auto-fit bounds on feed change |
| Stops | `/[locale]/stops` | Live | Backend `/api/v1/stops` endpoints (CRUD, Leaflet map with terminus markers, direction display, GTFS copy, location_type filtering) |
| Schedules | `/[locale]/schedules` | Live | Backend `/api/v1/schedules` (22 endpoints: calendars CRUD, trips CRUD, GTFS ZIP import, validation) |
| Drivers | `/[locale]/drivers` | Live | Backend `/api/v1/drivers` (5 endpoints: CRUD, search, shift/status filters, agent integration) |
| Vehicles | `/[locale]/vehicles` | Live | Backend `/api/v1/vehicles` (8 endpoints: fleet CRUD, maintenance tracking, driver assignment, search/filter by type/status) |
| GTFS | `/[locale]/gtfs` | Live | Backend `/api/v1/schedules` + `/api/v1/transit/feeds` + `/api/v1/compliance` (4 tabs: data overview stats, GTFS ZIP import, GTFS export with agency filter, EU compliance exports — NeTEx XML, SIRI-VM, SIRI-SM downloads with filters and export status) |
| Documents | `/[locale]/documents` | Live | Backend `/api/v1/knowledge` endpoints (upload, list, detail, delete, download) |
| Users | `/[locale]/users` | Live | Backend `/api/v1/auth/users` (admin-only CRUD, role/status filters, search, reset-password) |
| Fleet Devices | `/[locale]/fleet` | Live | Backend `/api/v1/fleet/devices` (CRUD, search, protocol/status filters, vehicle linking, IMEI validation) |
| Fleet Map | `/[locale]/fleet/map` | Live | Backend `/api/v1/fleet/positions` (Leaflet map with device markers, 15s auto-refresh, device list sidebar, connection status) |
| Telemetry | `/[locale]/fleet/telemetry` | Live | Backend `/api/v1/fleet/history` (6 Recharts gauges: speed, RPM, fuel, coolant, engine load, battery. Device selector, 1h/6h/24h time range) |
| Geofences | `/[locale]/geofences` | Live | Backend `/api/v1/geofences` (8 endpoints: CRUD, events, dwell reports. Split layout: table + polygon map. Click-to-place polygon editor, zone type colors, event history tab, dwell stats) |
| Chat | `/[locale]/chat` | Live | Agent `POST /v1/chat/completions` (streaming SSE, bilingual LV/EN, unified Pydantic AI agent with 11 tools) |
| Login | `/[locale]/login` | Live | Auth.js credentials → `POST /api/v1/auth/login` (DB-backed, bcrypt) |
| Unauthorized | `/[locale]/unauthorized` | Live | — |

## GTFS Data Sources (Rīgas Satiksme)

Import GTFS data to populate Routes, Schedules, and live vehicle tracking:

| Feed | URL | Format |
|------|-----|--------|
| Static schedules | `https://saraksti.rigassatiksme.lv/riga/gtfs.zip` | GTFS ZIP |
| Vehicle positions | `https://saraksti.rigassatiksme.lv/vehicle_positions.pb` | Protobuf |
| Trip updates | `https://saraksti.rigassatiksme.lv/trip_updates.pb` | Protobuf |
| Combined RT | `https://saraksti.rigassatiksme.lv/gtfs_realtime.pb` | Protobuf |

**Quick test:** `curl -o /tmp/gtfs.zip https://saraksti.rigassatiksme.lv/riga/gtfs.zip && curl -X POST http://localhost:8123/api/v1/schedules/import/gtfs -F "file=@/tmp/gtfs.zip"` — or upload via the Schedules page Import tab.

Official open data page: https://www.rigassatiksme.lv/en/about-us/publishable-information/open-data/

## Key Conventions

- **No hardcoded colors** — use semantic tokens from `tokens.css`
- **i18n required** — all user-visible text via `next-intl` (Latvian + English)
- **RBAC enforced** — middleware.ts controls route access by role
- **Server components default** — use `'use client'` only when needed
- **shadcn/ui components** — install from `npx shadcn@latest add [component]`
- **SWR for data fetching** — dashboard hooks use SWR with `swrFetcher` (wraps `authFetch`). Global `SWRProvider` in layout. Token cached 60s client-side via `getToken()` in `auth-fetch.ts`

## Security Practices

- **No hardcoded credentials** — demo passwords come from env vars (`DEMO_USER_PASSWORD`), never committed in source
- **Auth tokens** — stored via httpOnly cookies (Auth.js), never localStorage
- **File uploads** — client-side size validation (50MB limit) before upload
- **Security headers** — CSP, HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff configured in `next.config.ts`
- **XSS prevention** — no `dangerouslySetInnerHTML` without sanitization, external links use `rel="noopener noreferrer"`
- **Cookie attributes** — all cookies set with `SameSite=Lax` explicitly (not relying on browser defaults)
- **Locale-aware redirects** — auth middleware preserves user's current locale (not hardcoded `/lv/login`)

<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 21, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #16621 | 12:30 PM | 🔵 | Documentation Structure Audit Reveals 75 Redundant Files | ~502 |
| #16619 | " | 🔄 | Removed Accidental Duplicate Directory Structures | ~255 |
</claude-mem-context>
