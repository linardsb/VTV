# Plan: OPS-4.3 Authorization Audit Log

## Context

Compliance and incident response require "who tried to access what and got denied". Currently, auth denials are logged via structlog (`auth.token_invalid`, `auth.role_escalation_attempt`, etc.) but not persisted to a queryable store. Without audit trails, breach investigation has no primary evidence. This feature emits structured `auth.denied` events and persists them to a TimescaleDB hypertable with an admin query API.

## Security Context Assessment

| Context | Active | Reason |
|---------|--------|--------|
| CTX-AUTH | **Yes** | Touches auth denial paths, JWT rejection, token revocation |
| CTX-RBAC | **Yes** | New admin endpoint needs role gate; audit touches RBAC scope denial |
| CTX-INPUT | **Yes** | Admin query endpoint accepts date-range + user_id filters |
| CTX-INFRA | No | No Docker/nginx changes |
| CTX-FILE | No | No file uploads |
| CTX-AGENT | No | No agent tools |

## Research Summary

### Current Auth Denial Points (Hook Locations)

| Hook | File | Lines | Status Code | Current Log Event |
|------|------|-------|-------------|-------------------|
| Missing credentials | `app/auth/dependencies.py` | 59-64 | 401 | (none) |
| Invalid/expired JWT | `app/auth/dependencies.py` | 66-73 | 401 | `auth.token_invalid` |
| Token revoked | `app/auth/dependencies.py` | 76-82 | 401 | `auth.token_revoked` |
| User not found | `app/auth/dependencies.py` | 97-104 | 401 | `auth.token_invalid` |
| Inactive user | `app/auth/dependencies.py` | 106-111 | 403 | `auth.unauthorized_access` |
| Role check failure | `app/auth/dependencies.py` | 131-141 | 403 | `auth.role_escalation_attempt` |
| Rate limit exceeded | `app/main.py` | 262 | 429 | (none - slowapi handler) |

### Existing Patterns to Follow

- **TimescaleDB hypertable:** `alembic/versions/b7c8d9e0f1a2_add_vehicle_positions_hypertable.py` — create table, check TimescaleDB availability, `create_hypertable()`, compression, retention policy
- **Admin endpoints:** `app/core/auth/routes.py` (assignments CRUD, prefix `/api/v1/admin/assignments`), `app/core/jobs/routes.py` (job status, prefix `/admin/jobs`)
- **Structured logging:** `get_logger(__name__)`, event naming `domain.component.action_state`
- **Pagination:** `PaginationParams` + `PaginatedResponse[T]` from `app.shared.schemas`
- **Request ID:** `get_request_id()` from `app.core.logging` (ContextVar, set by `RequestLoggingMiddleware`)
- **Rate limit identity:** `request.state.rate_limit_user_id` / `request.state.rate_limit_role` (set by `RateLimitIdentityMiddleware`)

### Scope Denial Hook — Deviation from Spec

The spec lists `app/core/auth/scope.py::get_request_scope` as a hook point, but `get_request_scope()` never denies — it resolves scope (returning a `RequestScope` with route_ids). Denial happens implicitly downstream in repository methods that return empty results or 404s. There is no single interception point in `scope.py` to emit an audit event. Scope-based denials manifest as "resource not found" (404) at the route level, not as explicit 403s. This hook is intentionally omitted.

### Key Design Decision: Dedicated Module Location

Place audit helper in `app/core/auth/audit.py` alongside existing `scope.py` and `routes.py`. The model goes in `app/core/auth/models.py` (already has `DispatcherAssignment`). Admin query routes go in `app/core/auth/routes.py` (extend existing admin router). No new VSA feature directory needed.

## Test Landscape

### Existing Fixtures Available
- `conftest.py`: `client` (TestClient), `mock_settings`, `_clear_auth_cache`
- `app/core/auth/tests/conftest.py`: `make_scope()` factory
- Auth override pattern: `app.dependency_overrides[get_current_user] = _mock_admin_user`

