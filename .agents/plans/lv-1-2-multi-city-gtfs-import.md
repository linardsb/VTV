# Plan: LV-1.2 Multi-City GTFS Static Import

## Feature Metadata
**Feature Type**: Enhancement (Phase 2 of multi-feed)
**Estimated Complexity**: Medium
**Primary Systems Affected**: schedules, core/config, main.py
**Depends On**: Multi-feed migration (DONE — `a1b2c3d4e5f6`)

## Context

The DB layer for multi-feed GTFS is already in place: `feed_id` columns on Agency/Route/Calendar/Trip/Shape, composite unique constraints, bulk upsert with composite conflict keys, and import/export endpoints that accept `feed_id` query params. What's **missing** is:

1. Repository `get_*_by_gtfs_id` methods don't filter by `feed_id` — manual CRUD duplicate checks will collide across feeds
2. No feed management endpoints — can't list configured feeds or see last-import status
3. No feed status tracking in DB — no `last_imported_at` per feed
4. No daily background re-import task — must trigger imports manually
5. No tests for multi-feed coexistence

### Already Implemented (DO NOT RE-IMPLEMENT)
- `feed_id` columns + composite unique constraints on all GTFS models (`models.py`)
- Migration `a1b2c3d4e5f6` with backfill
- `GTFSImporter.__init__(zip_data, feed_id)` propagation (`gtfs_import.py`)
- `import_gtfs(zip_data, feed_id="riga")` in service with feed-scoped upserts (`service.py`)
- `POST /import?feed_id=riga` endpoint (`routes.py:392`)
- `GET /export?feed_id=riga` endpoint (`routes.py:373`)
- `TransitFeedConfig` with `feed_id`, `static_url` fields (`config.py:18-27`)
- `TRANSIT_FEEDS_JSON` config parsing with legacy fallback (`config.py:97-118`)
- Bulk upsert methods using composite `(feed_id, gtfs_*_id)` conflict keys
- `get_*_gtfs_map(feed_id=None)` methods correctly scoped

## Security Context Assessment

**Active: CTX-RBAC, CTX-INPUT**
- New endpoints need `require_role("admin")` + rate limiting
- `feed_id` path param needs max_length validation
- No CTX-FILE (import endpoint already exists), no CTX-AUTH (no new auth flow)

## Type Check Baseline

- **pyright** `app/schedules/`: 0 errors, 0 warnings
- **mypy** `app/schedules/`: 0 errors
- **pyright** `app/main.py`: 0 errors
- Target: 0 regressions

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/schedules/feed_status.py` | `GTFSFeedStatus` model + `GTFSFeedStatusRepository` |
| CREATE | `app/schedules/feed_task.py` | Daily auto-import background task |
| UPDATE | `app/schedules/models.py` | Add `GTFSFeedStatus` model import/re-export |
| UPDATE | `app/schedules/schemas.py` | Add `FeedStatusResponse`, `FeedListResponse` |
| UPDATE | `app/schedules/repository.py` | Add `feed_id` param to 4 `get_*_by_gtfs_id` methods |
| UPDATE | `app/schedules/service.py` | Fix 4 duplicate-check callers + add `list_feeds`/`import_feed_from_url` |
| UPDATE | `app/schedules/routes.py` | Add `GET /feeds` + `POST /feeds/{feed_id}/import` |
| UPDATE | `app/core/config.py` | Add `gtfs_auto_import_enabled` + `gtfs_auto_import_hour_utc` settings |
| UPDATE | `app/main.py` | Start daily import task + register shutdown |
| UPDATE | `app/schedules/tests/conftest.py` | Add `make_feed_status` factory |
| CREATE | `app/schedules/tests/test_feed_management.py` | Tests for feed endpoints, task, multi-feed coexistence |
| CREATE | `alembic/versions/xxx_add_gtfs_feed_status.py` | Migration for `gtfs_feed_status` table |

## Implementation Steps

### Step 1: Feed Status Model + Migration
**File**: `app/schedules/feed_status.py` (CREATE)

Create `GTFSFeedStatus` model to track per-feed import state:
```python
class GTFSFeedStatus(Base, TimestampMixin):
    __tablename__ = "gtfs_feed_status"

    feed_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    operator_name: Mapped[str] = mapped_column(String(200), nullable=False)
    static_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_imported_at: Mapped[datetime.datetime | None]
    last_import_routes: Mapped[int] = mapped_column(Integer, default=0)
    last_import_trips: Mapped[int] = mapped_column(Integer, default=0)
    last_import_error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    auto_import_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

