# Plan: Docker, Database Migration & Backend Architecture Hardening

## Feature Metadata
**Feature Type**: Refactor / Bug Fix
**Estimated Complexity**: High
**Primary Systems Affected**: Docker (compose, Dockerfile, nginx), Alembic migrations, core infrastructure (database, middleware, config, exceptions, health), auth feature, transit feature

## Feature Description

This plan addresses 22 identified issues across the Docker orchestration layer, database migration system, and backend architecture. The problems range from high-severity security gaps (unprotected seed endpoint, nginx body size blocking file uploads) to medium-severity reliability issues (no auto-migration on Docker startup, missing health conditions in service dependencies, no DB session rollback on errors) to low-severity cleanup items (redundant indexes, hardcoded pyright platform, missing explicit dependencies).

The goal is zero gaps: every Docker service starts reliably with proper health checks and dependency ordering, database migrations run automatically on startup, the backend handles errors consistently across all features, and security concerns around demo user seeding are addressed. After this plan executes, `make docker` produces a fully-functional, production-hardened deployment from a clean state.

## User Story

As a **platform operator**
I want Docker Compose to produce a fully-working deployment from scratch — with automatic migrations, proper service health dependencies, consistent error handling, and no security gaps
So that I can deploy VTV reliably without manual intervention or hidden failure modes

## Solution Approach

We fix all issues in-place across 3 phases: Docker infrastructure first (service orchestration must work before anything else), then backend architecture fixes (database session safety, exception consistency, missing protections), then cleanup (redundant indexes, dependency declarations, config corrections). Each task targets exactly one file to keep changes atomic and reviewable.

**Approach Decision:**
We chose incremental in-place fixes because:
- No new features — purely hardening existing code
- Each fix is independent and testable in isolation
- Avoids large refactors that could introduce regressions

**Alternatives Considered:**
- Full Docker rewrite with multi-stage compose profiles: Rejected because current compose structure is sound, only details need fixing
- Rewrite database layer with explicit Unit of Work pattern: Rejected as over-engineering — adding rollback to `get_db()` achieves the same safety with minimal change

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `docker-compose.yml` — Docker service definitions (all 5 services)
- `Dockerfile` (root) — Backend multi-stage build
- `nginx/nginx.conf` — Reverse proxy configuration with rate limiting
- `Makefile` — Development workflow commands
- `.env.example` — Environment variable reference

### Similar Features (Examples to Follow)
- `app/schedules/exceptions.py` (lines 1-61) — Correct exception hierarchy pattern (inherits from `DatabaseError`/`NotFoundError`/`ValidationError`)
- `app/core/exceptions.py` (lines 1-86) — Global exception handler registration pattern
- `app/core/redis.py` (lines 30-39) — Singleton close with `RuntimeError` handling

### Files to Modify
- `docker-compose.yml` — Fix volume path, health conditions, add migration service, document volume
- `Dockerfile` — Fix CMD to use proper uvicorn (no reload)
- `nginx/nginx.conf` — Increase body size for API routes
- `app/core/database.py` — Add rollback on error in `get_db()`
- `app/core/middleware.py` — Tighten upload path matching
- `app/core/exceptions.py` — Register auth exceptions globally
- `app/auth/exceptions.py` — Inherit from core exceptions
- `app/auth/routes.py` — Remove manual exception handling (use global handlers)
- `app/transit/routes.py` — Add rate limiting to `/feeds`
- `app/auth/service.py` — Environment-gate the seed functionality
- `pyproject.toml` — Fix pyright platform, add email-validator
- `.env.example` — Document seed API key
- `Makefile` — Add migration step to docker target
- `.dockerignore` — Ensure alembic directory included

## Implementation Plan

### Phase 1: Docker Infrastructure (Tasks 1-7)
Fix Docker service orchestration so `make docker` works reliably from scratch: proper volume paths, health conditions, auto-migration, nginx body size, and production-safe CMD.

### Phase 2: Backend Architecture (Tasks 8-15)
Fix database session safety, exception consistency, auth security, rate limiting gaps, upload path specificity, and middleware hardening.

### Phase 3: Cleanup & Config (Tasks 16-19)
Fix pyright platform, add missing dependency, update env documentation, and clean up model indexes.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Fix Docker Compose Service Orchestration
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