### Test Patterns to Follow
- Structlog capture: `from structlog.testing import capture_logs; with capture_logs() as cap_logs:`
- Admin role gate: fixture sets `dependency_overrides[get_current_user]`, yield, restore
- Rate limiter disabled: `limiter.enabled = False` at module level
- Mock AsyncSession: `AsyncMock()` for repo tests
- Security convention tests auto-discover endpoints via `app.routes`

## Type Check Baseline

- `app/core/auth/` — **0 errors** (pyright + mypy)
- `app/core/rate_limit.py` — **0 errors** (pyright + mypy)
- `app/admin/` — Does not exist (not needed; routes go in `app/core/auth/routes.py`)

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/core/auth/audit.py` | `emit_auth_denial()` helper + `AuthAuditRepository` |
| UPDATE | `app/core/auth/models.py` | Add `AuthAuditEvent` SQLAlchemy model |
| CREATE | `app/core/auth/schemas.py` | Request/response schemas for audit query API |
| UPDATE | `app/core/auth/routes.py` | Add `GET /api/v1/admin/audit/auth` endpoint |
| UPDATE | `app/auth/dependencies.py` | Call `emit_auth_denial()` at each rejection point |
| UPDATE | `app/core/rate_limit.py` | Add custom 429 handler that calls `emit_auth_denial()` |
| UPDATE | `app/main.py` | Register custom rate limit handler, import audit router if separate |
| CREATE | `alembic/versions/xxxx_auth_audit_events.py` | TimescaleDB hypertable migration |
| UPDATE | `app/core/config.py` | Add `auth_audit_enabled` + `auth_audit_retention_days` settings |
| CREATE | `app/core/auth/tests/test_audit.py` | 12 unit tests for audit functionality |
| UPDATE | `docs/logging-standard.md` | Document `auth.audit.denied` event |

## Implementation Steps

### Step 1: Config settings
**File:** `app/core/config.py`
**Action:** Add settings to `Settings` class:
```python
# Auth audit log (OPS-4.3)
auth_audit_enabled: bool = True
auth_audit_retention_days: int = 90
```
**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: SQLAlchemy model
**File:** `app/core/auth/models.py`
**Action:** Add `AuthAuditEvent` model after existing `DispatcherAssignment`:
```python
class AuthAuditEvent(Base):
    """Persisted authorization denial event for compliance audit trail."""
    __tablename__ = "auth_audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, server_default=func.now()
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    enforcement_layer: Mapped[str] = mapped_column(String(50), nullable=False)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
```
Note: No `TimestampMixin` — hypertable uses `recorded_at` as time column, and audit events are immutable (no `updated_at`).
**Validation:** `uv run ruff check app/core/auth/models.py && uv run pyright app/core/auth/models.py`

### Step 3: Alembic migration
**File:** `alembic/versions/xxxx_auth_audit_events.py`
**Action:** Create migration following `b7c8d9e0f1a2` hypertable pattern:
1. Create `auth_audit_events` table with columns from Step 2
2. Create composite index on `(user_id, recorded_at DESC)`
3. Check TimescaleDB availability
4. If available: `create_hypertable('auth_audit_events', 'recorded_at', chunk_time_interval => INTERVAL '1 day')`
5. Enable compression: segmentby `enforcement_layer`, orderby `recorded_at DESC`
6. Add compression policy: 7 days
7. Add retention policy: `{auth_audit_retention_days}` days (default 90, but migration uses 90 as static default since settings aren't available at migration time)
**Run:** `make db-revision m="add_auth_audit_events_hypertable"` then `make db-migrate`
**Validation:** Migration generates cleanly, `make db-migrate` succeeds

### Step 4: Pydantic schemas
**File:** `app/core/auth/schemas.py` (CREATE)
**Action:**
```python
"""Schemas for auth audit query API (OPS-4.3)."""
import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EnforcementLayer = Literal["jwt", "role", "scope", "rate_limit"]

