# Security Contexts — Context-Triggered Security Requirements

Derived from VTV security audit findings. Not every context applies to every feature — detect which contexts are relevant based on the feature's scope, then apply only those requirements.

## How to Use

1. **Detect** — Match the feature description and affected files against the trigger keywords/paths below
2. **List** — Note which contexts are active (usually 1-3 per feature, rarely all 6)
3. **Apply** — Add the corresponding security requirements to the plan/review

## Context Definitions

### CTX-AUTH: Authentication & Session Management

**Triggers:** Feature touches auth, tokens, login, session, password, Redis dependency, brute force, or JWT handling.
**Paths:** `app/auth/`, `app/core/middleware.py`, `app/core/config.py` (JWT settings)

**Requirements:**
- **Fail-closed on external deps** — If Redis (or any external service) is unavailable, DENY access. Never return `False` from security checks when the backing store is down. Pattern: `except RedisError: raise HTTPException(503)` not `except: return False`
- **Token revocation must be fail-closed** — If the denylist check fails, treat the token as revoked
- **Brute force protection must be fail-closed** — If lockout state can't be checked, block the attempt
- **Security logging at error+ level** — Failed auth attempts logged at `logger.error()`, not `warning` or `debug`
- **No hardcoded secrets** — JWT secrets, demo passwords must come from env vars with startup validation that rejects defaults in production

**Plan task template:**
```
- Add fail-closed error handling for all external dependency calls in auth paths
- Verify token/session checks raise on backend failure (not silently pass)
- Add startup validation for any new secrets/credentials (reject defaults when ENV != dev)
```

---

### CTX-RBAC: API Endpoint Authorization

**Triggers:** Feature adds or modifies REST endpoints, CRUD operations, or data access patterns.
**Paths:** `app/*/routes.py`, any new `routes.py` file

**Requirements:**
- **Role-level access, not just auth** — Use `require_role(["admin", "dispatcher"])` not just `get_current_user` for sensitive endpoints. Think: "who should NOT see this data?"
- **IDOR prevention** — List endpoints must scope queries to the user's authorized data. Detail endpoints must verify the requester has access to the specific resource
- **Principle of least privilege** — Default to most restrictive roles, widen only with justification
- **Rate limiting on mutation endpoints** — POST/PUT/DELETE endpoints should have rate limits
- **Convention test coverage** — `TestAllEndpointsRequireAuth` catches missing auth, but role-level granularity must be designed explicitly

**Plan task template:**
```
- Define role matrix: which roles can access each endpoint (table format)
- Use require_role() with explicit role list on every endpoint (not bare get_current_user)
- Add test cases verifying forbidden access for unauthorized roles
```

---

### CTX-FILE: File Handling & Uploads

**Triggers:** Feature handles file uploads, document ingestion, attachments, or file type detection.
**Paths:** `app/knowledge/`, any endpoint accepting `UploadFile`

**Requirements:**
- **Magic bytes validation** — Never trust `Content-Type` header alone. Read first 8+ bytes and verify against known signatures (PDF: `%PDF`, PNG: `\x89PNG`, etc.)
- **Filename sanitization** — `re.sub(r"[^\w\-.]", "_", filename)` + validate with `pathlib.Path.is_relative_to()` to prevent directory traversal
- **Size limits enforced server-side** — Streaming chunk-based limits, not just `Content-Length` header (which can be spoofed)
- **Unknown types rejected** — Return 415 Unsupported Media Type, never silently process as "text"
- **Cleanup on failure** — Delete stored files if processing fails (no orphaned uploads)

**Plan task template:**
```
- Implement magic bytes validation for all accepted file types
- Add filename sanitization with directory traversal prevention
- Add streaming size limit check (not just Content-Length)
- Add test: upload with spoofed Content-Type header is rejected
- Add test: malformed file content is rejected despite correct Content-Type
```

---

### CTX-AGENT: AI Agent & LLM Integration

