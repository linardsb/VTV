# GTFS Merge Import — Implementation Plan

## Context

The current GTFS import (`POST /api/v1/schedules/import/gtfs`) uses a **replace-all** strategy: it calls `clear_all_schedule_data()` which deletes ALL agencies, routes, calendars, calendar_dates, trips, and stop_times before inserting the new data. This means:
- A partial ZIP (e.g., only routes.txt) wipes all other data
- Users cannot incrementally update schedules
- Every import is destructive

**Goal:** Change to a **merge/upsert** strategy where:
- Entities with matching GTFS IDs get **updated** (not duplicated)
- New entities get **created**
- Existing entities NOT in the ZIP are **preserved** (not deleted)
- Stops follow the same pattern (upsert by gtfs_stop_id)

## Files to Modify

| File | Change |
|------|--------|
| `app/schedules/repository.py` | Add `upsert_*()` methods for each entity type |
| `app/schedules/service.py` | Replace `clear_all_schedule_data()` flow with upsert flow |
| `app/schedules/schemas.py` | Extend `GTFSImportResponse` with created/updated counts |
| `app/schedules/tests/test_routes.py` | Update import test mock to match new response |
| `app/stops/repository.py` | Add `upsert_stop()` bulk method |

No new files. No migration needed (no schema changes — unique indices already exist on GTFS ID fields).

## Implementation Steps

### Step 1: Extend `GTFSImportResponse` schema

In `app/schedules/schemas.py`, add created/updated breakdown:

```python
class GTFSImportResponse(BaseModel):
    agencies_count: int          # total in ZIP
    agencies_created: int        # new
    agencies_updated: int        # existing, updated
    routes_count: int
    routes_created: int
    routes_updated: int
    calendars_count: int
    calendars_created: int
    calendars_updated: int
    calendar_dates_count: int
    calendar_dates_created: int
    calendar_dates_updated: int
    trips_count: int
    trips_created: int
    trips_updated: int
    stop_times_count: int
    stop_times_created: int
    stop_times_updated: int
    stops_count: int             # NEW: stops imported from ZIP
    stops_created: int
    stops_updated: int
    skipped_stop_times: int
    warnings: list[str]
```

### Step 2: Add bulk upsert methods to `app/schedules/repository.py`

Use PostgreSQL `ON CONFLICT ... DO UPDATE` via SQLAlchemy's `insert().on_conflict_do_update()`. Pattern for each entity:

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def bulk_upsert_agencies(self, agencies: list[Agency]) -> tuple[int, int]:
    """Upsert agencies by gtfs_agency_id. Returns (created, updated)."""
    if not agencies:
        return 0, 0
    # Count existing before upsert
    existing_ids = set()
    for a in agencies:
        result = await self.db.execute(
            select(Agency.id).where(Agency.gtfs_agency_id == a.gtfs_agency_id)
        )
        if result.scalar_one_or_none() is not None:
            existing_ids.add(a.gtfs_agency_id)

    stmt = pg_insert(Agency).values([{
        "gtfs_agency_id": a.gtfs_agency_id,
        "agency_name": a.agency_name,
        "agency_url": a.agency_url,
        "agency_timezone": a.agency_timezone,
        "agency_lang": a.agency_lang,
    } for a in agencies])
    stmt = stmt.on_conflict_do_update(
        index_elements=["gtfs_agency_id"],
        set_={col: stmt.excluded[col] for col in ["agency_name", "agency_url", "agency_timezone", "agency_lang"]},
    )
    await self.db.execute(stmt)
    await self.db.flush()

    updated = len(existing_ids)
    created = len(agencies) - updated
    return created, updated
```

Same pattern for: routes, calendars, trips. For calendar_dates and stop_times (no unique GTFS ID), use delete-by-parent + re-insert:
- `calendar_dates`: delete all for affected calendar_ids, then insert fresh
- `stop_times`: delete all for affected trip_ids, then insert fresh

### Step 3: Add bulk upsert for stops in `app/stops/repository.py`

Same `ON CONFLICT` pattern on `gtfs_stop_id`.

### Step 4: Rewrite `import_gtfs()` in `app/schedules/service.py`

Replace the current flow:
```
1. Parse ZIP
2. clear_all_schedule_data()     ← DELETE THIS
3. Bulk create everything
```

With merge flow:
```
1. Parse ZIP
2. Upsert stops (if in ZIP)     ← new
3. Upsert agencies              ← changed
4. Reload agency map (get IDs)
5. Upsert routes (with resolved agency_id)
6. Reload route map
7. Upsert calendars
8. Reload calendar map
9. Delete + re-insert calendar_dates for affected calendars
10. Upsert trips (with resolved route_id + calendar_id)
11. Reload trip map
12. Delete + re-insert stop_times for affected trips
13. Commit
14. Return response with created/updated counts
```

Key change: After each upsert, reload the map of GTFS ID → DB ID so child entities can resolve their foreign keys. This replaces the current "parallel refs" pattern which only works with fresh inserts.

### Step 5: Update test mock in `app/schedules/tests/test_routes.py`

Update `test_import_gtfs_200` mock to return the new response fields (created/updated counts).

## Verification

1. `uv run ruff format . && uv run ruff check --fix .` — formatting/lint
2. `uv run mypy app/` — type checking
3. `uv run pyright app/` — type checking
4. `uv run pytest -v -m "not integration"` — all 450+ tests pass
5. Manual test: Import the Riga GTFS ZIP twice — second import should show 0 created, N updated
