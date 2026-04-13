# Plan: OPS-4.1 Per-User Rate Limit Bucketing

## Context

Current slowapi limiter uses a single `_get_client_ip` key function — all users hitting the same endpoint share one rate-limit bucket per IP. One abusive authenticated client exhausts the bucket for everyone behind the same NAT/proxy. Per-user bucketing gives fairness and turns rate limits into real DoS defense for authenticated abuse.

## Security Context Assessment

- **CTX-AUTH** — Active. Feature reads JWT tokens to extract identity. Must handle invalid/missing tokens gracefully (fall back to IP, never crash). Revoked tokens still get user-tier limits until `get_current_user` rejects them — acceptable tradeoff (documented below).
- **CTX-RBAC** — Active. Rate limit tiers are role-based (admin/dispatcher/editor/viewer/anonymous).
- **CTX-INPUT** — Not triggered (no new user-facing query params).
- **CTX-INFRA** — Partially active. Redis key patterns change; must verify TTL cleanup.

## Research Summary

**Current architecture (`app/core/rate_limit.py:80-83`):**
- `Limiter(key_func=_get_client_ip, storage_uri=redis_or_none)` — IP-only bucketing
- `_get_client_ip()` trusts `X-Real-IP` only from Docker bridge networks (lines 30-52)
- Redis storage for cross-worker enforcement; in-memory fallback for dev/test

**Auth flow (`app/auth/dependencies.py:45-118`):**
- `get_current_user()` is a FastAPI dependency — runs AFTER slowapi's `key_func`
- JWT payload contains `sub` (user_id as int) and `role` (str) directly (token.py:17-24)
- `decode_token()` does HMAC-only decode, no DB lookup — safe for lightweight middleware

**Critical constraint:** slowapi's `key_func` runs before FastAPI dependencies resolve. Solution: lightweight middleware that decodes JWT → stores `user_id`/`role` on `request.state` → key_func reads from state.

**Existing config (`app/core/config.py:136-140`):**
- `rate_limit_chat`, `rate_limit_transit`, `rate_limit_health`, `rate_limit_default` — all UNUSED (limits hardcoded in decorators). Will wire new tier settings through to actual usage.

**Reference pattern (`app/public_api/service.py:150-193`):**
- Per-API-key Redis INCR+EXPIRE fixed-window counter with tier lookup. Different mechanism (custom, not slowapi) but same concept.

**Roles in system:** `admin`, `dispatcher`, `editor`, `viewer` (auth/models.py, str field)

## Test Landscape

- **20+ test files** disable rate limiting with `limiter.enabled = False` at module level
- **`app/public_api/tests/test_rate_limit.py`** — best reference for per-key tier testing with mocked Redis
- **`app/tests/test_security.py:244-297`** — `TestRateLimiterIp` validates IP extraction, source code inspection tests
- **Mock pattern:** `MagicMock(spec=User)` with `.id`, `.email`, `.role`, `.is_active` fields
- **Dependency override pattern:** `app.dependency_overrides[get_current_user] = lambda: mock_user` with cleanup in yield fixture
- **New rate limit tests must be in their own file** — can't mix with files that disable limiter globally

## Type Check Baseline

| File | Pyright | Mypy |
|------|---------|------|
| `app/core/rate_limit.py` | 0 errors | 0 errors |
| `app/core/agents/routes.py` | 0 errors | 0 errors |
| `app/analytics/routes.py` | 0 errors | 0 errors |
| `app/core/tests/` | 0 errors | — |

## Design Decision: Known Tradeoffs

1. **Revoked tokens get user-tier limits.** The middleware does JWT decode without revocation check (no Redis/DB). A revoked JWT still gets the authenticated rate-limit bucket until `get_current_user` rejects it (which happens immediately). Acceptable: request fails fast anyway and the user's actual actions are blocked.
2. **`request.state` is untyped.** Use `getattr(request.state, "rate_limit_user_id", None)` not `request.state.rate_limit_user_id` to avoid `AttributeError` in test environments.
3. **slowapi stacking behavior must be verified.** Step 1 includes a verification that multiple `@limiter.limit()` decorators stack (both enforced). If not, sub-buckets will need a different mechanism.

## Tier Definitions

| Role | Scope | Rate | Redis Key Pattern |
|------|-------|------|-------------------|
| `admin` | user | 1000/min | `LIMITER/user:{id}/...` |
| `dispatcher` | user | 300/min | `LIMITER/user:{id}/...` |
| `editor` | user | 100/min | `LIMITER/user:{id}/...` |
| `viewer` | user | 50/min | `LIMITER/user:{id}/...` |
| anonymous | IP | 30/min | `LIMITER/ip:{ip}/...` |

