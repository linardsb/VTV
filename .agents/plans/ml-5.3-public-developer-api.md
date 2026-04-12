# Plan: ML-5.3 Public Developer API with API Key Auth

## Context

Third-party developers (rider apps, transit researchers, journalists) need direct data access. A dedicated public API at `/public/v1/` with API key auth isolates external traffic from internal endpoints — independent rate limiting, versioning, revocation, and usage monitoring.

## Security Context Assessment

| Context | Active | Rationale |
|---------|--------|-----------|
| **CTX-AUTH** | Yes | API key auth, hashing, revocation, fail-closed on Redis down |
| **CTX-RBAC** | Yes | Key management needs role gating (admin/editor); public endpoints need API key validation |
| **CTX-INPUT** | Yes | Query params on public endpoints need max_length, escape_like |
| **CTX-INFRA** | Partial | CORS changes for public endpoints, Redis rate limiting config |
| CTX-FILE | No | No file uploads |
| CTX-AGENT | No | No agent/LLM integration |

## Research Summary

**Reference VSA feature:** `app/fleet/` (12 files, CRUD + webhooks, RBAC, rate limiting)
**Auth patterns:** `app/auth/service.py:90-98` (bcrypt), `app/auth/dependencies.py:121-144` (require_role factory), `app/auth/token.py` (Redis revocation)
**Rate limiting:** `app/core/rate_limit.py:30-83` (slowapi + Redis, IP-keyed)
**Redis:** `app/core/redis.py:31-44` (async singleton, decode_responses=True)
**TimescaleDB:** `alembic/versions/b7c8d9e0f1a2_*` (hypertable + compression + retention)
**Transit data:** `app/transit/routes.py:44-68`, `app/stops/routes.py:29-44`, `app/schedules/routes.py`
**CORS:** `app/core/middleware.py:151-191` (CORSMiddleware, credentials=True, restricted origins)
**Config:** `app/core/config.py` (Pydantic BaseSettings, `@lru_cache` singleton)
**Shared:** `PaginationParams` + `PaginatedResponse[T]` (`app/shared/schemas.py:11-64`), `TimestampMixin` (`app/shared/models.py:10-41`), `AppError` hierarchy (`app/core/exceptions.py:14-138`)

## Test Landscape

**Fixtures:** Root `conftest.py` — `client`, `mock_settings`, `_clear_auth_cache`. Integration: `app/tests/conftest.py` — `test_db_engine`, `test_db_session`.
**Auth test patterns:** `app/auth/tests/test_routes.py` — 401/403 assertions, `_make_auth_header`. `app/auth/tests/test_service.py` — bcrypt, Redis mock via `patch()`.
**Rate limit tests:** All route tests disable with `limiter.enabled = False`. No existing rate limit behavior tests — we need to write them.
**Redis mocking:** `patch("app.auth.service._check_redis_brute_force", ...)` pattern. No FakeRedis.
**Security conventions:** `app/tests/test_security.py` — 110+ tests. New public endpoints must be added to convention checks.
**Factory pattern:** `make_*(** overrides)` returning model instances (see `app/stops/tests/conftest.py:12`).

## Type Check Baseline

| Tool | Errors | Location |
|------|--------|----------|
| Pyright (project) | **8** | All in `app/transit/tests/test_eticket_importer.py` |
| Mypy (project) | **2** | Same file |
| Auth module | **0** | Clean |
| Stops module | **0** | Clean |
| Fleet module | **0** | Clean |

**Target:** Zero new errors from `app/public_api/`.

## Critical Design Decisions

### 1. SHA-256, Not Bcrypt, for API Key Hashing

Bcrypt uses random salts — same input produces different hashes. You cannot index or look up by hash. API keys are high-entropy random strings (not user-chosen passwords), so fast hashing is safe. SHA-256 with indexed `key_hash` column gives O(1) lookup. This is the standard pattern (Stripe, GitHub, AWS).

### 2. Key Format

`vtv_pk_<32 hex chars>` — prefix enables secret scanners (detect-secrets) and log identification. Store: SHA-256 hash + preview (`vtv_pk_...abcd`). Raw key shown once at creation.

### 3. Two Routers, Two Auth Mechanisms

| Router | Prefix | Auth | Purpose |
|--------|--------|------|---------|
| `key_mgmt_router` | `/api/v1/public-api/keys` | JWT + `require_role(["admin", "editor"])` | Create/list/revoke keys |
| `public_router` | `/public/v1` | `X-API-Key` header | Read-only transit data |

