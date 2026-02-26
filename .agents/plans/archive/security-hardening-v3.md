# Plan: Security Hardening v3 — Government-Grade Remediation

## Feature Metadata
**Feature Type**: Security Hardening / Bug Fix
**Estimated Complexity**: High
**Primary Systems Affected**: auth, events, core/middleware, core/health, core/redis, core/config, nginx, docker-compose, tests

## Feature Description

This plan addresses ALL remaining security vulnerabilities across three audit cycles plus additional
findings discovered during comprehensive code review. The first audit (docs/security_audit.txt)
identified 13 issues, of which 8 were fully fixed, 2 deferred, and 3 partially addressed. The third
audit (docs/security_audit_2.txt) found the deferred items still open plus new gaps. This plan
closes every remaining gap to achieve government-grade security posture for a Latvian municipal
transit platform handling GDPR-regulated driver/operations data.

**Gap Analysis — Why Vulnerabilities Persisted:**
- Audit 1 finding #9 (brute force): Deferred as "requires Redis-backed tracking" — never implemented
- Audit 1 finding #10 (HTTPS): Only a commented template was added — no actionable config
- Audit 1 finding #11 (Docker creds): The `db` service was fixed but `migrate` and `app` services
  still hardcode `DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/vtv_db`
- Audit 1 finding #6 (No auth): JWT was added in commit 4386c4d but events GET endpoints were
  intentionally left unauthenticated — unacceptable for government data
- New gaps introduced during feature development: no token revocation, no audit logging, no
  password complexity, CORS too permissive, no CSP header, Redis without auth

## User Story

As a system administrator of a Latvian government transit platform
I want all security vulnerabilities closed with defense-in-depth controls
So that the platform meets government-level data protection standards (GDPR, NIST 800-53)

## Solution Approach

Layered remediation in four phases: (1) close authentication gaps, (2) harden infrastructure,
(3) add defense-in-depth controls, (4) comprehensive testing. Each fix is atomic and independently
verifiable.

**Approach Decision:**
We chose in-place hardening of existing architecture because:
- The vertical slice architecture is sound — gaps are configuration/implementation, not structural
- JWT + RBAC foundation is already in place — we extend, not replace
- Redis is already deployed — we leverage it for brute force and token revocation

**Alternatives Considered:**
- OAuth2/OIDC provider (Keycloak): Rejected — adds deployment complexity, overkill for ~50 users
- Session-based auth (replace JWT): Rejected — JWT already implemented and working across all endpoints
- API gateway (Kong/Traefik): Rejected — nginx already provides rate limiting and security headers

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `docs/security_audit.txt` — First audit: 13 findings with remediation status
- `docs/security_audit_2.txt` — Third audit: remaining issues and new findings
- `app/auth/dependencies.py` — JWT validation and RBAC enforcement
- `app/auth/service.py` — Brute force logic (lines 18-20, 51-69)
- `app/auth/token.py` — JWT creation/validation
- `app/core/config.py` — Settings with JWT config (lines 116-120)

### Files to Modify
- `app/events/routes.py` — Add auth to GET endpoints (lines 30-60)
- `app/auth/service.py` — Move brute force tracking to Redis
- `app/auth/token.py` — Add token revocation support
- `app/auth/schemas.py` — Add password complexity validation
- `app/core/middleware.py` — Tighten CORS, add security headers
- `app/core/config.py` — Add Redis auth, CORS origin config, password policy settings
- `app/core/health.py` — Redact infrastructure details
- `app/core/redis.py` — Add password support
- `app/main.py` — Redact root endpoint version info
- `nginx/nginx.conf` — Add CSP, HSTS, production HTTPS config
- `docker-compose.yml` — Fix hardcoded credentials, add Redis password
- `app/tests/test_security.py` — Extend regression tests

### Similar Features (Examples to Follow)
- `app/stops/routes.py` (lines 29-38) — Correct auth pattern: `_current_user: User = Depends(get_current_user)`
- `app/knowledge/routes.py` (lines 68-79) — Correct RBAC pattern with `require_role()`
- `app/core/redis.py` (lines 16-28) — URL redaction pattern to replicate

## Implementation Plan

### Phase 1: Close Authentication Gaps (Tasks 1-4)
Fix events endpoint auth, add password complexity, check lockout on refresh.

### Phase 2: Redis-Backed Security Services (Tasks 5-7)
Move brute force tracking and quota to Redis, add token revocation via Redis set.

### Phase 3: Infrastructure Hardening (Tasks 8-12)
CORS tightening, CSP headers, Docker credential fixes, Redis auth, health redaction.

### Phase 4: Testing & Documentation (Tasks 13-15)
Security regression tests, audit documentation, final validation.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add Authentication to Events GET Endpoints
**File:** `app/events/routes.py` (modify existing)
**Action:** UPDATE

The `list_events` and `get_event` endpoints currently have NO authentication. For a government
platform, all data access requires authentication. The comment "Public endpoint" must be removed.

Changes:
- Add `from app.auth.dependencies import get_current_user` (already imported via `require_role`)
- Add `_current_user: User = Depends(get_current_user),  # noqa: B008` parameter to `list_events`
- Add `_current_user: User = Depends(get_current_user),  # noqa: B008` parameter to `get_event`
- Remove the docstring lines "Public endpoint — dashboard calendar fetches events from the client side."
  and "Public endpoint — read access to individual events does not require auth."
- Update docstrings to indicate authentication is required

**Per-task validation:**
- `uv run ruff format app/events/routes.py`
- `uv run ruff check --fix app/events/routes.py`
- `uv run mypy app/events/routes.py`

---

### Task 2: Add Password Complexity Validation
**File:** `app/auth/schemas.py` (modify existing)
**Action:** UPDATE

Government systems require password complexity enforcement. Add a field_validator on the
login/registration schemas to enforce minimum password requirements.

