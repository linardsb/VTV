# Execution Report: GTFS Merge Import

## Summary

Changed GTFS import from replace-all strategy (clear + insert) to merge/upsert strategy. Entities matched by GTFS ID are updated in place, new entities are created, and entities not in the ZIP are preserved.

## Implementation vs Plan

| Planned | Actual | Status |
|---------|--------|--------|
| Extend GTFSImportResponse with created/updated fields | Done — added `*_created`, `*_updated` fields with `= 0` defaults | Match |
| Add bulk upsert methods to ScheduleRepository | Done — 4 upsert methods + 2 delete methods + 4 GTFS map methods + 1 helper | Match |
| Add bulk_upsert + get_gtfs_map to StopRepository | Done | Match |
| Rewrite import_gtfs to merge flow | Done — removed clear_all, uses upsert + FK resolution via GTFS maps | Match |
| Update tests | Done — rewrote 2 import tests to mock new upsert flow | Match |
| Update frontend types | Done — GTFSImportResponse interface + ResultBadge component | Match |

## Key Decisions

- **Child entities (calendar_dates, stop_times)** use delete-by-parent + re-insert rather than upsert, since they lack unique GTFS IDs.
- **`_existing_gtfs_ids` helper** uses `InstrumentedAttribute[str]` type hint to satisfy mypy with SQLAlchemy column types.
- **Dict comprehension** `{row[0]: row[1] for row in result.all()}` instead of `dict(result.all())` to satisfy mypy's `Row` vs `tuple` typing.

## Challenges

1. **mypy arg-type**: `ColumnElement[str]` vs `InstrumentedAttribute[str]` — fixed by using the correct SQLAlchemy type.
2. **mypy arg-type**: `dict(result.all())` returns `Row[tuple[str, int]]` not `tuple[str, int]` — fixed with dict comprehension.
3. **Ruff ARG002**: `_existing_gtfs_ids` initially had unused `model` parameter — removed it and updated all callers.
4. **Test mocks**: Both import tests mocked the old flow — rewrote to mock upsert methods and GTFS ref lists.

## Validation Results

- Ruff format: PASS
- Ruff check: PASS
- MyPy: PASS (0 errors, 149 files)
- Pyright: PASS (0 errors)
- Pytest: PASS (451 tests, 58 schedule-specific)