Apply the following changes to `docker-compose.yml`:

1. **Fix PostgreSQL volume path** (line 12): Change `postgres_data:/var/lib/postgresql` to `postgres_data:/var/lib/postgresql/data`. The standard pgvector/PostgreSQL data directory is `/var/lib/postgresql/data`, not the parent.

2. **Add CMS health check** (inside `cms` service, after `expose`): Add:
   ```yaml
   healthcheck:
     test: ["CMD-SHELL", "curl -f http://localhost:3000 || exit 1"]
     interval: 10s
     timeout: 5s
     retries: 5
     start_period: 30s
   ```

3. **Add nginx health check** (inside `nginx` service, after `ports`): Add:
   ```yaml
   healthcheck:
     test: ["CMD-SHELL", "curl -f http://localhost:80/health || exit 1"]
     interval: 10s
     timeout: 5s
     retries: 3
   ```

4. **Fix CMS depends_on to use health condition** (line 118-119): Change from bare list to:
   ```yaml
   depends_on:
     app:
       condition: service_healthy
   ```

5. **Fix nginx depends_on to use health conditions** (lines 133-135): Change to:
   ```yaml
   depends_on:
     app:
       condition: service_healthy
     cms:
       condition: service_healthy
   ```

6. **Add document storage volume** to the `app` service `volumes` section:
   ```yaml
   - document_data:/app/data/documents
   ```
   And add `document_data:` to the top-level `volumes:` section.

7. **Add security comment to Redis port** (after line 28, matching the DB comment pattern):
   ```yaml
   # SECURITY: Consider removing in production - only needed for direct Redis access during development
   ```

8. **Install curl in CMS Dockerfile** for the healthcheck (the `cms` image must have curl). Read `cms/apps/web/Dockerfile` and add `RUN apk add --no-cache curl` or equivalent after the base image line (if alpine-based) or `RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*` (if debian-based). Check which base image is used.

**Per-task validation:**
- `docker-compose config` exits with 0 (validates compose file syntax)

---

### Task 2: Fix Dockerfile CMD for Production
**File:** `Dockerfile` (modify existing)
**Action:** UPDATE