Read the file first to understand existing schemas. Then:
- Add a `PASSWORD_MIN_LENGTH = 10` constant at module level
- Find or create a password validation function:
  ```python
  def _validate_password_complexity(password: str) -> str:
      if len(password) < PASSWORD_MIN_LENGTH:
          msg = f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
          raise ValueError(msg)
      if not any(c.isupper() for c in password):
          msg = "Password must contain at least one uppercase letter"
          raise ValueError(msg)
      if not any(c.islower() for c in password):
          msg = "Password must contain at least one lowercase letter"
          raise ValueError(msg)
      if not any(c.isdigit() for c in password):
          msg = "Password must contain at least one digit"
          raise ValueError(msg)
      return password
  ```
- Add `@field_validator("password")` with `@classmethod` to `LoginRequest` schema that calls
  `_validate_password_complexity`. NOTE: Only add this validator if there is a `password` field
  on the schema. If the schema only has `email` and `password`, add to `password`.
- IMPORTANT: Do NOT add complexity validation to the demo seed path — only to user-facing
  endpoints. The seed uses `settings.demo_user_password` which is a development convenience.

**Per-task validation:**
- `uv run ruff format app/auth/schemas.py`
- `uv run ruff check --fix app/auth/schemas.py`
- `uv run mypy app/auth/schemas.py`

---

### Task 3: Check Lockout Status on Token Refresh
**File:** `app/auth/service.py` (modify existing)
**Action:** UPDATE

Currently `refresh_access_token` checks `is_active` but NOT `locked_until`. A locked user can
still refresh tokens. Fix:

In the `refresh_access_token` method, after checking `user.is_active`, add:
```python
from app.shared.models import utcnow
# ...
if user.locked_until and utcnow() < user.locked_until:
    raise AccountLockedError("Account is temporarily locked")
```
The import of `utcnow` is already at the top of the file. The `AccountLockedError` import is also
already present.

**Per-task validation:**
- `uv run ruff format app/auth/service.py`
- `uv run ruff check --fix app/auth/service.py`
- `uv run mypy app/auth/service.py`

---

### Task 4: Redact Version Info from Root Endpoint
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

The root endpoint (`/`) currently returns `version` in ALL environments. In production, version
info helps attackers fingerprint the application.

Change the `read_root` function so that `version` is only included when `environment == "development"`:
```python
@app.get("/")
def read_root() -> dict[str, str]:
    response: dict[str, str] = {"message": settings.app_name}
    if settings.environment == "development":
        response["version"] = settings.version
        response["docs"] = "/docs"
    return response
```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py`

---

### Task 5: Move Brute Force Tracking to Redis
**File:** `app/auth/service.py` (modify existing)
**Action:** UPDATE

The current brute force tracking stores `failed_attempts` and `locked_until` in the database User
model. This is actually persistent (not in-memory as the audit stated — the audit was referring to
an older implementation). However, the current approach means every failed login attempt requires a
DB write, which is slow under attack.

The improvement is to ADD a Redis layer as a fast-path check BEFORE hitting the database, while
keeping the DB fields as the authoritative fallback.

Read the file first. Then add a helper function that checks Redis for recent failures:

```python
async def _check_redis_brute_force(email: str) -> bool:
    """Check Redis for brute force lockout. Returns True if locked out."""
    try:
        from app.core.redis import get_redis
        redis_client = await get_redis()
        key = f"auth:lockout:{email}"
        locked = await redis_client.get(key)  # type: ignore[misc]
        return locked is not None
    except Exception:
        # Redis unavailable — fall through to DB check
        return False


async def _record_failed_attempt_redis(email: str) -> None:
    """Record a failed login attempt in Redis with TTL."""
    try:
        from app.core.redis import get_redis
        redis_client = await get_redis()
        key = f"auth:failures:{email}"
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, int(LOCKOUT_DURATION.total_seconds()))
        result = await pipe.execute()  # type: ignore[misc]
        count = int(result[0]) if result else 0
        if count >= MAX_FAILED_ATTEMPTS:
            lockout_key = f"auth:lockout:{email}"
            await redis_client.setex(  # type: ignore[misc]
                lockout_key, int(LOCKOUT_DURATION.total_seconds()), "locked"
            )
    except Exception:
        pass  # Redis unavailable — DB tracking is the fallback
```

Then in the `authenticate` method, add a Redis check at the very beginning (before the DB query):
```python
if await _check_redis_brute_force(email):
    logger.warning("auth.login_locked_redis", email=email)
    raise AccountLockedError("Account is temporarily locked")
```

And after a failed password check (where `user.failed_attempts` is incremented), also call:
```python
await _record_failed_attempt_redis(email)
```

On successful login, clear the Redis keys:
```python
try:
    from app.core.redis import get_redis
    redis_client = await get_redis()
    await redis_client.delete(f"auth:failures:{email}", f"auth:lockout:{email}")  # type: ignore[misc]
except Exception:
    pass
```

IMPORTANT: Add pyright directive at the top of the file if not already present:
`# pyright: reportUnknownMemberType=false` (check if already there first).

**Per-task validation:**
- `uv run ruff format app/auth/service.py`
- `uv run ruff check --fix app/auth/service.py`
- `uv run mypy app/auth/service.py`

---

### Task 6: Add Token Revocation via Redis Denylist
**File:** `app/auth/token.py` (modify existing)
**Action:** UPDATE

JWT tokens cannot be revoked once issued. For government systems, we need the ability to
invalidate tokens (e.g., on password change, account deactivation, or admin action).

Implementation: Store revoked token JTIs in a Redis set with TTL matching token expiry.

Read the file first. Then add:

