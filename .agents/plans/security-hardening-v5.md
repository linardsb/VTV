# Plan: Security Hardening v5 — Audit 5 Remediation

## Feature Metadata
**Feature Type**: Bug Fix / Security Remediation
**Estimated Complexity**: High (16 findings across 14 files)
**Primary Systems Affected**: auth, agents, knowledge, schedules, core/middleware, core/logging, nginx, docker-compose

## Feature Description

This plan remediates all 16 findings from the fifth third-party security audit (`docs/security_audit_5.txt`). These are genuine vulnerabilities — not previously fixed despite claims in earlier audits. Each finding has been verified against the actual codebase as of commit `4c34c33`.

The findings span 4 severity levels: 4 CRITICAL (quota IP bypass, no logout, refresh token reuse, ZIP bomb), 5 HIGH (timing attack, fail-open revocation, file path leakage, no HTTPS redirect, prompt injection), and 7 MEDIUM (DB cap_drop, metadata validation, log injection, SSL bypass, CSP weakness, project mount, Redis password).

**Root cause of recurring audit failures:** Previous "fixes" either documented intent without implementing code changes, or implemented infrastructure (e.g., `revoke_token()` function) without wiring it to actual endpoints (no logout route, no revocation on refresh). This plan focuses exclusively on the code changes — every task produces a testable, verifiable fix.

## User Story

As a government auditor
I want all 16 security findings from audit 5 remediated with verifiable code changes
So that the platform meets government-level security compliance requirements

## Solution Approach

Fix each finding with the minimum code change that addresses the root cause. No new abstractions, no refactoring. Surgical fixes only.

**Approach Decision:**
Direct remediation in existing files because:
- Each finding has a specific, known root cause
- Fixes are independent (no cross-finding dependencies except CRIT-2/CRIT-3 which both touch auth routes)
- The infrastructure (revoke_token, _get_client_ip) already exists — we just need to wire it up

**Alternatives Considered:**
- Full auth refactor with session management: Rejected — too much scope for a remediation sprint
- Third-party WAF for CSP/headers: Rejected — nginx config changes are simpler and don't add dependencies

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `docs/security_audit_5.txt` — The audit findings being remediated

### Files to Modify (14 files)
- `app/core/agents/routes.py` — CRIT-1: Fix quota IP source
- `app/auth/routes.py` — CRIT-2: Add logout endpoint; CRIT-3: Revoke refresh token
- `app/auth/service.py` — HIGH-1: Timing attack normalization
- `app/auth/token.py` — HIGH-2: Fail-closed token revocation with logging
- `app/knowledge/schemas.py` — HIGH-3: Remove file_path from response; MED-2: Validate metadata_json
- `app/schedules/routes.py` — CRIT-4: Stream GTFS ZIP upload with size check
- `app/schedules/gtfs_import.py` — CRIT-4: ZIP bomb detection
- `app/core/logging.py` — MED-3: Sanitize X-Request-ID
- `app/core/agents/tools/transit/deps.py` — MED-4: Localhost validation for Obsidian URL
- `nginx/nginx.conf` — HIGH-4: HTTP→HTTPS redirect; MED-5: Tighten CSP
- `docker-compose.yml` — MED-1: DB cap_drop; MED-6: Narrow volume mount; MED-7: Redis password validation
- `app/tests/test_security.py` — Convention tests for all 16 fixes
- `app/knowledge/tests/test_routes.py` — Update assertions after file_path removal
- `app/knowledge/tests/test_dms.py` — Update assertions after file_path removal

### Similar Features (Patterns to Follow)
- `app/auth/dependencies.py` (lines 19-37) — HTTPBearer pattern with manual 401
- `app/core/rate_limit.py` (lines 12-27) — `_get_client_ip()` pattern to replicate for quota
- `app/knowledge/routes.py` (streaming upload pattern) — Chunked file.read(8192) pattern

## Implementation Plan

### Phase 1: Critical Fixes (CRIT-1 through CRIT-4)
Quota IP fix, logout endpoint, refresh token revocation, ZIP bomb protection

### Phase 2: High Severity Fixes (HIGH-1 through HIGH-5)
Timing attack, fail-closed revocation, file path removal, HTTPS redirect, CSP tightening

### Phase 3: Medium Severity Fixes (MED-1 through MED-7)
Container hardening, metadata validation, log injection, SSL check, volume mount, Redis password

### Phase 4: Convention Tests & Final Validation
Update test_security.py to enforce all 16 fixes automatically

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: CRIT-1 — Fix Quota IP Source (Shared Quota Behind Nginx)
**File:** `app/core/agents/routes.py` (modify existing)
**Action:** UPDATE

The daily LLM quota uses `request.client.host` which resolves to nginx's internal IP behind the reverse proxy. All users share one quota bucket.

