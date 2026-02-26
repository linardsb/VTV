# Plan: Wire Up Route Status Filter (Active / Inactive)

## Feature Metadata
**Feature Type**: Bug Fix / Enhancement
**Estimated Complexity**: Low-Medium
**Route**: `/[locale]/(dashboard)/routes` (existing page)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer (no change)

## Feature Description

The Routes page has a status filter dropdown (Active / Inactive / All) in the sidebar filter panel that is **dead code**. The UI element exists, the state is tracked, but the filter is never applied to the data.

**Current behavior:** Selecting "Aktīvs" or "Neaktīvs" from the status dropdown does nothing. The table still shows all routes regardless of filter selection.

**Root cause (3 layers):**
1. **Backend:** `GET /api/v1/schedules/routes` does not accept an `is_active` query parameter — the repository, service, and route handler all lack this filter.
2. **Frontend API client:** `fetchRoutes()` in `schedules-client.ts` does not accept or send an `is_active` parameter.
3. **Frontend page:** `loadRoutes()` in `routes/page.tsx` does not include `statusFilter` in the API call params.

**Desired behavior:** When the user selects "Aktīvs" or "Neaktīvs" from the status dropdown, only routes with matching `is_active` status are shown in the table. Pagination counts update accordingly. Selecting "Visi statusi" (All) returns all routes.

## Design System

### Master Rules (from MASTER.md)
- No changes to UI components or styling needed — the dropdown already exists and is styled correctly
- Semantic tokens already used throughout the filters panel

### Page Override
- None exists for routes — none needed for this fix

### Tokens Used
- No new tokens needed — this is a data-flow fix, not a visual change

## Components Needed

### Existing (no changes)
- `Select` / `SelectContent` / `SelectItem` — already rendering the status dropdown in `route-filters.tsx`
- `Badge` in `route-table.tsx` — already showing active/inactive status per row

### New shadcn/ui to Install
- None

### Custom Components to Create
- None

## i18n Keys

No new i18n keys needed. All required keys already exist:
- `routes.filters.allStatuses` → "Visi statusi" / "All Statuses"
- `routes.filters.active` → "Aktīvs" / "Active"
- `routes.filters.inactive` → "Neaktīvs" / "Inactive"

## Data Fetching

### Current Flow (broken)
```
statusFilter state → (dead end, never read)
loadRoutes() → fetchRoutes({ page, page_size, search, route_type, agency_id })
                                                    ↑ no is_active param
```

### Target Flow (fixed)
```
statusFilter state → loadRoutes() → fetchRoutes({ ..., is_active })
                                           ↓
                        GET /api/v1/schedules/routes?is_active=true
                                           ↓
                   route handler → service → repository → WHERE is_active = true
```

### API Endpoint Change
- **Endpoint:** `GET /api/v1/schedules/routes`
- **New query param:** `is_active` (optional boolean, default: no filter)
- **Behavior:** When `is_active=true`, return only active routes. When `is_active=false`, return only inactive. When omitted, return all.

## RBAC Integration

No changes — the routes page RBAC is already configured correctly.

## Sidebar Navigation

No changes — the routes nav entry already exists.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, backend conventions
- `cms/CLAUDE.md` — Frontend conventions

### Files to Modify (Backend — 5 files)
- `app/schedules/repository.py` — Add `is_active` param to `list_routes()` and `count_routes()`
- `app/schedules/service.py` — Add `is_active` param to `list_routes()`
- `app/schedules/routes.py` — Add `is_active` query parameter to `list_routes` endpoint
- `app/schedules/tests/test_routes.py` — Add test for `is_active` query parameter
- `app/schedules/tests/conftest.py` — Verify `make_route()` supports `is_active` override (it likely already does via `**kwargs`)

### Files to Modify (Frontend — 2 files)
- `cms/apps/web/src/lib/schedules-client.ts` — Add `is_active` to `fetchRoutes()` params
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Wire `statusFilter` into `loadRoutes()` and its dependency array

### Pattern Files (for reference)
- `app/stops/routes.py` — Example of boolean query parameter (`is_active` on stops `list_stops`)

## Design System Color Rules

No visual changes in this plan. The executing agent MUST NOT modify any styling, colors, or layout. This is purely a data-flow fix.

## React 19 Coding Rules

The only React change is adding `statusFilter` to the `loadRoutes` dependency array and passing it to `fetchRoutes()`. Rules to follow:
- **No `setState` in `useEffect`** — not applicable here, just adding a dependency
- **Hook ordering** — `statusFilter` is already declared before `loadRoutes` via `useState`, so no ordering issue
- The `loadRoutes` `useCallback` dependency array MUST include `statusFilter` so it re-fetches when the filter changes

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Read all files to modify
**Action:** READ