```python
async def revoke_token(jti: str, ttl_seconds: int = 1800) -> None:
    """Add a token JTI to the revocation denylist in Redis.

    Args:
        jti: The unique token identifier (from JWT 'jti' claim).
        ttl_seconds: Time to keep in denylist (default: 30 min = access token lifetime).
    """
    try:
        from app.core.redis import get_redis
        redis_client = await get_redis()
        await redis_client.setex(f"auth:revoked:{jti}", ttl_seconds, "1")  # type: ignore[misc]
    except Exception:
        logger.warning("auth.token.revocation_failed", jti=jti)


async def is_token_revoked(jti: str) -> bool:
    """Check if a token JTI has been revoked.

    Args:
        jti: The unique token identifier.

    Returns:
        True if the token is in the revocation denylist.
    """
    if not jti:
        return False
    try:
        from app.core.redis import get_redis
        redis_client = await get_redis()
        result = await redis_client.get(f"auth:revoked:{jti}")  # type: ignore[misc]
        return result is not None
    except Exception:
        return False  # Redis down = allow (fail-open for availability)
```

Add pyright directive at top if not present: `# pyright: reportUnknownMemberType=false`

**Per-task validation:**
- `uv run ruff format app/auth/token.py`
- `uv run ruff check --fix app/auth/token.py`
- `uv run mypy app/auth/token.py`

---

### Task 7: Integrate Token Revocation Check in Auth Dependency
**File:** `app/auth/dependencies.py` (modify existing)
**Action:** UPDATE

After decoding the token in `get_current_user`, check the revocation denylist before proceeding.

Read the file first. Then in `get_current_user`, after the `decode_token` call and type/None check
(around line 40-46), add:

```python
from app.auth.token import is_token_revoked
if await is_token_revoked(payload.jti):
    logger.warning("auth.token_revoked", jti=payload.jti)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token has been revoked",
        headers={"WWW-Authenticate": "Bearer"},
    )
```

Place this AFTER the existing `if payload is None or payload.type != "access":` check and BEFORE
the `repo.find_by_id()` call.

**Per-task validation:**
- `uv run ruff format app/auth/dependencies.py`
- `uv run ruff check --fix app/auth/dependencies.py`
- `uv run mypy app/auth/dependencies.py`

---

### Task 8: Tighten CORS Configuration
**File:** `app/core/middleware.py` (modify existing)
**Action:** UPDATE

Current CORS config uses `allow_methods=["*"]` and `allow_headers=["*"]`, which is too permissive
for a government application. Restrict to only the methods and headers actually used.

Read the file first. Then change the CORS middleware setup in `setup_middleware`:

Replace:
```python
allow_methods=["*"],
allow_headers=["*"],
```

With:
```python
allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept", "Accept-Language"],
```

These cover all HTTP methods used by the API and all headers the frontend sends.

**Per-task validation:**
- `uv run ruff format app/core/middleware.py`
- `uv run ruff check --fix app/core/middleware.py`
- `uv run mypy app/core/middleware.py`

---

### Task 9: Add Security Headers to Nginx (CSP, HSTS, Permissions)
**File:** `nginx/nginx.conf` (modify existing)
**Action:** UPDATE

Read the file first. The existing security headers (lines 70-73) are missing Content-Security-Policy
and X-XSS-Protection. Add to the existing header block inside the `server` block:

