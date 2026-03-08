# Plan: OpenAPI Spec Completions

## Feature Metadata
**Feature Type**: Enhancement / Bug Fix
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/compliance/routes.py`, `app/compliance/schemas.py`, `app/transit/routes.py`, `app/transit/schemas.py`, `cms/packages/sdk/`

## Feature Description

The compliance module (NeTEx/SIRI exports) has 4 endpoints that are **completely missing from the OpenAPI spec** — the `"compliance"` tag doesn't appear at all. This blocks SDK type generation for the frontend's EU compliance exports tab on the GTFS page.

The root cause has two layers:
1. **Stale SDK**: The `cms/packages/sdk/openapi.json` was generated before the compliance feature existed and was never re-generated. It contains 48 paths across 10 tags — `compliance` is absent entirely.
2. **Missing response models**: Three compliance endpoints (`/netex`, `/siri/vm`, `/siri/sm`) return raw `Response` objects (XML bytes) with no `response_model` or `responses` parameter. FastAPI generates empty response schemas for these. The status endpoint (`/status`) correctly uses `response_model=ExportMetadata`.
3. **Transit feeds endpoint**: `GET /api/v1/transit/feeds` returns `list[dict[str, object]]` instead of a typed Pydantic model, producing a generic schema.

The fix adds proper OpenAPI response metadata to all affected endpoints and regenerates the SDK.

## User Story

As a **frontend developer** working on the CMS GTFS compliance tab,
I want the compliance and transit feed endpoints to have proper OpenAPI schemas,
So that the auto-generated TypeScript SDK (`@vtv/sdk`) includes typed methods and response types for all EU compliance exports and transit feed status.

## Security Contexts

**Active contexts:**
- **CTX-RBAC**: Existing compliance endpoints already use `get_current_user` — no changes needed, but we verify no regression during the refactor.
- **CTX-INPUT**: Adding `responses` metadata doesn't introduce new input handling, but we verify query parameter constraints remain intact.

**Not applicable:**
- CTX-AUTH: No auth flow changes
- CTX-FILE: No file upload handling
- CTX-AGENT: No agent tool changes
- CTX-INFRA: No infrastructure changes

## Solution Approach

We use FastAPI's `responses` parameter on the route decorator to document XML response types in the OpenAPI spec, while keeping the actual `-> Response` return type for streaming XML bytes. This is the standard FastAPI pattern for non-JSON endpoints.

**Approach Decision:**
We chose the `responses` parameter approach because:
- It preserves the existing `Response(content=xml_bytes, media_type="application/xml")` pattern that works correctly
- It adds OpenAPI documentation without changing runtime behavior
- It allows the SDK generator to see the endpoints exist (even if XML responses aren't directly typed in TypeScript, the endpoint methods and query parameters will be generated)

**Alternatives Considered:**
- **Convert XML to JSON responses**: Rejected — breaks EU compliance standards (NeTEx/SIRI require XML)
- **Use `response_class=Response` on decorator**: Rejected — doesn't add schema information, just changes the default response class
- **Only regenerate SDK**: Rejected — would add compliance endpoints to spec but with empty response schemas, and transit `/feeds` would still lack typing

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/compliance/routes.py` (lines 1-98) — All 4 compliance endpoints, 3 return `Response`, 1 returns `ExportMetadata`
- `app/compliance/schemas.py` (lines 1-28) — Only `ExportMetadata` exists, no schemas for XML response documentation
- `app/transit/routes.py` (lines 69-88) — The `get_feeds` endpoint returns `list[dict[str, object]]`
- `app/transit/schemas.py` (lines 1-125) — Existing transit schemas, need to add `TransitFeedStatus`

### Similar Features (Examples to Follow)
- `app/transit/routes.py` (lines 42-67) — Pattern for `response_model=VehiclePositionsResponse` on GET endpoint
- `app/schedules/routes.py` (lines 370-400) — GTFS import endpoint uses `response_model=GTFSImportResponse` even for file upload
- `app/analytics/routes.py` (lines 34-55) — Clean `response_model` usage on GET endpoints

