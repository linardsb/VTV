# Authentication

JWT-based authentication and role-based access control (RBAC) for all backend API endpoints. DB-backed user management with bcrypt password hashing and brute-force protection.

## Key Flows

### Login (POST /api/v1/auth/login)

1. Find user by email (return 401 if not found or inactive)
2. Check lockout (return 423 if `locked_until` > now)
3. Clear expired lockout if `locked_until` < now
4. Verify password with bcrypt (increment `failed_attempts` on failure, lock after 5)
5. Reset `failed_attempts` on success
6. Issue JWT access token (30min) + refresh token (7 days)
7. Return `{id, email, name, role, access_token, refresh_token}`

### Token Refresh (POST /api/v1/auth/refresh)

1. Decode refresh token — reject if invalid, expired, or type != "refresh"
2. Fetch user by ID from token payload — reject if not found or inactive
3. Issue new access token with current role from DB
4. Return `{access_token}`

### Authentication Dependency (get_current_user)

1. Extract Bearer token from Authorization header (return 401 if missing)
2. Decode JWT — reject if invalid, expired, or type != "access"
3. Fetch user by ID from DB — reject if not found (401) or inactive (403)
4. Return User model for use in route handlers

### Role Authorization (require_role)

1. Run `get_current_user` first (authentication)
2. Check `user.role` against allowed roles list
3. Return 403 "Insufficient permissions" if role not allowed
4. Return User model if authorized

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
| `failed_attempts` | Integer | Not null, default 0 | Brute-force counter |
| `locked_until` | DateTime(tz) | Nullable | Lockout expiry timestamp |
| `created_at` | DateTime | Not null | Auto-set via TimestampMixin |
| `updated_at` | DateTime | Not null | Auto-set via TimestampMixin |

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
| Auth (seed) | W | - | - | - |
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
2. Account locks after 5 failed attempts for 15 minutes
3. Expired lockouts clear automatically on next login attempt
4. Successful login resets failed attempt counter
5. Seed endpoint is idempotent — only creates users when the table is empty
6. Access tokens carry the role claim — no DB lookup needed for role checks in JWT
7. Refresh tokens omit role — role is re-fetched from DB to pick up role changes
8. Startup validation fails hard if `JWT_SECRET_KEY` is default in non-dev environments
9. `HTTPBearer(auto_error=False)` returns 401 (not 403) for missing Authorization header

## Integration Points

- **Frontend (Auth.js)**: `auth.ts` credentials provider calls `POST /api/v1/auth/login`. Stores `access_token` and `refresh_token` in encrypted Auth.js JWT session cookie.
- **Frontend (authFetch)**: `src/lib/auth-fetch.ts` wraps all API calls with `Authorization: Bearer <token>` from Auth.js session. Used by all 6 API clients (agent, documents, stops, schedules, drivers, events). Uses dynamic imports to work in both server components (`auth()`) and client components (`getSession()` from `next-auth/react`).
- **All backend routes**: Import `get_current_user` or `require_role()` from `app.auth.dependencies` as FastAPI `Depends()`.
- **Health endpoints**: `GET /health` and `GET /` remain public (no auth required).

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/login` | Public | Authenticate with email + password, returns JWT tokens |
| POST | `/api/v1/auth/refresh` | Public | Exchange refresh token for new access token |
| POST | `/api/v1/auth/seed` | Admin only | Create demo users (development only, idempotent) |

## Files

| File | Purpose |
|------|---------|
| `token.py` | JWT creation (`create_access_token`, `create_refresh_token`) and validation (`decode_token`) |
| `dependencies.py` | FastAPI auth dependencies (`get_current_user`, `require_role()`) |
| `schemas.py` | Pydantic models: `LoginRequest`, `LoginResponse`, `RefreshRequest`, `RefreshResponse`, `UserResponse` |
| `service.py` | Business logic: `authenticate()`, `refresh_access_token()`, `seed_demo_users()` |
| `repository.py` | DB operations: `find_by_email()`, `find_by_id()`, `create()`, `update()`, `count()` |
| `models.py` | SQLAlchemy `User` model |
| `exceptions.py` | `InvalidCredentialsError` (401), `AccountLockedError` (423) |
