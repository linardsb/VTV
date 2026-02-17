# Plan: check_driver_availability Transit Tool

## Feature Metadata
**Feature Type**: New Capability (Agent Tool)
**Estimated Complexity**: Medium
**Primary Systems Affected**: Transit tools module, agent registration, transit schemas

> **NOTE: This is tool planning for an AI agent.** Tools are functions that an LLM calls during autonomous workflows. Their docstrings, parameter design, and error handling are optimized for machine consumption, not human developers.

## Feature Description

The `check_driver_availability` tool is the fifth and final read-only transit tool for VTV's Pydantic AI agent. It enables dispatchers to query driver availability for specific shifts, dates, and route qualifications.

Unlike the other four transit tools which consume GTFS data (public feeds), this tool's production data source is the VTV CMS tRPC API for driver management. However, the CMS driver management module is Phase 2 (not yet implemented). Therefore, this implementation uses a **mock data provider** that returns realistic simulated driver availability data for Riga's transit system. The mock provider is designed as a clean module that will be replaced by an HTTP client when the CMS API is available — no changes to the tool function itself will be needed.

The tool supports filtering by date, shift type (morning/afternoon/evening/night), route qualification, and returns structured availability data including driver counts, individual driver details with certifications, and a summary formatted for the LLM agent to relay.

## User Story

As a **dispatcher**
I want to **check which drivers are available for a specific shift and date**
So that **I can plan shift coverage and identify qualified drivers for routes that need staffing**

## Tool Interface

```python
async def check_driver_availability(
    ctx: RunContext[TransitDeps],
    date: str | None = None,         # YYYY-MM-DD, defaults to today (Riga TZ)
    shift: str | None = None,        # "morning" | "afternoon" | "evening" | "night" | None (all)
    route_id: str | None = None,     # Filter to drivers qualified for this GTFS route
) -> str:
    """Check available drivers for shifts and route assignments."""
```

**Example calls the agent would make:**
- `check_driver_availability()` — All available drivers today
- `check_driver_availability(shift="morning")` — Morning shift drivers today
- `check_driver_availability(date="2026-02-18", shift="afternoon", route_id="bus_22")` — Afternoon drivers qualified for route 22

**Return format:** JSON-serialized `DriverAvailabilityReport` with driver list, shift counts, summary text.

## Composition

This tool fits into dispatcher workflows:
1. **Shift planning:** `check_driver_availability(shift="morning")` → see who's available
2. **Route coverage:** `check_driver_availability(route_id="bus_22")` → find qualified drivers, then `get_route_schedule(route_id="bus_22")` to see how many trips need coverage
3. **Performance review:** `get_adherence_report(route_id="bus_22")` → identify underperforming route, then `check_driver_availability(route_id="bus_22")` → check if staffing is the issue

## Solution Approach

We chose a **mock data provider with identical interface to the future CMS client** because:
- The CMS driver API doesn't exist yet (Phase 2)
- Dispatchers can still demo and test the agent with realistic data
- The tool function itself won't change when the real API is connected — only the data provider module gets swapped
- Follows YAGNI: no premature CMS HTTP client code

