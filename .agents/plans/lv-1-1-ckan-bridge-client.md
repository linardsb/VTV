# Plan: LV-1.1 CKAN data.gov.lv Bridge Client

## Context

ATD intercity GTFS data is queryable via CKAN Datastore SQL API at `data.gov.lv` — zero infrastructure needed. This gives the agent immediate intercity data access (10K stops, all regional routes) while the full GTFS importer is extended for multi-city. CKAN becomes a fallback after the local DB is primary.

**Creates:**
1. `app/transit/ckan_client.py` — async CKAN Datastore SQL API client with Redis caching (5 min TTL), pagination (>32K rows), rate limiting (1 req/s)
2. `app/core/agents/tools/transit/search_intercity.py` — 2 agent tools: `search_intercity_stops`, `search_intercity_routes`
3. Config additions, tool registration, tests

## Security Context Assessment

| Context | Active | Rationale |
|---------|--------|-----------|
| CTX-AUTH | No | No auth changes |
| CTX-RBAC | Yes | New agent tools accessible via chat endpoint (inherits existing auth) |
| CTX-INPUT | Yes | SQL queries constructed from user input → parameterize via CKAN API |
| CTX-AGENT | Yes | New agent tools — docstrings, output sanitization, no credential exposure |
| CTX-FILE | No | No file handling |
| CTX-INFRA | No | No Docker/nginx changes |

**Key security requirements:**
- SQL injection prevention: CKAN Datastore SQL API accepts raw SQL — must sanitize/parameterize all user input before embedding in SQL strings
- No credential exposure in tool responses or logs
- Agent tool docstrings follow 5-principle format for LLM selection guidance
- Rate limiting protects data.gov.lv from excessive requests

## Research Summary

### Reference Files

| File | Role |
|------|------|
| `app/transit/historical_gtfs_importer.py` | Reference for data.gov.lv CKAN API integration, httpx patterns |
| `app/core/agents/tools/transit/search_stops.py` | Reference for agent tool structure, validation, response format |
| `app/core/agents/tools/transit/deps.py` | `UnifiedDeps` dataclass — add `ckan_http_client` field |
| `app/core/agents/agent.py:130-155` | Tool registration list — add 2 new imports + tools |
| `app/core/config.py:398-399` | Existing `data_gov_lv_*` settings — add `ckan_*` settings nearby |
| `app/core/redis.py` | `get_redis()` singleton for cache operations |
| `app/core/agents/tools/transit/schemas.py` | Response dataclasses — add intercity schemas |
| `app/shared/geo.py` | `haversine_distance()` for proximity search |
| `app/core/agents/exceptions.py` | `TransitDataError` for error wrapping |
| `app/core/logging.py` | `get_logger()` for structured logging |

### VSA Pattern

Follow `search_stops.py` as the primary template for agent tool structure:
- Module-level constants for limits/defaults
- `_validate_*` helper → `str | None` error message
- Main tool function: `async def tool_name(ctx: RunContext[UnifiedDeps], ...) -> str`
- Returns JSON string on success, actionable error message on failure
- Structured logging with `transit.ckan.*` domain prefix

### Existing Shared Utilities

- `haversine_distance(lat1, lon1, lat2, lon2) -> float` (meters) from `app.shared.geo`
- `get_redis() -> Redis` from `app.core.redis`
- `get_logger(__name__)` from `app.core.logging`
- `TransitDataError` from `app.core.agents.exceptions`

## Test Landscape

### Existing Test Patterns
- **httpx mocking:** `AsyncMock()` on client methods, `MagicMock()` for response objects with `.json()`, `.raise_for_status()`
- **Redis mocking:** `@patch("module.get_redis")` → `AsyncMock()` with `.set()`, `.get()`, `.mget()`
- **Agent tool mocking:** `_make_ctx() -> MagicMock` factory creating `ctx.deps.settings`, `ctx.deps.transit_http_client`
- **Template files:** `test_historical_gtfs_importer.py` (CKAN API), `test_search_stops.py` (agent tool)
- **Markers:** `@pytest.mark.asyncio` for all async tests; `@pytest.mark.integration` only for real DB
- **Return annotations required** on all helper functions