Replace line 61:
```dockerfile
CMD ["python", "-m", "app.main"]
```
With:
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8123"]
```

This runs uvicorn directly without `reload=True` (which the `python -m app.main` path enables via the `if __name__ == "__main__"` block). Production containers should not watch for file changes.

**Per-task validation:**
- Verify the Dockerfile syntax: `docker build --check .` or read the file to confirm correct syntax

---

### Task 3: Add Auto-Migration on Docker Startup
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

Add a one-off `migrate` service that runs before the `app` service starts. Insert this service definition BEFORE the `app` service:

```yaml
  migrate:
    build:
      context: .
      dockerfile: Dockerfile
    command: ["python", "-m", "alembic", "upgrade", "head"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/vtv_db
    env_file:
      - path: .env
        required: false
    depends_on:
      db:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
```

Then update the `app` service `depends_on` to also wait for migration:
```yaml
depends_on:
  db:
    condition: service_healthy
  redis:
    condition: service_healthy
  migrate:
    condition: service_completed_successfully
```

This ensures migrations run exactly once before the app starts, and only after the DB is healthy.

**Per-task validation:**
- `docker-compose config` exits with 0

---

### Task 4: Fix Nginx Body Size for File Uploads
**File:** `nginx/nginx.conf` (modify existing)
**Action:** UPDATE

The global `client_max_body_size 1m;` (line 41) blocks GTFS import (ZIP files) and document uploads (knowledge endpoint) that the backend allows up to 10MB.

Add `client_max_body_size 10m;` inside the `/api/` location block (after line 73, before `proxy_pass`):
```nginx
location /api/ {
    limit_req zone=api burst=50 nodelay;
    client_max_body_size 10m;

    proxy_pass http://fastapi;
    ...
}
```

This overrides the global 1MB limit only for API routes. The LLM chat endpoint keeps the global 1MB limit (sufficient for text payloads). The CMS frontend keeps 1MB (static pages, no uploads through nginx to CMS).

**Per-task validation:**
- `docker run --rm -v $(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro nginx:1.27-alpine nginx -t` validates nginx config (or just read the file and verify syntax)

---

### Task 5: Update Makefile Docker Target with Migration
**File:** `Makefile` (modify existing)
**Action:** UPDATE

The `docker` target (line 19-20) should explicitly mention that migrations run automatically via the `migrate` service. Update the comment:
```makefile
docker: ## Build and start all services (db, redis, auto-migrate, app, cms, nginx on :80)
	AUTH_SECRET=$$(openssl rand -base64 32) docker-compose up -d --build
```

No functional change needed — the `migrate` service added in Task 3 runs automatically as part of `docker-compose up`. Just update the comment for discoverability.

**Per-task validation:**
- `make help` displays the updated description

---

### Task 6: Ensure Alembic Directory Included in Docker Build
**File:** `.dockerignore` (modify existing)
**Action:** UPDATE

Read the current `.dockerignore`. The `alembic/` directory is NOT excluded (only `cms/`, `nginx/`, `.agents/`, `docs/`, `documents/`, `.claude/`, `.playwright-mcp/` are excluded). However, `*.md` is excluded which means `alembic/README` (if any) would be excluded. The critical `.py` files in `alembic/versions/` are included. Verify this is correct — no change needed unless `alembic/` is missing.

Also verify `alembic.ini` is included (line 21: `!alembic.ini` — yes, it's allow-listed).

If everything checks out, skip this task. If `alembic/` is excluded, add `!alembic/` to the allowlist.

**Per-task validation:**
- Read `.dockerignore` and confirm `alembic/` directory and `alembic.ini` are not excluded

---

### Task 7: Fix CMS Dockerfile for Healthcheck Support
**File:** `cms/apps/web/Dockerfile` (modify existing)
**Action:** UPDATE

Read the CMS Dockerfile to determine the base image. If it's based on `node:*-alpine`, add:
```dockerfile
RUN apk add --no-cache curl
```
If it's based on `node:*-slim` or `node:*-bookworm`, add:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
```

This is required for the Docker health check added in Task 1 (`curl -f http://localhost:3000`).

If the image already has curl (check with `which curl` in the build stage), skip this addition.

Also, pin the pnpm version if it currently uses `pnpm@latest`:
- Find the line with `corepack prepare pnpm@latest --activate`
- Check `cms/package.json` for a `"packageManager"` field that specifies the version
- Replace `pnpm@latest` with the pinned version (e.g., `pnpm@9.15.0` or whatever is in `package.json`)

**Per-task validation:**
- Read the file and verify curl installation step exists and pnpm version is pinned

---

### Task 8: Add Database Session Rollback on Error
**File:** `app/core/database.py` (modify existing)
**Action:** UPDATE

The current `get_db()` (lines 42-58) only closes the session in `finally`. Add explicit rollback on exceptions:

Replace:
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    ...
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

With:
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session.

    Yields:
        AsyncSession: Database session for the request.

    On success, the caller is responsible for committing.
    On exception, the session is rolled back before closing.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

This ensures any uncommitted changes are rolled back on unhandled exceptions, preventing dirty session state from leaking between requests.

**Per-task validation:**
- `uv run ruff format app/core/database.py`
- `uv run ruff check --fix app/core/database.py` passes
- `uv run mypy app/core/database.py` passes with 0 errors
- `uv run pyright app/core/database.py` passes

---

### Task 9: Align Auth Exceptions with Core Exception Hierarchy
**File:** `app/auth/exceptions.py` (modify existing)
**Action:** UPDATE

Current auth exceptions inherit from bare `Exception`, which bypasses the global exception handler in `app/core/exceptions.py`. All other features (schedules, stops, knowledge) inherit from `DatabaseError` or its subclasses.

Replace the entire file content with:
```python
"""Authentication-specific exceptions.

Inherits from core exceptions for automatic HTTP status code mapping:
- InvalidCredentialsError -> 401 (custom handler)
- AccountLockedError -> 423 (custom handler)
"""

from app.core.exceptions import DatabaseError


class InvalidCredentialsError(DatabaseError):
    """Raised when email/password combination is invalid."""


class AccountLockedError(DatabaseError):
    """Raised when account is locked due to too many failed attempts."""
```

**Per-task validation:**
- `uv run ruff format app/auth/exceptions.py`
- `uv run ruff check --fix app/auth/exceptions.py` passes
- `uv run mypy app/auth/exceptions.py` passes with 0 errors
- `uv run pyright app/auth/exceptions.py` passes

---

### Task 10: Register Auth Exception Handlers Globally
**File:** `app/core/exceptions.py` (modify existing)
**Action:** UPDATE

Add auth-specific exception handlers to the global handler registration. This replaces the manual try/except in auth routes with consistent global handling.

Add these imports at the top of the file (after existing imports):
```python
from app.auth.exceptions import AccountLockedError, InvalidCredentialsError
```

Add two new handler functions after `database_exception_handler`:
```python
async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
    """Handle invalid credentials with 401 Unauthorized."""
    logger.warning(
        "auth.invalid_credentials",
        extra={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error": str(exc) or "Invalid email or password", "type": "InvalidCredentialsError"},
    )


async def account_locked_handler(request: Request, exc: AccountLockedError) -> JSONResponse:
    """Handle locked accounts with 423 Locked."""
    logger.warning(
        "auth.account_locked",
        extra={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=status.HTTP_423_LOCKED,
        content={"error": str(exc) or "Account is temporarily locked", "type": "AccountLockedError"},
    )
```

Register them in `setup_exception_handlers`:
```python
app.add_exception_handler(InvalidCredentialsError, cast(Any, invalid_credentials_handler))
app.add_exception_handler(AccountLockedError, cast(Any, account_locked_handler))
```

**IMPORTANT:** Check if importing from `app.auth.exceptions` creates a circular import. The dependency chain is: `app.core.exceptions` <- `app.auth.exceptions` (auth imports from core). Importing auth FROM core would create a cycle. To avoid this, use a lazy import inside `setup_exception_handlers`:
```python
def setup_exception_handlers(app: FastAPI) -> None:
    from app.auth.exceptions import AccountLockedError, InvalidCredentialsError
    # ... register handlers
```

**Per-task validation:**
- `uv run ruff format app/core/exceptions.py`
- `uv run ruff check --fix app/core/exceptions.py` passes
- `uv run mypy app/core/exceptions.py` passes with 0 errors
- `uv run pyright app/core/exceptions.py` passes

---

### Task 11: Simplify Auth Routes (Remove Manual Exception Handling)
**File:** `app/auth/routes.py` (modify existing)
**Action:** UPDATE

Now that auth exceptions are handled globally (Task 10), simplify the login route. Remove the try/except block and let exceptions propagate to the global handler.

Replace the login function body (lines 30-43) from:
```python
async def login(...) -> LoginResponse | JSONResponse:
    _ = request
    try:
        return await service.authenticate(body.email, body.password)
    except InvalidCredentialsError:
        return JSONResponse(...)
    except AccountLockedError:
        return JSONResponse(...)
```

To:
```python
async def login(...) -> LoginResponse:
    """Authenticate user with email and password."""
    _ = request
    return await service.authenticate(body.email, body.password)
```

Key changes:
- Return type changes from `LoginResponse | JSONResponse` to just `LoginResponse`
- Remove `JSONResponse` import if it's no longer used (check if seed endpoint uses it — it doesn't, so remove it)
- Remove `InvalidCredentialsError` and `AccountLockedError` imports (no longer used in this file)
- Remove the `status` import if only used for the exception handling (check — it's not used elsewhere, so remove)

**Per-task validation:**
- `uv run ruff format app/auth/routes.py`
- `uv run ruff check --fix app/auth/routes.py` passes
- `uv run mypy app/auth/routes.py` passes with 0 errors
- `uv run pyright app/auth/routes.py` passes

---

### Task 12: Secure the Seed Endpoint
**File:** `app/auth/routes.py` (modify existing)
**Action:** UPDATE

The `/api/v1/auth/seed` endpoint is publicly accessible. Add environment-based protection so it only works in development mode.

Update the seed endpoint to check the environment:
```python
from app.core.config import get_settings

@router.post("/seed", response_model=list[UserResponse])
@limiter.limit("5/minute")
async def seed_demo_users(
    request: Request,
    service: AuthService = Depends(get_service),  # noqa: B008
) -> list[UserResponse]:
    """Seed demo users (development only, no-op if users exist)."""
    _ = request
    settings = get_settings()
    if settings.environment != "development":
        return []
    users = await service.seed_demo_users()
    return [UserResponse.model_validate(u) for u in users]
```

This silently returns an empty list in non-development environments. No error, no information leak.

**Per-task validation:**
- `uv run ruff format app/auth/routes.py`
- `uv run ruff check --fix app/auth/routes.py` passes
- `uv run mypy app/auth/routes.py` passes with 0 errors
- `uv run pyright app/auth/routes.py` passes

---

### Task 13: Add Rate Limiting to Transit `/feeds` Endpoint
**File:** `app/transit/routes.py` (modify existing)
**Action:** UPDATE

The `/feeds` endpoint (line 47) is missing a rate limiter, unlike all other endpoints in the application.

Add the rate limiter decorator and `Request` parameter:
```python
@router.get("/feeds")
@limiter.limit("30/minute")
async def get_feeds(request: Request) -> list[dict[str, object]]:
    """List configured transit feeds and their status."""
    _ = request
    settings = get_settings()
    ...
```

Note: `Request` and `limiter` are already imported in this file.

**Per-task validation:**
- `uv run ruff format app/transit/routes.py`
- `uv run ruff check --fix app/transit/routes.py` passes
- `uv run mypy app/transit/routes.py` passes with 0 errors
- `uv run pyright app/transit/routes.py` passes

---

### Task 14: Tighten Upload Path Matching in Body Size Middleware
**File:** `app/core/middleware.py` (modify existing)
**Action:** UPDATE

The current check (line 56) `if "/import" in path or "/knowledge" in path` is overly broad — any URL containing these substrings gets the 10MB limit.

Replace with explicit path prefix matching:
```python
# Allow larger uploads for specific file-based endpoints
path = request.url.path
upload_paths = (
    "/api/v1/schedules/import",
    "/api/v1/schedules/validate",
    "/api/v1/knowledge",
)
if any(path.startswith(p) for p in upload_paths):
    max_size = 10_485_760  # 10MB for file uploads
else:
    max_size = self._max_body_size
```

This restricts the 10MB allowance to exactly the endpoints that need it: GTFS import, GTFS validation (also accepts ZIP uploads), and all knowledge endpoints (document upload).

**Per-task validation:**
- `uv run ruff format app/core/middleware.py`
- `uv run ruff check --fix app/core/middleware.py` passes
- `uv run mypy app/core/middleware.py` passes with 0 errors
- `uv run pyright app/core/middleware.py` passes

---

### Task 15: Add Nginx Health Check Location Block
**File:** `nginx/nginx.conf` (modify existing)
**Action:** UPDATE

The nginx service now has a Docker healthcheck that curls `http://localhost:80/health` (added in Task 1). The `/health` location block already exists (lines 83-91) and proxies to FastAPI, so this should work. However, the healthcheck inside the container hits nginx itself, which then proxies to FastAPI. If FastAPI is down, the nginx healthcheck fails — which is correct behavior (nginx should report unhealthy if its upstream is down).

No nginx config change needed. Verify the existing `/health` location block is correct.

**SKIP this task if the `/health` location block already correctly proxies to FastAPI.**

**Per-task validation:**
- Read `nginx/nginx.conf` and confirm `/health` location exists with `proxy_pass http://fastapi`

---

### Task 16: Fix Pyright Platform Configuration
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Line 181: `pythonPlatform = "Darwin"` is macOS-specific. Docker containers and CI run Linux.

Remove this line entirely. Pyright defaults to the current platform, which is correct for local development, and removing the hard-coded value prevents false positives in Linux environments.

**Per-task validation:**
- `uv run pyright app/` passes (verify no new errors from removing the platform setting)

---

### Task 17: Add email-validator as Explicit Dependency
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

`app/auth/schemas.py` uses Pydantic's `EmailStr` which requires `email-validator`. It currently works as a transitive dependency but should be explicit.

Add to the `dependencies` list in `pyproject.toml`:
```toml
"email-validator>=2.0.0",
```

Insert it alphabetically (after `"bcrypt>=5.0.0"`).

Then run:
```bash
uv lock
```

**Per-task validation:**
- `uv lock` succeeds
- `uv run python -c "from pydantic import EmailStr; print('OK')"` exits 0

---

### Task 18: Update `.env.example` Documentation
**File:** `.env.example` (modify existing)
**Action:** UPDATE

Add documentation for the `ENVIRONMENT` setting's impact on the seed endpoint. After line 3 (`ENVIRONMENT=development`), add a comment:
```bash
# ENVIRONMENT controls seed endpoint access:
# - "development": /api/v1/auth/seed creates demo users
# - "production" or any other value: seed endpoint returns empty (no-op)
ENVIRONMENT=development
```

Also update the Auth section (after line 51) to note that demo users all use "admin" as password and should be changed:
```bash
# Auth (REQUIRED for Docker deployment - generate with: openssl rand -base64 32)
# AUTH_SECRET=<generate-a-real-secret>
# NOTE: Demo seed users all use password "admin" - change in production
```

**Per-task validation:**
- Read the file and confirm comments are present

---

### Task 19: Run Full Validation Pyramid
**File:** N/A (validation only)
**Action:** VALIDATE

Run the complete validation pyramid to ensure all changes pass:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (all features)**
```bash
uv run pytest -v -m "not integration"
```

If any level fails, fix the issue before proceeding to the next level. If fixing introduces a new error, re-run ALL checks from Level 1.

**Per-task validation:**
- All 3 levels exit with code 0
- Zero errors, zero warnings

---

## Migration (if applicable)

No new database migrations required by this plan. The changes are:
- Docker orchestration (compose, Dockerfile, nginx)
- Python application code (middleware, exceptions, routes)
- Configuration (pyproject.toml, .env.example)

The `migrate` service added in Task 3 runs existing migrations (`alembic upgrade head`) automatically on Docker startup. No new tables or columns are added.

## Logging Events

No new logging events added. Existing events affected:
- `auth.invalid_credentials` — Now emitted by global handler (was inline in routes)
- `auth.account_locked` — Now emitted by global handler (was inline in routes)

## Testing Strategy

### Unit Tests
**Location:** Existing test files
- `app/auth/tests/` — Verify login still returns 401/423 for invalid credentials/locked accounts
- `app/core/tests/` — Verify `get_db()` rollback behavior

### Integration Tests
**Mark with:** `@pytest.mark.integration`
- Database session rollback on simulated error

### Edge Cases
- Seed endpoint returns `[]` when `ENVIRONMENT=production` (no error, no info leak)
- CMS healthcheck curl works after Docker build
- Migration service exits successfully before app starts
- Nginx allows 10MB uploads to `/api/v1/schedules/import`
- Nginx blocks >1MB to non-API routes

### Existing Test Impact
- Auth route tests may need updating if they assert on `JSONResponse` from login endpoint (now handled by global exception handler returning same content)
- Transit route tests for `/feeds` may need `request` fixture if they use `TestClient` (rate limiter needs `Request`)

## Acceptance Criteria

This feature is complete when:
- [ ] `docker-compose config` validates without errors
- [ ] `make docker` starts all services with proper ordering (db -> migrate -> app, redis -> app, app -> cms -> nginx)
- [ ] Database migrations run automatically on fresh Docker startup
- [ ] Nginx allows 10MB uploads to `/api/v1/schedules/import` and `/api/v1/knowledge/*`
- [ ] Auth exceptions (401, 423) handled consistently via global exception handlers
- [ ] Seed endpoint returns empty list in non-development environments
- [ ] Transit `/feeds` endpoint has rate limiting
- [ ] Database sessions rolled back on unhandled exceptions
- [ ] All type checkers pass (mypy + pyright)
- [ ] All unit tests pass
- [ ] No new type suppressions added beyond what's documented

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order (Tasks 1-19)
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-3 in Task 19)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (all features)**
```bash
uv run pytest -v -m "not integration"
```

**Level 4: Docker Validation**
```bash
docker-compose config
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-3 exit code 0, all tests pass, zero errors. Level 4 validates compose syntax. Level 5 optional.

## Dependencies

- Shared utilities used: `get_settings()`, `get_logger()`, `PaginationParams`, `TimestampMixin`, `ErrorResponse`
- Core modules used: `app.core.config`, `app.core.database`, `app.core.exceptions`, `app.core.middleware`, `app.core.rate_limit`, `app.core.redis`
- New dependencies: `email-validator>=2.0.0` (explicit — was transitive via Pydantic)
- New env vars: None new — `ENVIRONMENT` already exists, just documented its impact on seed

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101 forbids assert outside test files. Use conditional checks instead.
2. **No `object` type hints** — Import and use actual types directly. Never write `def f(data: object)` then isinstance-check.
3. **Untyped third-party libraries** — When adding a dependency without `py.typed`:
   - mypy: Add `[[tool.mypy.overrides]]` with `ignore_missing_imports = true`
   - pyright: Add file-level `# pyright: reportUnknown...=false` directives to the ONE file interfacing with the library
   - **NEVER** use pyright `[[executionEnvironments]]` with a scoped `root` — it breaks `app.*` import resolution
4. **Mock exceptions must match catch blocks** — If production code catches `httpx.HTTPError`, tests must mock `httpx.ConnectError` (or another subclass), not bare `Exception`.
5. **No unused imports or variables** — Ruff F401 catches unused imports, Ruff F841 catches unused local variables. Don't write speculative code — only import/assign what you actually use.
6. **No unnecessary noqa/type-ignore** — Ruff RUF100 flags unused suppression comments.
7. **Test helper functions need return type annotations** — mypy `disallow_untyped_defs=false` for tests only relaxes *defining* untyped functions, but `disallow_untyped_call` is still globally true.
8. **No EN DASH in strings** — Ruff RUF001 forbids ambiguous Unicode characters like `--` (EN DASH, U+2013). Always use `-` (HYPHEN-MINUS, U+002D).
9. **Circular imports with lazy imports** — When `app.core.exceptions` needs to import from `app.auth.exceptions`, use lazy imports inside the function body to break the cycle: `from app.auth.exceptions import ...` inside `setup_exception_handlers()`, NOT at module level.
10. **FastAPI `Query(None)` needs `# noqa: B008`** — Just like `Depends()`, `Query()` is a function call in argument defaults. Ruff B008 flags all of these.
11. **ARG001 applies to ALL unused function params** — Any function parameter not used in the body triggers ARG001. For `request` in rate-limited endpoints, always add `_ = request`.
12. **Removing imports may break other references** — When removing `InvalidCredentialsError` import from `app/auth/routes.py`, verify no other code in that file references it.
13. **Docker healthcheck `curl` must be installed in the image** — Alpine images don't have curl by default. The CMS Dockerfile must install it.
14. **`docker-compose config` validates syntax but not runtime** — Always verify service dependencies form a DAG (no cycles).
15. **`uv lock` after adding dependencies** — After modifying `pyproject.toml` dependencies, always run `uv lock` to update the lockfile before any other validation.

## Notes

**Security decisions:**
- The seed endpoint is gated by `ENVIRONMENT != "development"` rather than removed entirely, because it's useful for development and demo deployments. The existing guard (`if count > 0: return []`) prevents re-seeding even in development.
- Demo passwords remain `"admin"` — this is acceptable for development. Production deployments should change passwords after seeding or use a different user creation flow.

**Future considerations:**
- The redundant `index=True` on primary key columns (`id` fields in all models) could be cleaned up in a future migration, but the cost is negligible and removing them requires a migration that drops indexes.
- The module-level `engine = create_async_engine(...)` in `database.py` prevents lazy initialization. This could be refactored to a factory pattern, but it works correctly for all current use cases (tests mock the engine, Docker always has `DATABASE_URL`).
- Consider adding `docker-compose.prod.yml` override for production (no exposed DB/Redis ports, no seed endpoint, TLS termination).

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach — in-place fixes, no new features
- [ ] Clear on task execution order (Docker first, then backend, then cleanup)
- [ ] Validation commands are executable in this environment
- [ ] `uv run ruff --version` works (dev dependencies installed)
