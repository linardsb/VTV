# Review: Calendar "Created By" Feature

**Date:** 2026-02-25
**Reviewer:** Claude Code
**Scope:** All files modified for the calendar creator attribution feature

## Summary

Clean, well-structured vertical slice enhancement. Type safety, security, logging, and test coverage are solid. Two medium findings worth addressing: `lazy="joined"` adds an unconditional JOIN to every calendar query (including bulk operations that don't need user data), and there's no test verifying that `created_by_name` actually resolves to a real user name (only NULL path tested).

## Findings

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `app/schedules/models.py:76` | `lazy="joined"` on `creator` relationship adds a LEFT JOIN to the users table on **every** Calendar query, including bulk operations like `list_all_calendars()` (GTFS export), `list_calendars()` in `validate_schedule()`, and GTFS import's `get_calendar_by_gtfs_id()` — none of which need the user name | Use `lazy="selectin"` or `lazy="noload"` as default with explicit `options(joinedload(Calendar.creator))` only in `list_calendars()` and `get_calendar()` repository methods that serve the API. This avoids unnecessary JOINs in bulk/internal operations. Alternatively, accept this as a minor perf trade-off since the users table is small and the JOIN is on an indexed FK | Medium |
| `app/schedules/tests/test_service.py:168-174` | `test_create_calendar_success` asserts `created_by_id == 42` but never tests that `created_by_name` resolves to an actual user name — only the NULL path is tested in `test_create_calendar_without_user` | Add an integration test (or mock the `creator` relationship on the Calendar object) that verifies `created_by_name` returns a real name when the relationship is loaded. Example: set `calendar.creator = MagicMock(name="Test User")` and assert `result.created_by_name == "Test User"` | Medium |
| `cms/apps/web/src/components/schedules/calendar-dialog.tsx` | Calendar detail dialog doesn't display `created_by_name` — only the table column shows it. If a user clicks a calendar row, the dialog view doesn't show who created it | Consider adding a "Created by" field in the dialog metadata section for consistency. This is a UX gap, not a code defect | Low |

## Standard-by-Standard Assessment

### 1. Type Safety -- PASS
- All functions fully annotated (params + return)
- `TYPE_CHECKING` import avoids circular deps cleanly
- `from __future__ import annotations` used correctly
- Zero `# type: ignore` or `# pyright: ignore` suppressions
- mypy 0 errors, pyright 0 errors

### 2. Pydantic Schemas -- PASS
- `CalendarResponse` has `created_by_id` and `created_by_name` with proper defaults
- `from_attributes=True` correctly reads the model `@property`
- `CalendarUpdate` intentionally excludes `created_by_id` (can't change creator)
- `CalendarCreate` doesn't include `created_by_id` (set by service layer, not user input)

### 3. Structured Logging -- PASS
- `schedules.calendar.create_started` and `create_completed` pair maintained
- `created_by_id=user_id` added to `create_completed` event
- Follows `domain.component.action_state` pattern

### 4. Database Patterns -- PASS
- `select()` style queries (no `.query()`)
- Calendar inherits `Base` and `TimestampMixin`
- Migration has named FK constraint (`fk_calendars_created_by_id`) and clean downgrade
- `ondelete="SET NULL"` supports GDPR user deletion
- Nullable column for backwards compatibility with existing data

### 5. Architecture -- PASS
- No runtime cross-feature imports (User is TYPE_CHECKING only)
- Vertical slice boundaries respected
- Service layer accepts `user_id` as keyword-only arg — clean API
- Route layer is thin (extracts user ID, delegates to service)
- GTFS import path untouched (uses `bulk_upsert_calendars`, bypasses `create_calendar`)

### 6. Docstrings -- PASS
- Service method has Google-style docstring with Args/Returns/Raises
- Model property has one-line docstring
- Migration has descriptive docstrings

### 7. Testing -- PASS (with gap noted above)
- `test_create_calendar_success` — tests user_id=42 path
- `test_create_calendar_without_user` — tests None/GTFS import path
- Test factory updated with `created_by_id: None`
- All 67 feature tests pass, 691/692 full suite pass

### 8. Security -- PASS
- Route uses `require_role("admin", "editor")` — auth enforced
- `TestAllEndpointsRequireAuth` passes (auto-discovery confirms auth)
- All 105 security convention tests pass
- `ondelete="SET NULL"` ensures GDPR deletion works
- No role names leaked in error messages
- No type suppressions added
- Ruff Bandit (S rules) clean

## Stats

- Files reviewed: 11 (model, schema, service, routes, repository, migration, conftest, test_service, TS types, i18n x2, calendar-table, calendar-dialog)
- Issues: 3 total — 0 Critical, 0 High, 2 Medium, 1 Low

## Verdict

**PASS** — Ready to commit. The two medium findings are optimization and test coverage improvements that can be addressed in a follow-up if desired.
