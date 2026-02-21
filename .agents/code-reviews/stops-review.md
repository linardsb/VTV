# Code Review: app/stops/

**Reviewer:** Claude Opus 4.6
**Date:** 2026-02-21
**Module:** Stop management feature (CRUD + geolocation + proximity search)
**Files reviewed:** 12 source files (7 production + 5 test)

## Summary

The stops module is a well-structured vertical slice feature with clean layer separation, complete type annotations, proper exception hierarchy, and 33 passing unit tests. Static analysis is clean (ruff, mypy, pyright all pass with zero errors). The code follows project conventions consistently.

Key strengths:
- Textbook vertical slice: schemas -> models -> repository -> service -> exceptions -> routes
- Complete structured logging at service layer with domain.action_state pattern
- Proper Pydantic validation on all inputs (coordinates, lengths, ranges)
- Clean test pyramid: repository (9), service (14), routes (10)

Areas for improvement center on a moderate SQL wildcard injection gap, a performance concern in the proximity search, missing test coverage for several business-logic branches, and a duplicated utility function.

**Severity counts:** Critical: 0 | High: 2 | Medium: 5 | Low: 5

---

## Findings

### Critical

None.

---

### High

**H1. ILIKE wildcard injection in search parameter**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/repository.py`, lines 70 and 98
- **Standard:** 4 (Security)
- **Description:** The `search` parameter is interpolated directly into an `ilike` pattern via f-string: `Stop.stop_name.ilike(f"%{search}%")`. While SQLAlchemy parameterizes the value (preventing SQL injection), the LIKE pattern characters `%` and `_` in user input are NOT escaped. A user submitting `search=%` would match every row. A user submitting `search=____` would match all 4-character stop names. This allows users to craft wildcard patterns that bypass the intended substring-match semantics.
- **Impact:** Data leakage through pattern manipulation. Could also be used for enumeration attacks or to force expensive full-table scans by submitting complex wildcard patterns.
- **Fix:** Escape LIKE special characters before interpolation:
  ```python
  def _escape_like(value: str) -> str:
      """Escape LIKE wildcards in user input."""
      return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

  # In list() and count():
  query = query.where(Stop.stop_name.ilike(f"%{_escape_like(search)}%"))
  ```
  Note: The same pattern exists in `app/schedules/repository.py` lines 154, 185.

---

**H2. Proximity search loads ALL stops into memory**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/service.py`, line 246
- **Standard:** 5 (Performance)
- **Description:** `search_nearby` calls `self.repository.list(offset=0, limit=10000, active_only=True)` which loads up to 10,000 stop rows into Python memory on every proximity request. The README notes this is "sufficient for ~2000 stops" but the hard-coded limit of 10,000 suggests awareness that the dataset could grow. For 10,000 stops, each request allocates all rows, iterates with Haversine computation, then discards most results.
- **Impact:** At scale (5,000+ stops), this becomes a significant memory and CPU bottleneck. Each concurrent proximity request duplicates the full stop list in memory. Rate limiting at 30/min mitigates but does not eliminate the concern.
- **Recommended path:** For the current scale (~2000 stops), add an in-memory cache with a TTL (e.g., 60s) to avoid re-querying on every request. For future scaling, add a SQL-level bounding-box pre-filter:
  ```python
  # Rough bounding box pre-filter (1 degree latitude ~ 111km)
  lat_delta = radius_meters / 111_000
  lon_delta = radius_meters / (111_000 * math.cos(math.radians(lat)))
  query = query.where(
      Stop.stop_lat.between(lat - lat_delta, lat + lat_delta),
      Stop.stop_lon.between(lon - lon_delta, lon + lon_delta),
  )
  ```
  Or migrate to PostGIS when the roadmap calls for it.

---

### Medium