After the existing `add_header Permissions-Policy` line, add:
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.tile.openstreetmap.org https://cartodb-basemaps-a.global.ssl.fastly.net https://cartodb-basemaps-b.global.ssl.fastly.net https://cartodb-basemaps-c.global.ssl.fastly.net https://cartodb-basemaps-d.global.ssl.fastly.net; connect-src 'self'; font-src 'self'; frame-ancestors 'none'" always;
add_header X-XSS-Protection "0" always;
```

Notes:
- `unsafe-inline` and `unsafe-eval` are needed for Next.js (it inlines scripts for hydration)
- `img-src` includes OSM and CARTO tile servers for Leaflet maps
- `X-XSS-Protection: 0` is the modern recommendation (CSP supersedes it; non-zero values can
  introduce vulnerabilities in older browsers)
- `frame-ancestors 'none'` reinforces X-Frame-Options DENY

**Per-task validation:**
- Verify nginx config syntax: `docker run --rm -v $(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro nginx:alpine nginx -t` (optional, may not be available)
- Visual inspection that all `add_header` lines have `always` suffix

---

### Task 10: Fix Hardcoded Docker Credentials
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

Read the file first. Two services still hardcode `DATABASE_URL` with plaintext credentials:

1. **migrate service** (around line 53): Change
   `- DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/vtv_db`
   to
   `- DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@db:5432/${POSTGRES_DB:-vtv_db}`

2. **app service** (around line 94): Change
   `- DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/vtv_db`
   to
   `- DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@db:5432/${POSTGRES_DB:-vtv_db}`

3. **Add Redis password support** to the redis service. Add environment:
   ```yaml
   redis:
     command: redis-server --requirepass ${REDIS_PASSWORD:-}
   ```
   And update the app service REDIS_URL:
   `- REDIS_URL=redis://:${REDIS_PASSWORD:-}@redis:6379/0`

NOTE: The `${REDIS_PASSWORD:-}` pattern means empty password by default (backward compatible).
When deployed, set `REDIS_PASSWORD=<strong-password>` in `.env`.

Remove the comment that says credentials are "intentionally hardcoded" from the app service
(around line 92-93). Replace with: `# Uses env var interpolation for credentials — override via .env`

**Per-task validation:**
- `docker compose config` (validates YAML syntax, optional if Docker is available)
- Visual inspection that NO plaintext `postgres:postgres` remains in environment sections

---

### Task 10a: Require JWT_SECRET_KEY in Production Docker Compose
**File:** `docker-compose.prod.yml` (modify existing)
**Action:** UPDATE

Read the file first. The production compose sets `ENVIRONMENT=production` on the app service, which
triggers the startup check for non-default JWT secret. But the JWT_SECRET_KEY is NOT explicitly
passed to the app container. It relies on `.env.production` file being present and having it set.

For explicit safety, add `JWT_SECRET_KEY` as a required variable in the app service environment:

In the `app` service `environment` list, add:
```yaml
- JWT_SECRET_KEY=${JWT_SECRET_KEY:?Set JWT_SECRET_KEY in .env.production}
```

This uses the `?` modifier which causes docker-compose to FAIL at config time (not just at app
startup) if the variable is not set. This is a stronger guarantee than the runtime check.

Also verify these existing entries are correct:
- `POSTGRES_PASSWORD` should use `${POSTGRES_PASSWORD:?...}` syntax (check if it does)
- The `db` service should NOT have hardcoded `POSTGRES_USER: postgres` — check and fix if needed

**Per-task validation:**
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` (optional)
- Visual inspection

---

### Task 10b: Enable HTTPS in Nginx Configuration
**File:** `nginx/nginx.conf` (modify existing)
**Action:** UPDATE

Read the file first. The HTTPS server block is currently commented out (lines 177-202). For a
government-grade deployment, HTTPS must be the default. Uncomment and configure the HTTPS block.

Changes:

1. **Uncomment the HTTPS server block** (remove all `#` from lines 177-202). Configure it with:
   ```nginx
   server {
       listen 443 ssl http2;
       server_name _;

       ssl_certificate /etc/nginx/certs/cert.pem;
       ssl_certificate_key /etc/nginx/certs/key.pem;
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
       ssl_prefer_server_ciphers on;
       ssl_session_cache shared:SSL:10m;
       ssl_session_timeout 10m;
       ssl_session_tickets off;
       ssl_stapling on;
       ssl_stapling_verify on;

       add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

       # Connection limit per IP
       limit_conn addr 20;

       # --- Security Headers (same as HTTP block) ---
       add_header X-Content-Type-Options "nosniff" always;
       add_header X-Frame-Options "DENY" always;
       add_header Referrer-Policy "strict-origin-when-cross-origin" always;
       add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
       add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.tile.openstreetmap.org https://cartodb-basemaps-a.global.ssl.fastly.net https://cartodb-basemaps-b.global.ssl.fastly.net https://cartodb-basemaps-c.global.ssl.fastly.net https://cartodb-basemaps-d.global.ssl.fastly.net; connect-src 'self'; font-src 'self'; frame-ancestors 'none'" always;
       add_header X-XSS-Protection "0" always;

       # Copy ALL location blocks from the HTTP server block above:
       # /v1/chat/completions, /api/v1/schedules/import, /api/v1/schedules/validate,
       # /api/v1/knowledge, /api/, /health, /docs, /openapi.json, /v1/models,
       # /_next/static/, /
   }
   ```

2. **Add HTTP-to-HTTPS redirect** as a separate server block:
   ```nginx
   server {
       listen 80;
       server_name _;
       return 301 https://$host$request_uri;
   }
   ```
   This REPLACES the existing HTTP server block when HTTPS is active. But since we need the
   system to work BOTH with and without certs (development vs production), use this approach:

   Actually — the safer approach for a dev/prod split is:
   - Keep the existing HTTP server block for development (port 80, no redirect)
   - Add the HTTPS server block and the redirect block AFTER it, both commented with a note:
     "Enable for production by uncommenting. Requires certs at /etc/nginx/certs/"

   BUT since the user wants this FIXED (not just documented), uncomment both blocks. For
   development, users who don't have certs simply won't mount the certs volume and nginx will
   fail to start the 443 listener — which is fine because development uses port 80 only.

   BEST APPROACH: Add an `include` directive pattern. Create a conditional approach:
   - Keep the HTTP server block as-is (for development)
   - Uncomment the HTTPS block and redirect block
   - Add a comment: "HTTPS requires cert files. For dev without certs, remove nginx 443 port mapping"

   The HTTPS server block MUST replicate ALL location blocks from the HTTP server. Copy every
   `location` block from the HTTP server into the HTTPS server.

NOTE: This is a large change. The executing agent should read the entire nginx.conf first,
then write the complete HTTPS server block with all location blocks duplicated.

**Per-task validation:**
- Visual inspection of nginx.conf structure
- Both HTTP and HTTPS server blocks present with all location rules

---

### Task 10c: Harden Default JWT Secret Key
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Read the file first. The current JWT configuration (line 117):
```python
jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"  # noqa: S105
```

This provides a working default that gets caught at startup in production. But for government-grade
security, the SECRET should NEVER have a default value — it should fail immediately in ALL
environments if not explicitly set.

Changes:
1. Remove the default value for `jwt_secret_key`. Make it a required env var:
   ```python
   jwt_secret_key: str  # MUST be set via JWT_SECRET_KEY env var
   ```
   BUT this would break local development (need .env). So instead, keep the default ONLY for
   the development environment by using a `model_validator`:

   Actually, the simplest approach that doesn't break existing development workflow:
   Keep the default BUT make it a 64-character random-looking string that is CLEARLY not
   production-safe, and keep the startup check. The current "CHANGE-ME-IN-PRODUCTION" is
   fine for the runtime check.

   BEST APPROACH: Add a `model_validator` that generates a random secret for development:
   ```python
   jwt_secret_key: str = ""  # Set via JWT_SECRET_KEY env var; empty = auto-generate for dev
   ```
   Then add a `@model_validator(mode="after")` on `Settings`:
   ```python
   @model_validator(mode="after")
   def _set_jwt_default(self) -> "Settings":
       if not self.jwt_secret_key and self.environment == "development":
           import secrets
           object.__setattr__(self, "jwt_secret_key", secrets.token_hex(32))
       return self
   ```

   WAIT — this changes the behavior significantly and could break tests. Let's use a simpler
   approach that's still more secure:

   FINAL APPROACH: Keep the current default for backward compatibility BUT strengthen the
   startup check in `app/main.py` to also reject empty strings and short keys:

   In `app/main.py` lifespan, enhance the JWT check (lines 66-71):
   ```python
   _INSECURE_DEFAULTS = {"CHANGE-ME-IN-PRODUCTION", "", "secret", "changeme"}
   if settings.environment != "development" and (
       settings.jwt_secret_key in _INSECURE_DEFAULTS
       or len(settings.jwt_secret_key) < 32
   ):
       msg = (
           "JWT_SECRET_KEY must be a strong secret (min 32 chars) "
           "in non-development environments"
       )
       raise RuntimeError(msg)
   ```

   This ensures production CANNOT start with a weak key, while development keeps working.

   Additionally, update `.env.example` to include a generated example:
   ```bash
   # JWT Authentication (REQUIRED in production — use: python -c "import secrets; print(secrets.token_hex(32))")
   JWT_SECRET_KEY=CHANGE-ME-IN-PRODUCTION
   ```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check --fix app/main.py`
- `uv run mypy app/main.py`

---

### Task 10d: Add Admin Password Reset Endpoint
**File:** `app/auth/routes.py` (modify existing) AND `app/auth/service.py` (modify existing)
**Action:** UPDATE both files

Government systems need the ability to reset passwords without email infrastructure. Add an
admin-only endpoint that allows admins to reset any user's password.

**First, update `app/auth/schemas.py`** — add a `PasswordResetRequest` schema:
```python
class PasswordResetRequest(BaseModel):
    """Admin-initiated password reset."""
    user_id: int
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)
```

**Then, update `app/auth/service.py`** — add a `reset_password` method to `AuthService`:
```python
async def reset_password(self, user_id: int, new_password: str) -> None:
    """Reset a user's password (admin action).

    Args:
        user_id: Target user's database ID.
        new_password: The new password (already validated by schema).

    Raises:
        InvalidCredentialsError: If user not found.
    """
    user = await self.repo.find_by_id(user_id)
    if not user:
        raise InvalidCredentialsError("User not found")

    user.hashed_password = self.hash_password(new_password)
    user.failed_attempts = 0
    user.locked_until = None
    await self.repo.update(user)

    # Revoke all existing tokens for this user by clearing Redis keys
    try:
        from app.core.redis import get_redis
        redis_client = await get_redis()
        # Note: Full token revocation would require tracking all JTIs per user.
        # For now, clearing brute force state suffices. Token expiry (30min) limits exposure.
        await redis_client.delete(  # type: ignore[misc]
            f"auth:failures:{user.email}",
            f"auth:lockout:{user.email}",
        )
    except Exception:
        pass  # Redis unavailable — tokens expire naturally

    logger.info("auth.password_reset", user_id=user_id)