**Triggers:** Feature involves agent tools, skill management, LLM prompts, or AI-generated content.
**Paths:** `app/core/agents/`, `app/skills/`, any Pydantic AI tool function

**Requirements:**
- **Prompt injection defense** — Scan user input for injection patterns (role overrides, system prompt leaks, instruction ignoring). Log warnings but don't block (reduce false positives)
- **Skill creation limits** — Agent-created skills must be inactive by default, require human activation
- **Output sanitization** — LLM-generated content displayed to users must be escaped/sanitized
- **Tool permissions** — Tools that write data must validate the operation is authorized for the current user context
- **No credential exposure** — Tool responses must never include raw credentials, tokens, or connection strings

**Plan task template:**
```
- Add prompt injection pattern scanning on user input (log + warn, don't block)
- Ensure any agent-created artifacts are inactive/draft by default
- Sanitize LLM output before storage or display
- Verify tool functions don't expose credentials in responses or logs
```

---

### CTX-INFRA: Infrastructure & Configuration

**Triggers:** Feature modifies Docker config, nginx, CORS settings, SSL/TLS, backup scripts, or environment configuration.
**Paths:** `docker-compose*.yml`, `nginx/`, `scripts/`, `app/core/config.py`, `app/core/middleware.py`

**Requirements:**
- **No hardcoded credentials** — Use `${VAR:-default}` interpolation in Docker/scripts, env vars in Python config
- **SSL verification enabled by default** — If SSL must be disabled (self-signed certs), make it configurable via env var, not hardcoded `verify=False`
- **CORS credentials + wildcard prevention** — If `allow_credentials=True`, origins MUST NOT include `*`. Add startup validation
- **Backend ports internal-only in production** — Only nginx should be exposed. Dev compose can expose ports, prod compose must not
- **Backup encryption** — Database backups must be encrypted at rest or the documentation must explicitly note the gap

**Plan task template:**
```
- Verify no hardcoded credentials in config files (use env var interpolation)
- If adding SSL connections, default to verify=True with configurable override
- If modifying CORS, add validation: credentials + wildcard origins = startup error
- If modifying Docker, verify prod compose doesn't expose internal service ports
```

---

### CTX-INPUT: User Input & Query Handling

**Triggers:** Feature accepts search queries, filter parameters, form input, or constructs database queries from user data.
**Paths:** Any endpoint with `Query()`, `Form()`, or `Path()` parameters, any LIKE/ILIKE query

**Requirements:**
- **SQL injection prevention** — Always use parameterized queries via SQLAlchemy `select()`. For LIKE/ILIKE, use `escape_like()` from `app.shared.utils`
- **Input length limits** — All string Query/Path params must have `max_length` constraint
- **Pattern validation** — Constrained string fields use `Literal[...]` types or regex `pattern` validators
- **XSS prevention** — User input stored in DB must be escaped before rendering (backend responsibility: validate input shape; frontend responsibility: escape output)
- **GTFS-specific** — Time fields validated for range (hours 0-47 for GTFS, minutes/seconds 0-59), not just format

**Plan task template:**
```
- Add max_length to all string Query/Path parameters
- Use escape_like() for any LIKE/ILIKE query construction
- Add Literal[...] types for constrained string fields (status, category, priority)
- Add input validation tests: oversized input, special characters, SQL injection attempts
```

---

## Quick Reference: Context Detection

| If the feature... | Active contexts |
|---|---|
| Adds new API endpoints | CTX-RBAC, CTX-INPUT |
| Handles file uploads | CTX-FILE, CTX-RBAC, CTX-INPUT |
| Modifies auth/login flow | CTX-AUTH, CTX-RBAC |
| Adds agent tools | CTX-AGENT, CTX-RBAC |
| Modifies Docker/nginx/config | CTX-INFRA |
| Adds search/filter features | CTX-INPUT, CTX-RBAC |
| Adds CRUD with user input | CTX-RBAC, CTX-INPUT |
| Modifies existing endpoints | CTX-RBAC (verify no regression) |
