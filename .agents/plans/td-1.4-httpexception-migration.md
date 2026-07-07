# Plan: Codebase-wide `HTTPException` → `AppError` Migration (T-001 follow-up)

> **Source:** `TECH_DEBT_AUDIT.md` Section 3, T-001 disposition (codebase-wide
> migration of remaining raises was tagged `→ DEEPEN`; T-021 also folds in).
> **Stage tag:** Tech-Debt 1.4 (transit slice was 1.3 quick win).
> **Workflow:** `/be-execute .agents/plans/td-1.4-httpexception-migration.md`
> after maintainer review.

## Background

CLAUDE.md mandates: *"Inherit from `AppError` in `core.exceptions` for
automatic HTTP status mapping."* Transit slice T-001 migrated 7 raises in
`app/transit/routes.py`; this plan finishes the rest.

**Current AppError taxonomy** (`app/core/exceptions.py`):
- `NotFoundError` → 404
- `ConflictError` → 409
- `GoneError` → 410
- `DomainValidationError` → 422
- `RBACConfigurationError` → 500
- (auth-flow specific) `InvalidCredentialsError`, `AccountLockedError`,
  `InvalidAPIKeyError`, `APIKeyRateLimitError` — stay as-is, separate handlers.

**Inventory** — `grep -rn "raise HTTPException" app/ --include="*.py" | grep -v "tests/"`:

| File | Lines | Status code(s) | Disposition |
|------|-------|----------------|-------------|
| `app/analytics/routes.py` | 128, 136, 167, 170, 173 | 400 ×4, 503 ×1 | **Migrate** — 400 → `BadRequestError` (new), 503 → `ServiceUnavailableError` (new) |
| `app/auth/routes.py` | 68, 210 | 404, ? | **Migrate** — 404 → `NotFoundError`; verify L68 status |
| `app/auth/dependencies.py` | 69, 85, 101, 119, 137, 152, 191 | 401 ×7 | **KEEP** — each call site precedes `emit_auth_denial()` (OPS-4.3 audit log); `WWW-Authenticate: Bearer` header is part of the 401 contract; converting these would require parallel handler that both emits the audit row AND sets the auth header |
| `app/core/agents/routes.py` | 66 | ? | **Migrate** (verify status) |
| `app/core/health.py` | 438, 469, 477, 518, 537, 573, 617 | 503 mostly | **KEEP** — health probes are intentionally HTTP-direct so readiness/liveness probes get exact status codes without going through the app-error machinery; latency budget matters |
| `app/fleet/routes.py` | 47, 50 | 401 ×2 | **KEEP** (or new `WebhookAuthError`) — webhook token check, not user JWT; fold into a future webhook-auth refactor (out of scope for this PR) |
| `app/knowledge/routes.py` | 129, 134, 156, 347, 437 | 400/422 ×2, 413, 409, 422 | **Migrate** — 409 → `ConflictError`, 413 → `PayloadTooLargeError` (new), 422 → `DomainValidationError`, 400 → `BadRequestError` (new) |
| `app/schedules/routes.py` | 438 | ? | **Migrate** (verify status) |
| `app/transit/routes.py` | 412 | 503 | **Migrate** — `TransitDataError` → `ServiceUnavailableError` (closes T-021) |

**Net migrate count:** ~14 raises across 6 files. ~16 raises stay (auth/health/fleet by design).

## New AppError subclasses

Add to `app/core/exceptions.py`:

1. **`BadRequestError(AppError)` → 400** — generic client-input error
   distinct from validation. Used when the request shape parses but the
   *combination* of values is invalid (date_from > date_to, range > 90
   days). Keep `DomainValidationError` for true Pydantic-level shape
   issues.
2. **`PayloadTooLargeError(AppError)` → 413** — request body exceeds
   server limit. Single use site today (knowledge upload), but the global
   `BodySizeLimitMiddleware` already returns 413 directly for the 100KB
   middleware limit; this exception is for the per-route 50MB knowledge
   upload limit.
3. **`ServiceUnavailableError(AppError)` → 503** — transient upstream
   dependency failure. Replaces analytics line-136 raw-503 and
   transit:412 (T-021).

Status mapping update in `app_exception_handler` (`app/core/exceptions.py:86-95`):

```python
status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
if isinstance(exc, NotFoundError):
    status_code = status.HTTP_404_NOT_FOUND
elif isinstance(exc, ConflictError):
    status_code = status.HTTP_409_CONFLICT
elif isinstance(exc, GoneError):
    status_code = status.HTTP_410_GONE
elif isinstance(exc, DomainValidationError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
elif isinstance(exc, BadRequestError):                        # NEW
    status_code = status.HTTP_400_BAD_REQUEST
elif isinstance(exc, PayloadTooLargeError):                   # NEW
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
elif isinstance(exc, ServiceUnavailableError):                # NEW
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
```