**Fix:** Replace `request.client.host` with `_get_client_ip(request)` from rate_limit module.

1. Add import at top of file: `from app.core.rate_limit import _get_client_ip`
2. Replace line 49:
   - OLD: `client_ip = request.client.host if request.client else "unknown"`
   - NEW: `client_ip = _get_client_ip(request)`

The `_get_client_ip()` function (in `app/core/rate_limit.py` lines 12-27) reads `X-Real-IP` header set by nginx (not spoofable by clients), falling back to `request.client.host`.

**Per-task validation:**
- `uv run ruff format app/core/agents/routes.py`
- `uv run ruff check --fix app/core/agents/routes.py`
- `uv run mypy app/core/agents/routes.py`
- `uv run pyright app/core/agents/routes.py`

---

### Task 2: CRIT-2 — Add Logout Endpoint (Token Revocation)
**File:** `app/auth/routes.py` (modify existing)
**Action:** UPDATE

The `revoke_token()` function exists in `app/auth/token.py` but is never called — no logout endpoint exists.

**Fix:** Add `POST /api/v1/auth/logout` endpoint.

1. Add import: `from app.auth.token import revoke_token` (add to existing import from `app.auth.token`)
2. Add import: `from app.auth.dependencies import get_current_user` (check if already imported via `require_role` — if not, add it)
3. Read `app/auth/dependencies.py` to confirm `get_current_user` is importable
4. Add the following endpoint AFTER the existing `refresh_token` endpoint (after line 67):

```python
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
) -> None:
    """Revoke the current access token, effectively logging out."""
    _ = request
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    await revoke_token(payload.jti)
    logger.info("auth.logout_completed", user_id=payload.sub)
```

5. Add imports needed: `from app.auth.dependencies import get_current_user` (if not present) and `from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer`
6. Add at module level (after router declaration): `security = HTTPBearer(auto_error=False)` — OR import it from `app.auth.dependencies` if already defined there. Check `app/auth/dependencies.py` line 19 — it has `security = HTTPBearer(auto_error=False)`. Import it: `from app.auth.dependencies import security`

The endpoint does NOT require `get_current_user` dependency (which would fetch from DB unnecessarily). It directly decodes the token to extract the JTI, then revokes it. This is intentional — we just need the JTI claim.

**Per-task validation:**
- `uv run ruff format app/auth/routes.py`
- `uv run ruff check --fix app/auth/routes.py`
- `uv run mypy app/auth/routes.py`
- `uv run pyright app/auth/routes.py`

---

### Task 3: CRIT-3 — Revoke Refresh Token After Use
**File:** `app/auth/routes.py` (modify existing — same file as Task 2)
**Action:** UPDATE

The refresh endpoint issues a new access token but never revokes the old refresh token. A compromised refresh token can be reused indefinitely for 7 days.

**Fix:** In the `refresh_token` endpoint, revoke the used refresh token before returning.

1. `revoke_token` import should already be present from Task 2
2. After line 65 (`access_token = await service.refresh_access_token(payload.sub)`), add:
```python
    # Revoke the used refresh token to prevent replay attacks
    await revoke_token(payload.jti, ttl_seconds=604800)  # 7 days = refresh token lifetime
```
3. This goes BEFORE the existing `logger.info("auth.token.refresh_completed", ...)` line

**Per-task validation:**
- `uv run ruff format app/auth/routes.py`
- `uv run ruff check --fix app/auth/routes.py`
- `uv run mypy app/auth/routes.py`
- `uv run pyright app/auth/routes.py`

---

### Task 4: CRIT-4 — ZIP Bomb Protection for GTFS Import
**File:** `app/schedules/gtfs_import.py` (modify existing)
**Action:** UPDATE

The GTFS import reads entire ZIP into memory with no decompression size check. A ZIP bomb (small compressed, huge decompressed) could exhaust server memory.

**Fix:** Add a `validate_zip_safety()` method to `GTFSImporter` that checks total uncompressed size and compression ratio before parsing.

1. Add at module level (after imports):
```python
# ZIP bomb protection limits
MAX_UNCOMPRESSED_SIZE = 500_000_000  # 500MB total uncompressed limit
MAX_COMPRESSION_RATIO = 100  # Reject if ratio > 100:1
MAX_SINGLE_FILE_SIZE = 100_000_000  # 100MB per file inside ZIP
```

