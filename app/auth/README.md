# Authentication

DB-backed authentication with bcrypt password hashing and brute-force protection. Replaces hardcoded frontend credentials with a backend API that Auth.js calls during login.

## Key Flows

### Login (POST /api/v1/auth/login)

1. Find user by email (return 401 if not found or inactive)
2. Check lockout (return 423 if `locked_until` > now)
3. Clear expired lockout if `locked_until` < now
4. Verify password with bcrypt (increment `failed_attempts` on failure, lock after 5)
5. Reset `failed_attempts` on success, return `{id, email, name, role}`

### Seed Demo Users (POST /api/v1/auth/seed)

1. Count existing users — abort if any exist
2. Create 4 demo users: admin, dispatcher, editor, viewer (all password "admin")
3. Return created user list

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

## Business Rules

1. Passwords hashed with bcrypt (salt auto-generated)
2. Account locks after 5 failed attempts for 15 minutes
3. Expired lockouts clear automatically on next login attempt
4. Successful login resets failed attempt counter
5. Seed endpoint is idempotent — only creates users when the table is empty

## Integration Points

- **Frontend (Auth.js)**: `auth.ts` credentials provider calls `POST /api/v1/auth/login`. JWT `authorize()` callback sends email+password to backend, receives `{id, email, name, role}`.
- **Frontend (SessionProvider)**: Dashboard pages use `useSession()` to read role from JWT for RBAC (`IS_READ_ONLY` computation).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Authenticate with email + password |
| POST | `/api/v1/auth/seed` | Create demo users (only if none exist) |
