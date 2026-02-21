# Execution Report: Stops Terminus Markers & Direction Display

**Plan:** `.agents/plans/fe-stops-terminus-direction.md`
**Commit:** `4fc2359`
**Branch:** `main`
**Date:** 2026-02-20

## Summary

Implemented all 3 planned enhancements to the stops management page:
1. Terminus stops (Galapunkts/Terminus) with green markers on map
2. Direction text display in table and map popups
3. Copyable GTFS ID with clipboard feedback

Additionally implemented server-side `location_type` filtering (backend + frontend) which was not in the original plan but was necessary for correct pagination when filtering by stop type.

## Files Modified (12 total)

### Backend (4 files)
- `app/stops/repository.py` — Added `location_type` filter to `list()` and `count()` queries
- `app/stops/service.py` — Passes `location_type` through to repository
- `app/stops/routes.py` — Added `location_type: int | None = Query(None, ge=0, le=4)` query parameter
- `app/stops/tests/test_service.py` — Updated assertion to include `location_type=None`

### Frontend (6 files)
- `cms/apps/web/messages/lv.json` — Renamed "Stacija" to "Galapunkts", added copy button keys
- `cms/apps/web/messages/en.json` — Renamed "Station" to "Terminus", added copy button keys
- `cms/packages/ui/src/tokens.css` — Added `--color-stop-terminus` design token
- `cms/apps/web/src/components/stops/stop-map.tsx` — Green `MARKER_GREEN` for terminus stops, direction text in popups
- `cms/apps/web/src/components/stops/stop-table.tsx` — `CopyGtfsButton` component, direction text display, group hover
- `cms/apps/web/src/lib/stops-client.ts` — Added `location_type` parameter to `fetchStops`

### Page (1 file)
- `cms/apps/web/src/app/[locale]/(dashboard)/stops/page.tsx` — Server-side location_type filtering, detail/form overlap guard, batch map loading fix

### Config (1 file)
- `cms/apps/web/next.config.ts` — Added CARTO basemap domains to CSP

## Divergences from Plan

1. **Server-side location_type filtering** — Plan only covered client-side filter display. During implementation, discovered that client-side filtering of paginated data showed incorrect totals (e.g., "showing 3 of 1665" when filtering terminus stops). Added backend `location_type` query parameter to repository, service, and routes for accurate pagination.

2. **Batch map loading refactor** — Not in plan. Discovered `loadAllStops` used `Promise.all` for 16 parallel requests, triggering backend rate limiter (30/min). Changed to sequential batches of 5 with `Promise.allSettled` to avoid silent failures.

3. **Detail/form overlap guard** — Not in plan. Discovered that opening the edit form from the table while the detail sheet was open caused both panels to render simultaneously. Added `detailOpen && !formOpen` guard.

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| Map shows "0 pieturas" despite API returning 1665 stops | `loadAllStops` used `Promise.all` for 16 parallel requests; backend rate limiter (30/min) rejected pages 12-17; `Promise.all` rejects entirely if ANY promise fails | Changed to sequential batches of 5 using `Promise.allSettled`; collects partial results even if some requests fail |
| Location type filter shows wrong total count | Client-side filtering after pagination — table said "3 of 1665" instead of "3 of 137" | Added server-side `location_type` filter to backend `list()` and `count()` queries |
| Detail sheet and edit form overlap | Both sheets rendered simultaneously when clicking "Edit" from table row while detail was open | Added `detailOpen && !formOpen` condition to detail sheet's `open` prop |

## Validation Results

- TypeScript: PASS (0 errors)
- Lint: PASS (0 errors, 0 warnings)
- Build: PASS
- Design system: PASS (all hex colors documented as Leaflet exceptions)
- i18n: PASS (332 keys, both files in sync)
- Accessibility: WARN (1 pre-existing issue in chat-message-bubble.tsx, unrelated)