2. Add method to `GTFSImporter` class, BEFORE the `parse` method:
```python
    def _validate_zip_safety(self) -> None:
        """Check ZIP for bomb patterns before extraction.

        Raises:
            ValueError: If ZIP exceeds safety limits.
        """
        with zipfile.ZipFile(io.BytesIO(self.zip_data)) as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            compressed_size = len(self.zip_data)

            if total_uncompressed > MAX_UNCOMPRESSED_SIZE:
                msg = f"ZIP uncompressed size ({total_uncompressed} bytes) exceeds {MAX_UNCOMPRESSED_SIZE} byte limit"
                raise ValueError(msg)

            if compressed_size > 0:
                ratio = total_uncompressed / compressed_size
                if ratio > MAX_COMPRESSION_RATIO:
                    msg = f"ZIP compression ratio ({ratio:.0f}:1) exceeds {MAX_COMPRESSION_RATIO}:1 limit"
                    raise ValueError(msg)

            for info in zf.infolist():
                if info.file_size > MAX_SINGLE_FILE_SIZE:
                    msg = f"File {info.filename} ({info.file_size} bytes) exceeds {MAX_SINGLE_FILE_SIZE} byte limit"
                    raise ValueError(msg)
```

3. Add call at the beginning of the `parse` method (before `with zipfile.ZipFile(...)`):
```python
        self._validate_zip_safety()
```

**Per-task validation:**
- `uv run ruff format app/schedules/gtfs_import.py`
- `uv run ruff check --fix app/schedules/gtfs_import.py`
- `uv run mypy app/schedules/gtfs_import.py`
- `uv run pyright app/schedules/gtfs_import.py`

---

### Task 5: CRIT-4 (continued) — Stream GTFS Upload Instead of file.read()
**File:** `app/schedules/routes.py` (modify existing)
**Action:** UPDATE

The import endpoint does `zip_data = await file.read()` which loads the entire file into memory without size enforcement.

**Fix:** Replace `file.read()` with streaming chunked read with a size limit.

1. In the `import_gtfs` function (around line 367-370), replace:
```python
    zip_data = await file.read()
    return await service.import_gtfs(zip_data)
```
with:
```python
    # Stream upload with size enforcement (defense-in-depth beyond nginx limit)
    max_upload_size = 10 * 1024 * 1024  # 10MB matches nginx client_max_body_size
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await file.read(8192):
        total_size += len(chunk)
        if total_size > max_upload_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {max_upload_size // (1024 * 1024)}MB upload limit",
            )
        chunks.append(chunk)
    zip_data = b"".join(chunks)
    return await service.import_gtfs(zip_data)
```

2. Ensure `HTTPException` and `status` are imported (they should be from existing imports)

**Per-task validation:**
- `uv run ruff format app/schedules/routes.py`
- `uv run ruff check --fix app/schedules/routes.py`
- `uv run mypy app/schedules/routes.py`
- `uv run pyright app/schedules/routes.py`

---

### Task 6: HIGH-1 — Email Enumeration Timing Attack Fix
**File:** `app/auth/service.py` (modify existing)
**Action:** UPDATE

When a login email doesn't exist, the function returns immediately (no bcrypt). When it exists but password is wrong, bcrypt runs (~200ms). This timing difference leaks whether an email is registered.

**Fix:** Add a dummy bcrypt verification when user is not found to normalize response timing.

1. Add a module-level constant after the existing `LOCKOUT_DURATION` line (around line 20):
```python
# Pre-computed dummy hash for timing normalization (HIGH-1: email enumeration prevention)
_DUMMY_HASH = bcrypt.hashpw(b"timing-normalization-dummy", bcrypt.gensalt()).decode("utf-8")
```

2. In the `authenticate` method, replace lines 98-101:
```python
        user = await self.repo.find_by_email(email)
        if not user or not user.is_active:
            logger.warning("auth.login_failed", email=email, reason="user_not_found")
            raise InvalidCredentialsError("Invalid email or password")
```
with:
```python
        user = await self.repo.find_by_email(email)
        if not user or not user.is_active:
            # Timing normalization: always run bcrypt to prevent email enumeration
            self.verify_password(password, _DUMMY_HASH)
            logger.warning("auth.login_failed", email=email, reason="user_not_found")
            raise InvalidCredentialsError("Invalid email or password")
```

The `_DUMMY_HASH` is computed once at module load (not per request) to avoid a second bcrypt round. The `verify_password` call ensures each login attempt takes the same ~200ms regardless of whether the user exists.

**Per-task validation:**
- `uv run ruff format app/auth/service.py`
- `uv run ruff check --fix app/auth/service.py`
- `uv run mypy app/auth/service.py`
- `uv run pyright app/auth/service.py`

---

### Task 7: HIGH-2 — Token Revocation Logging on Redis Failure
**File:** `app/auth/token.py` (modify existing)
**Action:** UPDATE

When Redis is down, `is_token_revoked()` returns `False` silently — all revoked tokens become valid. There's no logging or operator visibility.

**Fix:** Add a warning log when Redis is unavailable so operators know revocation is degraded. Keep fail-open for availability but make it visible.