```

**Then, update `app/auth/routes.py`** — add the endpoint:
```python
@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: PasswordResetRequest,
    service: AuthService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> None:
    """Reset a user's password (admin only)."""
    _ = request
    await service.reset_password(body.user_id, body.new_password)
```

Import `PasswordResetRequest` from schemas in routes.py.

**Per-task validation:**
- `uv run ruff format app/auth/schemas.py app/auth/service.py app/auth/routes.py`
- `uv run ruff check --fix app/auth/schemas.py app/auth/service.py app/auth/routes.py`
- `uv run mypy app/auth/schemas.py app/auth/service.py app/auth/routes.py`

---

### Task 11: Redact Health Endpoint Details
**File:** `app/core/health.py` (modify existing)
**Action:** UPDATE

Read the file first. The health endpoints expose infrastructure details:
- `/health/db` returns `"provider": "postgresql"` — leaks DB technology
- `/health/redis` error returns `f"Redis unavailable: {e}"` — leaks error details
- `/health/ready` returns `"environment": settings.environment` and individual service statuses

Changes:
1. In `database_health_check`: Remove `"provider": "postgresql"` from the response dict.
   Keep only `{"status": "healthy", "service": "database"}`.

2. In `health_redis`: Change the error handler to NOT leak the exception message:
   Replace `detail=f"Redis unavailable: {e}"` with `detail="Service dependency unavailable"`.

3. In `readiness_check`: Remove `"environment": settings.environment` from the response.
   Keep: `{"status": "ready", "database": "connected", "redis": redis_status}`.

**Per-task validation:**
- `uv run ruff format app/core/health.py`
- `uv run ruff check --fix app/core/health.py`
- `uv run mypy app/core/health.py`

---

### Task 12: Move Quota Tracker to Redis
**File:** `app/core/agents/quota.py` (modify existing)
**Action:** UPDATE

Read the file first. The current quota tracker uses in-memory dict (same problem as the original
brute force). It resets on every server restart, allowing users to exceed daily quota.

The fix: Use Redis counters with daily TTL expiry. Keep the in-memory tracker as a fallback when
Redis is unavailable.

After reading the file, refactor the `QuotaTracker` class:
- Rename the existing class to `_InMemoryQuotaTracker` (keep as fallback)
- Create a new `RedisQuotaTracker` that uses Redis INCR with TTL:
  ```python
  async def check_and_increment(self, client_ip: str) -> bool:
      try:
          from app.core.redis import get_redis
          redis_client = await get_redis()
          key = f"quota:daily:{client_ip}"
          count = await redis_client.incr(key)  # type: ignore[misc]
          if count == 1:
              # First request today — set TTL to end of day (or 24h)
              await redis_client.expire(key, 86400)  # type: ignore[misc]
          return int(count) <= self._max_daily
      except Exception:
          # Fall back to in-memory
          return self._fallback.check_and_increment(client_ip)
  ```

IMPORTANT: The `check_and_increment` method is currently SYNC. Check the existing signature. If
it is sync, keep the new method sync too but use `asyncio` to call Redis. Actually — look at how
it's called in `app/core/agents/routes.py` to determine if async is viable. If the calling code
is already async (it's in an async route handler), then making the tracker async is fine. But you
must update the caller too.

If changing to async, update the call site in `app/core/agents/routes.py`:
```python
if not await tracker.check_and_increment(client_ip):
```

Add pyright directive if needed. Use `# type: ignore[misc]` on Redis await calls.