Read these files to understand current implementation before making changes:
- `app/schedules/repository.py` (lines 150–213) — `list_routes()` and `count_routes()`
- `app/schedules/service.py` (lines 130–168) — `list_routes()`
- `app/schedules/routes.py` (lines 75–87) — `list_routes` route handler
- `app/schedules/tests/conftest.py` — `make_route()` factory
- `cms/apps/web/src/lib/schedules-client.ts` (lines 74–96) — `fetchRoutes()`
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` (lines 140–158) — `loadRoutes()`

Also read this reference file for the boolean query param pattern:
- `app/stops/routes.py` — how `is_active` is used as a query parameter on the stops endpoint

---

### Task 2: Add `is_active` filter to repository
**File:** `app/schedules/repository.py` (modify)
**Action:** UPDATE

**In `list_routes()` method (starts at line 150):**
1. Add parameter `is_active: bool | None = None` after `agency_id`
2. Add filter clause after the `agency_id` filter block:
   ```python
   if is_active is not None:
       query = query.where(Route.is_active == is_active)
   ```

**In `count_routes()` method (starts at line 185):**
1. Add parameter `is_active: bool | None = None` after `agency_id`
2. Add identical filter clause after the `agency_id` filter block:
   ```python
   if is_active is not None:
       query = query.where(Route.is_active == is_active)
   ```

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV && uv run ruff check app/schedules/repository.py && uv run mypy app/schedules/repository.py
```

---

### Task 3: Add `is_active` filter to service
**File:** `app/schedules/service.py` (modify)
**Action:** UPDATE

**In `list_routes()` method (starts at line 130):**
1. Add parameter `is_active: bool | None = None` after `agency_id`
2. Update docstring Args section — add: `is_active: Filter by active status.`
3. Pass `is_active=is_active` to both `self.repository.list_routes()` and `self.repository.count_routes()` calls
4. Add `is_active=is_active` to the logger.info call for observability

The updated method signature should be:
```python
async def list_routes(
    self,
    pagination: PaginationParams,
    search: str | None = None,
    route_type: int | None = None,
    agency_id: int | None = None,
    is_active: bool | None = None,
) -> PaginatedResponse[RouteResponse]:
```

The repository calls should become:
```python
routes = await self.repository.list_routes(
    offset=pagination.offset,
    limit=pagination.page_size,
    search=search,
    route_type=route_type,
    agency_id=agency_id,
    is_active=is_active,
)
total = await self.repository.count_routes(
    search=search, route_type=route_type, agency_id=agency_id, is_active=is_active
)
```

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV && uv run ruff check app/schedules/service.py && uv run mypy app/schedules/service.py
```

---

### Task 4: Add `is_active` query parameter to route handler
**File:** `app/schedules/routes.py` (modify)
**Action:** UPDATE

**In `list_routes` endpoint function (starts at line 75):**
1. Add query parameter after `agency_id`:
   ```python
   is_active: bool | None = Query(None),  # noqa: B008
   ```
2. Pass `is_active=is_active` to `service.list_routes()` call

The updated function signature should be:
```python
async def list_routes(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    search: str | None = Query(None, max_length=200),  # noqa: B008
    route_type: int | None = Query(None, ge=0),  # noqa: B008
    agency_id: int | None = Query(None),  # noqa: B008
    is_active: bool | None = Query(None),  # noqa: B008
    service: ScheduleService = Depends(get_service),  # noqa: B008
) -> PaginatedResponse[RouteResponse]:
```

And the service call:
```python
return await service.list_routes(
    pagination, search=search, route_type=route_type, agency_id=agency_id, is_active=is_active
)
```

**IMPORTANT:** The `Query(None)` for a `bool | None` parameter works correctly with FastAPI — it accepts `?is_active=true` and `?is_active=false` as query strings and converts them to Python `True`/`False`. When omitted, it stays `None`.

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV && uv run ruff check app/schedules/routes.py && uv run mypy app/schedules/routes.py
```

---

### Task 5: Add backend test for `is_active` filter
**File:** `app/schedules/tests/test_routes.py` (modify)
**Action:** UPDATE

Add a new test after `test_list_routes_200`:

```python
def test_list_routes_filter_is_active():
    mock_svc = _mock_service()
    active_route = RouteResponse.model_validate(make_route(id=1, is_active=True))

    mock_svc.list_routes = AsyncMock(
        return_value=PaginatedResponse[RouteResponse](items=[active_route], total=1, page=1, page_size=20)
    )
    app.dependency_overrides[get_service] = lambda: mock_svc

    try:
        client = TestClient(app)
        response = client.get("/api/v1/schedules/routes?is_active=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        # Verify the service was called with is_active=True
        mock_svc.list_routes.assert_called_once()
        call_kwargs = mock_svc.list_routes.call_args
        assert call_kwargs.kwargs.get("is_active") is True or (
            len(call_kwargs.args) > 1 and call_kwargs.args[-1] is True
        )
    finally:
        app.dependency_overrides.clear()
```