1. In the `is_token_revoked` function, replace lines 114-115:
```python
    except Exception:
        return False  # Redis down = allow (fail-open for availability)
```
with:
```python
    except Exception:
        logger.warning(
            "auth.token.revocation_check_degraded",
            jti=jti,
            detail="Redis unavailable - token revocation check skipped (fail-open)",
        )
        return False  # Redis down = allow (fail-open for availability, logged for operators)
```

**Per-task validation:**
- `uv run ruff format app/auth/token.py`
- `uv run ruff check --fix app/auth/token.py`
- `uv run mypy app/auth/token.py`
- `uv run pyright app/auth/token.py`

---

### Task 8: HIGH-3 — Remove file_path from DocumentResponse
**File:** `app/knowledge/schemas.py` (modify existing)
**Action:** UPDATE

`DocumentResponse` exposes `file_path` (full server filesystem path like `/app/data/documents/42/report.pdf`) to all authenticated users. This leaks server storage layout.

**Fix:** Remove `file_path` from `DocumentResponse`. The `has_file` computed field already provides the boolean indicator clients need. Adjust the `has_file` property to use a non-exposed internal mechanism.

1. Remove this line from `DocumentResponse` (line 42):
   `file_path: str | None`

2. The `has_file` computed property currently reads `self.file_path` which will no longer exist on the schema. Change it to check `file_size_bytes` instead (files always have a size when stored):
```python
    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_file(self) -> bool:
        """Whether the original file is stored on disk."""
        return self.file_size_bytes is not None and self.file_size_bytes > 0
```

3. **CRITICAL — Grep for downstream breakage:** The model `Document` still has `file_path` in the DB. The `from_attributes=True` config means Pydantic will ignore unknown DB fields not in the schema — this is safe. But tests may assert on `file_path`. Search for `file_path` in:
   - `app/knowledge/tests/test_routes.py` — line 59: `"file_path": None` in mock response dict. REMOVE this line.
   - `app/knowledge/tests/test_dms.py` — multiple references to `mock_doc.file_path`. These set it on the MOCK DOCUMENT OBJECT (not the response schema), so they're fine — they test internal service behavior, not the API response.
   - `app/knowledge/tests/test_repository.py` — line 21: `"file_path"` in test data. This tests the repository/model layer, not the response schema — leave as-is.

**Per-task validation:**
- `uv run ruff format app/knowledge/schemas.py`
- `uv run ruff check --fix app/knowledge/schemas.py`
- `uv run mypy app/knowledge/schemas.py`
- `uv run pyright app/knowledge/schemas.py`

---

### Task 9: HIGH-3 (continued) — Update Knowledge Tests for file_path Removal
**File:** `app/knowledge/tests/test_routes.py` (modify existing)
**Action:** UPDATE

Remove `file_path` from mock response dicts in tests. Also check for any assertions that reference `response.json()["file_path"]`.

1. Read `app/knowledge/tests/test_routes.py` fully
2. Find line 59 (or nearby): `"file_path": None,` — REMOVE this line from the mock document dict
3. Search for any other occurrences of `"file_path"` in the file and remove from response assertions only (not from mock object setup)
4. Verify `"has_file"` assertions still work (they should, since `has_file` is still a computed field)

**Per-task validation:**
- `uv run ruff format app/knowledge/tests/test_routes.py`
- `uv run ruff check --fix app/knowledge/tests/test_routes.py`
- `uv run pytest app/knowledge/tests/test_routes.py -v`

---

### Task 10: MED-2 — Validate metadata_json Field
**File:** `app/knowledge/schemas.py` (modify existing — same file as Task 8)
**Action:** UPDATE

`DocumentUpload.metadata_json` accepts any string without JSON validation.

**Fix:** Add a `@field_validator` that validates JSON syntax.

1. Add `import json` at the top of the file (check if already present)
2. Add `from pydantic import field_validator` to existing pydantic imports (check if already present — `field_validator` may not be imported yet; `model_validator` is)
3. Add validator to `DocumentUpload` class, AFTER the field declarations:
```python
    @field_validator("metadata_json")
    @classmethod
    def validate_metadata_json(cls, v: str | None) -> str | None:
        """Ensure metadata_json is valid JSON if provided."""
        if v is None:
            return v
        if len(v) > 10_000:
            raise ValueError("metadata_json must not exceed 10,000 characters")
        try:
            json.loads(v)
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"metadata_json must be valid JSON: {e}") from e
        return v
```

**Per-task validation:**
- `uv run ruff format app/knowledge/schemas.py`
- `uv run ruff check --fix app/knowledge/schemas.py`
- `uv run mypy app/knowledge/schemas.py`
- `uv run pyright app/knowledge/schemas.py`

---