### Files to Modify
- `app/compliance/routes.py` — Add `responses` parameter to 3 XML endpoints
- `app/compliance/schemas.py` — Add response description schemas for OpenAPI docs
- `app/transit/routes.py` — Add `response_model` to `/feeds` endpoint
- `app/transit/schemas.py` — Add `TransitFeedStatus` schema
- `app/compliance/tests/test_routes.py` — Update tests to verify response schemas
- `app/transit/tests/test_routes.py` — Update tests for typed feeds response

### SDK Files (regeneration)
- `cms/packages/sdk/openapi.json` — Will be regenerated from live API
- `cms/packages/sdk/src/client/sdk.gen.ts` — Auto-generated, do not edit manually
- `cms/packages/sdk/src/client/types.gen.ts` — Auto-generated, do not edit manually

## Implementation Plan

### Phase 1: Schema Definitions
Add Pydantic schemas for the transit feeds endpoint and OpenAPI response documentation for compliance XML endpoints.

### Phase 2: Route Updates
Update route decorators with proper `response_model` and `responses` parameters.

### Phase 3: Test Updates & SDK Regeneration
Update tests and regenerate the SDK from the live OpenAPI spec.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add TransitFeedStatus Schema
**File:** `app/transit/schemas.py` (modify existing)
**Action:** UPDATE

Add a `TransitFeedStatus` Pydantic model and a `TransitFeedsResponse` wrapper after the existing `VehiclePositionsResponse` class (around line 68):

```python
class TransitFeedStatus(BaseModel):
    """Status of a single configured transit feed."""

    model_config = ConfigDict(strict=True)

    feed_id: str
    operator_name: str
    enabled: bool
    vehicle_count: int


class TransitFeedsResponse(BaseModel):
    """Response for transit feeds status endpoint."""

    model_config = ConfigDict(strict=True)

    feeds: list[TransitFeedStatus]
```

**Per-task validation:**
- `uv run ruff format app/transit/schemas.py`
- `uv run ruff check --fix app/transit/schemas.py` passes
- `uv run mypy app/transit/schemas.py` passes with 0 errors

---

### Task 2: Add Compliance OpenAPI Response Schemas
**File:** `app/compliance/schemas.py` (modify existing)
**Action:** UPDATE

Add descriptive schemas for OpenAPI documentation of the XML endpoints. These are NOT used at runtime for serialization — they exist purely to populate the OpenAPI spec so the SDK generator can see the endpoints. Add after the existing `ExportMetadata` class:

```python
class XMLExportResponse(BaseModel):
    """OpenAPI documentation schema for XML export responses.

    Not used at runtime — compliance endpoints return raw XML bytes via
    fastapi.responses.Response. This schema documents the response for
    OpenAPI spec generation and SDK type generation.
    """

    model_config = ConfigDict(strict=True)

    detail: str = "XML document returned as application/xml"
```

Also define reusable OpenAPI response dicts as module-level constants (these are used in route decorator `responses` params):

```python
NETEX_RESPONSES: dict[int | str, dict[str, object]] = {
    200: {
        "description": "NeTEx EPIP v1.2 XML document",
        "content": {"application/xml": {"schema": {"type": "string"}}},
    },
}

SIRI_VM_RESPONSES: dict[int | str, dict[str, object]] = {
    200: {
        "description": "SIRI-VM 2.0 Vehicle Monitoring XML document",
        "content": {"application/xml": {"schema": {"type": "string"}}},
    },
}

SIRI_SM_RESPONSES: dict[int | str, dict[str, object]] = {
    200: {
        "description": "SIRI-SM 2.0 Stop Monitoring XML document",
        "content": {"application/xml": {"schema": {"type": "string"}}},
    },
}
```

**Per-task validation:**
- `uv run ruff format app/compliance/schemas.py`
- `uv run ruff check --fix app/compliance/schemas.py` passes
- `uv run mypy app/compliance/schemas.py` passes with 0 errors

---

### Task 3: Update Transit Feeds Endpoint with Response Model
**File:** `app/transit/routes.py` (modify existing)
**Action:** UPDATE