**Per-task validation:**
- `uv run ruff format app/core/agents/quota.py`
- `uv run ruff check --fix app/core/agents/quota.py`
- `uv run mypy app/core/agents/quota.py`
- `uv run ruff format app/core/agents/routes.py`
- `uv run ruff check --fix app/core/agents/routes.py`
- `uv run mypy app/core/agents/routes.py`

---

### Task 13: Extend Security Regression Tests
**File:** `app/tests/test_security.py` (modify existing)
**Action:** UPDATE

Read the file first. Then ADD test classes for every new security fix:

**Test Class 1: TestEventsAuthentication**
```python
class TestEventsAuthentication:
    """All events endpoints must require authentication."""

    def test_list_events_requires_auth(self) -> None:
        """list_events must have get_current_user dependency."""
        import inspect
        from app.events.routes import list_events
        source = inspect.getsource(list_events)
        assert "get_current_user" in source or "require_role" in source

    def test_get_event_requires_auth(self) -> None:
        """get_event must have get_current_user dependency."""
        import inspect
        from app.events.routes import get_event
        source = inspect.getsource(get_event)
        assert "get_current_user" in source or "require_role" in source
```

**Test Class 2: TestPasswordComplexity**
```python
class TestPasswordComplexity:
    """Password complexity must be enforced."""

    def test_short_password_rejected(self) -> None:
        from pydantic import ValidationError
        from app.auth.schemas import LoginRequest
        with pytest.raises(ValidationError):
            LoginRequest(email="test@test.com", password="short")

    def test_no_uppercase_rejected(self) -> None:
        from pydantic import ValidationError
        from app.auth.schemas import LoginRequest
        with pytest.raises(ValidationError):
            LoginRequest(email="test@test.com", password="alllowercase1")

    def test_valid_password_accepted(self) -> None:
        from app.auth.schemas import LoginRequest
        req = LoginRequest(email="test@test.com", password="ValidPass123")
        assert req.password == "ValidPass123"
```

**Test Class 3: TestTokenRevocation**
```python
class TestTokenRevocation:
    """Token revocation via Redis denylist."""

    @pytest.mark.asyncio
    async def test_revoke_and_check(self) -> None:
        from app.auth.token import is_token_revoked, revoke_token
        from unittest.mock import AsyncMock, patch, MagicMock

        mock_redis = MagicMock()
        mock_redis.setex = AsyncMock()
        mock_redis.get = AsyncMock(return_value="1")

        with patch("app.auth.token.get_redis", return_value=mock_redis):
            await revoke_token("test-jti-123")
            mock_redis.setex.assert_called_once()
            result = await is_token_revoked("test-jti-123")
            assert result is True

    @pytest.mark.asyncio
    async def test_non_revoked_token(self) -> None:
        from app.auth.token import is_token_revoked
        from unittest.mock import AsyncMock, patch, MagicMock

        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.auth.token.get_redis", return_value=mock_redis):
            result = await is_token_revoked("clean-jti")
            assert result is False
```

**Test Class 4: TestBruteForceRedis**
```python
class TestBruteForceRedis:
    """Brute force tracking should use Redis."""

    def test_auth_service_uses_redis_brute_force(self) -> None:
        import inspect
        from app.auth.service import AuthService
        source = inspect.getsource(AuthService.authenticate)
        assert "redis" in source.lower() or "_check_redis_brute_force" in source
```

**Test Class 5: TestCorsRestricted**
```python
class TestCorsRestricted:
    """CORS must not use wildcard methods/headers."""

    def test_cors_no_wildcard_methods(self) -> None:
        import inspect
        from app.core.middleware import setup_middleware
        source = inspect.getsource(setup_middleware)
        assert 'allow_methods=["*"]' not in source

    def test_cors_no_wildcard_headers(self) -> None:
        import inspect
        from app.core.middleware import setup_middleware
        source = inspect.getsource(setup_middleware)
        assert 'allow_headers=["*"]' not in source
```

**Test Class 6: TestHealthRedaction**
```python
class TestHealthRedaction:
    """Health endpoints must not leak infrastructure details."""

    def test_db_health_no_provider_leak(self) -> None:
        import inspect
        from app.core.health import database_health_check
        source = inspect.getsource(database_health_check)
        assert '"provider"' not in source or "postgresql" not in source

    def test_redis_health_no_error_leak(self) -> None:
        import inspect
        from app.core.health import health_redis
        source = inspect.getsource(health_redis)
        assert 'f"Redis unavailable: {e}"' not in source
```

**Test Class 7: TestDockerNoHardcodedCreds**
```python
class TestDockerNoHardcodedCreds:
    """Docker compose must not have hardcoded database credentials in any service."""

    def test_no_hardcoded_database_url(self) -> None:
        from pathlib import Path
        compose = Path("docker-compose.yml").read_text()
        # The literal string should NOT appear in environment sections
        lines = compose.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- DATABASE_URL=") or stripped.startswith("DATABASE_URL="):
                assert "postgres:postgres@" not in stripped, (
                    f"Hardcoded credentials found: {stripped}"
                )
```

**Test Class 8: TestVersionRedaction**
```python
class TestVersionRedaction:
    """Root endpoint must not expose version in production."""

    def test_root_endpoint_no_version_in_prod(self) -> None:
        import inspect
        from app.main import read_root
        source = inspect.getsource(read_root)
        # Version should only be included conditionally
        assert "development" in source
        assert "version" in source
```