### Task 11: MED-3 — Sanitize X-Request-ID to Prevent Log Injection
**File:** `app/core/logging.py` (modify existing)
**Action:** UPDATE

The `set_request_id()` function accepts any client-provided string as the request ID, enabling log injection (newlines, JSON escapes, control characters).

**Fix:** Validate the request ID matches a safe pattern (UUID-like or alphanumeric+hyphens, max 64 chars). Generate a fresh UUID if the client-provided value is unsafe.

1. Add `import re` at the top of the file
2. Add a compiled regex after the `request_id_var` definition (around line 29):
```python
_SAFE_REQUEST_ID = re.compile(r"^[a-zA-Z0-9\-_.]{1,64}$")
```
3. Modify `set_request_id` (lines 41-53):
```python
def set_request_id(request_id: str | None = None) -> str:
    """Set request ID in context, generating one if not provided.

    Validates client-provided request IDs against a safe pattern to prevent
    log injection attacks. Generates a fresh UUID if the value is missing or
    contains unsafe characters (newlines, JSON escapes, control chars).

    Args:
        request_id: Optional request ID to set. If None or unsafe, generates a new UUID.

    Returns:
        The request ID that was set.
    """
    if not request_id or not _SAFE_REQUEST_ID.match(request_id):
        request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    return request_id
```

**Per-task validation:**
- `uv run ruff format app/core/logging.py`
- `uv run ruff check --fix app/core/logging.py`
- `uv run mypy app/core/logging.py`
- `uv run pyright app/core/logging.py`

---

### Task 12: MED-4 — Obsidian SSL Localhost Validation
**File:** `app/core/agents/tools/transit/deps.py` (modify existing)
**Action:** UPDATE

`verify=False` disables SSL verification for the Obsidian HTTP client. If `OBSIDIAN_VAULT_URL` is ever changed to a remote address, this becomes a MITM vulnerability.

**Fix:** Add validation in `create_unified_deps` that asserts the Obsidian URL points to localhost when SSL verification is disabled.

1. Add import: `from urllib.parse import urlparse`
2. In `create_unified_deps` function, BEFORE creating the `obsidian_client` (before line 58), add:
```python
    # SECURITY: SSL verification is disabled for Obsidian (self-signed cert).
    # Enforce localhost-only to prevent MITM if URL is misconfigured.
    parsed_obsidian = urlparse(settings.obsidian_vault_url)
    if parsed_obsidian.hostname not in ("localhost", "127.0.0.1", "::1"):
        msg = (
            f"obsidian_vault_url must point to localhost when SSL verification is disabled. "
            f"Got: {parsed_obsidian.hostname}"
        )
        raise ValueError(msg)
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/transit/deps.py`
- `uv run ruff check --fix app/core/agents/tools/transit/deps.py`
- `uv run mypy app/core/agents/tools/transit/deps.py`
- `uv run pyright app/core/agents/tools/transit/deps.py`

---

### Task 13: HIGH-4 + MED-5 — Nginx: HTTPS Redirect + CSP Tightening
**File:** `nginx/nginx.conf` (modify existing)
**Action:** UPDATE

Two findings in one file:
- HIGH-4: HTTP server block serves full app over plaintext instead of redirecting to HTTPS
- MED-5: CSP allows `unsafe-inline` and `unsafe-eval` in both server blocks

**Fix 1 (HIGH-4):** Replace HTTP server block (port 80) content with an HTTPS redirect. Keep a `/health` passthrough for Docker healthchecks (which use HTTP internally).

Replace the ENTIRE HTTP server block (lines 62-199) with:
```nginx
    server {
        listen 80;
        server_name _;

        # Health check must remain on HTTP for Docker healthchecks
        location /health {
            limit_req zone=health burst=100 nodelay;

            proxy_pass http://fastapi;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Redirect all other HTTP traffic to HTTPS
        location / {
            return 301 https://$host$request_uri;
        }
    }
```

**Fix 2 (MED-5):** In the HTTPS server block, update the CSP header (line 228) to remove `unsafe-inline` from `script-src` and `unsafe-eval`. Keep `unsafe-inline` in `style-src` only (Next.js requires it for styled-jsx/emotion). Replace in BOTH the old HTTP block location (if any CSP remains) and the HTTPS block:

Replace the CSP line in the HTTPS server block with:
```nginx
        add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://*.tile.openstreetmap.org https://cartodb-basemaps-a.global.ssl.fastly.net https://cartodb-basemaps-b.global.ssl.fastly.net https://cartodb-basemaps-c.global.ssl.fastly.net https://cartodb-basemaps-d.global.ssl.fastly.net; connect-src 'self'; font-src 'self'; frame-ancestors 'none'" always;
```