1. Add import for the new schemas at the top, alongside existing imports from `app.transit.schemas`:
   ```python
   from app.transit.schemas import (
       RouteDelayTrendResponse,
       TransitFeedStatus,
       TransitFeedsResponse,
       VehicleHistoryResponse,
       VehiclePositionsResponse,
   )
   ```

2. Update the `get_feeds` endpoint (currently around line 69):
   - Change decorator from `@router.get("/feeds")` to `@router.get("/feeds", response_model=TransitFeedsResponse)`
   - Change return type from `-> list[dict[str, object]]` to `-> TransitFeedsResponse`
   - Wrap the returned data in a `TransitFeedsResponse` model:

   ```python
   @router.get("/feeds", response_model=TransitFeedsResponse)
   @limiter.limit("30/minute")
   async def get_feeds(
       request: Request,
       _current_user: User = Depends(get_current_user),  # noqa: B008
   ) -> TransitFeedsResponse:
       """List configured transit feeds and their status."""
       _ = request
       settings = get_settings()
       feeds = [
           TransitFeedStatus(
               feed_id=f.feed_id,
               operator_name=f.operator_name,
               enabled=f.enabled,
               vehicle_count=0,
           )
           for f in settings.transit_feeds
       ]
       return TransitFeedsResponse(feeds=feeds)
   ```

**Note:** The `vehicle_count` is currently hardcoded to 0 in the existing code (it constructs a dict with `"vehicle_count": 0`). This plan preserves that behavior — live vehicle counts require a Redis lookup which is a separate enhancement.

**Per-task validation:**
- `uv run ruff format app/transit/routes.py`
- `uv run ruff check --fix app/transit/routes.py` passes
- `uv run mypy app/transit/routes.py` passes with 0 errors

---

### Task 4: Update Compliance Routes with OpenAPI Response Metadata
**File:** `app/compliance/routes.py` (modify existing)
**Action:** UPDATE

1. Add import for the response constants from schemas:
   ```python
   from app.compliance.schemas import (
       ExportMetadata,
       NETEX_RESPONSES,
       SIRI_SM_RESPONSES,
       SIRI_VM_RESPONSES,
   )
   ```

2. Add `responses` parameter to each XML endpoint decorator. This does NOT change runtime behavior — the endpoints still return `Response` objects with XML bytes. The `responses` parameter only populates the OpenAPI spec.

   Update `export_netex` (line 34):
   ```python
   @router.get("/netex", responses=NETEX_RESPONSES)
   ```

   Update `get_siri_vm` (line 52):
   ```python
   @router.get("/siri/vm", responses=SIRI_VM_RESPONSES)
   ```

   Update `get_siri_sm` (line 70):
   ```python
   @router.get("/siri/sm", responses=SIRI_SM_RESPONSES)
   ```

3. Do NOT change the return types (`-> Response`) or the function bodies. Only the decorator gets the `responses` kwarg.

**Per-task validation:**
- `uv run ruff format app/compliance/routes.py`
- `uv run ruff check --fix app/compliance/routes.py` passes
- `uv run mypy app/compliance/routes.py` passes with 0 errors

---

### Task 5: Update Transit Route Tests for Typed Feeds Response
**File:** `app/transit/tests/test_routes.py` (modify existing)
**Action:** UPDATE

Read the file first. Find the test for the `/feeds` endpoint and update assertions to match the new `TransitFeedsResponse` wrapper:

The response JSON will now be `{"feeds": [...]}` instead of a bare list `[...]`.

Update any test that calls `GET /api/v1/transit/feeds` to:
- Assert `response.json()["feeds"]` is a list
- Assert each item in the feeds list has `feed_id`, `operator_name`, `enabled`, `vehicle_count` keys

If no test currently exists for the `/feeds` endpoint, create one:

```python
@pytest.mark.asyncio
async def test_get_feeds_returns_typed_response() -> None:
    """GET /api/v1/transit/feeds returns TransitFeedsResponse with typed feed list."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/transit/feeds")

    assert response.status_code == 200
    data = response.json()
    assert "feeds" in data
    assert isinstance(data["feeds"], list)
```

**Per-task validation:**
- `uv run ruff format app/transit/tests/test_routes.py`
- `uv run ruff check --fix app/transit/tests/test_routes.py` passes
- `uv run pytest app/transit/tests/test_routes.py -v` — all tests pass