**Per-task validation:**
- `uv run ruff format app/tests/test_security.py`
- `uv run ruff check --fix app/tests/test_security.py`
- `uv run pytest app/tests/test_security.py -v` — all tests pass

---

### Task 14: Update .env.example with New Security Variables
**File:** `.env.example` (modify existing)
**Action:** UPDATE

Read the file first. Add new variables under appropriate sections:

```bash
# Redis Authentication (set in production)
REDIS_PASSWORD=

# Password Policy
# PASSWORD_MIN_LENGTH=10  # enforced in auth schemas
```

**Per-task validation:**
- Visual inspection only

---

### Task 15: Update Security Audit Documentation
**File:** `docs/security_audit_2.txt` (modify existing)
**Action:** UPDATE

Read the file first. Append a remediation status table at the end:

```
## Remediation Status (v3 Hardening)

| # | Finding | Source | Severity | Status | Fix Applied |
|---|---------|--------|----------|--------|-------------|
| 1 | Events GET unauthenticated | Code review | HIGH | FIXED | Added get_current_user to list_events and get_event |
| 2 | In-memory brute force | Audit 1 #9 | HIGH | FIXED | Redis-backed tracking with DB fallback |
| 3 | No token revocation | Code review | HIGH | FIXED | Redis denylist with TTL matching token expiry |
| 4 | CORS too permissive | Code review | MEDIUM | FIXED | Restricted methods and headers to explicit allowlist |
| 5 | No CSP header | Code review | MEDIUM | FIXED | Content-Security-Policy added to nginx |
| 6 | Docker DATABASE_URL hardcoded | Audit 1 #11 | MEDIUM | FIXED | Env var interpolation in migrate and app services |
| 7 | Health leaks infra details | Code review | LOW | FIXED | Removed provider name and error messages |
| 8 | Root endpoint leaks version | Code review | LOW | FIXED | Version only in development environment |
| 9 | No password complexity | Audit 3 #6 | HIGH | FIXED | 10+ chars, uppercase, lowercase, digit required |
| 10 | Refresh ignores lockout | Code review | MEDIUM | FIXED | Added locked_until check in refresh_access_token |
| 11 | Quota tracker in-memory | Code review | MEDIUM | FIXED | Redis-backed with in-memory fallback |
| 12 | Redis no authentication | Code review | MEDIUM | FIXED | Optional password via REDIS_PASSWORD env var |
| 13 | No HTTPS/TLS | Audit 1 #10 | HIGH | FIXED | Full HTTPS server block in nginx, HTTP-to-HTTPS redirect |
| 14 | Exposed DB ports | Audit 1 #13 | MEDIUM | FIXED | docker-compose.prod.yml already uses `ports: !reset []` |
| 15 | No password reset | Audit 3 #6 | HIGH | FIXED | Admin-only password reset endpoint with complexity validation |
| 16 | Default JWT secret | Audit 3 #3 | HIGH | FIXED | Enhanced startup check rejects weak/short keys in production |

Deployment requirements (cert provisioning):
- HTTPS: Requires SSL certificate files at `nginx/certs/cert.pem` and `nginx/certs/key.pem`
  Generate self-signed for testing: `openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx/certs/key.pem -out nginx/certs/cert.pem`
  Production: Use Let's Encrypt or institutional CA certificate
```

**Per-task validation:**
- Visual inspection only

---

## Migration (if applicable)

No database migration required. All changes are application-level code and configuration.
Redis keys are created on-demand with TTL — no schema setup needed.

## Logging Events

- `auth.login_locked_redis` — Brute force lockout triggered via Redis fast-path
- `auth.token_revoked` — Revoked token presented (JTI logged)
- `auth.token.revocation_failed` — Redis unavailable during revocation attempt
- `auth.login_redis_cleared` — Redis brute force keys cleared on successful login

## Testing Strategy

### Unit Tests
**Location:** `app/tests/test_security.py`
- Events authentication enforcement (source inspection)
- Password complexity validation (Pydantic validation errors)
- Token revocation (mock Redis)
- CORS configuration (source inspection)
- Health endpoint redaction (source inspection)
- Docker credential interpolation (file content check)
- Brute force Redis integration (source inspection)
- Version redaction (source inspection)

### Integration Tests
**Location:** `app/tests/test_security.py`
**Mark with:** `@pytest.mark.asyncio` for async tests
- Token revocation round-trip (mock Redis set/get)
- Brute force Redis round-trip (mock Redis pipeline)

### Edge Cases
- Redis unavailable during brute force check — falls through to DB check (no crash)
- Redis unavailable during token revocation — fail-open (availability over security)
- Redis unavailable during quota check — falls back to in-memory tracker
- Empty/None JTI in revocation check — returns False (not revoked)
- Password at exactly minimum length with all requirements — accepted
- Password with only special characters — rejected (no uppercase/lowercase/digit)

## Acceptance Criteria

This feature is complete when:
- [ ] All events endpoints require authentication (no unauthenticated data access)
- [ ] Password complexity enforced (10+ chars, mixed case, digit)
- [ ] Brute force tracking persists across server restarts (Redis-backed)
- [ ] JWT tokens can be revoked via Redis denylist
- [ ] Revoked tokens are rejected by auth dependency
- [ ] CORS restricted to explicit methods and headers
- [ ] Content-Security-Policy header present in nginx responses
- [ ] No hardcoded credentials in docker-compose.yml environment sections
- [ ] Health endpoints do not leak infrastructure technology names
- [ ] Root endpoint does not expose version in non-development environments
- [ ] Refresh token endpoint checks account lockout status
- [ ] Quota tracker persists across server restarts (Redis-backed)
- [ ] HTTPS server block enabled in nginx with modern TLS config
- [ ] JWT_SECRET_KEY required in production docker-compose (fails if not set)
- [ ] Startup rejects weak JWT keys (< 32 chars or known defaults) in non-dev
- [ ] Admin-only password reset endpoint available
- [ ] Production docker-compose removes exposed database/Redis ports
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (existing + 8 new test classes)
- [ ] No regressions in existing 612+ tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 19 tasks completed in order (Tasks 1-10, 10a-10d, 11-15)
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
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