### 4. Fixed-Window Rate Counter (Not Token Bucket)

Redis `INCR` + `EXPIRE(60s)` per API key per minute. Allows 2x burst at window boundaries — acceptable for v1. Key: `public_api:ratelimit:{api_key_id}`.

### 5. Fire-and-Forget Usage Tracking

`asyncio.create_task` for TimescaleDB INSERT — don't block response for usage logging.

### 6. CORS

Public data endpoints (`/public/v1/*`): `allow_origins=["*"]`, `allow_credentials=False`. Key management: existing restricted CORS. Add `X-API-Key` to `allow_headers`.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/public_api/__init__.py` | Module init |
| CREATE | `app/public_api/models.py` | `APIKey` + `APIKeyUsage` models |
| CREATE | `app/public_api/schemas.py` | Request/response schemas |
| CREATE | `app/public_api/repository.py` | DB operations for keys + usage |
| CREATE | `app/public_api/service.py` | Key lifecycle, rate limiting, usage tracking |
| CREATE | `app/public_api/auth.py` | `get_api_key` dependency (X-API-Key header validation) |
| CREATE | `app/public_api/exceptions.py` | `InvalidAPIKeyError`, `APIKeyRevokedError`, `APIKeyRateLimitError` |
| CREATE | `app/public_api/routes.py` | Key management + public data endpoints |
| CREATE | `app/public_api/tests/__init__.py` | Test module init |
| CREATE | `app/public_api/tests/conftest.py` | Factories + fixtures |
| CREATE | `app/public_api/tests/test_service.py` | Service unit tests |
| CREATE | `app/public_api/tests/test_auth.py` | API key auth dependency tests |
| CREATE | `app/public_api/tests/test_routes.py` | Route tests (both routers) |
| CREATE | `app/public_api/tests/test_rate_limit.py` | Rate limit logic unit tests |
| CREATE | `alembic/versions/l5m6n7o8p9q0_api_keys.py` | Migration: api_keys + api_key_usage hypertable |
| UPDATE | `app/main.py` | Register both routers |
| UPDATE | `app/core/config.py` | Add public API settings |
| UPDATE | `app/core/middleware.py` | Add `X-API-Key` to CORS allow_headers |
| UPDATE | `app/core/exceptions.py` | Add `APIKeyError` base if needed |

## Implementation Steps

### Step 1: Config Settings

**File:** `app/core/config.py` — ADD settings in `Settings` class

```python
# Public API settings
public_api_enabled: bool = True
public_api_default_rate_limit: int = 60  # requests per minute
public_api_tier_limits: dict[str, int] = {
    "free": 60,
    "basic": 300,
    "pro": 1000,
}
public_api_key_prefix: str = "vtv_pk_"
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Exception Classes

**File:** `app/public_api/exceptions.py` — CREATE

```python
from app.core.exceptions import AppError

class InvalidAPIKeyError(AppError):
    """API key missing, invalid, or expired."""
    def __init__(self) -> None:
        super().__init__("Invalid or missing API key", status_code=401)

class APIKeyRevokedError(AppError):
    """API key has been revoked."""
    def __init__(self) -> None:
        super().__init__("API key has been revoked", status_code=401)

class APIKeyRateLimitError(AppError):
    """Per-key rate limit exceeded."""
    def __init__(self, retry_after: int) -> None:
        super().__init__("Rate limit exceeded", status_code=429)
        self.retry_after = retry_after
```

**Validation:** `uv run ruff check app/public_api/exceptions.py && uv run pyright app/public_api/exceptions.py`

### Step 3: Models

**File:** `app/public_api/models.py` — CREATE

- `APIKey(Base, TimestampMixin)`: id (PK), name (String 100), key_hash (String 64, unique, indexed), key_preview (String 20), owner_user_id (FK users.id, indexed), tier (Literal["free", "basic", "pro"], default "free"), is_active (Boolean, default True), last_used_at (DateTime nullable), revoked_at (DateTime nullable), expires_at (DateTime nullable)
- `APIKeyUsage(Base)`: id (PK), api_key_id (FK api_keys.id, indexed), recorded_at (DateTime, indexed — hypertable partition column), endpoint (String 100), method (String 10), status_code (Integer), response_time_ms (Integer)
- Composite index on `(api_key_id, recorded_at)` for usage queries

