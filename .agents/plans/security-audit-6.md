# Security Audit 6 — Remediation Plan

**Source:** `documents/PLANNING/audit_6.txt`
**Priority:** CRITICAL — addresses 8 vulnerability categories
**Scope:** Backend only (no frontend changes)

---

## Overview

| # | Vulnerability | Severity | Files | Effort |
|---|---|---|---|---|
| 1 | Fail-Open Token Revocation | CRITICAL | `app/auth/token.py` | Small |
| 2 | Backend Port Exposure & Rate Limit Bypass | HIGH | `docker-compose.yml`, `app/core/rate_limit.py` | Small |
| 3 | IDOR — Missing RBAC on Drivers/Events/Knowledge | HIGH | `app/drivers/routes.py`, `app/events/routes.py`, `app/knowledge/routes.py` | Small |
| 4 | Prompt Injection & Agent Skill Escalation | HIGH | `app/core/agents/service.py`, `app/core/agents/tools/skills/manage_skills.py` | Medium |
| 5 | Brute Force Protection Fail-Open | CRITICAL | `app/auth/service.py` | Small |
| 6 | File Upload Content-Type Spoofing | MEDIUM | `app/knowledge/routes.py` | Small |
| 7 | Hardcoded Credentials in Source | HIGH | `app/core/config.py`, `app/auth/service.py` | Small |
| 8 | Infrastructure Misconfigurations | MEDIUM | `deps.py`, `db-backup.sh`, `app/auth/schemas.py`, `app/core/middleware.py` | Medium |

---

## Step 1: Fail-Open Token Revocation (Vuln #1)

**Problem:** `is_token_revoked()` in `app/auth/token.py:120` returns `False` when Redis is unavailable, allowing revoked tokens to pass authentication.

**Fix:** Change fail-open to fail-closed. When Redis is down, deny the request rather than silently allowing potentially revoked tokens.

**File:** `app/auth/token.py`

```python
# Line 114-120: Change from fail-open to fail-closed
except Exception:
    logger.error(
        "auth.token.revocation_check_failed",
        jti=jti,
        detail="Redis unavailable - denying request (fail-closed)",
    )
    return True  # Redis down = deny (fail-closed for security)
```

**Impact:** Users get 401 during Redis outages instead of silently bypassing revocation. This is the correct tradeoff — a brief availability hit vs. revoked tokens being honored.

**Validation:** Write a unit test that mocks Redis as unavailable and asserts `is_token_revoked()` returns `True`.

---

## Step 2: Brute Force Protection Fail-Open (Vuln #5)

**Problem:** `_check_redis_brute_force()` in `app/auth/service.py:44` returns `False` when Redis is down, allowing unlimited password guessing.

**Fix:** Fall back to the database-based lockout check which already exists (the `user.locked_until` check on line 116). The Redis check is a fast-path optimization — when it fails, the DB check still catches locked accounts. However, the issue is that *new* lockouts can't be recorded when Redis is down, so we need a DB fallback for recording attempts too.

**File:** `app/auth/service.py`

```python
# Line 42-44: Change fail-open to fail-closed + log at error level
except Exception:
    logger.error(
        "auth.redis_lockout_check_failed",
        email=email,
        detail="Redis unavailable - relying on DB lockout only",
    )
    return False  # DB lockout check (service.py:116) still catches locked users
```

**Rationale:** The DB-based `user.locked_until` check (line 116) is the second layer that still works. The real protection gap is that `_record_failed_attempt_redis` also silently fails. The DB-based `user.failed_attempts` counter (line 128-132) already handles this — it locks the account in the DB after MAX_FAILED_ATTEMPTS. So the dual-layer protection is already present; we just need to ensure logging is at `error` level so operators notice Redis outages immediately.

**Action:** Upgrade all three Redis brute-force `logger.warning` calls to `logger.error` in `_check_redis_brute_force`, `_record_failed_attempt_redis`, and `_clear_redis_brute_force`. The DB fallback is already functional.

