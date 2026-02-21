# Code Review: app/schedules/

**Reviewer:** Claude Opus 4.6
**Date:** 2026-02-21
**Module:** Schedule Management (22 REST endpoints, GTFS ZIP import)
**Files Reviewed:** schemas.py, models.py, repository.py, service.py, exceptions.py, routes.py, gtfs_import.py, tests/conftest.py, tests/test_routes.py, tests/test_service.py, tests/test_gtfs_import.py

---

## Summary

The schedules feature is the largest vertical slice in the VTV codebase (22 endpoints, ~1,200 lines across 7 source files). Overall architecture is solid: clean layer separation, proper exception hierarchy, comprehensive Pydantic validation on schemas, and well-structured GTFS import with parallel reference resolution. The GTFS parser is well-designed with its deferred FK resolution pattern using parallel reference lists.

However, the review identified **3 Critical**, **6 High**, **8 Medium**, and **7 Low** severity issues across security, correctness, performance, and testing gaps.

---

## Findings

### Critical

**C1. No file upload validation on GTFS import endpoint -- ZIP bomb / memory exhaustion**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/routes.py`, line 326
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/service.py`, line 539
- **Standard:** Security (4)
- The import endpoint reads the entire uploaded file into memory with `await file.read()` and passes raw bytes to the parser. There is no validation of:
  - **File size** -- The global `BodySizeLimitMiddleware` caps requests at 100KB, but GTFS ZIP files for even a small city can be 5-50MB. This means the import endpoint is effectively broken for real-world GTFS feeds, OR the middleware limit will need to be raised, at which point there's no per-endpoint size control.
  - **Content type** -- No check that the uploaded file is actually a ZIP (`file.content_type`).
  - **ZIP bomb protection** -- `zipfile.ZipFile` in `gtfs_import.py` line 76 opens the ZIP without checking the decompressed size. A malicious 100KB ZIP could decompress to gigabytes.
  - **File count** -- No limit on the number of entries in the ZIP.
- **Impact:** Denial of service via memory exhaustion. An attacker could upload a crafted ZIP that expands to consume all available memory.
- **Recommendation:** Add content-type validation, a dedicated file size limit for the import endpoint (e.g., 50MB), and decompression size limits in the GTFS parser. Consider streaming the ZIP processing rather than loading the full file into memory.

**C2. Wrong exception type used for duplicate agency creation**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/service.py`, lines 97-99
- **Standard:** Error Handling (3)
- `create_agency()` raises `RouteAlreadyExistsError` when a duplicate agency is detected. This is semantically incorrect -- it should raise an `AgencyAlreadyExistsError`. The error message mentions "Agency" but the exception type says "Route", which produces a misleading `type` field in the API error response (`RouteAlreadyExistsError` instead of the expected agency-related error).
- **Impact:** Confusing error responses for API consumers, incorrect error type in logs and monitoring.
- **Recommendation:** Create `AgencyAlreadyExistsError(ValidationError)` in `exceptions.py` and use it in `create_agency()`.

**C3. Wrong exception type used for missing calendar date exception**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/service.py`, lines 368-371
- **Standard:** Error Handling (3)
- `remove_calendar_exception()` raises `StopTimeNotFoundError` when a calendar date exception is not found. This is semantically wrong -- a calendar date exception is not a stop time. The docstring even documents `StopTimeNotFoundError` as the exception, compounding the confusion.
- **Impact:** Misleading 404 error responses (`StopTimeNotFoundError` when the entity is a calendar date exception), wrong error type in monitoring/logs.
- **Recommendation:** Create `CalendarDateNotFoundError(NotFoundError)` in `exceptions.py` and use it here. Alternatively, reuse the existing `CalendarNotFoundError` with a descriptive message, though a dedicated exception is cleaner.

---

### High

