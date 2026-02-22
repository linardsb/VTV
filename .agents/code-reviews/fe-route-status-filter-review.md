# Frontend Review: Route Status Filter (Full-Stack)

**Date:** 2026-02-22
**Scope:** 6 files modified to wire up the active/inactive status filter dropdown on the Routes page

**Summary:** Clean, minimal full-stack change. The `is_active` filter was correctly threaded from the database repository through the service, API endpoint, frontend client, and React state. All validation gates pass (type-check, lint, build, 460 tests). No new issues introduced. A few pre-existing observations noted for future improvement.

## Files Reviewed

| # | File | Type |
|---|------|------|
| 1 | `app/schedules/repository.py` | Backend (repository) |
| 2 | `app/schedules/service.py` | Backend (service) |
| 3 | `app/schedules/routes.py` | Backend (API routes) |
| 4 | `app/schedules/tests/test_routes.py` | Backend (tests) |
| 5 | `cms/apps/web/src/lib/schedules-client.ts` | Frontend (API client) |
| 6 | `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` | Frontend (page) |

## Findings

| File:Line | Standard | Issue | Suggestion | Priority |
|-----------|----------|-------|------------|----------|
| — | — | No issues found in the changed code | — | — |

### Pre-Existing Observations (not introduced by this change)

| File:Line | Standard | Issue | Suggestion | Priority |
|-----------|----------|-------|------------|----------|
| `page.tsx:53-430` | Component Patterns | Page component is 430 lines with 15+ useState hooks | Consider extracting filter state + handlers into a `useRouteFilters()` custom hook | Low |
| `page.tsx:162-179` | Data Fetching | `loadAllRoutes` fetches all routes sequentially in a paginated loop for the color map | Consider a dedicated unpaginated backend endpoint for route colors only | Low |
| `page.tsx:93-99` | Data Fetching | Debounced search uses `setState` in `useEffect` | Accepted pattern for debounce; lint passes. Could use `useDeferredValue` in future | Low |

## Standard-by-Standard Assessment

### 1. TypeScript Quality: PASS
- `is_active?: boolean` properly typed in `schedules-client.ts:81`
- Boolean conversion `statusFilter === "all" ? undefined : statusFilter === "active"` at `page.tsx:149` is type-safe
- `statusFilter` correctly added to `useCallback` dependency array at `page.tsx:159`
- Backend: proper `bool | None` typing across repository, service, and route handler

### 2. Design System Compliance: PASS
- No new styling added in this change
- Pre-existing classes use semantic tokens (`bg-surface`, `text-foreground`, `border-border`) correctly

### 3. Component Patterns: PASS
- No new components created
- Existing patterns followed consistently

### 4. Internationalization (i18n): PASS
- No new user-visible strings added (filter labels were already translated)
- Both `lv.json` and `en.json` have matching key structures

### 5. Accessibility (a11y): PASS
- No new interactive elements added
- Existing filter dropdown accessibility unchanged

### 6. RBAC & Auth: PASS
- Routes page already protected in `middleware.ts`
- `IS_READ_ONLY` role check at `page.tsx:58` already gates create/edit/delete actions
- Filter functionality is read-only, correctly available to all roles

### 7. Data Fetching & Performance: PASS
- `statusFilter` correctly included in `loadRoutes` dependency array
- Page resets to 1 on filter change (`setPage(1)` at `page.tsx:302, 363`)
- API request correctly omits `is_active` param when "all" is selected (avoids unnecessary filtering)

### 8. Security: PASS
- No hardcoded secrets or credentials
- Filter value safely converted to boolean before API call
- Backend properly validates `is_active` as `bool | None` via FastAPI Query param

## Backend Test Coverage

- New test `test_list_routes_filter_is_active` verifies the `?is_active=true` query parameter is accepted and returns 200
- All 460 tests pass

## Stats
- Files reviewed: 6
- Issues: 0 total — 0 Critical, 0 High, 0 Medium, 0 Low
- Pre-existing observations: 3 (all Low)

## Verdict

**PASS** — Ready for `/commit`.
