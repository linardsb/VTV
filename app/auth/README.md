# Authentication

JWT-based authentication and role-based access control (RBAC) for all backend API endpoints. DB-backed user management with bcrypt password hashing, Redis-backed brute-force protection, JWT token revocation via Redis denylist, and admin password reset with complexity enforcement.

## Key Flows

### Login (POST /api/v1/auth/login)

1. **Redis fast-path check**: Query `auth:lockout:{email}` — reject immediately if locked (avoids DB hit)
2. Find user by email (return 401 if not found or inactive)
3. Check DB lockout (`locked_until` > now → return 423; expired lockout → clear and continue)
4. Verify password with bcrypt
5. On failure: increment `failed_attempts` in DB + record in Redis (`auth:failures:{email}` with INCR + TTL)
6. After 5 failures: set `locked_until` in DB + set `auth:lockout:{email}` in Redis (15-min TTL)
7. On success: reset `failed_attempts`, clear Redis brute-force keys (`auth:failures:*`, `auth:lockout:*`)
8. Issue JWT access token (30min) + refresh token (7 days)
9. Return `{id, email, name, role, access_token, refresh_token}`

### Token Refresh (POST /api/v1/auth/refresh)

1. Decode refresh token — reject if invalid, expired, or type != "refresh"
2. Fetch user by ID from token payload — reject if not found or inactive
3. Check lockout status — reject if `locked_until` > now (locked users cannot refresh)
4. Issue new access token with current role from DB
5. Return `{access_token}`

### Authentication Dependency (get_current_user)

1. Extract Bearer token from Authorization header (return 401 if missing — uses `HTTPBearer(auto_error=False)`)
2. Decode JWT — reject if invalid, expired, or type != "access"
3. **Check token revocation** — query Redis denylist (`auth:revoked:{jti}`), reject if revoked
4. Fetch user by ID from DB — reject if not found (401) or inactive (403)
5. Return User model for use in route handlers

### Role Authorization (require_role)

1. Run `get_current_user` first (authentication)
2. Check `user.role` against allowed roles list
3. Return 403 "Insufficient permissions" if role not allowed (never exposes role names)
4. Return User model if authorized

### Admin Password Reset (POST /api/v1/auth/reset-password)

1. Requires admin role (`require_role("admin")`)
2. Validate new password complexity (10+ chars, uppercase, lowercase, digit)
3. Hash new password with bcrypt
4. Reset `failed_attempts` to 0 and clear `locked_until`
5. Clear Redis brute-force keys for the user's email
6. Return 204 No Content

### Token Revocation

1. `revoke_token(jti, ttl_seconds)` stores JTI in Redis with TTL matching token lifetime
2. `is_token_revoked(jti)` checks Redis denylist — returns True if found
3. Fail-open design: if Redis is unavailable, tokens are NOT considered revoked (availability over security)
4. Revocation is checked on every authenticated request via `get_current_user`

### Seed Demo Users (POST /api/v1/auth/seed)

1. Requires admin role (`require_role("admin")`)
2. Only runs in development environment
3. Count existing users — abort if any exist
4. Create 5 demo users: 2 admin, 1 dispatcher, 1 editor, 1 viewer
5. Password from `DEMO_USER_PASSWORD` env var (default: "admin")

## Database Schema

Table: `users`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | Primary key |
| `email` | String(255) | Unique, indexed, not null | Login email |
| `hashed_password` | String(255) | Not null | bcrypt hash |
| `name` | String(255) | Not null | Display name |
| `role` | String(20) | Not null, default "viewer" | admin/dispatcher/editor/viewer |
| `is_active` | Boolean | Not null, default true | Account active flag |
| `failed_attempts` | Integer | Not null, default 0 | Brute-force counter (DB fallback) |
| `locked_until` | DateTime(tz) | Nullable | Lockout expiry timestamp |
| `created_at` | DateTime | Not null | Auto-set via TimestampMixin |
| `updated_at` | DateTime | Not null | Auto-set via TimestampMixin |

## Redis Keys

| Key Pattern | Type | TTL | Purpose |
|-------------|------|-----|---------|
| `auth:failures:{email}` | Counter (INCR) | 15 min | Failed login attempt count |
| `auth:lockout:{email}` | String ("locked") | 15 min | Fast-path lockout flag |
| `auth:revoked:{jti}` | String ("1") | 30 min (access) / 7 days (refresh) | Token revocation denylist |

## JWT Token Design

