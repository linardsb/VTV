# Code Review: app/shared/

**Reviewer:** Senior Backend Engineer
**Date:** 2026-02-21
**Module:** `/Users/Berzins/Desktop/VTV/app/shared/`
**Files reviewed:** `__init__.py`, `models.py`, `schemas.py`, `utils.py`, `tests/conftest.py`, `tests/test_models.py`, `tests/test_schemas.py`, `tests/test_utils.py`

---

## Summary

The shared module is compact (4 source files, 4 test files) and provides cross-cutting utilities: timestamp mixins, pagination schemas, error response schemas, and datetime helpers. The code is generally well-structured with good documentation and type safety. However, there are several issues ranging from a DRY violation (duplicate `utcnow`) to dead code, an architectural violation of the three-feature rule, and a missing validation gap in the paginated response schema.

**Verdict:** Mostly sound. 0 critical, 3 high, 4 medium, 3 low findings.

---

## Findings

### Critical

None.

### High

**H1. Duplicate `utcnow()` definition violates DRY**
- **Files:** `/Users/Berzins/Desktop/VTV/app/shared/models.py` (line 10) and `/Users/Berzins/Desktop/VTV/app/shared/utils.py` (line 6)
- **Standard:** Code Quality (DRY)
- **Detail:** `utcnow()` is defined identically in two files within the same module. `models.py` defines it for use as a SQLAlchemy column default. `utils.py` defines it as a general-purpose utility. External features import from `models.py` (stops, schedules test conftest), and tests import from `utils.py`. This creates confusion about the canonical import path and is a maintenance hazard -- a bugfix in one would be missed in the other.
- **Fix:** Remove `utcnow()` from `utils.py`. Re-export it from `models.py` via `__init__.py` so consumers have a single canonical import: `from app.shared.models import utcnow` (already the pattern used by features).

**H2. `ErrorResponse` violates the three-feature rule**
- **File:** `/Users/Berzins/Desktop/VTV/app/shared/schemas.py` (line 67)
- **Standard:** Architecture (three-feature rule)
- **Detail:** `ErrorResponse` is defined in the shared module but is not imported by any feature or the main application. It is only referenced in its own docstring example and its own tests. The global exception handler in `app/core/exceptions.py` constructs raw dicts instead of using `ErrorResponse`. This class belongs nowhere in `shared/` -- it has zero feature consumers.
- **Fix:** Either (a) remove `ErrorResponse` entirely (YAGNI), or (b) refactor the exception handlers in `app/core/exceptions.py` to use `ErrorResponse` for consistency. If kept, it should live in `app/core/` alongside the exception handlers, not in `shared/`.

**H3. `format_iso()` violates the three-feature rule**
- **File:** `/Users/Berzins/Desktop/VTV/app/shared/utils.py` (line 22)
- **Standard:** Architecture (three-feature rule)
- **Detail:** `format_iso()` is a trivial wrapper around `datetime.isoformat()` and is not imported by any feature outside the shared module itself. It exists only in `utils.py` and its tests. With zero feature consumers, it does not meet the three-feature threshold for inclusion in `shared/`.
- **Fix:** Remove `format_iso()` and its tests. Callers can use `dt.isoformat()` directly -- the wrapper adds no value.

### Medium

**M1. `PaginatedResponse` lacks field validation**
- **File:** `/Users/Berzins/Desktop/VTV/app/shared/schemas.py` (lines 54-57)
- **Standard:** Security (input validation)
- **Detail:** The fields `total`, `page`, and `page_size` on `PaginatedResponse` have no constraints. While `PaginationParams` correctly validates `page >= 1` and `1 <= page_size <= 100`, the response schema accepts any integer -- including negative values. Since this is a response schema constructed server-side, the risk is low, but adding `ge=0` on `total` and `ge=1` on `page`/`page_size` would catch programming errors early and document the contract.
- **Fix:** Add `Field(ge=0)` to `total` and `Field(ge=1)` to `page` and `page_size`.

**M2. Unused `TypeVar` import in `schemas.py`**
- **File:** `/Users/Berzins/Desktop/VTV/app/shared/schemas.py` (lines 4, 8)
- **Standard:** Code Quality
- **Detail:** Line 4 imports `TypeVar` and line 8 defines `T = TypeVar("T")`. However, `PaginatedResponse` on line 36 uses PEP 695 syntax (`class PaginatedResponse[T]`), which creates its own scoped type parameter. The module-level `T = TypeVar("T")` is dead code. Ruff F841 or a similar unused-variable check should flag this.
- **Fix:** Remove `from typing import TypeVar` and the `T = TypeVar("T")` line.