**Validation:** `uv run ruff format app/schedules/feed_status.py && uv run ruff check --fix app/schedules/feed_status.py && uv run pyright app/schedules/feed_status.py`

### Step 2: Alembic Migration
**File**: `alembic/versions/xxx_add_gtfs_feed_status.py` (CREATE via `make db-revision`)

Run: `make db-revision m="add gtfs_feed_status table"`

Migration creates `gtfs_feed_status` table with `feed_id` as PK. Insert seed row for "riga" from existing data using `op.execute()`:
```sql
INSERT INTO gtfs_feed_status (feed_id, operator_name, auto_import_enabled, created_at, updated_at)
VALUES ('riga', 'Rigas Satiksme', true, NOW(), NOW())
ON CONFLICT DO NOTHING
```

Downgrade: `op.drop_table("gtfs_feed_status")`

**Validation:** `make db-migrate` (if Docker running) or manual review

### Step 3: Feed Status Schemas
**File**: `app/schedules/schemas.py` (UPDATE)

Add at the end of the file:
```python
class FeedStatusResponse(BaseModel):
    """Per-feed import status."""
    feed_id: str
    operator_name: str
    static_url: str | None
    last_imported_at: datetime.datetime | None
    last_import_routes: int
    last_import_trips: int
    last_import_error: str | None
    auto_import_enabled: bool
    enabled: bool  # from TransitFeedConfig
    model_config = ConfigDict(from_attributes=True)
```

**Validation:** `uv run pyright app/schedules/schemas.py`

### Step 4: Fix Repository `get_*_by_gtfs_id` Methods
**File**: `app/schedules/repository.py` (UPDATE)

Add optional `feed_id` parameter to 4 methods. When provided, add `.where(Model.feed_id == feed_id)`:

1. `get_agency_by_gtfs_id(self, gtfs_agency_id: str, feed_id: str | None = None)` (line 97)
2. `get_route_by_gtfs_id(self, gtfs_route_id: str, feed_id: str | None = None)` (line 159)
3. `get_calendar_by_gtfs_id(self, gtfs_service_id: str, feed_id: str | None = None)` (line 316)
4. `get_trip_by_gtfs_id(self, gtfs_trip_id: str, feed_id: str | None = None)` (line 479)

Pattern for each:
```python
async def get_agency_by_gtfs_id(
    self, gtfs_agency_id: str, feed_id: str | None = None
) -> Agency | None:
    query = select(Agency).where(Agency.gtfs_agency_id == gtfs_agency_id)
    if feed_id is not None:
        query = query.where(Agency.feed_id == feed_id)
    result = await self.db.execute(query)
    return result.scalar_one_or_none()
```

Also add `GTFSFeedStatusRepository` class (or add methods to `ScheduleRepository`):
```python
async def get_feed_status(self, feed_id: str) -> GTFSFeedStatus | None
async def upsert_feed_status(self, feed_id: str, operator_name: str, **kwargs) -> GTFSFeedStatus
async def list_feed_statuses(self) -> list[GTFSFeedStatus]
```

**Validation:** `uv run pyright app/schedules/repository.py`

### Step 5: Fix Service Duplicate-Check Callers
**File**: `app/schedules/service.py` (UPDATE)

Update 4 duplicate-check calls to pass `feed_id="riga"` (manual CRUD defaults to riga feed):

1. Line 104: `await self.repository.get_agency_by_gtfs_id(data.gtfs_agency_id)` → `await self.repository.get_agency_by_gtfs_id(data.gtfs_agency_id, feed_id="riga")`
2. Line 206: `await self.repository.get_route_by_gtfs_id(data.gtfs_route_id)` → `await self.repository.get_route_by_gtfs_id(data.gtfs_route_id, feed_id="riga")`
3. Line 312: `await self.repository.get_calendar_by_gtfs_id(data.gtfs_service_id)` → `await self.repository.get_calendar_by_gtfs_id(data.gtfs_service_id, feed_id="riga")`
4. Line 487: `await self.repository.get_trip_by_gtfs_id(data.gtfs_trip_id)` → `await self.repository.get_trip_by_gtfs_id(data.gtfs_trip_id, feed_id="riga")`

Add new service methods:
```python
async def list_feeds(self) -> list[FeedStatusResponse]:
    """List all configured feeds enriched with DB import status."""

async def import_feed_from_url(self, feed_id: str, url: str) -> GTFSImportResponse:
    """Download GTFS ZIP from URL and import for the given feed."""
```

Update `import_gtfs` to upsert `GTFSFeedStatus` at the end of successful import (and on error):
```python
# After successful import, update feed status
await self.repository.upsert_feed_status(
    feed_id=feed_id,
    operator_name=feed_id,  # or from config
    last_imported_at=utcnow(),
    last_import_routes=routes_created + routes_updated,
    last_import_trips=trips_created + trips_updated,
    last_import_error=None,
)
```