Add corresponding `app.add_exception_handler(...)` registrations in
`setup_exception_handlers` (`app/core/exceptions.py:202`).

## Implementation Order

1. **Step 1 — `app/core/exceptions.py`** (single source of truth)
   - Add `BadRequestError`, `PayloadTooLargeError`, `ServiceUnavailableError` classes (each: `class X(AppError): pass`).
   - Update `app_exception_handler` status_code chain.
   - Register all three in `setup_exception_handlers`.
   - Update `app/shared/__init__.py` / module re-exports if any.

2. **Step 2 — `app/analytics/routes.py`** (5 raises)
   - L128: `ValueError` from service → `BadRequestError(str(e))`.
   - L136: 503 fallback → `ServiceUnavailableError("Transit data temporarily unavailable")`.
   - L167: `Invalid date format` → `BadRequestError("Invalid date format")`.
   - L170: `date_from must be <= date_to` → `BadRequestError(...)`.
   - L173: `Date range must not exceed 90 days` → `BadRequestError(...)`.
   - Update existing test assertions that match `HTTPException` to match the new types.

3. **Step 3 — `app/knowledge/routes.py`** (5 raises)
   - L129/L134: verify status, migrate to `BadRequestError` or `DomainValidationError`.
   - L156: `File exceeds 50MB limit` → `PayloadTooLargeError(...)`.
   - L347: 409 conflict → `ConflictError(str(e))`.
   - L437: `query_hash must be 32 hex chars` → `DomainValidationError(...)` (shape-level).

4. **Step 4 — `app/transit/routes.py:412`** (closes T-021)
   - `except TransitDataError as exc: raise ServiceUnavailableError(str(exc)) from exc`.
   - Remove the comment in §6 of `TECH_DEBT_AUDIT.md` that flags this as the deliberate bridge.

5. **Step 5 — `app/auth/routes.py`, `app/core/agents/routes.py`, `app/schedules/routes.py`** (4 raises)
   - One pass per file. Verify status code, pick the right AppError subclass.

6. **Step 6 — Convention test**
   - Add `app/tests/test_exception_conventions.py::test_no_raw_httpexception_in_routes`
     that AST-walks `app/**/routes.py`, finds `Raise(HTTPException(...))` nodes,
     and asserts the count equals an explicit allowlist (auth/dependencies,
     health, fleet webhook). Prevents regression.

7. **Step 7 — Documentation**
   - Update `app/core/exceptions.py` module docstring to list all subclasses + status codes.
   - Append to `TECH_DEBT_AUDIT.md` Section 3: T-001 status → `RESOLVED (codebase-wide)`, T-021 → `RESOLVED`.

## Out of Scope

- `app/auth/dependencies.py` 7 raises — keep. The `emit_auth_denial()` ordering
  and `WWW-Authenticate: Bearer` header set on 401 are part of the JWT
  contract; migrating means writing a parallel handler. Track as a separate
  planning round if ever desired.
- `app/core/health.py` 7 raises — keep. Health endpoints intentionally bypass
  app-error machinery for latency and to keep readiness probe semantics
  exact.
- `app/fleet/routes.py` 2 webhook raises — keep. Webhook auth is its own
  concern; fold into a future webhook-hardening planning round.

## Validation

```bash
uv run ruff format .
uv run ruff check --fix .
uv run mypy app/
uv run pyright app/
uv run pytest -v -m "not integration"
uv run pytest app/tests/test_security.py -v
uv run pytest app/tests/test_exception_conventions.py -v   # NEW (Step 6)
```

Integration tests (if Docker running):
```bash
uv run pytest -v -m integration
```

## Risk

- **Test breakage:** existing tests that match `HTTPException` shape will
  fail until updated. Expected and required — count after migration =
  count of grep `HTTPException` in tests minus the kept-by-design rows.
- **Status code drift:** verify each migration doesn't change observable
  status code. The status mapping in `app_exception_handler` is the
  contract; per-call-site status changes are *not* in scope.
- **Header drop:** `WWW-Authenticate: Bearer` is set explicitly on auth
  401s. The reason `auth/dependencies.py` is out of scope.

## Acceptance

- [ ] 14 raises migrated, 16 raises kept (auth/health/fleet).
- [ ] 3 new AppError subclasses + 3 new handler registrations.
- [ ] All 10 validation gates pass (ruff/mypy/pyright/pytest/security).
- [ ] Convention test asserts allowlist count, fails on new raw `HTTPException` in `routes.py`.
- [ ] `TECH_DEBT_AUDIT.md` updated with T-001 codebase-wide RESOLVED + T-021 RESOLVED.

## Estimated Effort

- Steps 1-5 implementation: ~3-4h.
- Step 6 convention test: ~1h (AST walking + allowlist).
- Step 7 docs: ~30min.
- **Total:** half-day, single bundled PR.
