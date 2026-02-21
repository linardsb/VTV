# Code Review: Docker & Backend Hardening

**Scope:** All files modified in the docker-db-backend-hardening execution (14 files)

**Summary:** Solid infrastructure hardening with proper Docker orchestration, exception hierarchy consolidation, and rate limiting gap closure. A few medium-priority issues around naming semantics, missing test coverage for new handlers, and a Docker security consideration.

## Findings

| File:Line | Standard | Issue | Suggestion | Priority |
|-----------|----------|-------|------------|----------|
| `app/auth/exceptions.py:8` | 5. Architecture | Auth exceptions inherit from `DatabaseError` but represent authentication failures, not database errors. Semantically misleading inheritance. | Consider renaming `DatabaseError` to `AppError` or `ServiceError` in a future refactor, or add an intermediate `AuthError(DatabaseError)` base. Current design works but the naming is confusing — authentication failures are not "database errors." | Medium |
| `app/core/exceptions.py:69` | 1. Type Safety | `invalid_credentials_handler` and `account_locked_handler` accept `exc: Exception` instead of specific types (`InvalidCredentialsError`, `AccountLockedError`). The handlers lose type narrowing. | Use the specific exception types in the signature. FastAPI's type system requires `cast(Any, ...)` anyway, so the handler signature can be precise: `exc: InvalidCredentialsError`. This would require moving imports to top-level (lazy import is already in `setup_exception_handlers`). | Low |
| `app/core/exceptions.py:69-112` | 7. Testing | New `invalid_credentials_handler` and `account_locked_handler` functions have no direct unit tests. They're tested indirectly via route tests, but the handler logic (logging, response format) is untested. | Add unit tests in `app/core/tests/test_exceptions.py` that verify: (a) 401 status + response body for `invalid_credentials_handler`, (b) 423 status + response body for `account_locked_handler`, (c) logger.warning is called with correct event names. | High |
| `docker-compose.yml:50` | 8. Security | `migrate` service hardcodes `DATABASE_URL` with plaintext credentials `postgres:postgres`. If `.env` provides a different password, the migration will connect with wrong creds. | Remove the hardcoded `DATABASE_URL` from `migrate.environment` and rely on `.env` file only, or use `${POSTGRES_PASSWORD:-postgres}` interpolation to stay consistent with the `db` service. | Medium |
| `docker-compose.yml:90` | 8. Security | `app` service also hardcodes `DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/vtv_db` which overrides any `.env` value. | Same fix — use `DATABASE_URL=${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@db:5432/vtv_db}` or remove the override and document that `.env` must set Docker-internal URLs. | Medium |
| `docker-compose.yml:140` | 8. Security | `AUTH_SECRET=${AUTH_SECRET:?AUTH_SECRET must be set}` will crash `docker-compose up` if not set, but `make db` workaround uses `AUTH_SECRET=dev-placeholder`. This creates divergent behavior. | Document in `.env.example` that `AUTH_SECRET` is required for `docker-compose up` (full stack) but not for `make db` (dev subset). Alternatively, use `AUTH_SECRET=${AUTH_SECRET:-}` with a runtime check in the CMS app. | Low |
| `app/auth/routes.py:43` | 3. Structured Logging | `seed_demo_users` endpoint has no logging for the environment gate rejection (non-development returns `[]`). Silent behavior makes debugging harder. | Add `logger.info("auth.seed.skipped", environment=settings.environment)` before the early return. | Low |
| `app/core/middleware.py:56-61` | 5. Architecture | Upload path allowlist is hardcoded in middleware. If new upload endpoints are added (e.g., document uploads via different paths), developers must remember to update this list. | Acceptable for now (3 paths), but consider a config-driven approach or decorator-based opt-in if this list grows beyond 5 entries. Not actionable yet. | Low |
| `Dockerfile:61` | 5. Architecture | CMD uses `--host 0.0.0.0` which is correct for containers but the inline comments still reference "adjust if your app uses a different port." | Remove the placeholder comments on lines 56-57 and 59-60 — they're generic scaffolding text that no longer applies. | Low |
| `.dockerignore:17-19` | 5. Architecture | `*.md` is excluded but `!pyproject.toml`, `!uv.lock`, `!alembic.ini` are negated. The `*.md` exclusion will also exclude `README.md` inside the build context, which is fine. But `!alembic.ini` negation is needed since Alembic needs it at runtime. | This is correct. No change needed. | - |
| `app/core/database.py:57-59` | 4. Database | `get_db()` now has explicit rollback, but `session.close()` in the `finally` block is redundant — the `async with AsyncSessionLocal()` context manager already handles closing. | Remove the `finally: await session.close()` block. The `async with` guarantees cleanup. Having both is harmless but misleading. | Low |
| `nginx/nginx.conf:74` | 8. Security | `client_max_body_size 10m` for all `/api/` routes. Most API endpoints don't need 10MB bodies — only GTFS import and knowledge uploads. | More granular: add a nested `location /api/v1/schedules/import` and `location /api/v1/knowledge` with 10m, keep general `/api/` at 1m. This provides defense-in-depth. | Low |

## Stats

- Files reviewed: 14
- Issues: 12 total — 0 Critical, 1 High, 3 Medium, 8 Low

## Priority Summary

### High (fix before commit)
1. **Missing handler tests** — Add unit tests for `invalid_credentials_handler` and `account_locked_handler` in `app/core/tests/test_exceptions.py`

### Medium (fix soon)
1. **Semantic naming** — `DatabaseError` base class for auth exceptions is misleading (future refactor)
2. **Hardcoded DB credentials** in docker-compose `migrate` and `app` services could diverge from `.env`

### Low (backlog)
- Redundant `session.close()`, missing seed logging, Dockerfile comment cleanup, nginx body size granularity, handler type signatures