**Validation:** `uv run pyright app/schedules/service.py`

### Step 6: New Endpoints
**File**: `app/schedules/routes.py` (UPDATE)

Add two endpoints:

```python
@router.get("/feeds", response_model=list[FeedStatusResponse])
@limiter.limit("30/minute")
async def list_feeds(
    request: Request,
    service: ScheduleService = Depends(get_service),
    _current_user: User = Depends(get_current_user),
) -> list[FeedStatusResponse]:
    """List all configured GTFS feeds with import status."""
    _ = request
    return await service.list_feeds()


@router.post("/feeds/{feed_id}/import", response_model=GTFSImportResponse)
@limiter.limit("5/minute")
async def import_feed_from_url(
    request: Request,
    feed_id: str = Path(..., max_length=50),
    service: ScheduleService = Depends(get_service),
    _current_user: User = Depends(require_role("admin")),
) -> GTFSImportResponse:
    """Trigger GTFS static import for a configured feed by downloading its static_url."""
    _ = request
    return await service.import_feed_from_url(feed_id)
```

**Note:** `POST /feeds/{feed_id}/import` reads the URL from `settings.transit_feeds` config — no user-supplied URL (prevents SSRF). Returns 404 if `feed_id` not in config or has no `static_url`.

**Validation:** `uv run pyright app/schedules/routes.py`

### Step 7: Config Settings
**File**: `app/core/config.py` (UPDATE)

Add to `Settings` class:
```python
gtfs_auto_import_enabled: bool = False
gtfs_auto_import_hour_utc: int = 3  # 03:00 UTC daily
```

**Validation:** `uv run pyright app/core/config.py`

### Step 8: Daily Auto-Import Background Task
**File**: `app/schedules/feed_task.py` (CREATE)

Follow `app/transit/weather_etl.py` / `app/analytics/adherence_task.py` pattern:

```python
_task: asyncio.Task[None] | None = None

async def _run_daily_feed_import() -> None:
    """Loop: sleep until next run hour, then import all enabled feeds."""
    settings = get_settings()
    logger = get_logger(__name__)
    while True:
        # Calculate sleep until next run
        now = datetime.datetime.now(datetime.UTC)
        next_run = now.replace(hour=settings.gtfs_auto_import_hour_utc, minute=0, second=0)
        if next_run <= now:
            next_run += datetime.timedelta(days=1)
        await asyncio.sleep((next_run - now).total_seconds())

        for feed in settings.transit_feeds:
            if not feed.enabled or not feed.static_url:
                continue
            try:
                async with get_db_context() as db:
                    repo = ScheduleRepository(db)
                    service = ScheduleService(repo)
                    result = await service.import_feed_from_url(feed.feed_id)
                    logger.info("schedules.feed_task.import_completed",
                                feed_id=feed.feed_id, routes=result.routes_count)
            except Exception:
                logger.error("schedules.feed_task.import_failed",
                             feed_id=feed.feed_id, exc_info=True)

async def start_feed_import_task() -> None:
    global _task
    settings = get_settings()
    if not settings.gtfs_auto_import_enabled:
        return
    _task = asyncio.create_task(_run_daily_feed_import())

async def stop_feed_import_task() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
```

**Validation:** `uv run pyright app/schedules/feed_task.py`

### Step 9: Wire Background Task into Lifespan
**File**: `app/main.py` (UPDATE)

Add imports and startup/shutdown calls following existing patterns:
- After `start_weather_etl()` (line 153): `await start_feed_import_task()`
- Add to ShutdownCoordinator: `coordinator.register(ShutdownTask(name="gtfs_feed_import", drain_timeout_s=5.0, drain=stop_feed_import_task))`

**Validation:** `uv run pyright app/main.py`

### Step 10: Test Fixtures
**File**: `app/schedules/tests/conftest.py` (UPDATE)

Add `make_feed_status` factory:
```python
def make_feed_status(**overrides: Any) -> GTFSFeedStatus:
    defaults = {
        "feed_id": "riga",
        "operator_name": "Rigas Satiksme",
        "static_url": "https://data.riga.lv/gtfs.zip",
        "last_imported_at": utcnow(),
        "last_import_routes": 50,
        "last_import_trips": 200,
        "last_import_error": None,
        "auto_import_enabled": True,
    }
    defaults.update(overrides)
    return GTFSFeedStatus(**defaults)
```

### Step 11: Tests
**File**: `app/schedules/tests/test_feed_management.py` (CREATE)