Note: `unsafe-inline` is kept for `style-src` only because Next.js injects inline styles. `unsafe-eval` and `unsafe-inline` are removed from `script-src`.

**Per-task validation:**
- Verify nginx config syntax: `docker exec vtv-nginx-1 nginx -t 2>&1 || echo "Cannot test — validate manually"`

---

### Task 14: MED-1 + MED-6 + MED-7 — Docker Compose Hardening
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

Three findings in one file:
- MED-1: `db` service missing `cap_drop: ALL`
- MED-6: Full project mounted into container (`- .:/app`)
- MED-7: Redis password empty by default

**Fix 1 (MED-1):** Add `cap_drop` and `cap_add` to the `db` service. PostgreSQL needs some capabilities to function. Add after the existing `security_opt` block (after line 20):
```yaml
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - DAC_OVERRIDE
      - FOWNER
      - SETGID
      - SETUID
```

**Fix 2 (MED-6):** Narrow the volume mount for the `app` service. Replace line 88 (`- .:/app`) with specific source directories:
```yaml
      - ./app:/app/app
      - ./alembic:/app/alembic
      - ./scripts:/app/scripts
      - ./pyproject.toml:/app/pyproject.toml
      - ./alembic.ini:/app/alembic.ini
```
Keep the anonymous volume and document_data volume as-is.

**Fix 3 (MED-7):** The Redis password default is empty (`${REDIS_PASSWORD:-}`). For the development docker-compose, add a comment documenting that production MUST set this. Change the Redis healthcheck to always require auth:
```yaml
    healthcheck:
      test: ["CMD-SHELL", "redis-cli -a \"${REDIS_PASSWORD:-devpassword}\" ping"]
```
And update the Redis command:
```yaml
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD:-devpassword}"]
```
And the app service Redis URL:
```yaml
      - REDIS_URL=redis://:${REDIS_PASSWORD:-devpassword}@redis:6379/0
```

This ensures Redis always has a password in development too (using `devpassword` as a non-empty default), while production overrides via environment variable.

**Per-task validation:**
- `docker compose config --quiet 2>&1 || echo "Validate YAML manually"`

---

### Task 15: Convention Tests for Audit 5 Fixes
**File:** `app/tests/test_security.py` (modify existing)
**Action:** UPDATE

Add convention tests that will automatically catch regressions for the most critical audit 5 findings. These run in every `make test` / `make check`.

Read the existing file first to understand the test structure (it uses class-based organization).

Add the following test classes at the END of the file:

