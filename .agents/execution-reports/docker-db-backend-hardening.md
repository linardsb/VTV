# Execution Report: Docker & Backend Hardening

**Plan:** `.agents/plans/docker-db-backend-hardening.md`
**Date:** 2026-02-21

## Summary

Infrastructure hardening across Docker orchestration, backend exception hierarchy, rate limiting, and nginx security. 19 plan tasks + code review fixes.

## Files Modified (18)

### Docker / Infrastructure
- `docker-compose.yml` — Added `migrate` service, healthchecks for all services, dependency ordering with conditions, variable interpolation for credentials, document storage volume
- `Dockerfile` — Fixed CMD to use uvicorn directly (no reload in production), removed scaffolding comments
- `cms/apps/web/Dockerfile` — Pinned pnpm to `10.28.2` for reproducible builds
- `nginx/nginx.conf` — Granular body size limits (10MB for upload paths, 1MB default for `/api/`)
- `Makefile` — Updated docker target comment for auto-migrate
- `.env.example` — Documented ENVIRONMENT/AUTH_SECRET behavior

### Backend Architecture
- `app/core/exceptions.py` — Renamed `DatabaseError` to `AppError`, added `invalid_credentials_handler` (401) and `account_locked_handler` (423), updated docstrings
- `app/auth/exceptions.py` — Updated base class to `AppError`
- `app/stops/exceptions.py` — Updated base class to `AppError`
- `app/schedules/exceptions.py` — Updated base class to `AppError`
- `app/knowledge/exceptions.py` — Updated base class to `AppError`
- `app/auth/routes.py` — Removed manual try/except (global handlers), added environment gate with logging, added structured logger
- `app/transit/routes.py` — Added rate limiting to `/feeds` endpoint
- `app/core/middleware.py` — Tightened upload path matching with explicit prefixes
- `app/core/database.py` — Added explicit rollback on exceptions, removed redundant close
- `pyproject.toml` — Removed Darwin-specific pyright config, added email-validator dep
- `reference/vsa-patterns.md` — Updated pattern examples from `DatabaseError` to `AppError`

### Tests
- `app/core/tests/test_exceptions.py` — Added 2 tests for auth handlers, updated handler count assertion, renamed references
- `app/core/tests/test_database.py` — Updated to assert context manager cleanup instead of explicit close

## Validation Results

| Check | Result |
|-------|--------|
| ruff format | PASS (153 files unchanged) |
| ruff check | PASS (0 issues) |
| mypy | PASS (0 errors, 149 files) |
| pyright | PASS (0 errors) |
| pytest | PASS (450 passed, 9 deselected) |

## Deviations from Plan

1. **wget vs curl for healthchecks** — Alpine images have wget built-in; avoids installing curl
2. **AppError rename** — Plan kept `DatabaseError`; code review flagged semantic mismatch; renamed to `AppError` during review fix phase
3. **Granular nginx body limits** — Plan used single 10MB for `/api/`; review suggested per-path limits; implemented 3 specific 10MB paths + default 1MB

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| `test_setup_exception_handlers_registers_handlers` FAILED | Test asserted 3 handlers; now 5 after adding auth handlers | Updated assertion to expect 5, added auth exception imports |
| `test_get_db_yields_session` FAILED | Test asserted `session.close()` called; removed redundant close | Updated test to assert `__aexit__` called by context manager |