---

### Task 6: Update Compliance Route Tests
**File:** `app/compliance/tests/test_routes.py` (modify existing)
**Action:** UPDATE

Read the file first. Add a test verifying that compliance endpoints appear in the OpenAPI schema. This catches future regressions where endpoints might silently drop from the spec.

Add a new test:

```python
@pytest.mark.asyncio
async def test_compliance_endpoints_in_openapi_spec() -> None:
    """All 4 compliance endpoints appear in the OpenAPI schema."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    spec = response.json()
    paths = spec["paths"]

    expected_paths = [
        "/api/v1/compliance/netex",
        "/api/v1/compliance/siri/vm",
        "/api/v1/compliance/siri/sm",
        "/api/v1/compliance/status",
    ]
    for path in expected_paths:
        assert path in paths, f"{path} missing from OpenAPI spec"

    # XML endpoints should document application/xml response
    for xml_path in expected_paths[:3]:
        responses = paths[xml_path]["get"]["responses"]
        assert "200" in responses
        content = responses["200"].get("content", {})
        assert "application/xml" in content, f"{xml_path} missing application/xml content type"

    # Status endpoint should document application/json response
    status_responses = paths[expected_paths[3]]["get"]["responses"]
    assert "200" in status_responses
    status_content = status_responses["200"].get("content", {})
    assert "application/json" in status_content
```

**Per-task validation:**
- `uv run ruff format app/compliance/tests/test_routes.py`
- `uv run ruff check --fix app/compliance/tests/test_routes.py` passes
- `uv run pytest app/compliance/tests/test_routes.py -v` — all tests pass

---

### Task 7: Regenerate SDK from Live OpenAPI Spec
**Action:** SDK REGENERATION (multi-step)

This task requires the FastAPI server to be running. If it's not running, skip this task and note it as a manual follow-up.

1. Start the backend (if not already running):
   ```bash
   make dev-be &
   # Wait for API to be ready
   sleep 5
   curl -sf http://localhost:8123/health
   ```

2. Download the fresh OpenAPI spec:
   ```bash
   curl -s http://localhost:8123/openapi.json > cms/packages/sdk/openapi.json
   ```

3. Verify compliance endpoints are present:
   ```bash
   python3 -c "
   import json
   with open('cms/packages/sdk/openapi.json') as f:
       spec = json.load(f)
   compliance = [p for p in spec['paths'] if 'compliance' in p]
   print(f'Compliance paths: {len(compliance)}')
   for p in compliance:
       print(f'  {p}')
   assert len(compliance) == 4, f'Expected 4 compliance paths, got {len(compliance)}'
   print('OK: All compliance endpoints in spec')
   "
   ```

4. Regenerate TypeScript SDK:
   ```bash
   cd cms && pnpm --filter @vtv/sdk generate-sdk
   ```

5. Verify the SDK generated compliance types:
   ```bash
   grep -c "compliance" cms/packages/sdk/src/client/sdk.gen.ts
   ```

**If FastAPI is not running:** Save the openapi.json regeneration as a documented follow-up step. The backend code changes are complete and correct regardless — SDK regeneration is a separate concern.

**Per-task validation:**
- `cms/packages/sdk/openapi.json` contains 4 compliance paths
- `cms/packages/sdk/src/client/sdk.gen.ts` contains compliance endpoint methods
- `cd cms && pnpm type-check` passes (if frontend tooling is available)

---

## Logging Events

No new logging events needed — existing compliance and transit logging is sufficient. The changes are purely schema/metadata additions.

## Testing Strategy

### Unit Tests
**Location:** `app/compliance/tests/test_routes.py`
- OpenAPI spec includes all 4 compliance endpoints
- XML endpoints document `application/xml` content type
- Status endpoint documents `application/json` content type
- Existing tests continue to pass (no runtime behavior change)

**Location:** `app/transit/tests/test_routes.py`
- Feeds endpoint returns `TransitFeedsResponse` wrapper
- Each feed item has typed fields (`feed_id`, `operator_name`, `enabled`, `vehicle_count`)
- Existing transit tests pass (no regression)