**M1. Duplicated `_haversine_distance` function**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/service.py`, lines 26-47
- **Standard:** 8 (Code Quality - DRY)
- **Description:** The `_haversine_distance` function is duplicated verbatim in `app/core/agents/tools/transit/search_stops.py` lines 33-53. The service.py file even has a `# NOTE: duplicated from` comment acknowledging this. Per the three-feature rule, if this is used in 2 places now, it should be extracted on the third use. However, both are production code paths (not test helpers), and the duplication creates a divergence risk.
- **Fix:** Since this is an exact duplicate of a pure utility function with no feature-specific dependencies, consider extracting to `app/shared/geo.py` now rather than waiting for a third user. The NOTE comment proves the duplication is known, and extracting a 10-line math function has near-zero risk.

---

**M2. Missing test coverage for `update_stop` duplicate GTFS ID check**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/tests/test_service.py`
- **Standard:** 6 (Testing)
- **Description:** `service.update_stop()` (lines 165-200 of service.py) contains logic to detect duplicate `gtfs_stop_id` when the field is being changed. This branch has NO test coverage -- there is no test that exercises the `StopAlreadyExistsError` path during update. The tests cover `update_stop_success` and `update_stop_not_found` but not `update_stop_duplicate_gtfs_id`.
- **Missing test:**
  ```python
  async def test_update_stop_duplicate_gtfs_id(service):
      stop = make_stop(id=1, gtfs_stop_id="1001")
      existing = make_stop(id=2, gtfs_stop_id="2002")
      data = StopUpdate(gtfs_stop_id="2002")
      service.repository.get = AsyncMock(return_value=stop)
      service.repository.get_by_gtfs_id = AsyncMock(return_value=existing)

      with pytest.raises(StopAlreadyExistsError, match="already exists"):
          await service.update_stop(1, data)
  ```

---

**M3. Missing test coverage for `location_type` filter**
- **Files:** `/Users/Berzins/Desktop/VTV/app/stops/tests/test_service.py`, `/Users/Berzins/Desktop/VTV/app/stops/tests/test_routes.py`
- **Standard:** 6 (Testing)
- **Description:** The `location_type` query parameter was added as a server-side filter (per README: "location_type filter is applied server-side to ensure pagination totals match filtered results"), but there are zero tests verifying this filter at the service or route layer. The repository test for `list_with_search` only tests the `search` parameter. A regression in the `location_type` filter would go undetected.
- **Missing tests:** Add at least one service-level test that passes `location_type=1` and verifies the repository is called with the correct filter.

---

**M4. Repository `list` and `count` have duplicated filter logic**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/repository.py`, lines 45-75 and 77-102
- **Standard:** 8 (Code Quality - DRY)
- **Description:** The `list()` and `count()` methods independently apply the same three filter conditions (`active_only`, `search`, `location_type`). If a new filter is added, it must be added to both methods -- a maintenance risk. If the filters diverge, the count will not match the list results, breaking pagination.
- **Fix:** Extract a private `_apply_filters` method:
  ```python
  def _apply_filters(
      self, query: Select, *, active_only: bool, search: str | None, location_type: int | None
  ) -> Select:
      if active_only:
          query = query.where(Stop.is_active.is_(True))
      if search:
          query = query.where(Stop.stop_name.ilike(f"%{_escape_like(search)}%"))
      if location_type is not None:
          query = query.where(Stop.location_type == location_type)
      return query
  ```

---