**H1. GTFS import reads all stops into memory with hardcoded 100K limit**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/service.py`, line 560
- **Standard:** Performance (5)
- `all_stops = await stop_repo.list(offset=0, limit=100000, active_only=False)` loads up to 100,000 stop records into memory to build the `stop_map`. For a production system with many stops, this is wasteful. Additionally, the hardcoded `100000` limit means if a system has more stops, the import will silently produce incorrect results (stop_times referencing stops beyond the limit will be skipped).
- **Recommendation:** Use a dedicated repository method that returns only `(gtfs_stop_id, id)` tuples, or paginate through all stops. At minimum, remove the hardcoded limit and use a streaming approach.

**H2. Validate endpoint loads all data into memory -- N+1 query pattern**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/service.py`, lines 660-721
- **Standard:** Performance (5)
- `validate_schedule()` loads all calendars (limit 100K), all trips (limit 100K), then for each unique route_id and calendar_id does individual `get_route()`/`get_calendar()` lookups (N+1), and then for every single trip calls `list_stop_times()` (another N queries). For a real GTFS feed with thousands of trips, this will generate thousands of database queries.
- **Recommendation:** Use batch queries with `WHERE id IN (...)` for route/calendar existence checks. Load all stop_times in a single query grouped by trip_id, or use SQL JOINs to validate referential integrity in one or two queries.

**H3. `replace_stop_times` in repository is not atomic with the trip existence check**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/repository.py`, lines 559-582
- **Standard:** Error Handling (3), Architecture (1)
- `replace_stop_times()` deletes all existing stop times and inserts new ones, with a `commit()` at line 579. If the insert loop fails partway through (e.g., FK constraint violation on a bad `stop_id`), the delete has already been committed and the trip loses all its stop times. This should be wrapped in an explicit transaction or use `flush()` with a single commit at the service layer.
- **Recommendation:** Convert the method to use `flush()` instead of `commit()`, and let the service layer handle the commit. Alternatively, use `begin_nested()` (savepoint) to make the delete+insert atomic.

**H4. ILIKE search pattern is not sanitized for SQL wildcards**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/repository.py`, lines 152-154
- **Standard:** Security (4)
- The search parameter is interpolated into an ILIKE pattern as `f"%{search}%"`. If a user passes `%` or `_` characters in their search query, these are interpreted as SQL wildcards, allowing unintended pattern matching. For example, searching for `%` would match every route.
- **Recommendation:** Escape `%` and `_` characters in the search string before wrapping in wildcards. SQLAlchemy doesn't auto-escape these for `ilike()`.

**H5. GTFS import wraps all exceptions as `GTFSImportError`, masking the original type**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/service.py`, lines 640-647
- **Standard:** Error Handling (3)
- The `except Exception as e` block at line 640 catches every exception (including `ValueError`, `KeyError`, `zipfile.BadZipFile`) and wraps it as `GTFSImportError`. Since `GTFSImportError` inherits from `DatabaseError`, it maps to HTTP 500. However, an invalid ZIP file (user error) should arguably return 422 (unprocessable), not 500.
- **Recommendation:** Catch specific exception types: `zipfile.BadZipFile` and `csv.Error` should raise a validation error (422). Only unexpected exceptions should become `GTFSImportError` (500). Also, the broad `except Exception` catches `CancelledError` on Python 3.12+ (which no longer inherits from `BaseException` -- correction: it does inherit from `BaseException` in 3.12+, but future-proofing is wise).

**H6. No `AgencyNotFoundError` -- missing agency endpoint**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/exceptions.py`, `/Users/Berzins/Desktop/VTV/app/schedules/routes.py`
- **Standard:** Architecture (1), Error Handling (3)
- There are endpoints to list and create agencies, but no GET/PATCH/DELETE endpoints for individual agencies. Meanwhile, the `create_route` operation accepts an `agency_id` FK. If the referenced agency doesn't exist, the database will raise an IntegrityError at commit time, producing an unhandled 500 error instead of a descriptive 404/422.
- **Recommendation:** Either add agency CRUD endpoints (GET/PATCH/DELETE by ID) or add FK validation in `create_route()` and `create_trip()` service methods to verify the referenced agency exists before attempting creation.

---

### Medium

**M1. `CalendarCreate` schema lacks `start_date < end_date` validation**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/schemas.py`, lines 87-99
- **Standard:** Error Handling (3), Code Quality (8)
- The validation endpoint (`validate_schedule`) checks for `start_date > end_date`, but the `CalendarCreate` schema allows creating calendars with inverted dates. This means invalid data can enter the database and is only caught later during validation.
- **Recommendation:** Add a `@model_validator(mode='after')` to `CalendarCreate` and `CalendarUpdate` that verifies `start_date <= end_date` when both are provided.

**M2. Inconsistent repository patterns -- some methods accept models, others accept schemas**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/repository.py`
- **Standard:** Architecture (1)
- `create_agency()` (line 39) accepts an `Agency` model instance, while `create_route()` (line 90) accepts a `RouteCreate` schema and does the conversion internally. Similarly, `create_calendar()` takes a `Calendar` model, but `create_route` takes `RouteCreate`. This inconsistency makes the API surface confusing and harder to maintain.
- **Recommendation:** Standardize on one pattern. The VTV VSA patterns document recommends repositories accept schemas and return models.