### Integration Tests
None needed — this is a metadata/schema enhancement with no database or Redis interaction.

### Edge Cases
- Empty transit feeds list: `TransitFeedsResponse(feeds=[])` should serialize correctly
- SDK regeneration when API is not running: documented as manual follow-up
- Existing frontend code using bare list response from `/feeds`: must update to access `.feeds` property

## Acceptance Criteria

This feature is complete when:
- [ ] All 4 compliance endpoints appear in OpenAPI spec at `/openapi.json`
- [ ] XML endpoints document `application/xml` response content type
- [ ] `GET /api/v1/transit/feeds` has typed `response_model=TransitFeedsResponse`
- [ ] `TransitFeedStatus` schema has `feed_id`, `operator_name`, `enabled`, `vehicle_count` fields
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + integration)
- [ ] No type suppressions added
- [ ] No regressions in existing tests
- [ ] SDK `openapi.json` regenerated with compliance endpoints (or documented as follow-up)

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/compliance/tests/ app/transit/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if running)**
```bash
curl -s http://localhost:8123/openapi.json | python3 -c "
import json, sys
spec = json.load(sys.stdin)
c = [p for p in spec['paths'] if 'compliance' in p]
print(f'Compliance endpoints: {len(c)}')
assert len(c) == 4
print('PASS')
"
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors. Level 5 confirms live spec.

## Dependencies

- Shared utilities used: `PaginatedResponse`, `ConfigDict` from pydantic
- Core modules used: `get_current_user`, `get_settings`, `get_db`, `limiter`
- New dependencies: None
- New env vars: None

## Known Pitfalls

1. **Schema field additions break consumers (anti-pattern #11)**: The `TransitFeedsResponse` wrapper changes the `/feeds` response shape from `[...]` to `{"feeds": [...]}`. Any frontend code consuming this endpoint must be updated. Grep for `transit/feeds` and `/feeds` in `cms/` to find affected files.

2. **`responses` dict type annotation**: The `responses` parameter on FastAPI route decorators expects `dict[int | str, dict[str, Any]]`. Use `dict[int | str, dict[str, object]]` to avoid importing `Any` — the values are all strings and dicts which satisfy `object`.

3. **OpenAPI spec stale after changes**: The `cms/packages/sdk/openapi.json` is a static snapshot. After modifying route decorators, the SDK must be regenerated from the live API. If the API isn't running, document this as a follow-up step.

4. **`list[dict[str, object]]` return type**: FastAPI infers schema from `-> list[dict[str, object]]` as a generic array of objects. Switching to `-> TransitFeedsResponse` gives the spec a named schema with typed fields.

5. **Existing compliance test assertions**: The XML endpoint tests assert `response.headers["content-type"] == "application/xml"`. Adding `responses` metadata to the decorator does NOT change the actual response content type — tests should continue to pass without modification.

## Frontend Impact

The `/feeds` response shape changes from a bare list to a wrapper object:

**Before:** `[{"feed_id": "riga", ...}]`
**After:** `{"feeds": [{"feed_id": "riga", ...}]}`

The executing agent should grep for references to the feeds endpoint in the CMS:
```bash
grep -rn "feeds" cms/apps/web/src/ --include="*.ts" --include="*.tsx" | grep -i "transit"
```

Any frontend code accessing the response directly as an array must be updated to access `.feeds`. This is a **breaking change** for the frontend — document it but do NOT modify CMS files in this plan (that's a separate frontend task).

## Notes

- The compliance feature was added after the last SDK generation. This is a one-time catch-up.
- Future workflow improvement: Add a CI check that compares the live OpenAPI spec against the committed SDK spec (see `be-validate` step 7 — SDK sync check).
- The `XMLExportResponse` schema is defined for documentation completeness but may be removed if the `responses` dict approach is sufficient. Keep it if the team wants a Pydantic model reference.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understand the difference between `response_model` (JSON responses) and `responses` (OpenAPI metadata for any content type)
- [ ] Understand that compliance XML endpoints must NOT change their runtime behavior
- [ ] Clear on task execution order
- [ ] Validation commands are executable in this environment