**Alternatives Considered:**
- **Stub that returns "feature not available"**: Rejected because the tool would be useless for demos and testing, and the agent's system prompt lists 5 transit tools — returning errors degrades trust
- **Build CMS driver API first**: Rejected because it's Phase 2 scope, and this tool is the last MVP transit tool blocking feature-completeness
- **Use GTFS data for driver info**: Rejected because GTFS has no driver data — it's a schedule format, not a workforce management system

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/agents/tools/transit/get_adherence_report.py` (full file) — **Primary pattern reference.** Mirror the exact tool structure: imports, logger setup, validation helpers, `async def` tool function with RunContext[TransitDeps], try/except with structured logging, JSON serialization of Pydantic models
- `app/core/agents/tools/transit/schemas.py` (full file) — All existing transit schemas. New schemas go at the bottom following the same `BaseModel` + `ConfigDict(strict=True)` + Google docstring pattern
- `app/core/agents/tools/transit/deps.py` (full file) — TransitDeps dataclass. NO changes needed — mock data provider doesn't require new deps

### Similar Features (Examples to Follow)
- `app/core/agents/tools/transit/get_adherence_report.py` (lines 260-305) — Tool function signature and agent-optimized docstring pattern (WHEN TO USE / WHEN NOT TO USE / PARAMETERS / EFFICIENCY / COMPOSITION sections)
- `app/core/agents/tools/transit/get_adherence_report.py` (lines 306-494) — Function body: start timer, log started, validate inputs, fetch data, compute results, build Pydantic model, serialize to JSON, log completed with duration
- `app/core/agents/tools/transit/tests/test_get_adherence_report.py` (full file) — Test patterns: `_make_ctx()` helper, patch-based mocking, JSON parsing assertions, helper function unit tests

### Files to Modify
- `app/core/agents/tools/transit/schemas.py` — Add DriverInfo, ShiftSummary, DriverAvailabilityReport schemas
- `app/core/agents/agent.py` — Register check_driver_availability tool (add import + add to tools list)

### Files to Create
- `app/core/agents/tools/transit/driver_data.py` — Mock data provider module
- `app/core/agents/tools/transit/check_driver_availability.py` — Tool implementation
- `app/core/agents/tools/transit/tests/test_check_driver_availability.py` — Unit tests

## Implementation Plan

### Phase 1: Foundation (Schemas + Mock Data Provider)
Define the response schemas and the mock data provider that simulates realistic driver availability data for Riga's transit system.

### Phase 2: Core Implementation (Tool Function)
Implement the tool function following the exact pattern from `get_adherence_report.py` — validate inputs, fetch data from provider, filter/aggregate, build response model, serialize.

### Phase 3: Integration & Validation (Agent Registration + Tests)
Register the tool with the Pydantic AI agent and create comprehensive unit tests.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add Driver Availability Schemas
**File:** `app/core/agents/tools/transit/schemas.py` (modify existing)
**Action:** UPDATE

Add the following schemas at the **bottom** of the file (after the `AdherenceReport` class), following the established pattern (BaseModel + ConfigDict(strict=True) + Google-style docstring):

**Schema 1: `DriverInfo`**
- `driver_id: str` — Unique driver identifier (e.g., "DRV-001")
- `name: str` — Driver display name (e.g., "J. Bērziņš")
- `license_categories: list[str]` — License categories held (e.g., ["D", "D1"])
- `qualified_route_ids: list[str]` — GTFS route IDs this driver is certified to operate
- `shift: str` — Assigned shift ("morning", "afternoon", "evening", "night")
- `status: str` — Availability status ("available", "on_duty", "on_leave", "sick")
- `phone: str | None = None` — Contact phone, if available
- `notes: str | None = None` — Special notes (e.g., "overtime eligible", "trainee")

**Schema 2: `ShiftSummary`**
- `shift: str` — Shift name
- `total_drivers: int` — Total drivers assigned to this shift
- `available_count: int` — Drivers with "available" status
- `on_duty_count: int` — Drivers currently on duty
- `on_leave_count: int` — Drivers on planned leave
- `sick_count: int` — Drivers on sick leave

**Schema 3: `DriverAvailabilityReport`**
- `report_date: str` — ISO date the report covers
- `service_type: str` — Day classification ("weekday", "saturday", "sunday")
- `shift_filter: str | None = None` — Shift filter applied, or None for all
- `route_filter: str | None = None` — Route filter applied, or None for all
- `total_drivers: int` — Total matching drivers
- `available_count: int` — Drivers available for assignment
- `shifts: list[ShiftSummary]` — Per-shift breakdown
- `drivers: list[DriverInfo]` — Individual driver details (capped for token efficiency)
- `summary: str` — Pre-formatted text summary for agent to relay to user

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/schemas.py`
- `uv run ruff check --fix app/core/agents/tools/transit/schemas.py`
- `uv run mypy app/core/agents/tools/transit/schemas.py`
- `uv run pyright app/core/agents/tools/transit/schemas.py`

---

### Task 2: Create Mock Data Provider
**File:** `app/core/agents/tools/transit/driver_data.py` (create new)
**Action:** CREATE

Create a mock data provider module that simulates realistic driver availability for Riga's transit system. This module will be replaced by a CMS API client in Phase 2 when driver management is implemented in the CMS.

**Module structure:**

1. **Module docstring** explaining this is a mock data provider and what replaces it.

