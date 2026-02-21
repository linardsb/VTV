# Execution Report: Full Codebase Health Audit

**Date:** 2026-02-21
**Scope:** All backend features (core, shared, stops, schedules, transit, knowledge) + frontend CMS

## Process

1. **Phase 1** — Automated baselines: `/be-validate` + `/fe-validate`
2. **Phase 2** — Backend code reviews: 6 modules reviewed against 8 quality standards
3. **Phase 3** — Frontend code review: 1 review against 8 frontend quality standards
4. **Phase 4** — Critical and high-severity fixes applied
5. **Phase 5** — Audit summary compiled

## Findings

| Module | Critical | High | Medium | Low | Total |
|--------|----------|------|--------|-----|-------|
| app/core/ | 0 | 6 | 11 | 10 | 27 |
| app/shared/ | 0 | 3 | 4 | 3 | 10 |
| app/stops/ | 0 | 2 | 5 | 5 | 12 |
| app/schedules/ | 3 | 6 | 8 | 7 | 24 |
| app/transit/ | 1 | 3 | 5 | 4 | 13 |
| app/knowledge/ | 3 | 5 | 6 | 5 | 19 |
| cms/apps/web/ | 1 | 4 | 10 | 0 | 15 |
| **TOTAL** | **8** | **29** | **49** | **34** | **120** |

## Bugs Found and Fixed

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| `gtfs_import.py` type mismatch — mypy/pyright/pytest all failing | `_parse_stop_times` return type was 3-tuple but method returned 4-tuple. Early return path also wrong. | Fixed return type annotation to `tuple[list[StopTime], list[Trip], list[Stop \| None], int]` + early return `[], [], [], 0` |
| Poller `current_stop_name` always `None` in production | `poller.py:153` hardcoded `None` instead of resolving from static cache like the service does | Changed to `static.get_stop_name(vp.stop_id) if vp.stop_id else None` |
| `create_agency()` raises `RouteAlreadyExistsError` | Wrong exception class imported — copy-paste error from route creation | Created `AgencyAlreadyExistsError`, updated `service.py` to use it |
| `remove_calendar_exception()` raises `StopTimeNotFoundError` | Wrong domain entity in exception — should be calendar date | Created `CalendarDateNotFoundError`, updated `service.py` to use it |
| Path traversal in knowledge download endpoint | `FileResponse` served resolved path without validating it falls within storage root | Added `is_relative_to(storage_root)` check before serving file |
| Filename injection in knowledge upload | `file.filename` from user used directly without sanitization | Added `Path.name` stripping, null byte removal, dot-file protection |
| Speed `0.0 m/s` treated as `None` (stationary vehicles) | `if v.speed` truthiness check — `0.0` is falsy in Python | Changed to `if v.speed is not None` |
| 9 ruff lint errors across codebase | Formatting (2 files), unsorted imports (2), unused noqa (2), legacy typing (3) | `ruff format` + `ruff check --fix` auto-resolved all 9 |

## Deferred Items

| Item | Reason |
|------|--------|
| knowledge/C2: No file size limit on upload | Needs architectural decision on streaming vs middleware limit adjustment |
| fe/C1: Hardcoded demo credentials | Needs auth system design (DB-backed users) |

## Artifacts

- `.agents/code-reviews/AUDIT-SUMMARY.md` — Cross-module summary with priority rankings
- `.agents/code-reviews/core-review.md` — 27 findings
- `.agents/code-reviews/shared-review.md` — 10 findings
- `.agents/code-reviews/stops-review.md` — 12 findings
- `.agents/code-reviews/schedules-review.md` — 24 findings
- `.agents/code-reviews/transit-review.md` — 13 findings
- `.agents/code-reviews/knowledge-review.md` — 19 findings
- `.agents/code-reviews/fe-web-review.md` — 15 findings

## Verification

- [x] `ruff format --check .` — PASS
- [x] `ruff check .` — PASS
- [x] `mypy app/` — PASS (137 files)
- [x] `pyright app/` — PASS
- [x] `pytest app/` — PASS (434 tests)
- [x] `tsc --noEmit` — PASS
- [x] `eslint` — PASS
- [x] `next build` — PASS (11 routes)