15+ tests covering:

**Repository feed_id scoping (4 tests):**
- `test_get_agency_by_gtfs_id_scoped_to_feed` — same gtfs_agency_id in two feeds returns correct one
- `test_get_route_by_gtfs_id_scoped_to_feed` — same pattern
- `test_get_calendar_by_gtfs_id_scoped_to_feed`
- `test_get_trip_by_gtfs_id_scoped_to_feed`

**Feed status CRUD (2 tests):**
- `test_upsert_feed_status_creates_new` — first upsert creates row
- `test_upsert_feed_status_updates_existing` — second upsert updates, not duplicates

**Feed list endpoint (2 tests):**
- `test_list_feeds_returns_configured_feeds` — GET /feeds returns feed list with status
- `test_list_feeds_requires_auth` — unauthenticated → 401

**Feed import endpoint (3 tests):**
- `test_import_feed_requires_admin` — editor/viewer → 403
- `test_import_feed_unknown_feed_id_404` — feed_id not in config → 404
- `test_import_feed_success` — mock httpx download + import, verify response

**Multi-feed coexistence (2 tests):**
- `test_import_two_feeds_no_collision` — import riga then atd (mock ZIPs), both stored, counts correct
- `test_reimport_feed_preserves_other` — reimport riga, verify atd routes untouched

**Background task (2 tests):**
- `test_feed_task_starts_when_enabled` — with `gtfs_auto_import_enabled=True`, task starts
- `test_feed_task_skips_disabled_feeds` — feed with `enabled=False` not imported

**Service duplicate check (2 tests):**
- `test_create_agency_same_gtfs_id_different_feed_allowed` — create agency in "atd" when same gtfs_id exists in "riga"
- `test_create_route_same_gtfs_id_different_feed_allowed`

**Validation:** `uv run pytest app/schedules/tests/test_feed_management.py -v`

### Step 12: Update Existing Tests
**File**: `app/schedules/tests/test_service.py` (UPDATE)

Update mocks for the 4 `get_*_by_gtfs_id` calls that now accept optional `feed_id`:
- Lines 58, 78: `get_route_by_gtfs_id` mock calls
- Lines 170, 184, 220, 242: `get_calendar_by_gtfs_id` mock calls
- Lines 293, 312: `get_trip_by_gtfs_id` mock calls

The mocks already use `AsyncMock(return_value=...)` which accepts any kwargs, so they should work without changes. But verify that `assert_called_once_with()` assertions (if any) are updated to include `feed_id="riga"`.

**Validation:** `uv run pytest app/schedules/tests/test_service.py -v`

## Preflight Warnings

- `test_service.py` line 559: `get_agency_gtfs_map.assert_called_once()` — uses `assert_called_once()` (no args check), safe
- `test_service.py` lines 481-487: Mock assignments use `AsyncMock(return_value=...)` — compatible with added kwargs
- No `assert_called_once_with` on `get_*_by_gtfs_id` in existing tests — signature change is safe
- Anti-pattern #11: Schema additions — `FeedStatusResponse` is new (no existing constructors to break)
- Anti-pattern #29: Optional field additions — `feed_id` param on repository methods is optional with `None` default (backward compat)

## Security Checklist

| Endpoint | Auth | Rate Limit | Validation |
|----------|------|------------|------------|
| `GET /feeds` | `get_current_user` | 30/min | N/A (read-only) |
| `POST /feeds/{feed_id}/import` | `require_role("admin")` | 5/min | `feed_id` max_length=50 via Path |

- [x] No user-supplied URLs — `static_url` comes from server config only (SSRF prevention)
- [x] `feed_id` path param validated with `max_length=50`
- [x] Error responses use `AppError` hierarchy (404 for unknown feed)
- [x] No new ILIKE queries (no `escape_like()` needed)

## Out of Scope (Follow-up)

- **Agent tools multi-feed**: `static_cache.py` loads single feed — needs `(feed_id, route_id)` keying. Separate task.
- **Cache invalidation namespacing**: `invalidate_route_cache()` doesn't scope by feed. Low priority — cache is short-TTL.
- **Create schemas `feed_id` field**: Manual CRUD defaults to "riga". Adding `feed_id` to `AgencyCreate`/`RouteCreate` is a future enhancement.

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] `GET /feeds` returns configured feeds with status
- [ ] `POST /feeds/riga/import` triggers download + import
- [ ] `POST /feeds/unknown/import` → 404
- [ ] Pyright errors = 0 (baseline was 0)
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
- [ ] Existing schedule tests still pass: `uv run pytest app/schedules/tests/ -v`