2. **`_MOCK_DRIVERS` constant** — A list of ~20 mock `DriverInfo`-compatible dictionaries with:
   - Realistic Latvian names (abbreviated as initial + surname, e.g., "J. Bērziņš", "A. Kalniņa", "M. Ozols")
   - Driver IDs following pattern "DRV-001" through "DRV-020"
   - Mixed license categories: most have ["D"], some have ["D", "D1"], a few have ["D", "DE"]
   - Each driver assigned to one shift: ~6 morning, ~5 afternoon, ~5 evening, ~4 night
   - `qualified_route_ids`: each driver qualified for 3-8 routes from realistic Riga route IDs (use "bus_1", "bus_3", "bus_7", "bus_13", "bus_15", "bus_22", "bus_24", "bus_30", "bus_32", "bus_37", "bus_40", "bus_45", "bus_48", "bus_53")
   - Mixed statuses: ~14 "available", ~3 "on_duty", ~2 "on_leave", ~1 "sick"
   - A few have `notes` like "overtime eligible", "trainee — supervised only", "senior driver"
   - `phone` for available drivers only (format "+371 2XXX XXXX")

3. **`_SHIFT_HOURS` constant** — Dict mapping shift names to display time ranges:
   ```python
   _SHIFT_HOURS: dict[str, str] = {
       "morning": "05:00–13:00",
       "afternoon": "13:00–21:00",
       "evening": "17:00–01:00",
       "night": "22:00–06:00",
   }
   ```

4. **`_VALID_SHIFTS` constant** — Frozenset of valid shift names for input validation.