**M5. `stop_factory` fixture returns `type` instead of specific type**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/tests/conftest.py`, line 43
- **Standard:** 2 (Type Safety)
- **Description:** The `stop_factory` fixture is annotated as returning `type` (bare `type` object). This loses all type information about the `_Factory` class and its `create` method. Callers get no IDE autocompletion or type checking on `stop_factory.create(...)`.
- **Fix:** Either use `Protocol` or `type[_Factory]`, or simplify by returning the `make_stop` function directly:
  ```python
  @pytest.fixture
  def stop_factory() -> Callable[..., Stop]:
      return make_stop
  ```
  Note: The `stop_factory` fixture appears unused in the current tests (all tests use `make_stop` directly), so removing it entirely is also an option.

---

### Low

**L1. `StopUpdate` cannot distinguish "set to null" from "not provided" for `parent_station_id`**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/schemas.py`, line 40
- **Standard:** 3 (Error Handling)
- **Description:** `parent_station_id: int | None = None` -- since the default is `None` and the field type includes `None`, there is no way to distinguish between "user wants to clear this field" and "user did not include this field" when using `model_dump(exclude_unset=True)`. In practice, sending `{"parent_station_id": null}` will correctly set it to `None` because Pydantic tracks which fields were explicitly set. However, `StopUpdate(parent_station_id=None)` in Python code (without JSON deserialization) will NOT include it in `exclude_unset`. This is a latent gotcha, not currently causing bugs.
- **Impact:** Low -- JSON API path works correctly. Only a concern if `StopUpdate` is constructed programmatically.

---

**L2. Hard-coded limit=10000 in proximity search**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/service.py`, line 246
- **Standard:** 8 (Code Quality)
- **Description:** The magic number `10000` is used as the limit for loading all stops. This should be a named constant (e.g., `_NEARBY_FETCH_LIMIT = 10_000`) for clarity and easy adjustment.

---

**L3. `conftest.py` `make_stop_response_dict` is unused**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/tests/conftest.py`, lines 114-138
- **Standard:** 8 (Code Quality - YAGNI)
- **Description:** The `make_stop_response_dict` helper function is defined but not called by any test in the module. This is dead code that adds maintenance burden.
- **Fix:** Remove the function, or add a `# NOTE: used by integration tests` comment if it is used elsewhere.

---

**L4. `test_create` emits a RuntimeWarning about unawaited coroutine**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/tests/test_repository.py`, line 84-98
- **Standard:** 6 (Testing)
- **Description:** Test output shows: `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` from `repository.py:114: self.db.add(stop)`. This is because `self.db.add` is an `AsyncMock` but `.add()` is a synchronous method on `AsyncSession`. The mock should use `MagicMock` for the `.add` method specifically.
- **Fix:**
  ```python
  repo.db.add = MagicMock()  # add() is sync, not async
  ```

---

**L5. Logging event names inconsistently drop the component segment**
- **File:** `/Users/Berzins/Desktop/VTV/app/stops/service.py`
- **Standard:** 7 (Logging)
- **Description:** The documented logging pattern is `domain.component.action_state`, but the service uses two-segment names like `stops.fetch_started`, `stops.list_started`, `stops.create_started`. A more consistent pattern would be `stops.service.fetch_started` or `stops.stop.fetch_started` to include the component segment. The current names still work for grep and filtering, but they don't follow the three-segment pattern shown in the logging standard examples (`agent.tool.execution_started`, `transit.search_stops.started`).
- **Impact:** Cosmetic. The current pattern is internally consistent within the stops module and is adequate for filtering.

---

## Recommendations

1. **Priority fix (H1):** Escape LIKE wildcards in the `search` parameter. This is a simple 3-line function that closes the wildcard injection gap. Apply the same fix to `app/schedules/repository.py`.

2. **Add missing tests (M2, M3):** The update-duplicate-gtfs-id and location_type filter branches have zero coverage. These are business-critical paths that should each have at least one test.

3. **Extract `_apply_filters` (M4):** The duplicated filter logic between `list()` and `count()` is a divergence risk. Extract to a shared private method.

4. **Consider caching for proximity (H2):** At current scale (~2000 stops) the full-table load works, but adding a simple in-memory cache with 60s TTL would eliminate redundant DB round-trips for repeated proximity queries.

5. **Extract `_haversine_distance` (M1):** The duplication is acknowledged with a NOTE comment. Extract to `app/shared/geo.py` before a third copy appears.

6. **Clean up test warnings (L4):** The RuntimeWarning in `test_create` is harmless but noisy. Fix by using `MagicMock` for the synchronous `.add()` method.