**Key design:** `key_hash` is SHA-256 hex digest (64 chars). `key_preview` stores `vtv_pk_...{last4}`. No `TimestampMixin` on `APIKeyUsage` (high-volume, use `recorded_at` only).

**Validation:** `uv run ruff check app/public_api/models.py && uv run pyright app/public_api/models.py`

### Step 4: Schemas

**File:** `app/public_api/schemas.py` — CREATE

```
APIKeyCreate(BaseModel): name (str, max_length=100)
APIKeyCreateResponse(BaseModel): id, name, key (raw key — shown once), key_preview, tier, created_at
APIKeyResponse(BaseModel): id, name, key_preview, tier, is_active, last_used_at, revoked_at, expires_at, created_at
  - ConfigDict(from_attributes=True)
APIKeyListResponse(PaginatedResponse[APIKeyResponse]): (inherits)
PublicRouteResponse(BaseModel): route_id, short_name, long_name, type, agency_name
PublicStopResponse(BaseModel): stop_id, name, lat, lon, code
PublicVehicleResponse(BaseModel): vehicle_id, route_id, latitude, longitude, bearing, speed, timestamp, feed_id
```

**Validation:** `uv run ruff check app/public_api/schemas.py && uv run pyright app/public_api/schemas.py`

### Step 5: Repository

**File:** `app/public_api/repository.py` — CREATE

Methods:
- `create_key(key_hash, key_preview, name, owner_user_id, tier) -> APIKey`
- `find_by_hash(key_hash: str) -> APIKey | None` — indexed lookup
- `find_by_id(key_id: int) -> APIKey | None`
- `list_by_owner(owner_user_id: int, pagination: PaginationParams) -> tuple[list[APIKey], int]`
- `revoke_key(key_id: int) -> APIKey | None` — sets `revoked_at = utcnow()`
- `update_last_used(key_id: int) -> None` — fire-and-forget update
- `record_usage(api_key_id, endpoint, method, status_code, response_time_ms) -> None` — INSERT into api_key_usage

**Validation:** `uv run ruff check app/public_api/repository.py && uv run pyright app/public_api/repository.py`

### Step 6: Service

**File:** `app/public_api/service.py` — CREATE