class AuthAuditEventResponse(BaseModel):
    """Single audit event in API response."""
    id: int
    recorded_at: datetime.datetime
    request_id: str
    user_id: int | None
    path: str
    method: str
    status_code: int
    reason: str
    enforcement_layer: str
    client_ip: str | None
    user_role: str | None
    extra: dict[str, Any] | None

    model_config = {"from_attributes": True}

```
Note: No separate query params schema — the admin endpoint uses inline `Query()` params directly (matches existing assignment endpoint pattern). `EnforcementLayer` Literal type is exported for use in the route.
**Validation:** `uv run ruff check app/core/auth/schemas.py && uv run pyright app/core/auth/schemas.py`

### Step 5: Audit helper + repository
**File:** `app/core/auth/audit.py` (CREATE)
**Action:**
- `AuthAuditRepository` class with:
  - `insert(event: AuthAuditEvent) -> None` — single insert
  - `list(*, user_id, from_date, to_date, enforcement_layer, status_code, offset, limit) -> list[AuthAuditEvent]` — filtered query
  - `count(*, same filters) -> int` — for pagination
- `emit_auth_denial()` async function:
  1. Emits structured log: `logger.warning("auth.audit.denied", request_id=..., user_id=..., path=..., reason=..., enforcement_layer=...)`
  2. If `settings.auth_audit_enabled`: fire-and-forget insert to DB via `asyncio.create_task()` (wraps in try/except to never raise)
  3. PII safety: never logs password, token, or authorization header values
- `_get_request_context(request: Request) -> dict` helper to extract request_id, path, method, client_ip from request (uses `get_request_id()` + `request.client.host`)
- Import: `from app.core.logging import get_logger, get_request_id`

**Key design:**
- `emit_auth_denial()` accepts `request: Request | None` (None for cases where request context isn't easily available)
- Fire-and-forget DB write: `asyncio.create_task(_persist_audit_event(...))` with exception handler
- Uses `get_db_context()` from `app.core.database` for standalone session (not request-scoped, since audit writes should not participate in the request's transaction)

**Validation:** `uv run ruff check app/core/auth/audit.py && uv run pyright app/core/auth/audit.py`

### Step 6: Wire into auth dependencies
**File:** `app/auth/dependencies.py`
**Action:** At each HTTPException raise point, call `emit_auth_denial()` before raising:

1. **Line 59-64** (missing credentials): Add `await emit_auth_denial(request=None, user_id=None, path="unknown", method="unknown", status_code=401, reason="missing_credentials", enforcement_layer="jwt")`
   - Note: `get_current_user` doesn't have access to `Request`. Two options:
     - **Option A:** Add `request: Request` parameter to `get_current_user` — but this breaks the dependency signature used everywhere via `Depends(get_current_user)`.
     - **Option B:** Use ContextVar for request_id (already available) and skip path/method for dependency-level denials, filling them in via middleware post-processing.
     - **Chosen: Option A modified** — add `request: Request` as a FastAPI dependency parameter. FastAPI auto-injects `Request` into dependency functions. This is safe because `Request` is always available in the dependency chain. Existing `Depends(get_current_user)` and `Depends(require_role(...))` callers don't need changes since FastAPI resolves `Request` automatically.

   Update signature: `async def get_current_user(request: Request, credentials: ... , db: ...) -> User:`
   Then at each rejection:
   ```python
   await emit_auth_denial(
       request=request,
       user_id=payload.sub if payload else None,
       status_code=401,
       reason="token_invalid",
       enforcement_layer="jwt",
   )
   ```

2. **Line 66-73** (invalid token): `reason="token_invalid_or_expired"`, `enforcement_layer="jwt"`
3. **Line 76-82** (revoked): `reason="token_revoked"`, `enforcement_layer="jwt"`, `user_id=payload.sub`
4. **Line 97-104** (user not found): `reason="user_not_found"`, `enforcement_layer="jwt"`, `user_id=payload.sub`
5. **Line 106-111** (inactive): `reason="account_inactive"`, `enforcement_layer="jwt"`, `user_id=user.id`
6. **Line 131-141** (role check): `reason=f"role_required:{','.join(roles)}"`, `enforcement_layer="role"`, `user_id=current_user.id`
   - `require_role._check_role` also needs `request: Request` parameter (same auto-injection pattern)

**Validation:** `uv run ruff check app/auth/dependencies.py && uv run pyright app/auth/dependencies.py`

### Step 7: Wire into rate limit handler
**File:** `app/core/rate_limit.py` + `app/main.py`
**Action:**
- Create custom rate limit exceeded handler in `app/core/rate_limit.py`:
  ```python
  async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
      """Custom 429 handler that emits auth audit event."""
      user_id = getattr(request.state, "rate_limit_user_id", None)
      await emit_auth_denial(
          request=request,
          user_id=user_id,
          status_code=429,
          reason=f"rate_limit_exceeded:{exc.detail}",
          enforcement_layer="rate_limit",
          extra={"user_role": getattr(request.state, "rate_limit_role", None)},
      )
      return JSONResponse(
          status_code=429,
          content={"error": f"Rate limit exceeded: {exc.detail}"},
          headers=getattr(exc, "headers", None) or {},
      )
  ```
- In `app/main.py`: Replace `_rate_limit_exceeded_handler` import with `rate_limit_exceeded_handler` from `app.core.rate_limit`
- Update line 262: `app.add_exception_handler(RateLimitExceeded, cast(Any, rate_limit_exceeded_handler))`

**Validation:** `uv run ruff check app/core/rate_limit.py app/main.py && uv run pyright app/core/rate_limit.py app/main.py`

### Step 8: Admin query endpoint
**File:** `app/core/auth/routes.py`
**Action:** Add to existing assignments router file:
```python
@router.get(
    "/audit/auth",
    response_model=PaginatedResponse[AuthAuditEventResponse],
    summary="Query authorization audit events",
)
@limiter.limit("30/minute")
async def list_auth_audit_events(
    request: Request,
    _current_user: User = Depends(require_role("admin")),
    pagination: PaginationParams = Depends(),
    from_date: datetime.datetime | None = Query(None, alias="from"),  # noqa: B008
    to_date: datetime.datetime | None = Query(None, alias="to"),  # noqa: B008
    user_id: int | None = Query(None),  # noqa: B008
    enforcement_layer: EnforcementLayer | None = Query(None),  # noqa: B008
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AuthAuditEventResponse]:
    repo = AuthAuditRepository(db)
    total = await repo.count(user_id=user_id, from_date=from_date, to_date=to_date, enforcement_layer=enforcement_layer)
    items = await repo.list(user_id=user_id, from_date=from_date, to_date=to_date, enforcement_layer=enforcement_layer, offset=pagination.offset, limit=pagination.page_size)
    return PaginatedResponse[AuthAuditEventResponse](
        items=[AuthAuditEventResponse.model_validate(e) for e in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
```
Note: The router prefix is already `/api/v1/admin/assignments`, so either:
- **Option A:** Create a separate router for `/api/v1/admin/audit` and register in main.py
- **Option B:** Use the existing router but change the prefix to `/api/v1/admin` and adjust assignment paths

**Chosen: Option A** — Create `audit_router` in the same `routes.py` file with prefix `/api/v1/admin/audit`, register separately in `main.py`. Keeps assignment routes unchanged.

**Validation:** `uv run ruff check app/core/auth/routes.py && uv run pyright app/core/auth/routes.py`

### Step 9: Register audit router in main.py
**File:** `app/main.py`
**Action:**
- Add import: `from app.core.auth.routes import audit_router`
- Add after assignments router: `app.include_router(audit_router)`
- Update rate limit handler import (from Step 7)

**Validation:** `uv run ruff check app/main.py && uv run pyright app/main.py`

### Step 10: Unit tests
**File:** `app/core/auth/tests/test_audit.py` (CREATE)
**Action:** 12 tests:

**Denial event emission (3):**
1. `test_emit_auth_denial_logs_structured_event` — `capture_logs()`, verify event name `auth.audit.denied`, all fields present
2. `test_emit_auth_denial_disabled_skips_db_write` — set `auth_audit_enabled=False`, verify log emitted but no DB insert
3. `test_emit_auth_denial_db_error_does_not_raise` — mock DB to raise, verify no exception propagates (fire-and-forget safety)

**Hypertable insert (1):**
4. `test_audit_repository_insert` — mock AsyncSession, verify `session.add()` + `session.flush()` called with correct model

**Retention policy (1):**
5. `test_migration_sets_retention_policy` — read migration file, assert `add_retention_policy` with 90 days

**Admin query filters (3):**
6. `test_audit_endpoint_filters_by_user_id` — mock repo, call with `?user_id=42`, verify filter passed
7. `test_audit_endpoint_filters_by_date_range` — mock repo, call with `?from=...&to=...`
8. `test_audit_endpoint_filters_by_enforcement_layer` — mock repo, call with `?enforcement_layer=jwt`

**Pagination (1):**
9. `test_audit_endpoint_pagination` — mock repo returning 50 total, request page 2, verify offset calculation

**Index usage (1):**
10. `test_composite_index_exists_in_migration` — read migration file, assert index on `(user_id, recorded_at)`

**PII redaction (2):**
11. `test_audit_event_never_contains_password` — emit denial with request containing password field, verify `extra` dict does not contain `password` or `token`
12. `test_audit_event_never_contains_auth_header` — verify `authorization` header value not stored

**Admin role gate (1 bonus):**
13. `test_audit_endpoint_requires_admin` — dispatcher gets 403

**Validation:** `uv run pytest app/core/auth/tests/test_audit.py -v`

### Step 11: Update logging taxonomy
**File:** `docs/logging-standard.md`
**Action:** Add under auth domain:
- `auth.audit.denied` — WARNING — Authorization denial persisted to audit trail. Fields: `request_id`, `user_id`, `path`, `method`, `status_code`, `reason`, `enforcement_layer`

**Validation:** `make audit-log-taxonomy`

## Preflight Warnings

- `app/auth/dependencies.py` — Adding `request: Request` parameter to `get_current_user`: callers via `Depends(get_current_user)` are unaffected (FastAPI resolves `Request` automatically). `dependency_overrides` in tests also unaffected (FastAPI resolves the override function's own signature independently). **Direct calls** like `await get_current_user(credentials=..., db=...)` in `app/auth/tests/test_dependencies.py` **will break** — they need a `request` argument added. Grep for `get_current_user(` (not `Depends(`) in test files to find them.
- `app/main.py` line 262 — Replacing `_rate_limit_exceeded_handler` changes the 429 response behavior. Verify rate limit response format stays compatible (existing tests may assert on response body).
- `app/core/auth/routes.py` — Adding a second router to this file requires careful import management in `main.py`.
- Rate limit handler is currently a slowapi import. The custom handler must preserve slowapi's response headers (`X-RateLimit-*`, `Retry-After`).

## Security Checklist

For the new `GET /api/v1/admin/audit/auth` endpoint:
- [x] `require_role("admin")` dependency
- [x] `@limiter.limit("30/minute")` rate limiting
- [x] Input validation via Query params with types (datetime, int, Literal)
- [x] Error responses use standard FastAPI HTTPException
- [x] No ILIKE queries needed (exact match filters only)
- [x] PII: never store password/token/authorization header in audit events
- [x] Never expose role names in denial error messages to end users (audit events are admin-only, so role info is acceptable in stored events)

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] New endpoint has auth (`require_role("admin")`) + rate limiting (`30/minute`)
- [ ] Pyright errors <= baseline (0 errors before)
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
- [ ] Trigger a 403, 401, and 429 -> all three appear in `GET /admin/audit/auth`
- [ ] Dispatcher accessing admin-only endpoint -> event logged with `reason="role_required:admin"`
- [ ] Logging taxonomy audit passes: `make audit-log-taxonomy`
- [ ] ER diagram updated: `make er-diagram` (required after new migration per CLAUDE.md)