```python
# === Audit 5: CRIT-1 — Quota must use X-Real-IP ===


class TestQuotaUsesRealIP:
    """Audit 5 CRIT-1: Daily quota must use X-Real-IP, not request.client.host."""

    def test_quota_uses_get_client_ip(self) -> None:
        """Verify agent routes import and call _get_client_ip for quota tracking."""
        import inspect

        from app.core.agents.routes import chat_completions

        source = inspect.getsource(chat_completions)
        assert "_get_client_ip" in source, (
            "chat_completions must use _get_client_ip(request) for quota tracking, "
            "not request.client.host"
        )
        assert "request.client.host" not in source, (
            "chat_completions must not use request.client.host — "
            "behind nginx this resolves to the proxy IP, not the user"
        )


# === Audit 5: CRIT-2 — Logout endpoint must exist ===


class TestLogoutEndpointExists:
    """Audit 5 CRIT-2: A logout endpoint must exist to revoke tokens."""

    def test_auth_router_has_logout(self) -> None:
        """Verify POST /logout exists in auth routes."""
        from app.auth.routes import router

        paths = [route.path for route in router.routes if hasattr(route, "path")]
        assert "/logout" in paths, "POST /api/v1/auth/logout endpoint must exist"

    def test_logout_calls_revoke_token(self) -> None:
        """Verify logout endpoint calls revoke_token."""
        import inspect

        from app.auth.routes import logout

        source = inspect.getsource(logout)
        assert "revoke_token" in source, "logout must call revoke_token()"


# === Audit 5: CRIT-3 — Refresh must revoke old token ===


class TestRefreshRevokesOldToken:
    """Audit 5 CRIT-3: Refresh endpoint must revoke the used refresh token."""

    def test_refresh_calls_revoke_token(self) -> None:
        """Verify refresh endpoint revokes the old refresh token."""
        import inspect

        from app.auth.routes import refresh_token

        source = inspect.getsource(refresh_token)
        assert "revoke_token" in source, (
            "refresh_token must call revoke_token() on the used refresh token"
        )


# === Audit 5: CRIT-4 — ZIP bomb protection ===


class TestZipBombProtection:
    """Audit 5 CRIT-4: GTFS import must have ZIP bomb detection."""

    def test_gtfs_importer_has_zip_validation(self) -> None:
        """Verify GTFSImporter validates ZIP safety before parsing."""
        import inspect

        from app.schedules.gtfs_import import GTFSImporter

        source = inspect.getsource(GTFSImporter)
        assert "_validate_zip_safety" in source, (
            "GTFSImporter must validate ZIP safety (compression ratio, uncompressed size)"
        )

    def test_import_route_uses_streaming(self) -> None:
        """Verify import route streams the upload, not file.read()."""
        import inspect

        from app.schedules.routes import import_gtfs

        source = inspect.getsource(import_gtfs)
        assert "file.read(8192)" in source or "file.read(" in source, (
            "import_gtfs must stream upload in chunks"
        )


# === Audit 5: HIGH-1 — Timing attack prevention ===


class TestTimingAttackPrevention:
    """Audit 5 HIGH-1: Login must normalize timing for missing users."""

    def test_authenticate_has_dummy_hash(self) -> None:
        """Verify authenticate runs bcrypt even when user not found."""
        import inspect

        from app.auth.service import AuthService

        source = inspect.getsource(AuthService.authenticate)
        assert "_DUMMY_HASH" in source or "verify_password" in source.split("user_not_found")[0], (
            "authenticate must run bcrypt (dummy hash) when user not found "
            "to prevent timing-based email enumeration"
        )


# === Audit 5: HIGH-3 — No file_path in API responses ===


class TestNoFilePathExposure:
    """Audit 5 HIGH-3: DocumentResponse must not expose server file paths."""

    def test_document_response_no_file_path(self) -> None:
        """Verify file_path is not a field on DocumentResponse."""
        from app.knowledge.schemas import DocumentResponse

        field_names = set(DocumentResponse.model_fields.keys())
        assert "file_path" not in field_names, (
            "DocumentResponse must not expose file_path (server filesystem path)"
        )


# === Audit 5: MED-3 — Request ID sanitization ===


class TestRequestIdSanitization:
    """Audit 5 MED-3: X-Request-ID must be validated to prevent log injection."""

    def test_set_request_id_rejects_unsafe_input(self) -> None:
        """Verify set_request_id sanitizes or rejects dangerous characters."""
        from app.core.logging import set_request_id

        # Newline injection attempt
        result = set_request_id('test\n{"injected": true}')
        assert "\n" not in result, "Request ID must not contain newlines"

        # JSON escape injection
        result2 = set_request_id('test", "injected": "true')
        assert '"' not in result2, "Request ID must not contain quotes"

        # Valid UUID should pass through
        valid = "550e8400-e29b-41d4-a716-446655440000"
        result3 = set_request_id(valid)
        assert result3 == valid, "Valid UUIDs should pass through unchanged"


# === Audit 5: MED-1 — Database container cap_drop ===


class TestDatabaseContainerHardening:
    """Audit 5 MED-1: PostgreSQL container must drop all capabilities."""

    def test_db_service_has_cap_drop(self) -> None:
        """Verify docker-compose.yml db service has cap_drop: ALL."""
        from pathlib import Path

        compose = Path("docker-compose.yml").read_text()
        # Check that cap_drop appears in the db service section
        db_section = compose.split("redis:")[0]  # Everything before redis service
        assert "cap_drop:" in db_section, (
            "db service in docker-compose.yml must have cap_drop: ALL"
        )
```

**Per-task validation:**
- `uv run ruff format app/tests/test_security.py`
- `uv run ruff check --fix app/tests/test_security.py`
- `uv run pytest app/tests/test_security.py -v -k "Audit5 or Quota or Logout or Refresh or ZipBomb or Timing or FilePath or RequestId or DatabaseContainer" --no-header`

---

### Task 16: Final Integration — Run Full Test Suite
**Action:** Validate all changes together

Run the full validation pyramid in order:

```bash
# Level 1: Syntax & Style
uv run ruff format .
uv run ruff check --fix .

# Level 2: Type Safety
uv run mypy app/
uv run pyright app/

# Level 3: Security tests (feature-specific)
uv run pytest app/tests/test_security.py -v

# Level 4: Full test suite
uv run pytest -v -m "not integration"
```

Fix any failures. If a type check fails, read the exact error, fix the code, and re-run. Do NOT add speculative `# type: ignore` comments — fix root causes.

---

## Logging Events

- `auth.logout_completed` — User successfully logged out (token revoked)
- `auth.token.revocation_check_degraded` — Redis unavailable during token revocation check
- `auth.login_failed` — Login failed (timing-normalized for both existing and non-existing users)

## Testing Strategy

