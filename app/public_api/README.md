# Public Developer API (ML-5.3)

Third-party developer access to VTV transit data via API key authentication, with per-key rate limiting, tiered access, and usage tracking.

## Key Flows

### Create API Key

1. Admin/editor user sends POST with key name
2. Service generates `vtv_pk_<32 hex chars>` raw key
3. SHA-256 hash stored in DB (never bcrypt - keys are high-entropy)
4. Raw key returned once; only preview (`vtv_pk_...last4`) stored
5. Key defaults to "free" tier (60 req/min)

### Validate API Key (on every public request)

1. Extract `X-API-Key` header
2. SHA-256 hash the raw key, look up by indexed `key_hash` column (O(1))
3. Check: exists, not revoked, is_active, not expired
4. Fail-closed: any failure = 401 with `WWW-Authenticate: ApiKey`

### Rate Limit Check

1. Redis fixed-window counter: `INCR public_api:ratelimit:{key_id}`
2. First request in window sets 60s TTL via `EXPIRE`
3. Compare count to tier limit (free=60, basic=300, pro=1000)
4. Exceeds limit = 429 with `Retry-After: 60`
5. Redis failure = allow request (non-critical, logged as warning)

### Public Data Read

1. Validate API key + check rate limit
2. Read from existing services (ScheduleRepository, StopRepository, TransitService)
3. Fire-and-forget usage recording via `asyncio.create_task` to TimescaleDB
4. Return data with `Cache-Control`, `X-RateLimit-*`, and `Access-Control-Allow-Origin: *` headers

## Database Schema

Table: `api_keys`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `name` | String(100) | Not null | Human-readable key name |
| `key_hash` | String(64) | Unique, indexed | SHA-256 hex digest |
| `key_preview` | String(20) | Not null | Truncated preview (vtv_pk_...last4) |
| `owner_user_id` | Integer | FK users.id, indexed | Key owner |
| `tier` | String(10) | Not null, default "free" | Rate limit tier |
| `is_active` | Boolean | Not null, default true | Active flag |
| `last_used_at` | DateTime | Nullable | Last usage timestamp |
| `revoked_at` | DateTime | Nullable | Revocation timestamp |
| `expires_at` | DateTime | Nullable | Expiration timestamp |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

Table: `api_key_usage` (TimescaleDB hypertable, 1-day chunks)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `api_key_id` | Integer | FK api_keys.id, indexed | Key reference |
| `recorded_at` | DateTime | Not null, indexed | Partition column |
| `endpoint` | String(100) | Not null | Request path |
| `method` | String(10) | Not null | HTTP method |
| `status_code` | Integer | Not null | Response status |
| `response_time_ms` | Integer | Not null | Response time |

Composite index on `(api_key_id, recorded_at)`. Compression after 7 days, retention 90 days.

## Business Rules

1. API keys use SHA-256 hashing (not bcrypt) - keys are high-entropy random strings
2. Raw key shown exactly once at creation, never stored or logged
3. Key format `vtv_pk_<32 hex>` enables detect-secrets scanning
4. Revocation is immediate and irreversible (sets `revoked_at` + `is_active=False`)
5. Only key owner can list/revoke their own keys
6. Rate limiting uses Redis fixed-window counter (allows 2x burst at window boundaries)
7. Redis failure during rate check = allow request (non-critical)
8. Usage tracking is fire-and-forget (never blocks response)

## Integration Points

- **auth**: Key management endpoints use JWT + `require_role("admin", "editor")` from `app.auth.dependencies`
- **schedules**: Public `/routes` endpoint reads from `ScheduleRepository` (routes + agencies)
- **stops**: Public `/stops` endpoint reads from `StopRepository`
- **transit**: Public `/vehicles` endpoint reads from `TransitService` singleton (Redis cache)
- **core/redis**: Rate limiting uses shared Redis singleton from `app.core.redis`
- **core/exceptions**: Custom exception handlers registered in `setup_exception_handlers`

## API Endpoints

### Key Management (JWT auth, admin/editor only)

| Method | Path | Rate | Description |
|--------|------|------|-------------|
| POST | `/api/v1/public-api/keys/` | 10/min | Create new API key (returns raw key once) |
| GET | `/api/v1/public-api/keys/` | 30/min | List caller's keys (paginated) |
| DELETE | `/api/v1/public-api/keys/{key_id}` | 10/min | Revoke an API key |

### Public Data (API key auth, read-only)

| Method | Path | Cache | Description |
|--------|------|-------|-------------|
| GET | `/public/v1/routes` | 30s | Transit routes (paginated, filterable by type/search) |
| GET | `/public/v1/stops` | 30s | Transit stops (paginated, searchable) |
| GET | `/public/v1/vehicles` | 5s | Live vehicle positions (filterable by route/feed) |

All public endpoints return `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Access-Control-Allow-Origin: *` headers.