**NOTE:** First read `app/schedules/tests/conftest.py` to verify `make_route()` accepts `is_active` as a keyword argument. If it uses `**kwargs` pattern, this will work. If not, you'll need to add `is_active` parameter support to the factory.

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV && uv run pytest app/schedules/tests/test_routes.py -x -q
```

---

### Task 6: Run full backend validation
**Action:** VALIDATE

Run the full backend validation pyramid to ensure no regressions:

```bash
cd /Users/Berzins/Desktop/VTV && uv run ruff format --check . && uv run ruff check .
cd /Users/Berzins/Desktop/VTV && uv run mypy
cd /Users/Berzins/Desktop/VTV && uv run pytest -x -q
```

If any level fails, fix the issue and re-run ALL levels from Level 1. Do NOT proceed to frontend tasks until all backend checks pass.

---

### Task 7: Add `is_active` param to frontend API client
**File:** `cms/apps/web/src/lib/schedules-client.ts` (modify)
**Action:** UPDATE

**In `fetchRoutes()` function (starts at line 75):**

1. Add `is_active?: boolean` to the params type:
   ```typescript
   export async function fetchRoutes(params: {
     page?: number;
     page_size?: number;
     search?: string;
     route_type?: number;
     agency_id?: number;
     is_active?: boolean;
   }): Promise<PaginatedResponse<Route>> {
   ```

2. Add URL param construction after the `agency_id` block:
   ```typescript
   if (params.is_active !== undefined)
     searchParams.set("is_active", String(params.is_active));
   ```

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
```

---

### Task 8: Wire `statusFilter` into `loadRoutes()` on the Routes page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` (modify)
**Action:** UPDATE

**In `loadRoutes` useCallback (starts at line 140):**

1. Add `is_active` conversion logic and pass to `fetchRoutes()`. Convert from the string union to `boolean | undefined`:
   ```typescript
   const loadRoutes = useCallback(async () => {
     setIsLoading(true);
     try {
       const result = await fetchRoutes({
         page,
         page_size: PAGE_SIZE,
         search: debouncedSearch || undefined,
         route_type: typeFilter ?? undefined,
         agency_id: agencyFilter ?? undefined,
         is_active: statusFilter === "all" ? undefined : statusFilter === "active",
       });
       setRoutes(result.items);
       setTotalItems(result.total);
     } catch {
       setRoutes([]);
       setTotalItems(0);
     } finally {
       setIsLoading(false);
     }
   }, [page, debouncedSearch, typeFilter, agencyFilter, statusFilter]);
   ```

   Key changes:
   - Added `is_active` param: `"all"` → `undefined`, `"active"` → `true`, `"inactive"` → `false`
   - Added `statusFilter` to the `useCallback` dependency array

2. Also update the `onStatusFilterChange` handler to reset pagination. In both the mobile and desktop `<RouteFilters>` instances, change:
   ```typescript
   onStatusFilterChange={setStatusFilter}
   ```
   to:
   ```typescript
   onStatusFilterChange={(status) => { setStatusFilter(status); setPage(1); }}
   ```

   This ensures that when the user changes the status filter, they see page 1 of the new filtered results (not a potentially out-of-bounds page).

   There are **two** places this needs to change:
   - Line ~301 (mobile `RouteFilters`)
   - Line ~361 (desktop `RouteFilters`)

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint
```

---

### Task 9: Final frontend validation (3-Level Pyramid)
**Action:** VALIDATE

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

If any level fails, fix the issue and re-run ALL levels from Level 1.

**Success definition:** All 3 levels exit code 0, zero errors.

---

## Final Validation (Full Stack)

After all tasks pass individually, run the complete validation:

**Backend:**
```bash
cd /Users/Berzins/Desktop/VTV && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest -x -q
```

**Frontend:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint && pnpm --filter @vtv/web build
```

## Post-Implementation Checks

- [ ] `GET /api/v1/schedules/routes?is_active=true` returns only active routes
- [ ] `GET /api/v1/schedules/routes?is_active=false` returns only inactive routes
- [ ] `GET /api/v1/schedules/routes` (no param) returns all routes (backward compatible)
- [ ] Frontend: selecting "Aktīvs" shows only active routes in table
- [ ] Frontend: selecting "Neaktīvs" shows only inactive routes in table
- [ ] Frontend: selecting "Visi statusi" shows all routes
- [ ] Frontend: changing status filter resets to page 1
- [ ] Pagination total count updates to match filtered results
- [ ] No regressions in existing tests (backend 450+ tests pass)
- [ ] No TypeScript, lint, or build errors (frontend)

## Acceptance Criteria

This feature is complete when:
- [ ] Status filter dropdown on Routes page actually filters routes by active/inactive status
- [ ] Backend API supports `?is_active=true|false` query parameter
- [ ] Backend test covers the new parameter
- [ ] All backend checks pass (format, lint, types, tests)
- [ ] All frontend checks pass (type-check, lint, build)
- [ ] No regressions — all existing functionality works as before
- [ ] Ready for `/commit`

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `app/schedules/repository.py` | Modify | Add `is_active` param to `list_routes()` + `count_routes()` |
| `app/schedules/service.py` | Modify | Add `is_active` param to `list_routes()`, pass through |
| `app/schedules/routes.py` | Modify | Add `is_active` Query param to endpoint |
| `app/schedules/tests/test_routes.py` | Modify | Add test for `is_active` filter |
| `cms/apps/web/src/lib/schedules-client.ts` | Modify | Add `is_active` to `fetchRoutes()` params |
| `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` | Modify | Wire `statusFilter` → `loadRoutes()` + reset page on filter change |

**Total: 6 files modified, 0 files created**
