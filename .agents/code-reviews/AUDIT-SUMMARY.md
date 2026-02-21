# Full Codebase Health Audit Summary

**Date:** 2026-02-21
**Auditor:** Claude Opus 4.6
**Scope:** Full VTV platform (backend + frontend)

---

## Phase 1: Automated Baselines

### Backend (`/be-validate`)

| Check | Initial | After Fix |
|-------|---------|-----------|
| ruff format | FAIL (2 files) | PASS |
| ruff check | FAIL (9 errors) | PASS (9 auto-fixed) |
| mypy | FAIL (2 errors in gtfs_import.py) | PASS (137 files) |
| pyright | FAIL (5 errors in gtfs_import.py) | PASS |
| pytest | FAIL (1 failed / 296 pass) | PASS (434 tests) |

**Root cause fixed:** `gtfs_import.py:_parse_stop_times` return type annotation was 3-tuple but method returned 4-tuple. Fixed type annotation + early return path.

### Frontend (`/fe-validate`)

| Check | Status |
|-------|--------|
| TypeScript (`tsc --noEmit`) | PASS |
| ESLint | PASS |
| Next.js Build | PASS (11 routes) |

---

## Phase 2-3: Code Reviews Summary

### Issue Counts by Module

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

### All Critical Issues

| ID | Module | Description |
|----|--------|-------------|
| transit/C1 | transit | Poller always sets `current_stop_name` to `None` -- data loss in production Redis mode |
| knowledge/C1 | knowledge | Path traversal in file download endpoint -- no validation against storage root |
| knowledge/C2 | knowledge | No file size limit on upload -- memory exhaustion risk |
| knowledge/C3 | knowledge | Filename injection via unsanitized original filename |
| schedules/C1 | schedules | No file upload validation on GTFS import (no ZIP bomb protection, no size limit) |
| schedules/C2 | schedules | `create_agency()` raises wrong exception type (`RouteAlreadyExistsError` instead of agency error) |
| schedules/C3 | schedules | `remove_calendar_exception()` raises `StopTimeNotFoundError` (wrong domain entity) |
| fe/C1 | frontend | Hardcoded demo credentials in `auth.ts` (`admin@vtv.lv` / `admin`) |

### Top High-Severity Issues (most impactful)

| ID | Module | Description |
|----|--------|-------------|
| core/H2 | core | Redis URL with credentials leaked to logs |
| core/H4 | core | X-Forwarded-For header spoofing bypasses rate limiter |
| stops/H2 | stops | Proximity search loads ALL stops into memory (up to 10K) |
| schedules/H1 | schedules | GTFS import hardcoded 100K stop limit -- silent data loss |
| schedules/H2 | schedules | Validate endpoint has N+1 query patterns |
| knowledge/H1 | knowledge | Repository commits inside methods (transaction boundary leak) |
| fe/H2 | frontend | Dashboard page not protected by RBAC middleware matcher |
| fe/H4 | frontend | All page-level components are client components (SSR missed) |

---

## Most Common Patterns

### 1. ILIKE Wildcard Injection (3 occurrences)
- `stops/repository.py`, `schedules/repository.py`, `core/agents/tools/`
- User `%` and `_` not escaped in search parameters
- **Fix:** Escape wildcards before ILIKE queries

### 2. Memory-Loaded Full Collections (3 occurrences)
- `stops/service.py` (proximity: all stops), `schedules/service.py` (import: 100K stops), `schedules/service.py` (validate: all data)
- **Fix:** SQL-level bounding box pre-filters, streaming/pagination for bulk ops

### 3. Wrong Exception Types (2 occurrences)
- `schedules/service.py` -- `create_agency` raises `RouteAlreadyExistsError`
- `schedules/service.py` -- `remove_calendar_exception` raises `StopTimeNotFoundError`
- **Fix:** Create proper exception classes per domain entity

### 4. Mutable Global Singletons (2 occurrences)
- `core/` module-level singletons without thread safety
- `knowledge/` embedding provider singleton
- **Fix:** Use dependency injection or proper locks

### 5. Code Duplication (3+ occurrences)
- Transit tool utility functions (6 duplicated across 5 files)
- `utcnow()` in both `shared/models.py` and `shared/utils.py`
- Vehicle enrichment logic in both `transit/service.py` and `transit/poller.py`
- **Fix:** Extract shared utilities following three-feature rule

### 6. Dead Code in shared/ (2 occurrences)
- `ErrorResponse` schema (0 consumers)
- `format_iso()` utility (0 consumers)
- **Fix:** Remove dead code

---

## Features Ranked by Technical Debt

1. **app/schedules/** (24 issues, 3 Critical) -- Newest feature, most issues. Wrong exceptions, no upload validation, N+1 queries.
2. **app/core/** (27 issues, 0 Critical but 6 High) -- Infrastructure debt: logging leaks, rate limiter bypass, code duplication in agent tools.
3. **app/knowledge/** (19 issues, 3 Critical) -- Security-heavy: path traversal, upload issues, filename injection.
4. **cms/apps/web/** (15 issues, 1 Critical) -- Security: hardcoded credentials, missing RBAC. Architecture: all-client components.
5. **app/transit/** (13 issues, 1 Critical) -- Production data bug (stop name null), code duplication.
6. **app/stops/** (12 issues, 0 Critical) -- Mature feature, mostly medium/low. ILIKE injection + memory loading.
7. **app/shared/** (10 issues, 0 Critical) -- Dead code and DRY violations.

---

## Verification Status

- [x] Backend automated checks pass (ruff, mypy, pyright, pytest -- 434 tests)
- [x] Frontend automated checks pass (TypeScript, ESLint, Next.js build)
- [ ] Critical issues fixed (8 remaining -- see Phase 4)
- [x] All 7 review files written to `.agents/code-reviews/`

---

## Recommended Fix Priority

### Immediate (before any deployment)
1. Fix hardcoded credentials (fe/C1)
2. Fix path traversal in knowledge download (knowledge/C1)
3. Fix filename injection (knowledge/C3)
4. Fix wrong exception types (schedules/C2, C3)
5. Fix transit poller data loss (transit/C1)

### Short-term (production hardening)
6. Add file upload validation to schedules + knowledge
7. Fix RBAC middleware matcher gap
8. Sanitize Redis URL in logs
9. Escape ILIKE wildcards across all modules
10. Fix rate limiter X-Forwarded-For spoofing

### Medium-term (code health)
11. Extract duplicated transit tool utilities
12. Refactor page components to use server components
13. Add SQL-level pre-filters for proximity search
14. Remove dead code from shared/
15. Add missing test coverage gaps