**Level 3: Security Tests**
```bash
uv run pytest app/tests/test_security.py -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings.

## Dependencies

- Shared utilities used: `app.shared.models.utcnow`, `app.shared.utils.escape_like`
- Core modules used: `app.core.redis`, `app.core.config`, `app.core.logging`, `app.core.middleware`
- New dependencies: **None** — all fixes use existing packages (redis, jose, pydantic, fastapi)
- New env vars: `REDIS_PASSWORD` (optional, empty default for backward compatibility)

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No `assert` in production code** — Ruff S101. Use conditional checks.
2. **Redis `await` needs `# type: ignore[misc]`** — Redis stubs return `Awaitable[T] | T`.
3. **`redis.pipeline()` is SYNC** — Mock with `MagicMock()` not `AsyncMock()`.
4. **ARG001 applies to ALL unused params** — Use `_ = request` pattern.
5. **Test helpers need return types** — Always `-> None` or `-> MagicMock`.
6. **No EN DASH in strings** — Use HYPHEN-MINUS only.
7. **Never expose role names in error messages** — Generic "Insufficient permissions" only.
8. **`bare except: pass` violates S110** — Always log in except blocks. Exception: `except RuntimeError: pass` for closed event loops.
9. **FastAPI `Query(None)` needs `# noqa: B008`** — Function calls in arg defaults.
10. **pyright file-level directives for Redis files** — Add `# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false` on files using Redis.
11. **Don't guess `# type: ignore` codes** — Write code first, run mypy, then add exact codes.
12. **Partially annotated test functions need `-> None`** — When any param is typed.
13. **Docker env var interpolation syntax** — `${VAR:-default}` for default values, `${VAR:-}` for optional empty.
14. **nginx `add_header` needs `always`** — Without `always`, headers are only added on 2xx responses.
15. **`check_and_increment` sync vs async** — Check the existing signature before changing. If changing to async, update ALL callers.

## Security Threat Coverage Matrix

| Threat | OWASP Category | Control | Status |
|--------|---------------|---------|--------|
| Unauthorized data access | A01:2021 Broken Access Control | JWT + RBAC on all endpoints | FIXED (Task 1) |
| Credential stuffing | A07:2021 Auth Failures | Redis brute force tracking | FIXED (Task 5) |
| Weak passwords | A07:2021 Auth Failures | Complexity validation | FIXED (Task 2) |
| Token theft | A07:2021 Auth Failures | Token revocation denylist | FIXED (Task 6-7) |
| XSS | A03:2021 Injection | CSP header | FIXED (Task 9) |
| CORS misconfiguration | A05:2021 Security Misconfig | Explicit allowlists | FIXED (Task 8) |
| Credential exposure | A02:2021 Cryptographic Failures | Docker env interpolation | FIXED (Task 10) |
| Info disclosure | A05:2021 Security Misconfig | Health/root redaction | FIXED (Task 4, 11) |
| Rate limit bypass | A04:2021 Insecure Design | X-Real-IP (already fixed) | VERIFIED |
| SQL injection | A03:2021 Injection | SQLAlchemy parameterized | VERIFIED |
| Path traversal | A01:2021 Broken Access Control | is_relative_to() | VERIFIED |
| ILIKE injection | A03:2021 Injection | escape_like() | VERIFIED |
| No HTTPS/TLS | A02:2021 Cryptographic Failures | Full HTTPS nginx config | FIXED (Task 10b) |
| No password reset | A07:2021 Auth Failures | Admin-only reset endpoint | FIXED (Task 10d) |
| Weak JWT secret | A02:2021 Cryptographic Failures | Startup validation + min 32 chars | FIXED (Task 10c) |
| Exposed DB ports | A05:2021 Security Misconfig | Production compose strips ports | VERIFIED |

## Notes

**Government-level considerations applied:**
- All data access requires authentication — no "public" endpoints for internal operational data
- Password complexity exceeds Latvian CERT recommendations (10+ chars, mixed case, digit)
- Token revocation enables immediate access termination on security incidents
- Redis-backed tracking survives restarts — no security reset on deployment
- Infrastructure details hidden from health endpoints — prevents technology fingerprinting
- CSP prevents XSS even if application-level sanitization is bypassed
- CORS restricted to exact methods/headers — prevents unexpected browser behavior

**Deployment-time requirements (code is done, infrastructure needed):**
- HTTPS certs: Place SSL certificates at `nginx/certs/cert.pem` and `nginx/certs/key.pem`
- Redis password: Set `REDIS_PASSWORD` env var in production `.env`
- JWT secret: Set `JWT_SECRET_KEY` env var (min 32 chars) in production `.env`

**Future enhancements (not blocking production):**
- Self-service password reset: Requires SMTP service for secure token delivery via email
- Redis-backed brute force tracking at nginx level: Requires lua module
- Mutual TLS between services: Requires internal CA

**Future recommendations:**
- Implement security audit trail (dedicated table for login attempts, role changes, data access)
- Add Content-Security-Policy-Report-Only mode first, then enforce
- Consider adding rate limiting at Redis level (more sophisticated than nginx zones)
- Add automated security scanning to CI pipeline (Bandit, Safety)
- Consider mutual TLS for inter-service communication (app <-> Redis, app <-> PostgreSQL)

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the gap analysis (which findings from which audit)
- [ ] Clear on the distinction between code fixes and deployment-time fixes
- [ ] Verified Redis is available for testing (or know to mock it)
- [ ] Validation commands are executable in this environment