### Existing Fixtures
- `app/core/agents/tests/conftest.py`: `_reset_provider_breakers` (autouse), `_reset_skill_cache` (autouse)
- `app/transit/tests/conftest.py`: `make_eticket_*` factories
- `app/tests/conftest.py`: `test_db_session`, `test_db_engine`

## Type Check Baseline

| Directory | pyright | mypy |
|-----------|---------|------|
| `app/transit/` | 0 errors | 0 errors (38 files) |
| `app/core/agents/` | 0 errors | 0 errors (116 files) |

**Target:** Zero new errors after implementation.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/transit/ckan_client.py` | CKAN Datastore SQL API client class |
| CREATE | `app/core/agents/tools/transit/search_intercity.py` | 2 agent tools |
| UPDATE | `app/core/agents/tools/transit/deps.py` | Add `ckan_http_client` to `UnifiedDeps` |
| UPDATE | `app/core/agents/agent.py` | Import + register 2 new tools |
| UPDATE | `app/core/config.py` | Add `ckan_*` config fields |
| CREATE | `app/transit/tests/test_ckan_client.py` | CKANClient unit tests |
| CREATE | `app/core/agents/tools/transit/tests/test_search_intercity.py` | Agent tool unit tests |

## Implementation Steps

### Step 1: Add config fields

**File:** `app/core/config.py`
**Action:** UPDATE — add after line 399 (after `data_gov_lv_dataset_id`)

```python
# CKAN Datastore SQL API (LV-1.1 — intercity transit data)
ckan_datastore_sql_url: str = "https://data.gov.lv/dati/api/3/action/datastore_search_sql"
ckan_cache_ttl_s: int = 300
ckan_rate_limit_delay_s: float = 1.0
```

**CKAN resource IDs** — hardcode as constants in `ckan_client.py` (not config) since they're tied to the ATD dataset structure and don't change per environment.

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Create CKANClient

**File:** `app/transit/ckan_client.py`
**Action:** CREATE

**Class: `CKANClient`**
- Constructor: `__init__(self, http_client: httpx.AsyncClient, settings: Settings)`
- `CKAN_RESOURCES: dict[str, str]` — mapping table names → resource IDs for ATD intercity dataset:
  - `stops`, `routes`, `trips`, `stop_times`, `shapes`, `calendar`, `calendar_dates`, `fare_attributes`, `fare_rules`, `agency`
- Core method: `async def query_sql(self, sql: str) -> list[dict[str, Any]]`
  - POST to `settings.ckan_datastore_sql_url` with `{"sql": sql}`
  - Parse response: `result["records"]`
  - Redis caching: key `ckan:{sha256(sql)[:16]}`, TTL from `settings.ckan_cache_ttl_s`
  - Rate limiting: `asyncio.Lock` + `time.monotonic()` tracking, sleep if `< ckan_rate_limit_delay_s`
  - Pagination: if result contains 32000 records (CKAN default limit), auto-fetch remaining via `OFFSET` and `LIMIT 32000`
  - Error handling: catch `httpx.HTTPError`, `httpx.TimeoutException` → log + raise `TransitDataError`
- Helper: `async def _get_cached(self, cache_key: str) -> list[dict[str, Any]] | None`
- Helper: `async def _set_cache(self, cache_key: str, data: list[dict[str, Any]]) -> None`
- Helper: `def _cache_key(self, sql: str) -> str` — `ckan:{sha256(sql)[:16]}`

**SQL safety:** The CKAN API is read-only (SELECT only). Still, sanitize input:
- Escape single quotes in user-provided values (double them: `'` → `''`)
- Never embed raw user input — use helper `_escape_value(val: str) -> str`
- Log SQL queries at debug level (never at info — may contain PII like stop names)