**M3. `declared_attr` imported from legacy path**
- **File:** `/Users/Berzins/Desktop/VTV/app/shared/models.py` (line 6)
- **Standard:** Code Quality
- **Detail:** `declared_attr` is imported from `sqlalchemy.ext.declarative`, which is the SQLAlchemy 1.x legacy location. Since SQLAlchemy 2.0, the canonical import is `from sqlalchemy.orm import declared_attr`. While the legacy path still works in 2.0.40, it is deprecated and may be removed in a future major version.
- **Fix:** Change to `from sqlalchemy.orm import declared_attr`.

**M4. `TimestampMixin.created_at` / `updated_at` missing `cls` type annotation**
- **File:** `/Users/Berzins/Desktop/VTV/app/shared/models.py` (lines 29, 34)
- **Standard:** Type Safety
- **Detail:** The `@declared_attr.directive` methods use bare `cls` without a type annotation. While this is common in SQLAlchemy patterns, mypy and pyright may not be able to infer the type correctly. For strict type checking compliance, the parameter should be annotated.
- **Fix:** Add `from typing import Self` (Python 3.11+) and annotate as `def created_at(cls: type[Self]) -> Mapped[datetime]:` or use `cls: Any` if Self causes issues with the mixin pattern.

### Low

**L1. `test_timestamp_mixin_updates_updated_at_on_modification` uses `time.sleep()`**
- **File:** `/Users/Berzins/Desktop/VTV/app/shared/tests/test_models.py` (line 77)
- **Standard:** Performance / Testing
- **Detail:** The test uses `time.sleep(0.01)` to ensure a timestamp difference. This adds 10ms of wall-clock latency to every test run. For an async test, `asyncio.sleep()` would be more appropriate, though the real issue is relying on wall-clock time for deterministic assertions.
- **Fix:** Consider mocking `utcnow()` to return controlled timestamps instead of relying on sleep.

**L2. Test conftest creates real database connections**
- **File:** `/Users/Berzins/Desktop/VTV/app/shared/tests/conftest.py` (lines 17-53)
- **Standard:** Testing
- **Detail:** The conftest creates a real async engine and creates/drops all tables for each test function. This is appropriate for integration tests but the fixtures are `scope="function"`, meaning every integration test pays the DDL cost. For a small module this is acceptable, but as the schema grows, table creation/teardown per test will become slow.
- **Fix:** Consider `scope="session"` for the engine and use transaction rollback isolation instead of DDL per test. Not urgent at current scale.

**L3. No `__all__` exports in module files**
- **Files:** `/Users/Berzins/Desktop/VTV/app/shared/__init__.py`, `models.py`, `schemas.py`, `utils.py`
- **Standard:** Code Quality
- **Detail:** None of the module files define `__all__`, which means the public API is implicit. For a shared module that other features depend on, explicitly defining `__all__` clarifies the public contract and prevents accidental coupling to implementation details.
- **Fix:** Add `__all__` to `models.py` (`["TimestampMixin", "utcnow"]`), `schemas.py` (`["PaginationParams", "PaginatedResponse", "ErrorResponse"]`), and `utils.py` (`["format_iso"]` -- or remove the file per H3).

---

## Recommendations

### Immediate (address before next feature)

1. **Eliminate the `utcnow()` duplication (H1).** Pick `models.py` as the canonical location. Remove from `utils.py`. Update `__init__.py` to re-export if desired. This is the highest-impact fix -- confusion about import paths leads to subtle bugs.

2. **Remove or relocate `ErrorResponse` (H2) and `format_iso` (H3).** Both violate the three-feature rule. `ErrorResponse` is unused by any consumer; `format_iso` is a trivial wrapper. Removing them shrinks the module's surface area and enforces YAGNI.

3. **Remove the dead `TypeVar` (M2).** This is a one-line fix that eliminates dead code and a potential linter warning.

### Short-term (next sprint)

4. **Add field constraints to `PaginatedResponse` (M1).** Low risk, high clarity.

5. **Update the `declared_attr` import path (M3).** Future-proofs against SQLAlchemy 3.x.

### Longer-term

6. **Add `__all__` to all module files (L3).** Clarifies the public API contract.

7. **Replace `time.sleep()` in tests with mocked timestamps (L1).** Eliminates non-determinism and speeds up test execution.

8. **Consider transaction-based test isolation (L2).** Will matter more as the schema grows.

### What's working well

- **`TimestampMixin`** is well-designed: uses `@declared_attr.directive` correctly, provides both `created_at` and `updated_at` with proper UTC timezone handling, and `onupdate` is set on `updated_at` only.
- **`PaginationParams`** has good validation constraints and the `offset` property is a clean abstraction.
- **`PaginatedResponse[T]`** uses PEP 695 generics correctly, and the `total_pages` property handles the zero-total edge case.
- **Test coverage** is thorough for the functionality that exists: pagination params validation, offset calculation, total pages edge cases, timestamp timezone awareness, and update behavior.
- **Documentation** is excellent -- all classes and functions have docstrings with usage examples.