**Sub-buckets (stacked on top of tier):**
| Endpoint | Per-User Rate | Purpose |
|----------|--------------|---------|
| `/v1/chat/completions` | 10/min | LLM cost protection |
| `/api/v1/analytics/on-time-performance` | 5/hour | Heavy aggregation |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/core/rate_limit.py` | Add middleware, user-or-IP key func, dynamic tier limit func, tier config |
| UPDATE | `app/core/config.py` | Add tier settings, wire unused rate_limit_* fields |
| UPDATE | `app/main.py` | Register `RateLimitIdentityMiddleware` |
| UPDATE | `app/core/agents/routes.py` | Add sub-bucket decorator for chat endpoint |
| UPDATE | `app/analytics/routes.py` | Add sub-bucket decorator for analytics export |
| CREATE | `app/core/tests/test_rate_limit_tiers.py` | 12 unit tests for per-user bucketing |
| UPDATE | `app/tests/test_security.py` | Add convention tests for tier config and key patterns |

## Implementation Steps

### Step 0: Verify slowapi stacking behavior
Before implementing, verify that multiple `@limiter.limit()` decorators on one endpoint both enforce:
```bash
# Quick test in Python REPL or a throwaway test
# If stacking doesn't work, sub-buckets need custom Redis INCR logic (like public_api)
```
**Validation:** Document finding — determines Step 5-6 approach.

### Step 1: Add tier config to `app/core/config.py`

Add tier settings after the existing (unused) rate limit fields at line ~140:

```python
# Per-user rate limit tiers (OPS-4.1)
rate_limit_tier_admin: str = "1000/minute"
rate_limit_tier_dispatcher: str = "300/minute"
rate_limit_tier_editor: str = "100/minute"
rate_limit_tier_viewer: str = "50/minute"
rate_limit_tier_anonymous: str = "30/minute"
rate_limit_agent_chat: str = "10/minute"
rate_limit_analytics_export: str = "5/hour"
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Rewrite `app/core/rate_limit.py`

Add three new components while preserving `_get_client_ip` and `_get_storage_uri`:

**a) `RateLimitIdentityMiddleware` class:**
- On each request, extract `Authorization: Bearer <token>` header
- Call `decode_token(token)` — HMAC only, no DB, no revocation
- On success: set `request.state.rate_limit_user_id = payload.sub` and `request.state.rate_limit_role = payload.role`
- On failure (no header, invalid token, expired): do nothing — key_func will fall back to IP
- Import `decode_token` from `app.auth.token` (already exists)
- This is a Starlette `BaseHTTPMiddleware`

**b) `_user_or_ip_key(request: Request) -> str`:**
- Read `user_id = getattr(request.state, "rate_limit_user_id", None)`
- If `user_id is not None`: return `f"user:{user_id}"`
- Else: return `f"ip:{_get_client_ip(request)}"`

**c) `_dynamic_tier_limit(request: Request) -> str`:**
- Read `role = getattr(request.state, "rate_limit_role", None)`
- Look up tier from settings: `get_settings().rate_limit_tier_{role}` (via dict mapping)
- Default to anonymous tier if role is None or unknown

**d) Update limiter initialization:**
```python
limiter = Limiter(
    key_func=_user_or_ip_key,
    default_limits=[_dynamic_tier_limit],
    storage_uri=_storage_uri,
)
```

**e) Export `_chat_subbucket_key` and `_analytics_subbucket_key`** for sub-bucket decorators:
- `_chat_subbucket_key(request)` → `f"chat:user:{user_id}"` or `f"chat:ip:{ip}"`
- `_analytics_subbucket_key(request)` → `f"analytics:user:{user_id}"` or `f"analytics:ip:{ip}"`

**Validation:** `uv run ruff format app/core/rate_limit.py && uv run ruff check --fix app/core/rate_limit.py && uv run pyright app/core/rate_limit.py && uv run mypy app/core/rate_limit.py`

### Step 3: Register middleware in `app/main.py`

Add `RateLimitIdentityMiddleware` BEFORE the slowapi middleware in the middleware stack (so it runs first, populating `request.state` before rate limit checks).

Find where `SlowAPIMiddleware` or `SlowAPIASGIMiddleware` is added and insert the identity middleware before it.

**Validation:** `uv run ruff check app/main.py && uv run pyright app/main.py`

### Step 4: Update agent chat sub-bucket (`app/core/agents/routes.py`)

On the `chat_completions` endpoint (~line 41), add a second `@limiter.limit()` with sub-bucket key:

```python
@router.post("/chat/completions", response_model=ChatCompletionResponse)
@limiter.limit("10/minute", key_func=_chat_subbucket_key)  # sub-bucket
async def chat_completions(
    request: Request,
    ...
```

The existing endpoint limit is already `"10/minute"` — this now uses the sub-bucket key so it's per-user instead of per-IP. The global tier limit applies via `default_limits`.

Import `_chat_subbucket_key` from `app.core.rate_limit`.

**Validation:** `uv run ruff check app/core/agents/routes.py && uv run pyright app/core/agents/routes.py`