**Logging events:**
- `transit.ckan.query_started` (sql_hash, cached=bool)
- `transit.ckan.query_completed` (sql_hash, record_count, elapsed_ms, cached=bool)
- `transit.ckan.query_failed` (sql_hash, error)
- `transit.ckan.cache_hit` / `transit.ckan.cache_miss`
- `transit.ckan.pagination_needed` (total_fetched, page_count)
- `transit.ckan.rate_limited` (wait_s)

**Validation:** `uv run ruff format app/transit/ckan_client.py && uv run ruff check --fix app/transit/ckan_client.py && uv run pyright app/transit/ckan_client.py && uv run mypy app/transit/ckan_client.py`

### Step 3: Update UnifiedDeps

**File:** `app/core/agents/tools/transit/deps.py`
**Action:** UPDATE

Add `ckan_http_client: httpx.AsyncClient | None = None` to `UnifiedDeps` dataclass (optional, defaults to `None` so existing tests don't break).

In `create_unified_deps()`, create the CKAN client:
```python
ckan_client = httpx.AsyncClient(
    timeout=httpx.Timeout(15.0, connect=5.0),
    limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
)
```

Pass it into the `UnifiedDeps` constructor.

**Validation:** `uv run ruff check app/core/agents/tools/transit/deps.py && uv run pyright app/core/agents/tools/transit/deps.py`

### Step 4: Create agent tools

**File:** `app/core/agents/tools/transit/search_intercity.py`
**Action:** CREATE

**Two functions in one file** (they share the CKANClient dependency and intercity domain):

#### `search_intercity_stops`

```python
async def search_intercity_stops(
    ctx: RunContext[UnifiedDeps],
    query: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    limit: int = 10,
) -> str:
```

**Docstring (5-principle format):**
- WHEN TO USE: User asks about intercity/regional stops outside Riga (Liepāja, Ventspils, Jelgava, etc.), ATD bus stops, or "starppilsētu pieturas"
- WHEN NOT TO USE: For Riga city stops (use `search_stops`). For Riga municipal bus data.
- COMPOSITION: Use this to find intercity stop names/IDs, then use results to filter `search_intercity_routes`.
- Args: `query` for name search, `latitude`+`longitude` for proximity (Haversine in SQL), `limit` (max 50)
- Returns: JSON with stops array (stop_id, stop_name, stop_lat, stop_lon, distance_m if proximity)

**Logic:**
1. Validate params (either `query` or `lat/lon` required)
2. Build SQL: name search uses `LOWER(stop_name) LIKE LOWER('%{escaped_query}%')`, proximity uses `ORDER BY` with Haversine formula in SQL
3. Call `CKANClient.query_sql(sql)`
4. If proximity search, compute `haversine_distance` in Python for the `distance_m` field
5. Return JSON string

#### `search_intercity_routes`

```python
async def search_intercity_routes(
    ctx: RunContext[UnifiedDeps],
    query: str | None = None,
    stop_name: str | None = None,
) -> str:
```

**Docstring (5-principle format):**
- WHEN TO USE: User asks about intercity/regional bus routes, "Which buses go to Liepāja?", "starppilsētu maršruti", ATD routes
- WHEN NOT TO USE: For Riga city routes (use `query_bus_status` or `get_route_schedule`)
- COMPOSITION: Use `search_intercity_stops` first to resolve stop names, then pass the stop name here for filtering
- Args: `query` for route name/number search, `stop_name` for routes passing through a specific stop
- Returns: JSON with routes array (route_id, route_short_name, route_long_name, agency_name)

**Logic:**
1. Validate params (at least one of `query` or `stop_name`)
2. Build SQL: route search via `LOWER(route_long_name) LIKE ...` or join through `trips` → `stop_times` → `stops` for stop-name filtering
3. Call `CKANClient.query_sql(sql)`
4. Return JSON string

**Shared helpers in the file:**
- `_get_ckan_client(ctx: RunContext[UnifiedDeps]) -> CKANClient` — constructs from `ctx.deps.ckan_http_client` and `ctx.deps.settings`; raises `TransitDataError` if `ckan_http_client` is None
- `_escape_ckan_value(val: str) -> str` — escape single quotes, strip control chars

**Validation:** `uv run ruff format app/core/agents/tools/transit/search_intercity.py && uv run ruff check --fix app/core/agents/tools/transit/search_intercity.py && uv run pyright app/core/agents/tools/transit/search_intercity.py`

### Step 5: Register tools in agent.py

**File:** `app/core/agents/agent.py`
**Action:** UPDATE

Add imports:
```python
from app.core.agents.tools.transit.search_intercity import (
    search_intercity_routes,
    search_intercity_stops,
)
```

Add to tools list after `run_analytics_sql`:
```python
search_intercity_stops,
search_intercity_routes,
```

Update system prompt to mention intercity capability (append to transit glossary):
```
"- starppilsētu (intercity) | reģionāls (regional) | ATD (Autotransporta direkcija)\n"
```

**Validation:** `uv run ruff check app/core/agents/agent.py && uv run pyright app/core/agents/agent.py`

### Step 6: Create CKANClient tests

**File:** `app/transit/tests/test_ckan_client.py`
**Action:** CREATE

**Tests (12+):**

| Test | What it verifies |
|------|-----------------|
| `test_query_sql_success` | Happy path: POST → parse records |
| `test_query_sql_cached` | Second call returns from Redis, no HTTP |
| `test_query_sql_cache_miss` | First call misses cache, makes HTTP request |
| `test_query_sql_pagination` | 32000 records → auto-fetches page 2 |
| `test_query_sql_pagination_exact_limit` | Exactly 32000 records, page 2 empty |
| `test_query_sql_rate_limiting` | Second call within 1s delays |
| `test_query_sql_http_error` | `httpx.HTTPError` → `TransitDataError` |
| `test_query_sql_timeout` | `httpx.TimeoutException` → `TransitDataError` |
| `test_query_sql_invalid_json` | Malformed response → `TransitDataError` |
| `test_cache_key_deterministic` | Same SQL → same cache key |
| `test_cache_key_different_sql` | Different SQL → different cache key |
| `test_escape_value` | Single quotes escaped, control chars stripped |

**Mock patterns:**
- `httpx.AsyncClient.post` → `AsyncMock` with `MagicMock` response
- `get_redis` → `AsyncMock` with `.get()`, `.set()`
- `time.monotonic` → patch for rate limit testing

**Validation:** `uv run pytest app/transit/tests/test_ckan_client.py -v`

### Step 7: Create agent tool tests

**File:** `app/core/agents/tools/transit/tests/test_search_intercity.py`
**Action:** CREATE

**Tests (12+):**

| Test | What it verifies |
|------|-----------------|
| `test_search_stops_by_name` | Name query → LIKE SQL → JSON result |
| `test_search_stops_by_proximity` | lat/lon → Haversine SQL → sorted results |
| `test_search_stops_no_params` | No query or lat/lon → actionable error message |
| `test_search_stops_limit_clamped` | limit > 50 → clamped to 50 |
| `test_search_stops_ckan_error` | CKANClient raises → graceful error string |
| `test_search_stops_empty_results` | No matches → empty array JSON |
| `test_search_routes_by_name` | Route name query → JSON result |
| `test_search_routes_by_stop` | Stop name filter → join SQL → JSON result |
| `test_search_routes_no_params` | No query or stop → actionable error message |
| `test_search_routes_ckan_error` | CKANClient raises → graceful error string |
| `test_search_routes_empty_results` | No matches → empty array JSON |
| `test_escape_ckan_value` | SQL injection attempt → escaped |

**Mock pattern:**
```python
def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.deps.ckan_http_client = AsyncMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.ckan_datastore_sql_url = "https://data.gov.lv/test"
    ctx.deps.settings.ckan_cache_ttl_s = 300
    ctx.deps.settings.ckan_rate_limit_delay_s = 0.0  # No delay in tests
    ctx.deps.db_session_factory = MagicMock()
    return ctx
```

Patch `CKANClient.query_sql` for tool-level tests (don't re-test HTTP layer).

**Validation:** `uv run pytest app/core/agents/tools/transit/tests/test_search_intercity.py -v`

## CKAN Resource IDs

These are the ATD intercity GTFS resource IDs on data.gov.lv. Store as constants in `ckan_client.py`:

```python
# ATD intercity GTFS dataset resource IDs (data.gov.lv)
# Dataset: https://data.gov.lv/dati/lv/dataset/marsrutu-saraksti-gtfs-formata
CKAN_RESOURCES: dict[str, str] = {
    "agency": "<resource_id>",       # To be filled from actual dataset
    "stops": "<resource_id>",
    "routes": "<resource_id>",
    "trips": "<resource_id>",
    "stop_times": "<resource_id>",
    "calendar": "<resource_id>",
    "calendar_dates": "<resource_id>",
    "shapes": "<resource_id>",
}
```

**IMPORTANT:** Before implementation, fetch actual resource IDs from data.gov.lv:
```bash
curl -s "https://data.gov.lv/dati/api/3/action/package_show?id=marsrutu-saraksti-gtfs-formata" | jq '.result.resources[] | {name, id, format}'
```

## Preflight Warnings

- `app/core/agents/agent.py:130-155`: Tool list is a plain Python list — adding items is safe, but the comment counts (e.g., "Transit (7 read-only + 1 analytics)") must be updated
- `app/core/agents/tools/transit/deps.py:21-38`: `UnifiedDeps` is a dataclass — new optional fields with defaults are backwards-compatible
- `app/core/agents/tools/transit/deps.py:45-82`: `create_unified_deps()` constructs both HTTP clients — must add CKAN client creation here
- `SYSTEM_PROMPT` in `agent.py` references "13 tools" — update to "15 tools" after adding 2 new ones
- `CLAUDE.md` references "13 tools (7 transit + 4 Obsidian vault + 1 knowledge base + 1 skills management)" — update after implementation

## Security Checklist

- [ ] User input in SQL queries is escaped via `_escape_ckan_value()` (single quotes doubled, control chars stripped)
- [ ] No raw user input embedded in SQL without escaping
- [ ] CKAN API URL comes from config (not hardcoded in tool)
- [ ] Error messages don't expose CKAN resource IDs or internal SQL
- [ ] Logs use `sql_hash` (never raw SQL with user input)
- [ ] Tool responses don't include API keys or internal URLs
- [ ] Rate limiting prevents hammering data.gov.lv
- [ ] Redis cache keys are deterministic (sha256) — no cache poisoning vector
- [ ] `limit` parameter is clamped to prevent excessive data retrieval
- [ ] Agent tools inherit existing auth from chat endpoint (no new auth needed)

## Verification

- [ ] `uv run ruff format app/transit/ckan_client.py app/core/agents/tools/transit/search_intercity.py`
- [ ] `uv run ruff check app/transit/ app/core/agents/tools/transit/`
- [ ] `uv run mypy app/transit/ app/core/agents/`
- [ ] `uv run pyright app/transit/ app/core/agents/`
- [ ] `uv run pytest app/transit/tests/test_ckan_client.py -v` — all pass
- [ ] `uv run pytest app/core/agents/tools/transit/tests/test_search_intercity.py -v` — all pass
- [ ] `uv run pytest app/tests/test_security.py -v` — no regressions
- [ ] Pyright errors ≤ baseline (0 errors for both directories)
- [ ] `make check` passes (full suite)