5. **`async def get_driver_availability(date_str: str, shift: str | None, route_id: str | None) -> list[dict[str, ...]]`** function:
   - Type the return as `list[dict[str, str | list[str] | None]]` (the dicts match DriverInfo fields)
   - Filter `_MOCK_DRIVERS` by `shift` if provided
   - Filter by `route_id` if provided (check if route_id is in driver's qualified_route_ids)
   - Add slight date-based variation: use `hash(date_str) % 3` to simulate 0-2 extra drivers being "sick" on different dates (deterministic per date for testability)
   - Return the filtered list of driver dicts
   - Include Google-style docstring
   - NOTE: This function is async to match the interface of the future CMS API client. The mock implementation doesn't actually await anything, but making it async now means the tool function won't need changes when the real client is swapped in.

6. **Import only what you need:** `from __future__ import annotations` at top. No external dependencies beyond stdlib.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/driver_data.py`
- `uv run ruff check --fix app/core/agents/tools/transit/driver_data.py`
- `uv run mypy app/core/agents/tools/transit/driver_data.py`
- `uv run pyright app/core/agents/tools/transit/driver_data.py`

---

### Task 3: Implement check_driver_availability Tool
**File:** `app/core/agents/tools/transit/check_driver_availability.py` (create new)
**Action:** CREATE

Implement the tool function following the **exact pattern** from `get_adherence_report.py`.

**File structure:**

1. **Module docstring:** `"""Transit tool: check_driver_availability.\n\nQueries driver availability for shift planning and route coverage.\n"""`

2. **Imports:**
   ```python
   from __future__ import annotations

   import json
   import time
   from datetime import date, datetime
   from zoneinfo import ZoneInfo

   from pydantic_ai import RunContext

   from app.core.agents.tools.transit.deps import TransitDeps
   from app.core.agents.tools.transit.driver_data import (
       _VALID_SHIFTS,
       get_driver_availability,
   )
   from app.core.agents.tools.transit.schemas import (
       DriverAvailabilityReport,
       DriverInfo,
       ShiftSummary,
   )
   from app.core.logging import get_logger
   ```

3. **Constants:**
   ```python
   logger = get_logger(__name__)
   _RIGA_TZ = ZoneInfo("Europe/Riga")
   _MAX_DRIVERS_RESPONSE = 30  # Token efficiency cap
   ```

4. **`_validate_date(date_str: str | None) -> tuple[date, str] | str`** — Copy the exact same helper from `get_adherence_report.py` (lines 38-54). Same logic: parse YYYY-MM-DD or default to today in Riga timezone, return tuple on success or error string on failure.

5. **`_classify_service_type(query_date: date) -> str`** — Copy the exact same helper from `get_adherence_report.py` (lines 57-71). Classifies as "weekday", "saturday", "sunday".

6. **`async def check_driver_availability(ctx, date, shift, route_id) -> str`** tool function:

   **Signature:**
   ```python
   async def check_driver_availability(
       ctx: RunContext[TransitDeps],
       date: str | None = None,
       shift: str | None = None,
       route_id: str | None = None,
   ) -> str:
   ```

   **Agent-optimized docstring (MUST include all 6 sections):**
   - **WHEN TO USE:** Dispatcher asks about driver availability, shift staffing, who can drive a route, coverage gaps, "who's available for the morning shift?", driver scheduling
   - **WHEN NOT TO USE:** For vehicle locations (use query_bus_status). For schedule times (use get_route_schedule). For on-time performance (use get_adherence_report). For finding stops (use search_stops)
   - **PARAMETERS:** Document each param with guidance. `date` defaults to today Riga TZ. `shift` can be "morning", "afternoon", "evening", "night" or omit for all. `route_id` filters to drivers qualified for that specific route
   - **EFFICIENCY:** Omit `shift` for a quick full-day overview. Combine `shift` + `route_id` for targeted staffing queries. Response is capped at 30 drivers for token efficiency
   - **COMPOSITION:** After checking availability, use `get_route_schedule` to see how many trips need coverage, or `get_adherence_report` to check if understaffed routes have performance issues
   - Standard **Args** and **Returns** sections

   **Function body (follow `get_adherence_report` pattern exactly):**
   1. `start_time = time.monotonic()`
   2. Log `"transit.check_driver_availability.started"` with params
   3. Validate date using `_validate_date()` — return error string if invalid
   4. Validate shift if provided — if not in `_VALID_SHIFTS`, return error string listing valid options
   5. `try:` block:
      a. Call `await get_driver_availability(date_str, shift, route_id)`
      b. Build `DriverInfo` list from returned dicts
      c. Compute shift summaries — group drivers by shift, count statuses per shift
      d. Build `ShiftSummary` objects for each shift present
      e. Count totals: total_drivers, available_count
      f. Build summary string with key metrics (e.g., "Driver availability for 2026-02-17 (weekday), morning shift: 5 available of 6 total. 1 on leave.")
      g. Build `DriverAvailabilityReport` model
      h. Log `"transit.check_driver_availability.completed"` with duration_ms, total_drivers, available_count
      i. Return `json.dumps(report.model_dump(), ensure_ascii=False)`
   6. `except Exception as e:` block:
      a. Log `"transit.check_driver_availability.failed"` with exc_info, error, error_type, duration_ms
      b. Return actionable error string

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/check_driver_availability.py`
- `uv run ruff check --fix app/core/agents/tools/transit/check_driver_availability.py`
- `uv run mypy app/core/agents/tools/transit/check_driver_availability.py`
- `uv run pyright app/core/agents/tools/transit/check_driver_availability.py`

---

### Task 4: Register Tool with Pydantic AI Agent
**File:** `app/core/agents/agent.py` (modify existing)
**Action:** UPDATE

1. Add import (maintain alphabetical order with existing imports from transit tools):
   ```python
   from app.core.agents.tools.transit.check_driver_availability import check_driver_availability
   ```
   This import should go **after** the `get_adherence_report` import and **before** the `get_route_schedule` import (alphabetical by function name: check < get).

   Wait — the existing imports are ordered by module path, not function name. Looking at the current imports:
   ```python
   from app.core.agents.tools.transit.get_adherence_report import get_adherence_report
   from app.core.agents.tools.transit.get_route_schedule import get_route_schedule
   from app.core.agents.tools.transit.query_bus_status import query_bus_status
   from app.core.agents.tools.transit.search_stops import search_stops
   ```
   The new import should go **before** `get_adherence_report` (alphabetically: `check_driver_availability` < `get_adherence_report`):
   ```python
   from app.core.agents.tools.transit.check_driver_availability import check_driver_availability
   from app.core.agents.tools.transit.get_adherence_report import get_adherence_report
   from app.core.agents.tools.transit.get_route_schedule import get_route_schedule
   from app.core.agents.tools.transit.query_bus_status import query_bus_status
   from app.core.agents.tools.transit.search_stops import search_stops
   ```

2. Add `check_driver_availability` to the tools list in the `create_agent()` function (line 51). Place it after `get_adherence_report` in the list to match the PRD ordering:
   ```python
   tools=[query_bus_status, get_route_schedule, search_stops, get_adherence_report, check_driver_availability],
   ```

**Per-task validation:**
- `uv run ruff format app/core/agents/agent.py`
- `uv run ruff check --fix app/core/agents/agent.py`
- `uv run mypy app/core/agents/agent.py`
- `uv run pyright app/core/agents/agent.py`

---

### Task 5: Create Unit Tests
**File:** `app/core/agents/tools/transit/tests/test_check_driver_availability.py` (create new)
**Action:** CREATE

Create comprehensive unit tests following the **exact pattern** from `test_get_adherence_report.py`.

**Test helper functions (with return type annotations!):**

```python
def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.deps.http_client = AsyncMock()
    ctx.deps.settings = MagicMock()
    return ctx
```

**Unit tests for helper functions:**

1. **`test_validate_date_none_returns_today`** — `_validate_date(None)` returns tuple with today's date
2. **`test_validate_date_valid`** — `_validate_date("2026-02-17")` returns tuple with parsed date
3. **`test_validate_date_invalid`** — `_validate_date("bad")` returns error string

**Tool function tests (mock `get_driver_availability` via `patch`):**

4. **`test_check_driver_availability_invalid_date`** — Pass `date="not-a-date"`, assert "Invalid date" in result

5. **`test_check_driver_availability_invalid_shift`** — Pass `shift="graveyard"`, assert error message listing valid shifts

6. **`test_check_driver_availability_all_drivers`** — No filters, mock returns 5 drivers (3 available, 1 on_duty, 1 on_leave). Assert JSON response has correct totals, drivers list, summary.

7. **`test_check_driver_availability_shift_filter`** — Pass `shift="morning"`, mock returns only morning drivers. Assert all returned drivers have shift="morning".

8. **`test_check_driver_availability_route_filter`** — Pass `route_id="bus_22"`, mock returns drivers qualified for bus_22. Assert all returned drivers have "bus_22" in qualified_route_ids.

9. **`test_check_driver_availability_combined_filters`** — Pass `shift="afternoon"` + `route_id="bus_7"`, mock returns intersection. Assert correct filtering.

10. **`test_check_driver_availability_no_drivers_found`** — Mock returns empty list. Assert result contains helpful message about no drivers matching.

11. **`test_check_driver_availability_shift_summary_counts`** — Mock returns mixed drivers across 2 shifts. Assert `shifts` array has correct per-shift counts for each status.

12. **`test_check_driver_availability_token_cap`** — Mock returns 35 drivers. Assert `drivers` list in result is capped at 30 (the `_MAX_DRIVERS_RESPONSE` constant).

13. **`test_check_driver_availability_provider_error`** — Mock `get_driver_availability` raises `RuntimeError`. Assert actionable error message returned.

14. **`test_check_driver_availability_specific_date`** — Pass `date="2026-03-01"`, verify the report_date in response matches and service_type is correct (it's a Sunday).

**Mock data for tests** — Create a helper function `_make_mock_drivers()` that returns a list of driver dicts:
```python
def _make_mock_drivers(
    count: int = 5,
    shift: str = "morning",
    status: str = "available",
    route_ids: list[str] | None = None,
) -> list[dict[str, str | list[str] | None]]:
```
This returns `count` driver dicts with controllable shift, status, and route_ids. Use this in all test mocks.

**Patching target:** `"app.core.agents.tools.transit.check_driver_availability.get_driver_availability"` — patch the function where it's imported, not where it's defined.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/tests/test_check_driver_availability.py`
- `uv run ruff check --fix app/core/agents/tools/transit/tests/test_check_driver_availability.py`
- `uv run pytest app/core/agents/tools/transit/tests/test_check_driver_availability.py -v` — all tests pass

---

## Migration (if applicable)

No database migration needed. This tool uses a mock data provider (no database tables).

## Logging Events

- `transit.check_driver_availability.started` — When tool function is called (includes date, shift, route_id params)
- `transit.check_driver_availability.completed` — Successful response (includes duration_ms, total_drivers, available_count)
- `transit.check_driver_availability.failed` — Exception during execution (includes exc_info, error, error_type, duration_ms)

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tools/transit/tests/test_check_driver_availability.py`
- Helper functions (`_validate_date`, `_classify_service_type`) — validate input parsing and edge cases
- Tool function with mocked data provider — test all parameter combinations and error paths
- Token efficiency cap — verify driver list truncation

### Edge Cases
- Invalid date format — returns actionable error with format example
- Invalid shift name — returns error listing valid options
- No matching drivers — returns helpful "no drivers found" message with suggestions
- Provider error — returns actionable error asking to retry
- All drivers sick — returns report with 0 available count
- Date-based variation in mock — deterministic sick count per date

## Acceptance Criteria

This feature is complete when:
- [ ] `DriverInfo`, `ShiftSummary`, `DriverAvailabilityReport` schemas defined in schemas.py
- [ ] Mock data provider in `driver_data.py` returns realistic Riga driver data
- [ ] Tool function in `check_driver_availability.py` follows `get_adherence_report.py` pattern exactly
- [ ] Agent-optimized docstring with all 6 sections (WHEN TO USE, WHEN NOT TO USE, PARAMETERS, EFFICIENCY, COMPOSITION, Args/Returns)
- [ ] Tool registered in `agent.py` (import + tools list)
- [ ] 14 unit tests all passing
- [ ] All type checkers pass (mypy + pyright) with zero errors
- [ ] All linters pass (ruff format + ruff check) with zero errors
- [ ] Structured logging follows `transit.check_driver_availability.{started|completed|failed}` pattern
- [ ] No type suppressions added
- [ ] No regressions in existing tests (173+ unit tests still pass)
- [ ] Ready for `/commit`

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order (Task 1 through Task 5)
- [ ] Per-task validations passed for every task
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
uv run pytest app/core/agents/tools/transit/tests/test_check_driver_availability.py -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- Shared utilities used: `app.core.logging.get_logger`
- Core modules used: `app.core.agents.tools.transit.deps.TransitDeps`, `app.core.agents.tools.transit.schemas`
- New dependencies: **None** — mock data provider uses stdlib only
- New env vars: **None** — CMS API URL will be added in Phase 2 when driver management is built

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks instead.
2. **No `object` type hints** — Import and use actual types directly. Never write `def f(data: object)` then isinstance-check.
3. **Untyped third-party libraries** — Not applicable here (no new third-party deps), but if needed: mypy `[[tool.mypy.overrides]]` + pyright file-level directives. **NEVER** use pyright `[[executionEnvironments]]` with a scoped `root`.
4. **Mock exceptions must match catch blocks** — If production code catches `RuntimeError`, tests must mock `RuntimeError`, not bare `Exception`.
5. **No unused imports or variables** — Ruff F401 catches unused imports, Ruff F841 catches unused local variables. Don't write speculative code — only import/assign what you actually use.
6. **No unnecessary noqa/type-ignore** — Ruff RUF100 flags unused suppression comments.
7. **Test helper functions need return type annotations** — Always add `-> ReturnType` to test helpers (e.g., `def _make_ctx() -> MagicMock:`, `def _make_mock_drivers(...) -> list[dict[str, str | list[str] | None]]:`).
8. **Import sorting** — Use `ruff check --fix` (not just `ruff check`) to auto-fix I001 import sorting issues. `ruff format` does NOT handle import sorting.
9. **`_validate_date` and `_classify_service_type` are duplicated** — This is intentional (Two-Feature Rule from CLAUDE.md). These helpers exist in `get_adherence_report.py` too. When a third tool needs them, extract to a shared transit utility. Do NOT import from `get_adherence_report` — that creates a cross-tool coupling.
10. **Mock data types must match schema field types exactly** — `DriverInfo` uses `list[str]` for `license_categories` and `qualified_route_ids`. The mock data dicts MUST have actual `list[str]` values, not tuples or strings.

## Notes

- **Mock → Real migration path:** When CMS Phase 2 adds driver management, replace `driver_data.py` with a `driver_client.py` that calls the tRPC API via httpx. Add `cms_api_base_url: str` to Settings. The tool function's `get_driver_availability()` call signature stays identical.
- **Mock data is deterministic:** The date-based variation uses `hash(date_str) % 3` so the same date always returns the same result. This makes tests reliable and debugging reproducible.
- **No new dependencies:** This is the only transit tool that uses zero external libraries. The mock provider is pure Python stdlib.
- **This completes the transit tool suite:** All 5 transit tools from the PRD will be implemented after this. The next tool category is the 4 Obsidian vault tools.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed the "Known Pitfalls" section
- [ ] Understood the solution approach (mock data provider, NOT CMS API client)
- [ ] Clear on task execution order (schemas → mock data → tool → agent registration → tests)
- [ ] Validation commands are executable in this environment