### Step 5: Update analytics export sub-bucket (`app/analytics/routes.py`)

On `get_on_time_performance` (~line 79), change the limit to the sub-bucket:

```python
@router.get("/on-time-performance", response_model=OnTimePerformanceResponse)
@limiter.limit("5/hour", key_func=_analytics_subbucket_key)
async def get_on_time_performance(
```

Import `_analytics_subbucket_key` from `app.core.rate_limit`.

**Validation:** `uv run ruff check app/analytics/routes.py && uv run pyright app/analytics/routes.py`

### Step 6: Create `app/core/tests/test_rate_limit_tiers.py`

New test file (does NOT set `limiter.enabled = False` — needs limiter active for some tests).

**12 tests:**

1. `test_anonymous_ip_bucketing` — No auth header → key is `ip:{remote_addr}`
2. `test_authenticated_user_bucketing` — Valid JWT → key is `user:{user_id}`
3. `test_authenticated_different_users_separate_buckets` — Two users get independent buckets
4. `test_tier_selection_admin` — Admin role → 1000/minute limit string
5. `test_tier_selection_dispatcher` — Dispatcher role → 300/minute
6. `test_tier_selection_viewer` — Viewer role → 50/minute
7. `test_chat_subbucket_key_authenticated` — Chat sub-bucket returns `chat:user:{id}`
8. `test_chat_subbucket_key_anonymous` — Chat sub-bucket returns `chat:ip:{ip}`
9. `test_missing_auth_fallback_to_ip` — Invalid/expired JWT → falls back to IP key
10. `test_429_includes_retry_after` — Rate-limited response includes `Retry-After` header
11. `test_middleware_populates_request_state` — Middleware sets `rate_limit_user_id` and `rate_limit_role`
12. `test_unknown_role_defaults_to_anonymous_tier` — Unrecognized role string → anonymous tier limit

**Test patterns:**
- Mock `decode_token` for JWT decoding (not actual JWT creation)
- Use `MagicMock(spec=Request)` for unit tests of key functions
- Use `TestClient` + `app.dependency_overrides` for integration-style tests
- `from app.core.rate_limit import _user_or_ip_key, _dynamic_tier_limit, _chat_subbucket_key`

**Validation:** `uv run pytest app/core/tests/test_rate_limit_tiers.py -v && uv run pyright app/core/tests/test_rate_limit_tiers.py`

### Step 7: Add convention tests to `app/tests/test_security.py`

Extend `TestRateLimiterIp` (or add new `TestRateLimiterTiers` class):

- `test_source_code_has_user_or_ip_key` — rate_limit.py contains `user_or_ip_key` function
- `test_tier_config_covers_all_roles` — All 4 roles have tier settings in config
- `test_middleware_registered_before_slowapi` — Verify middleware ordering in `app/main.py`

**Validation:** `uv run pytest app/tests/test_security.py -v -k "RateLimiter"`

## Preflight Warnings

- **`limiter.enabled = False` at module level** in 20+ test files — new test file must NOT inherit this. Keep in separate `test_rate_limit_tiers.py`.
- **`_get_client_ip` is imported by `app/core/middleware.py:3`** and `app/core/agents/routes.py:61` — renaming would break these. Keep it as-is; only add new functions.
- **Hardcoded rate limit strings** in `@limiter.limit("10/minute")` across all route files — NOT changing these (existing per-endpoint caps remain, just now bucketed per-user via updated key_func).
- **Anti-pattern #5:** No unused imports. Only import `_chat_subbucket_key` in agents/routes.py and `_analytics_subbucket_key` in analytics/routes.py.
- **Anti-pattern #12:** `slowapi` is untyped. Existing `pyright: ignore[reportMissingTypeStubs]` on line 13-14 of rate_limit.py. Add same directives on new imports.

## Security Checklist

- [x] Middleware does NOT bypass auth — `get_current_user` still runs in dependencies (full JWT validation + revocation + DB lookup)
- [x] Middleware failure = silent fallback to IP bucketing (never blocks requests)
- [x] No credentials exposed in rate limit keys or error responses
- [x] `_get_client_ip` preserved — IP spoofing prevention unchanged
- [x] Generic 429 response — no role or user_id in error body
- [x] Redis key TTL managed by slowapi (fixed-window expiry) — no key bloat
- [x] `X-Forwarded-For` still NOT referenced (security convention test enforces this)

## Verification

- [ ] `make lint` passes (ruff format + ruff check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `uv run pytest app/core/tests/test_rate_limit_tiers.py -v` — all 12 tests pass
- [ ] `uv run pytest app/tests/test_security.py -v -k "RateLimiter"` — convention tests pass
- [ ] `make test` passes — no regressions in existing 1969 tests
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors <= baseline (0 errors before)
- [ ] Manual verification scenario: authenticated admin vs dispatcher vs anonymous get different rate limit behavior