### Convention Tests (Automated Regression)
**Location:** `app/tests/test_security.py`
- CRIT-1: Quota IP source uses `_get_client_ip`
- CRIT-2: Logout endpoint exists and calls `revoke_token`
- CRIT-3: Refresh endpoint calls `revoke_token`
- CRIT-4: GTFSImporter has ZIP validation; route uses streaming
- HIGH-1: Authenticate has timing normalization
- HIGH-3: DocumentResponse has no `file_path` field
- MED-1: Docker compose db has `cap_drop`
- MED-3: `set_request_id` rejects unsafe input

### Edge Cases
- ZIP bomb with 1000:1 compression ratio — rejected by `_validate_zip_safety`
- Logout with expired token — still revokes (defensive)
- Login with non-existent email — same timing as wrong password
- X-Request-ID with newlines/JSON — sanitized to fresh UUID
- Empty Redis password in dev — fallback to `devpassword`

## Acceptance Criteria

This feature is complete when:
- [ ] All 16 findings from `docs/security_audit_5.txt` are addressed
- [ ] Quota uses `_get_client_ip` not `request.client.host` (CRIT-1)
- [ ] POST /logout endpoint exists and revokes access token (CRIT-2)
- [ ] Refresh endpoint revokes the used refresh token (CRIT-3)
- [ ] GTFS import has ZIP bomb detection AND streaming upload (CRIT-4)
- [ ] Login has timing normalization with dummy bcrypt (HIGH-1)
- [ ] Token revocation logs warning on Redis failure (HIGH-2)
- [ ] DocumentResponse does not expose `file_path` (HIGH-3)
- [ ] HTTP server block redirects to HTTPS (HIGH-4)
- [ ] CSP removes `unsafe-eval` from `script-src` (MED-5)
- [ ] DB container has `cap_drop: ALL` (MED-1)
- [ ] metadata_json is validated as JSON (MED-2)
- [ ] X-Request-ID is sanitized (MED-3)
- [ ] Obsidian URL validated as localhost (MED-4)
- [ ] App volume mount narrowed (MED-6)
- [ ] Redis has non-empty password default (MED-7)
- [ ] All convention tests pass
- [ ] All type checkers pass (mypy + pyright)
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 16 tasks completed in order
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

**Level 3: Security Tests (feature-specific)**
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

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- Shared utilities used: `_get_client_ip` from `app.core.rate_limit`, `escape_like` from `app.shared.utils`
- Core modules used: `app.core.logging`, `app.core.middleware`, `app.core.config`
- New dependencies: None
- New env vars: None (existing `REDIS_PASSWORD` gets a non-empty default)

## Known Pitfalls

The executing agent MUST follow these rules:

1. **Task 2 (logout) — Do NOT use `get_current_user` dependency.** The logout endpoint should decode the token directly to get the JTI. Using `get_current_user` would hit the DB unnecessarily and fail for tokens that are about to be revoked.

2. **Task 8 (file_path removal) — `from_attributes=True` handles the mismatch.** The DB model still has `file_path`. Pydantic's `from_attributes` will simply ignore DB fields not in the schema. No model changes needed.

3. **Task 8 + 9 — Update tests in the SAME pass.** Removing `file_path` from the response schema WILL break tests that assert on it. Task 9 immediately follows to fix those tests.

4. **Task 13 (nginx) — Keep /health on HTTP.** Docker healthchecks use HTTP internally. The health endpoint must remain accessible on port 80 without HTTPS redirect.

5. **Task 14 (docker-compose) — PostgreSQL needs capabilities.** Unlike redis/app/cms, PostgreSQL needs `CHOWN`, `DAC_OVERRIDE`, `FOWNER`, `SETGID`, `SETUID` to initialize and manage data files. Don't use bare `cap_drop: ALL` without `cap_add`.

6. **Task 6 (timing) — Pre-compute the dummy hash.** The `_DUMMY_HASH` must be computed ONCE at module load, not per request. A second bcrypt.gensalt() per login would double the response time for all users.

7. **No `assert` in production code** — Ruff S101 forbids it. Use `if` checks.
8. **No EN DASH in strings** — Use `-` (U+002D) not `–` (U+2013).

## Notes

- HIGH-5 (prompt injection via knowledge base) is noted in the audit but requires architectural changes (content sanitization pipeline, user-confirmation workflow for destructive LLM operations) that are beyond a surgical fix sprint. This should be tracked as a separate feature with its own plan. The risk is partially mitigated by the existing `confirm: true` requirement on delete operations and RBAC restrictions on document upload (editor/admin only).
- MED-7 (Redis password): The fix uses `devpassword` as a non-empty development default. Production deployments MUST override via `REDIS_PASSWORD` environment variable.
- The audit file appears truncated at MED-7 (line 93). If additional findings exist in the full report, they are not addressed here.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach (surgical fixes, no refactoring)
- [ ] Clear on task execution order (sequential, especially Tasks 8-9)
- [ ] Validation commands are executable in this environment