**M3. `list_agencies()` lacks pagination**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/repository.py`, lines 79-86
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/routes.py`, line 46
- **Standard:** Performance (5)
- `list_agencies()` returns all agencies without pagination. The route endpoint also returns `list[AgencyResponse]` rather than a `PaginatedResponse`. While there are typically few agencies, this is inconsistent with the paginated pattern used for routes, calendars, and trips.
- **Recommendation:** Add pagination to `list_agencies()` for consistency, or document why agencies are exempt (typically <10 records).

**M4. No unique constraint on `(trip_id, stop_sequence)` in StopTime model**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/models.py`, lines 100-120
- **Standard:** Data Integrity
- The `StopTime` model allows duplicate `stop_sequence` values for the same trip at the database level. The validation endpoint checks for non-sequential ordering but doesn't prevent duplicates at the schema or model level.
- **Recommendation:** Add `__table_args__ = (UniqueConstraint('trip_id', 'stop_sequence', name='uq_stop_time_trip_seq'),)` to prevent data corruption.

**M5. No unique constraint on `(calendar_id, date)` in CalendarDate model**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/models.py`, lines 69-79
- **Standard:** Data Integrity
- Multiple calendar date exceptions can be created for the same date on the same calendar, which violates GTFS semantics (each date should have at most one exception type per service).
- **Recommendation:** Add `__table_args__ = (UniqueConstraint('calendar_id', 'date', name='uq_calendar_date'),)`.

**M6. `arrival_time` regex allows invalid times like `99:99:99`**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/schemas.py`, lines 205-209
- **Standard:** Security (4), Error Handling (3)
- The regex `^\d{2}:\d{2}:\d{2}$` validates format but not value ranges. It accepts `99:99:99` or `00:61:00`. While GTFS allows times >24:00:00 for overnight trips, minutes and seconds should be 0-59.
- **Recommendation:** Add a `field_validator` that parses hours/minutes/seconds and validates minutes < 60 and seconds < 60. Hours can exceed 24 (GTFS spec).

**M7. GTFS import `_parse_stops` doesn't set `parent_station_id`**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/gtfs_import.py`, lines 460-501
- **Standard:** Code Quality (8)
- The `_parse_stops` method creates `Stop` objects but doesn't handle the `parent_station` GTFS field. For complex station hierarchies (stations with platforms), this means parent relationships are silently dropped during import.
- **Recommendation:** Parse `parent_station` from stops.txt and resolve the relationship after initial stop creation, or add a warning when parent_station data is present but ignored.

**M8. Test functions marked `@pytest.mark.asyncio` in `test_gtfs_import.py` but are not actually async**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/tests/test_gtfs_import.py`, all test functions
- **Standard:** Testing (6)
- Every test in `test_gtfs_import.py` is marked with `@pytest.mark.asyncio` but none of them use `await`. The `GTFSImporter.parse()` method is synchronous. The tests work because pytest-asyncio handles this, but the async marking is misleading.
- **Recommendation:** Remove `@pytest.mark.asyncio` from all tests in this file since the parser is synchronous.

---

### Low

**L1. `_ = file_names` pattern is unnecessary**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/gtfs_import.py`, lines 170, 213, 259, 307, 352, 412, 474
- **Standard:** Code Quality (8)
- Every `_parse_*` method receives `file_names` as a parameter and then immediately discards it with `_ = file_names`. The `file_names` parameter is never used because `_read_csv` checks `zf.namelist()` directly. This parameter should be removed from all internal parsing methods.
- **Recommendation:** Remove `file_names` from all `_parse_*` method signatures. The `parse()` method already reads `file_names` once and doesn't need to pass it down.