**Validation:** Test that login still locks after 5 failed attempts when Redis is unavailable (DB path only).

---

## Step 3: Backend Port Exposure & Rate Limit Bypass (Vuln #2)

**Problem:**
- `docker-compose.yml:98` exposes backend port 8123 directly, bypassing nginx
- `docker-compose.yml:43` exposes Redis port 6379
- `rate_limit.py:33-35` trusts `X-Real-IP` header which is spoofable when accessing backend directly (bypassing nginx)

**Fix A — Docker Compose:** Create `docker-compose.prod.yml` override that removes direct port mappings. Keep dev ports in base file with security comments.

**File:** New `docker-compose.prod.yml`

```yaml
# Production overrides — removes dev port exposures
services:
  db:
    ports: !reset []
  redis:
    ports: !reset []
  app:
    ports: !reset []
    # Only expose internally to nginx
    expose:
      - "8123"
```

**Fix B — Rate Limiter:** Strip `X-Real-IP` when the request doesn't come through a trusted proxy. Use the connection's actual remote address as primary, only trust `X-Real-IP` when it comes from known proxy IPs (Docker internal network).

**File:** `app/core/rate_limit.py`

```python
import ipaddress

# Docker bridge network range (nginx → app)
_TRUSTED_PROXIES = {
    ipaddress.ip_network("172.16.0.0/12"),  # Docker default
    ipaddress.ip_network("10.0.0.0/8"),     # Docker custom
    ipaddress.ip_network("127.0.0.0/8"),    # Loopback
}

def _get_client_ip(request: Request) -> str:
    """Extract client IP, only trusting X-Real-IP from known proxies."""
    direct_ip = get_remote_address(request)
    try:
        addr = ipaddress.ip_address(direct_ip)
        if any(addr in net for net in _TRUSTED_PROXIES):
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()
    except ValueError:
        pass
    return direct_ip
```

**Validation:** Test that `X-Real-IP` is ignored when request comes from a non-proxy IP.

---

## Step 4: IDOR — Missing RBAC on Drivers/Events/Knowledge Read (Vuln #3)

**Problem:** Read endpoints for drivers, events, and knowledge use `get_current_user` (any authenticated user) instead of role-based access control.

**Current RBAC model (from auth README):**
- `admin` — full access
- `dispatcher` — operational data (drivers, events, transit)
- `editor` — content (knowledge, schedules)
- `viewer` — read-only dashboard + transit

**Fix:** Apply `require_role()` to sensitive endpoints.

**File:** `app/drivers/routes.py`
- `list_drivers` (line 38): Change `get_current_user` → `require_role("admin", "dispatcher")`
- `get_driver` (similar): Same change
- Write endpoints already use `require_role` — verify.

**File:** `app/events/routes.py`
- `list_events` (line 39): Change `get_current_user` → `require_role("admin", "dispatcher")`
- Write endpoints: Same change.

**File:** `app/knowledge/routes.py`
- Read endpoints (list, get, search): Change to `require_role("admin", "editor", "dispatcher")`
- Uploads already use `require_role("admin", "editor")` — good.

**Validation:** Test that a `viewer` role gets 403 on driver/event endpoints.

---

## Step 5: Prompt Injection & Agent Skill Escalation (Vuln #4)

**Problem:**
- User input goes directly to LLM without sanitization (`service.py:86`)
- Skills loaded into agent instructions can be poisoned by LLM-created skills (`service.py:102`)
- Agent can create persistent skills that alter future behavior (`manage_skills.py:121`)

**Fix A — Skill creation guardrails** (`manage_skills.py`):
1. Add content length limits (already have max 10000 chars in docstring, enforce in code)
2. Add content sanitization — strip system prompt injection patterns
3. Require human approval flag for skill activation (skills created by agent start as `is_active=False`)

