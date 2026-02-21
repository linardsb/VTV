# Execution Report: Routes Real API + Schedules Page

**Date:** 2026-02-21
**Plan:** `.claude/plans/buzzing-greeting-prism.md`

## Summary

Migrated the Routes page from 26 hardcoded mock routes to real backend API, created a new Schedules page with full CRUD for calendars/trips/GTFS import, and updated all i18n translations. Both pages now consume the backend's 22 schedule management endpoints.

## What Was Built

### Phase 1: Types & API Client (foundation)
- `types/schedule.ts` — 16 TypeScript interfaces matching backend schemas (PaginatedResponse<T>, Agency, Calendar, Trip, StopTime, etc.)
- `types/route.ts` — Rewritten from mock types (camelCase, string IDs) to backend types (snake_case, number IDs, GTFS route_type 0-12)
- `lib/color-utils.ts` — `toHexColor()`/`fromHexColor()` for backend "FF7043" ↔ frontend "#FF7043"
- `lib/schedules-client.ts` — 22 API functions (agencies 2, routes 5, calendars 7, trips 6, import 2)

### Phase 2: Routes Page → Real API (8 components + page)
- Updated all 6 route components to use snake_case fields, number IDs, server-side pagination
- Added agency filter dropdown, expanded GTFS type support (0-12), skeleton loading states
- Rewrote `routes/page.tsx` — full API migration with debounced search, toast notifications, GTFS route ID mapping for vehicle markers
- Deleted `lib/mock-routes-data.ts`

### Phase 3: Schedules Page (14 new files)
- 4 calendar components: table, form, detail (with exceptions), delete dialog
- 5 trip components: table, filters, form, detail (with stop times), delete dialog
- 1 GTFS import component: ZIP dropzone, import results, validation
- 1 page: 3-tab layout (Calendars/Trips/Import), shared lookup loading, full CRUD handlers
- Enabled in sidebar (`app-sidebar.tsx`)

### Phase 4: i18n
- Updated `en.json` and `lv.json` with ~100 new schedule keys + expanded route transport types

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| `setState` in `useEffect` (calendar-detail.tsx) | React 19 anti-pattern — used useEffect to reset exception form when calendar changed | Removed useEffect, added `key={selectedCalendar?.id}` on parent for key-based remount |
| Unused `agencies` variable (schedules/page.tsx) | `fetchAgencies()` result stored in state but no component consumed it | Removed agencies state + fetchAgencies import |
| Unused `_` destructured var (calendar-form.tsx) | `const { gtfs_service_id: _, ...rest }` flagged by ESLint | Renamed to `_serviceId` + `void _serviceId` |
| Missing `RouteType` export (use-vehicle-positions.ts) | `RouteType` type alias removed from route.ts during migration | Removed import and `as RouteType` cast, `routeType` is now `number` |

## Validation

- `pnpm --filter @vtv/web lint` — zero warnings, zero errors
- `pnpm --filter @vtv/web type-check` — zero errors

## File Inventory

**New files (14):** types/schedule.ts, lib/color-utils.ts, lib/schedules-client.ts, schedules/page.tsx, 10 schedule components
**Modified files (13):** types/route.ts, 6 route components, routes/page.tsx, stops/page.tsx, stop-map.tsx, use-vehicle-positions.ts, app-sidebar.tsx, en.json, lv.json
**Deleted files (1):** lib/mock-routes-data.ts