| Property | Access Token | Refresh Token |
|----------|-------------|---------------|
| Lifetime | 30 minutes | 7 days |
| Payload: `sub` | user_id (as string) | user_id (as string) |
| Payload: `role` | Current role | Empty (re-fetched on refresh) |
| Payload: `type` | "access" | "refresh" |
| Payload: `jti` | Unique ID (uuid4) | Unique ID (uuid4) |
| Algorithm | HS256 | HS256 |
| Secret | `JWT_SECRET_KEY` env var | Same |

## RBAC Permission Matrix

| Endpoint Group | admin | dispatcher | editor | viewer |
|---------------|-------|------------|--------|--------|
| Auth (seed, reset-password) | W | - | - | - |
| Schedules (CRUD) | CRUD | R | CRUD | R |
| Stops (CRUD) | CRUD | R | CRUD | R |
| Routes (CRUD) | CRUD | R | CRUD | R |
| Drivers (CRUD) | CRUD | CRUD | R | R |
| Knowledge (CRUD) | CRUD | R | CRUD | R |
| GTFS Import | W | - | W | - |
| Transit (read) | R | R | R | R |
| Chat/Agent | R | R | R | R |
| Events | CRUD | R | CRUD | R |

## Business Rules

1. Passwords hashed with bcrypt (salt auto-generated)
2. Account locks after 5 failed attempts for 15 minutes (tracked in both Redis and DB)
3. Redis provides fast-path lockout check before DB query (avoids DB writes under attack)
4. Expired lockouts clear automatically on next login attempt (both DB and Redis)
5. Successful login resets failed attempt counter and clears Redis brute-force keys
6. Seed endpoint is idempotent — only creates users when the table is empty
7. Access tokens carry the role claim — no DB lookup needed for role checks in JWT
8. Refresh tokens omit role — role is re-fetched from DB to pick up role changes
9. Startup validation fails hard if `JWT_SECRET_KEY` is default or < 32 chars in non-dev environments
10. `HTTPBearer(auto_error=False)` returns 401 (not 403) for missing Authorization header
11. Password complexity enforced on password reset only (not login — avoids locking out existing users with weak passwords)
12. Token revocation is fail-open: if Redis is unavailable, tokens are not considered revoked
13. Admin password reset clears brute-force state (both Redis keys and DB fields)
14. Redis unavailability falls back to DB-only brute-force tracking (logged at warning level)

## Integration Points

- **Frontend (Auth.js)**: `auth.ts` credentials provider calls `POST /api/v1/auth/login`. Stores `access_token` and `refresh_token` in encrypted Auth.js JWT session cookie.
- **Frontend (authFetch)**: `src/lib/auth-fetch.ts` wraps all API calls with `Authorization: Bearer <token>` from Auth.js session. Used by all 6 API clients (agent, documents, stops, schedules, drivers, events). Uses dynamic imports to work in both server components (`auth()`) and client components (`getSession()` from `next-auth/react`).
- **All backend routes**: Import `get_current_user` or `require_role()` from `app.auth.dependencies` as FastAPI `Depends()`.
- **Health endpoints**: `GET /health` and `GET /` remain public (no auth required).
- **Redis**: Brute-force tracking, token revocation denylist, and lockout state. Falls back gracefully when Redis is unavailable.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/login` | Public | Authenticate with email + password, returns JWT tokens |
| POST | `/api/v1/auth/refresh` | Public | Exchange refresh token for new access token |
| POST | `/api/v1/auth/seed` | Admin only | Create demo users (development only, idempotent) |
| POST | `/api/v1/auth/reset-password` | Admin only | Reset any user's password (complexity enforced) |

## Files

| File | Purpose |
|------|---------|
| `token.py` | JWT creation (`create_access_token`, `create_refresh_token`), validation (`decode_token`), revocation (`revoke_token`, `is_token_revoked`) |
| `dependencies.py` | FastAPI auth dependencies (`get_current_user` with revocation check, `require_role()`) |
| `schemas.py` | Pydantic models: `LoginRequest`, `LoginResponse`, `RefreshRequest`, `RefreshResponse`, `UserResponse`, `PasswordResetRequest` (with complexity validator) |
| `service.py` | Business logic: `authenticate()` (Redis + DB brute-force), `refresh_access_token()` (lockout check), `reset_password()`, `seed_demo_users()` |
| `repository.py` | DB operations: `find_by_email()`, `find_by_id()`, `create()`, `update()`, `count()` |
| `models.py` | SQLAlchemy `User` model |
| `exceptions.py` | `InvalidCredentialsError` (401), `AccountLockedError` (423) |