```python
# In _create_skill(), before creating:
# 1. Enforce length limits
if len(content) > 5000:
    return json.dumps({"error": "Skill content exceeds 5000 character limit."})

# 2. Skills created by agent are inactive by default (require admin activation)
# Add is_active=False to SkillCreate or set after creation
```

**Fix B — Input sanitization** (`service.py`):
1. Strip common prompt injection patterns from user messages
2. Add message length enforcement (already 4000 char limit in schemas — verify enforcement)

```python
# Before passing to agent, sanitize:
import re
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)\s+(instructions|prompts)",
    r"you\s+are\s+now\s+(?:a|an)\s+",
    r"system\s*:\s*",
    r"<\s*system\s*>",
]

def _sanitize_prompt(text: str) -> str:
    """Log and flag potential prompt injection attempts."""
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.warning("agent.prompt_injection_detected", pattern=pattern)
            # Don't strip — just log. Blocking legitimate messages is worse.
            break
    return text
```

**Fix C — Skills instruction isolation** (`service.py`):
Add a clear delimiter between system instructions and skill content to prevent skill content from overriding system behavior.

**Validation:** Test that agent-created skills start inactive. Test injection pattern logging.

---

## Step 6: File Upload Content-Type Spoofing (Vuln #6)

**Problem:** `_detect_source_type()` in `app/knowledge/routes.py:64` trusts the client's `Content-Type` header. A malicious file could be labeled as `application/pdf` but contain executable content.

**Fix:** Add magic bytes verification for critical file types.

**File:** `app/knowledge/routes.py`

```python
# Magic bytes for common formats
_MAGIC_BYTES: dict[str, list[bytes]] = {
    "pdf": [b"%PDF"],
    "docx": [b"PK\x03\x04"],  # ZIP-based (also xlsx)
    "xlsx": [b"PK\x03\x04"],
}

async def _verify_magic_bytes(file: UploadFile, detected_type: str) -> bool:
    """Verify file content matches claimed type via magic bytes."""
    if detected_type not in _MAGIC_BYTES:
        return True  # No magic bytes check for text/image types
    header = await file.read(8)
    await file.seek(0)  # Reset for downstream processing
    return any(header.startswith(magic) for magic in _MAGIC_BYTES[detected_type])
```

Add verification call in `upload_document()` after `_detect_source_type()`:

```python
source_type = _detect_source_type(file.content_type)
if source_type == "unknown":
    raise HTTPException(...)
if not await _verify_magic_bytes(file, source_type):
    raise HTTPException(
        status_code=415,
        detail=f"File content does not match declared type: {file.content_type}",
    )
```

**Validation:** Test uploading a text file with `content_type=application/pdf` — should be rejected.

---

## Step 7: Hardcoded Credentials (Vuln #7)

**Problem:**
- Real email `linardsberzins@gmail.com` in seed data (`service.py:353`)
- Default JWT secret `CHANGE-ME-IN-PRODUCTION` (`config.py:117`)
- Default demo password `admin` (`config.py:123`)

**Fix A — Seed data** (`app/auth/service.py:352-353`):
Replace real email with placeholder.

```python
("admin@vtv.local", password, "System Admin", "admin"),
```

**Fix B — Production JWT secret enforcement** (`app/core/config.py`):
Add a startup validator that refuses to start in production with the default secret.

```python
# Add to Settings class or as a post-init check in main.py
@field_validator("jwt_secret_key")
@classmethod
def validate_jwt_secret(cls, v: str, info: Any) -> str:
    """Reject default secret in non-development environments."""
    # Can't access other fields in field_validator easily,
    # so we check env var directly
    import os
    env = os.getenv("ENVIRONMENT", "development")
    if env != "development" and v == "CHANGE-ME-IN-PRODUCTION":
        msg = "JWT_SECRET_KEY must be set to a secure value in production"
        raise ValueError(msg)
    return v
```