**L2. Missing `AgencyCreate` update schema**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/schemas.py`
- **Standard:** Architecture (1)
- There is `RouteUpdate`, `CalendarUpdate`, and `TripUpdate` but no `AgencyUpdate`. This is consistent with the lack of an agency update endpoint, but if agency CRUD is planned, the update schema should be added alongside the endpoint.
- **Recommendation:** Track as technical debt; create when PATCH/PUT agency endpoint is added.

**L3. `_mock_service()` helper creates a new mock every time, leading to repetitive setup**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/tests/test_routes.py`, line 34
- **Standard:** Testing (6)
- Every route test creates its own `TestClient(app)` and sets up dependency overrides in a try/finally block. This boilerplate could be reduced with a fixture.
- **Recommendation:** Create a `@pytest.fixture` that yields a `(client, mock_service)` tuple with automatic cleanup.

**L4. `_TIME_PATTERN` duplicates the schema regex**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/service.py`, line 55
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/schemas.py`, lines 206, 209
- **Standard:** Code Quality (8) -- DRY
- The time validation regex `^\d{2}:\d{2}:\d{2}$` is defined both in the schema (as a `pattern` on `StopTimeCreate`) and in the service (as `_TIME_PATTERN`). These could drift apart.
- **Recommendation:** Extract the pattern to a shared constant and reference it in both places.

**L5. Unused import in `service.py`**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/service.py`, line 5
- **Standard:** Code Quality (8)
- The `re` module is imported at line 5 and only used at line 55 to compile `_TIME_PATTERN`. This is fine, but `_TIME_PATTERN` itself is only used in `validate_schedule()`. If validation is refactored, this import may become stale.
- **Recommendation:** No immediate action needed; just noting the tight coupling.

**L6. Test coverage gaps for edge cases**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/tests/test_service.py`
- **Standard:** Testing (6)
- Missing test cases:
  - `update_calendar` when calendar not found
  - `update_trip` when trip not found
  - `get_trip` when trip not found
  - `add_calendar_exception` when calendar not found
  - `remove_calendar_exception` when exception not found
  - `replace_stop_times` when trip not found
  - Calendar date range validation in `validate_schedule` (start_date > end_date)
  - `import_gtfs` when import fails (exception path)
- **Recommendation:** Add these edge case tests to improve coverage of error paths.

**L7. `list_calendar_dates` endpoint is missing**
- **File:** `/Users/Berzins/Desktop/VTV/app/schedules/routes.py`
- **Standard:** Architecture (1)
- There is `add_calendar_exception` and `remove_calendar_exception`, but no endpoint to list all exceptions for a calendar. The repository method `list_calendar_dates(calendar_id)` exists (line 345) but is only called internally (unused from routes).
- **Recommendation:** Add a `GET /calendars/{calendar_id}/exceptions` endpoint, or include exceptions in the `CalendarResponse` schema.

---

## Recommendations

### Immediate (address before next release)
1. **Fix exception types** (C2, C3) -- Create `AgencyAlreadyExistsError` and `CalendarDateNotFoundError` and use them in the correct service methods. This is a one-file change to `exceptions.py` and two-line fix in `service.py`.
2. **Add ZIP upload validation** (C1) -- Validate content type, add a per-endpoint size limit for the import route, and add decompression size checks in the GTFS parser.
3. **Fix `replace_stop_times` atomicity** (H3) -- Switch to `flush()` instead of `commit()` and commit in the service layer.
4. **Escape SQL wildcards** (H4) -- Add a utility function to escape `%` and `_` before wrapping in the ILIKE pattern.

### Short-term (within next sprint)
5. **Add database constraints** (M4, M5) -- Add unique constraints on `(trip_id, stop_sequence)` and `(calendar_id, date)` via Alembic migration.
6. **Add date validation to CalendarCreate** (M1) -- `@model_validator` to ensure `start_date <= end_date`.
7. **Add time value validation** (M6) -- Validate minutes < 60 and seconds < 60 in arrival/departure times.
8. **Optimize validate endpoint** (H2) -- Replace N+1 queries with batch lookups.

### Medium-term (next iteration)
9. **Add agency CRUD endpoints** (H6, L2) -- GET/PATCH/DELETE individual agencies.
10. **Add `list_calendar_dates` endpoint** (L7) -- Or include exceptions in calendar responses.
11. **Improve test coverage** (L6) -- Add tests for all error paths.
12. **Refactor GTFS import exception handling** (H5) -- Differentiate user errors (bad ZIP) from server errors.
13. **Optimize stops loading for import** (H1) -- Dedicated query for `(gtfs_stop_id, id)` pairs.
14. **Clean up parser method signatures** (L1) -- Remove unused `file_names` parameter.