Methods:
- `generate_key(name, owner_user_id, tier) -> tuple[str, APIKey]` — generates `vtv_pk_<32 hex>`, SHA-256 hashes, stores, returns (raw_key, model)
- `validate_key(raw_key: str) -> APIKey` — hash + lookup + active/expired/revoked checks. Fail-closed: if Redis unavailable, raise 503, don't silently pass.
- `check_rate_limit(api_key: APIKey) -> None` — Redis INCR + EXPIRE(60), compare to tier limit. On Redis failure: allow request (rate limiting is non-critical, don't block on Redis down for reads).
- `revoke_key(key_id, owner_user_id) -> APIKey` — verify ownership, revoke
- `list_keys(owner_user_id, pagination) -> tuple[list[APIKey], int]`
- `record_usage_async(api_key_id, endpoint, method, status_code, response_time_ms)` — `asyncio.create_task` wrapper

Logging: `public_api.service.key_created`, `public_api.service.key_revoked`, `public_api.service.rate_limit_exceeded`, `public_api.service.key_validation_failed`

**Validation:** `uv run ruff check app/public_api/service.py && uv run pyright app/public_api/service.py`

### Step 7: Auth Dependency

**File:** `app/public_api/auth.py` — CREATE

```python
async def get_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """Extract and validate API key from X-API-Key header.

    Returns 401 with WWW-Authenticate header on failure (anti-pattern #55).
    """
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    service = PublicAPIService(db)
    api_key = await service.validate_key(raw_key)
    await service.check_rate_limit(api_key)
    # Fire-and-forget usage tracking happens in route middleware/after_request
    return api_key
```

**Validation:** `uv run ruff check app/public_api/auth.py && uv run pyright app/public_api/auth.py`

### Step 8: Routes

**File:** `app/public_api/routes.py` — CREATE

**Key management router** (`/api/v1/public-api/keys`):
- `POST /` — Create key. Auth: `require_role(["admin", "editor"])`. Rate: 10/min.
- `GET /` — List caller's keys (paginated). Auth: `require_role(["admin", "editor"])`. Rate: 30/min.
- `DELETE /{key_id}` — Revoke key. Auth: `require_role(["admin", "editor"])`. Rate: 10/min.

**Public data router** (`/public/v1`):
- `GET /routes` — List transit routes (paginated). Auth: `get_api_key`. Cache-Control: `public, max-age=30`.
- `GET /stops` — List stops (paginated, optional `?near_lat=&near_lon=&radius_m=`). Auth: `get_api_key`. Cache-Control: `public, max-age=30`.
- `GET /vehicles` — Live vehicle positions. Auth: `get_api_key`. Cache-Control: `public, max-age=5`.

Each public endpoint: validate key → check rate limit → read data from existing services/repos → record usage (fire-and-forget) → return with `Cache-Control` + `X-RateLimit-Limit` + `X-RateLimit-Remaining` headers.

**Cross-feature reads:** Import and use `StopRepository`, `ScheduleRepository`, transit Redis reader directly (same DB session = same transaction, per VTV convention).

**Validation:** `uv run ruff check app/public_api/routes.py && uv run pyright app/public_api/routes.py`

### Step 9: Alembic Migration

**File:** `alembic/versions/l5m6n7o8p9q0_api_keys.py` — CREATE

1. Create `api_keys` table (all columns from Step 3)
2. Create `api_key_usage` table (all columns from Step 3)
3. Check TimescaleDB availability (follow `b7c8d9e0f1a2` pattern)
4. If available: `create_hypertable('api_key_usage', 'recorded_at', chunk_time_interval => INTERVAL '1 day')`
5. Add compression policy (7 days), retention policy (90 days)
6. Downgrade: drop both tables

**Validation:** `uv run ruff check alembic/versions/l5m6n7o8p9q0_api_keys.py`

### Step 10: Register Routers + CORS Update

**File:** `app/main.py` — UPDATE: add both router imports and `app.include_router()` calls

**File:** `app/core/middleware.py` — UPDATE: add `"X-API-Key"` to `allow_headers` list

**Validation:** `uv run ruff check app/main.py app/core/middleware.py && uv run pyright app/main.py`

### Step 11: Test Fixtures

**File:** `app/public_api/tests/conftest.py` — CREATE

- `make_api_key(**overrides) -> APIKey` factory
- `make_api_key_usage(**overrides) -> APIKeyUsage` factory
- `mock_db` fixture (AsyncMock)
- `service` fixture (PublicAPIService with mock_db)
- `_mock_admin_user()` helper
- `_setup_auth_override()` autouse fixture for route tests

### Step 12: Service Tests

**File:** `app/public_api/tests/test_service.py` — CREATE (target: 10+ tests)

- `test_generate_key_returns_raw_and_model` — raw key starts with `vtv_pk_`, model has SHA-256 hash
- `test_generate_key_hash_is_sha256` — verify hash matches `hashlib.sha256(raw_key.encode()).hexdigest()`
- `test_validate_key_success` — mock repo returns active key
- `test_validate_key_not_found` — raises InvalidAPIKeyError
- `test_validate_key_revoked` — raises APIKeyRevokedError
- `test_validate_key_expired` — raises InvalidAPIKeyError
- `test_check_rate_limit_under_limit` — Redis returns count < tier limit
- `test_check_rate_limit_exceeded` — Redis returns count >= tier limit, raises APIKeyRateLimitError
- `test_check_rate_limit_redis_down_allows_request` — Redis raises, request passes (non-critical)
- `test_revoke_key_success` — sets revoked_at
- `test_revoke_key_not_found` — raises NotFoundError

### Step 13: Auth Dependency Tests

**File:** `app/public_api/tests/test_auth.py` — CREATE (target: 5+ tests)

- `test_missing_api_key_returns_401` — no X-API-Key header → 401 with WWW-Authenticate
- `test_invalid_api_key_returns_401` — bad key → 401
- `test_valid_api_key_returns_model` — good key → APIKey object
- `test_revoked_key_returns_401`
- `test_rate_limited_key_returns_429` — with Retry-After header

### Step 14: Route Tests

**File:** `app/public_api/tests/test_routes.py` — CREATE (target: 12+ tests)

Key management:
- `test_create_key_success` — POST /api/v1/public-api/keys → 201, returns raw key
- `test_create_key_requires_editor_role` — viewer → 403
- `test_list_keys_success` — GET /api/v1/public-api/keys → 200, paginated
- `test_revoke_key_success` — DELETE /api/v1/public-api/keys/{id} → 200

Public endpoints:
- `test_get_vehicles_with_api_key` — GET /public/v1/vehicles → 200
- `test_get_vehicles_without_key` — no header → 401
- `test_get_routes_with_api_key` — GET /public/v1/routes → 200
- `test_get_stops_with_api_key` — GET /public/v1/stops → 200
- `test_public_endpoint_cache_control_header` — verify Cache-Control present
- `test_public_endpoint_rate_limit_headers` — verify X-RateLimit-* headers
- `test_revoked_key_rejected` — revoked key → 401
- `test_cors_headers_on_public_endpoint` — verify Access-Control-Allow-Origin: *

### Step 15: Rate Limit Tests

**File:** `app/public_api/tests/test_rate_limit.py` — CREATE (target: 5+ tests)

- `test_fixed_window_counter_increments` — mock Redis, verify INCR + EXPIRE calls
- `test_counter_resets_after_window` — TTL expires, new window starts
- `test_free_tier_limit_60` — exceeds 60 → error
- `test_pro_tier_limit_1000` — allows up to 1000
- `test_redis_failure_allows_request` — Redis exception → request passes

## Preflight Warnings

### CRITICAL: Security Convention Test Will Fail (Must Fix)

`app/tests/test_security.py:667-739` — `TestAllRoutesHaveAuth` auto-discovers ALL route functions in `app/*/routes.py` and asserts each has `get_current_user` or `require_role` in source. Public data endpoints use `get_api_key` instead.

**Fix required in Step 14:** Update the test to also accept `get_api_key` as valid auth:
- Line 733: Change `if "get_current_user" not in source and "require_role" not in source:` to also include `"get_api_key" not in source`

### CRITICAL: CORS Source Inspection Test

`app/tests/test_security.py:1148-1155` — Tests that `setup_middleware` source does NOT contain `allow_origins=["*"]`. If public endpoint CORS with `allow_origins=["*"]` is added inside `setup_middleware`, this test fails.

**Fix:** Do NOT add wildcard CORS to `setup_middleware`. Instead, add `Access-Control-Allow-Origin: *` as response headers directly in public data route handlers, or use a separate lightweight CORS middleware mounted only on the public router.

### Other Warnings
- `app/main.py` router registration — follow existing pattern exactly, avoid import ordering issues
- Anti-pattern #55: Use `HTTPException(401, headers={"WWW-Authenticate": "ApiKey"})`, not `HTTPBearer(auto_error=True)`
- Anti-pattern #11: Adding `tier` field to APIKey model — grep for all schema constructors before finalizing
- Anti-pattern #34: Redis await returns `Awaitable[T] | T` — add `# type: ignore[misc]` on await lines

## Security Checklist

### Key Management Endpoints (`/api/v1/public-api/keys/*`)
- [ ] `require_role(["admin", "editor"])` on all 3 endpoints
- [ ] `@limiter.limit()` on all 3 endpoints
- [ ] Input validation: `name` max_length=100 via Pydantic schema
- [ ] Error responses use `AppError` subclasses (no internal leakage)
- [ ] Generic "Insufficient permissions" (never expose role names — anti-pattern #57)

### Public Data Endpoints (`/public/v1/*`)
- [ ] `get_api_key` dependency on all 3 endpoints
- [ ] Per-key rate limiting via Redis fixed-window counter
- [ ] `escape_like()` for any ILIKE search params
- [ ] `max_length` on all string Query params
- [ ] 401 with `WWW-Authenticate: ApiKey` header (anti-pattern #55)
- [ ] Fail-closed on key validation (bad key = 401, never silent pass)
- [ ] Rate limit Redis failure = allow request (non-critical, log warning)

### API Key Security
- [ ] SHA-256 hashing (not bcrypt — keys are high-entropy)
- [ ] Raw key shown once at creation, never stored or logged
- [ ] Key preview stored: `vtv_pk_...{last4}` only
- [ ] `key_hash` column: unique + indexed for O(1) lookup
- [ ] Revocation is immediate (no cache delay)
- [ ] Key format `vtv_pk_<32 hex>` enables detect-secrets scanning

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `make test` passes (all 1698+ tests + new tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors <= 8 (baseline: 8 in transit test file)
- [ ] Mypy errors <= 2 (baseline: 2 in transit test file)
- [ ] New endpoints appear in security convention tests
- [ ] Public endpoints return `Cache-Control` headers
- [ ] Public endpoints return `X-RateLimit-Limit` / `X-RateLimit-Remaining` headers
- [ ] Key creation returns raw key exactly once
- [ ] Revoked key returns 401 immediately