**Fix C — Demo password** (`app/core/config.py:123`):
The default `admin` is acceptable for development only. The seed function already checks `environment != "development"` (line 343). Add a model validator to enforce minimum complexity in non-dev environments.

**Validation:** Test that app startup fails with default JWT secret when `ENVIRONMENT=production`.

---

## Step 8: Infrastructure Misconfigurations (Vuln #8)

### 8a. SSL verification disabled (`deps.py:72`)

**Problem:** Obsidian httpx client uses `verify=False`.

**File:** `app/core/agents/tools/transit/deps.py:72`

**Fix:** This is a known tradeoff — Obsidian Local REST API uses self-signed certs. Add a config option to provide a CA cert path for production, defaulting to `verify=False` for local dev only.

```python
# In config.py, add:
obsidian_verify_ssl: bool = False  # True in production with proper cert

# In deps.py:
verify=settings.obsidian_verify_ssl,
```

### 8b. Unencrypted backups (`db-backup.sh`)

**Fix:** Add optional gpg encryption. The script already has a NOTE about this. Add an `ENCRYPT_BACKUPS` env var toggle.

**File:** `scripts/db-backup.sh` — after the gzip step:

```bash
if [ "${ENCRYPT_BACKUPS:-false}" = "true" ]; then
    gpg --batch --yes --symmetric --cipher-algo AES256 \
        --passphrase-file "${GPG_PASSPHRASE_FILE:?GPG_PASSPHRASE_FILE required}" \
        "${BACKUP_FILE}"
    rm -f "${BACKUP_FILE}"
    BACKUP_FILE="${BACKUP_FILE}.gpg"
    echo "[$(date -Iseconds)] Backup encrypted with AES-256"
fi
```

### 8c. Weak password policy (`schemas.py:25`)

**Fix:** Add special character requirement.

**File:** `app/auth/schemas.py` — add after line 33:

```python
if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
    msg = "Password must contain at least one special character"
    raise ValueError(msg)
```

### 8d. CORS credentials with potential wildcard (`middleware.py:172`)

**Current state:** `allow_origins=settings.allowed_origins` is a specific list (`["http://localhost:3000", "http://localhost:8123"]`), NOT wildcard. The CORS config is actually fine — `allow_credentials=True` with explicit origins is the correct pattern. The audit flagged "potentially wildcard" but the code uses a specific list.

**Fix:** Add a startup check that `allowed_origins` doesn't contain `*` when credentials are enabled.

```python
# In setup_middleware(), before adding CORS:
if "*" in settings.allowed_origins:
    logger.error("security.cors_wildcard_with_credentials",
                 detail="CORS wildcard (*) with credentials=True is insecure")
    # Remove wildcard, keep only specific origins
    settings_origins = [o for o in settings.allowed_origins if o != "*"]
else:
    settings_origins = settings.allowed_origins
```

**Validation:** Test that CORS rejects wildcard when credentials are enabled.

---

## Execution Order

Execute in this order (highest impact first, dependencies respected):

1. **Step 1** — Token revocation fail-closed (CRITICAL, 15 min)
2. **Step 2** — Brute force logging upgrade (CRITICAL, 10 min)
3. **Step 7** — Hardcoded credentials cleanup (HIGH, 15 min)
4. **Step 4** — RBAC on drivers/events/knowledge (HIGH, 20 min)
5. **Step 3** — Port exposure & rate limit hardening (HIGH, 25 min)
6. **Step 5** — Prompt injection guardrails (HIGH, 30 min)
7. **Step 6** — File upload magic bytes (MEDIUM, 20 min)
8. **Step 8** — Infrastructure fixes (MEDIUM, 30 min)

## Post-Implementation

- Run `make check` (lint + types + tests) after each step
- Run `make security-audit-quick` after all steps
- Update `docs/TODO.md` with security audit completion
- Commit with `fix(security): address audit 6 findings — fail-closed auth, RBAC, input validation`
