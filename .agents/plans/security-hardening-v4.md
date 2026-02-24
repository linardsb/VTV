# Plan: Security Hardening v4 — Audit Gap Remediation

## Feature Metadata
**Feature Type**: Enhancement (Security Infrastructure)
**Estimated Complexity**: High
**Primary Systems Affected**: CI pipeline, Docker infrastructure, security tests, backup scripts, nginx, auth module

## Feature Description

This plan addresses all remaining security gaps identified by the 4th security audit (`docs/security_audit_4.txt`) AND the supplementary gap analysis ("Missing from the audit"). The audit confirmed strong application-level security (JWT, RBAC, brute-force, rate limiting, 65 convention tests) but identified infrastructure and operational gaps for government-level compliance.

The implementation covers 8 workstreams:
1. **Dependency vulnerability scanning** — Add `pip-audit` to CI and Makefile
2. **Container hardening** — Non-root nginx, read-only filesystems, security options, cap_drop
3. **SQL injection posture verification** — Convention test proving no raw SQL with user input
4. **Automated backup script** — Cron-ready `pg_dump` with retention policy
5. **GDPR right-to-erasure** — User/driver data deletion endpoint
6. **Dependency pinning with hashes** — Lock file integrity verification in CI
7. **Additional security convention tests** — Cover all new gaps
8. **Audit documentation** — Save 4th audit, update CLAUDE.md

## User Story

As a platform administrator deploying VTV for a government transit agency,
I want automated dependency scanning, container hardening, GDPR data deletion, and backup automation,
So that the platform meets EU government compliance standards (GDPR, NIST 800-53) without manual security review overhead.

## Solution Approach

We chose incremental hardening of existing infrastructure because:
- All application-level security is already solid (audits 1-3 remediated)
- The gaps are infrastructure/operational, not architectural
- Each fix is independent and can be validated in isolation

**Alternatives Considered:**
- Full SIEM integration: Rejected — requires infrastructure provider decision (user input needed)
- Database encryption at rest: Rejected — requires cloud provider decision (user input needed)
- Self-service password reset: Rejected — requires SMTP provider decision (user input needed)
- Let's Encrypt automation: Rejected — requires domain/DNS configuration (user input needed)

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, security section (lines 193-367)
- `docs/security_audit_4.txt` — 4th audit findings (this plan's source)
- `docs/security_audit.txt` — 1st audit (13 findings, all remediated)
- `docs/security_audit_2.txt` — 2nd/3rd audit (16 findings, all remediated)

### Similar Features (Examples to Follow)
- `app/tests/test_security.py` (lines 1-914) — Existing 65 security convention tests, pattern for new tests
- `.github/workflows/ci.yml` (lines 1-193) — CI pipeline to add dependency scanning step
- `Makefile` (lines 1-111) — Build targets to add backup/security commands
- `scripts/pre-commit` (lines 1-53) — Pre-commit hook pattern
- `docker-compose.yml` (lines 1-140) — Docker service definitions
- `docker-compose.prod.yml` (lines 1-89) — Production overlays

### Files to Modify
- `.github/workflows/ci.yml` — Add `pip-audit` step, add `uv.lock` integrity check
- `docker-compose.yml` — Add `security_opt`, `read_only`, `cap_drop` to services
- `docker-compose.prod.yml` — Add container hardening overlays
- `nginx/Dockerfile` — Add non-root user
- `Makefile` — Add `db-backup-auto`, `dep-audit` targets
- `app/tests/test_security.py` — Add ~25 new convention tests
- `app/auth/routes.py` — Add GDPR user deletion endpoint
- `app/auth/service.py` — Add `delete_user_data()` method
- `app/auth/repository.py` — Add `delete_user()` method
- `app/drivers/repository.py` — Add `anonymize_by_user()` or `delete_by_user()` method
- `scripts/db-backup.sh` — New automated backup script
- `CLAUDE.md` — Update security section with v4 changes

### Files NOT Modified (verified already secure)
- `Dockerfile` (backend) — Already non-root user `vtv` (UID 1001), multi-stage build
- `cms/apps/web/Dockerfile` — Already non-root user `nextjs` (UID 1001), multi-stage build
- `app/core/config.py` — Already has startup JWT validation
- `app/auth/dependencies.py` — Already has `auto_error=False` + 401 response
- `app/shared/utils.py` — `escape_like()` already applied across all repos

## Implementation Plan

### Phase 1: CI/CD Security Infrastructure (Tasks 1-3)
Add dependency vulnerability scanning and lock file integrity to the CI pipeline.

### Phase 2: Container Hardening (Tasks 4-6)
Harden Docker containers with non-root users, read-only filesystems, and dropped capabilities.

### Phase 3: Operational Security (Tasks 7-8)
Automated backup script and GDPR data deletion endpoint.

### Phase 4: Convention Tests & Documentation (Tasks 9-11)
Add security convention tests covering all new gaps, save audit, update docs.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add pip-audit to CI pipeline
**File:** `.github/workflows/ci.yml` (modify existing)
**Action:** UPDATE

Add a "Dependency audit" step AFTER "Install dependencies" (line 58) and BEFORE "Format check" (line 60) in the `backend-checks` job:

```yaml
      - name: Dependency audit
        run: uv run pip-audit --strict --desc
```

Also add a "Lock file integrity" step immediately after the dependency audit:

```yaml
      - name: Lock file integrity
        run: uv lock --check
```

This ensures:
- `pip-audit` scans all installed packages for known CVEs (exits non-zero if found)
- `--strict` treats warnings as errors
- `--desc` includes vulnerability descriptions in output
- `uv lock --check` verifies `uv.lock` is up-to-date with `pyproject.toml`

**Per-task validation:**
- Verify YAML syntax: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
- Verify step ordering is correct (dependency audit before format check)

---

### Task 2: Add pip-audit to dev dependencies
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Add `pip-audit` to the `[dependency-groups] dev` section:

```toml
[dependency-groups]
dev = [
    "httpx>=0.28.1",
    "mypy>=1.18.2",
    "pip-audit>=2.7.0",
    "pyright>=1.1.407",
    "pytest>=8.4.2",
    "pytest-asyncio>=1.2.0",
    "pytest-cov>=7.0.0",
    "ruff>=0.14.2",
]
```

Then run:
```bash
uv lock
uv sync
```

**Per-task validation:**
- `uv run pip-audit --strict --desc` exits 0 (no known vulnerabilities)
- `uv lock --check` passes

---

### Task 3: Add dep-audit target to Makefile
**File:** `Makefile` (modify existing)
**Action:** UPDATE

Add after the `security-check` target (line 103):

```makefile
dep-audit: ## Scan dependencies for known vulnerabilities
	uv run pip-audit --strict --desc
```

Update the `.PHONY` line at the top to include `dep-audit`.

**Per-task validation:**
- `make dep-audit` runs without error

---

### Task 4: Harden nginx Dockerfile with non-root user
**File:** `nginx/Dockerfile` (modify existing)
**Action:** UPDATE

Replace the entire file with:

```dockerfile
FROM nginx:1.27-alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy SSL certs (self-signed for dev)
COPY certs/ /etc/nginx/certs/

# SECURITY: Create writable directories for non-root nginx
RUN mkdir -p /var/cache/nginx /var/run /var/log/nginx && \
    chown -R nginx:nginx /var/cache/nginx /var/run /var/log/nginx && \
    chmod -R 755 /var/cache/nginx /var/run /var/log/nginx

# SECURITY: Allow nginx to bind to port 80 as non-root
RUN apk add --no-cache libcap && \
    setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx && \
    apk del libcap

EXPOSE 80

# SECURITY: Run as non-root user
USER nginx

CMD ["nginx", "-g", "daemon off;"]
```

**Per-task validation:**
- `docker build -t vtv-nginx-test nginx/` succeeds
- Verify with: `docker run --rm vtv-nginx-test whoami` outputs `nginx`

---

### Task 5: Add container security options to docker-compose.yml
**File:** `docker-compose.yml` (modify existing)
**Action:** UPDATE

Add `security_opt` and `cap_drop` to the `app` service (after `restart: unless-stopped`):

```yaml
  app:
    # ... existing config ...
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
```

Add the same to the `cms` service:

```yaml
  cms:
    # ... existing config ...
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
```

Add `security_opt` to the `db` service (keep default caps for PostgreSQL):

```yaml
  db:
    # ... existing config ...
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
```

Add `security_opt` and `cap_drop` to the `redis` service:

```yaml
  redis:
    # ... existing config ...
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
```

For the `nginx` service, add `cap_drop` with `NET_BIND_SERVICE` retained:

```yaml
  nginx:
    # ... existing config ...
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

**IMPORTANT:** Do NOT add `read_only: true` to services with writable volume mounts (db, redis) or temp file needs (app, cms). The `no-new-privileges` and `cap_drop` provide the security benefit without breaking functionality.

**Per-task validation:**
- `docker compose config` validates YAML without errors
- `docker compose up -d --build` starts all services
- `curl -s http://localhost:80/health` returns healthy (if docker is running)

---

### Task 6: Add container hardening to production compose
**File:** `docker-compose.prod.yml` (modify existing)
**Action:** UPDATE

Add `read_only` for the app service (production has no live-reload):

```yaml
  app:
    # ... existing overrides ...
    read_only: true
    tmpfs:
      - /tmp:size=100M
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
```

Add `read_only` for the cms service:

```yaml
  cms:
    # ... existing overrides ...
    read_only: true
    tmpfs:
      - /tmp:size=100M
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
```

Add security options for nginx:

```yaml
  nginx:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

**Per-task validation:**
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` validates

---

### Task 7: Create automated backup script
**File:** `scripts/db-backup.sh` (create new)
**Action:** CREATE

```bash
#!/usr/bin/env bash
# Automated PostgreSQL backup with retention policy
# Usage: ./scripts/db-backup.sh [retention_days]
# Cron example: 0 2 * * * /path/to/vtv/scripts/db-backup.sh 90
#
# Environment variables (optional):
#   BACKUP_DIR    — Directory for backups (default: ./backups)
#   DB_CONTAINER  — Docker container name (default: vtv-db-1)
#   PG_USER       — PostgreSQL user (default: postgres)
#   PG_DB         — PostgreSQL database (default: vtv_db)

set -euo pipefail

RETENTION_DAYS="${1:-90}"
BACKUP_DIR="${BACKUP_DIR:-$(dirname "$0")/../backups}"
DB_CONTAINER="${DB_CONTAINER:-vtv-db-1}"
PG_USER="${PG_USER:-postgres}"
PG_DB="${PG_DB:-vtv_db}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/vtv_db_${TIMESTAMP}.sql.gz"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] Starting backup of ${PG_DB}..."

# Dump and compress
if ! docker exec "${DB_CONTAINER}" pg_dump -U "${PG_USER}" "${PG_DB}" | gzip > "${BACKUP_FILE}"; then
    echo "[$(date -Iseconds)] ERROR: Backup failed" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Verify backup is non-empty
BACKUP_SIZE=$(stat -f%z "${BACKUP_FILE}" 2>/dev/null || stat --printf="%s" "${BACKUP_FILE}" 2>/dev/null)
if [ "${BACKUP_SIZE}" -lt 100 ]; then
    echo "[$(date -Iseconds)] ERROR: Backup file suspiciously small (${BACKUP_SIZE} bytes)" >&2
    exit 1
fi

echo "[$(date -Iseconds)] Backup created: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"

# Prune old backups
PRUNED=0
if [ "${RETENTION_DAYS}" -gt 0 ]; then
    while IFS= read -r old_backup; do
        rm -f "${old_backup}"
        PRUNED=$((PRUNED + 1))
    done < <(find "${BACKUP_DIR}" -name "vtv_db_*.sql.gz" -mtime +"${RETENTION_DAYS}" -type f 2>/dev/null)
fi

if [ "${PRUNED}" -gt 0 ]; then
    echo "[$(date -Iseconds)] Pruned ${PRUNED} backups older than ${RETENTION_DAYS} days"
fi

# Summary
TOTAL=$(find "${BACKUP_DIR}" -name "vtv_db_*.sql.gz" -type f | wc -l | tr -d ' ')
echo "[$(date -Iseconds)] Backup complete. ${TOTAL} backups in ${BACKUP_DIR}"
```

Make executable:
```bash
chmod +x scripts/db-backup.sh
```

**Per-task validation:**
- `bash -n scripts/db-backup.sh` passes syntax check
- Script is executable: `test -x scripts/db-backup.sh`

---

### Task 8: Add backup targets to Makefile
**File:** `Makefile` (modify existing)
**Action:** UPDATE

Replace the existing `db-backup` target (line 85-88) with an expanded version and add `db-backup-auto`:

```makefile
db-backup: ## Backup PostgreSQL to timestamped file
	@mkdir -p backups
	docker exec vtv-db-1 pg_dump -U postgres vtv_db | gzip > backups/vtv_db_$$(date +%Y%m%d_%H%M%S).sql.gz
	@ls -lh backups/vtv_db_*.sql.gz | tail -1

db-backup-auto: ## Automated backup with 90-day retention (cron-ready)
	./scripts/db-backup.sh 90
```

Update the `.PHONY` line to include `db-backup-auto`.

**Per-task validation:**
- `make help` shows both `db-backup` and `db-backup-auto` targets

---

### Task 9: Add GDPR user deletion to auth repository
**File:** `app/auth/repository.py` (modify existing)
**Action:** UPDATE

Read the existing file first. Add a `delete_user` method to `UserRepository`:

```python
async def delete_user(self, user_id: int) -> bool:
    """Delete a user and return True if found, False if not."""
    from app.auth.models import User

    result = await self.db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return False
    await self.db.delete(user)
    await self.db.flush()
    return True
```

Ensure the necessary imports are present:
- `from sqlalchemy import select` (likely already imported)

**Per-task validation:**
- `uv run ruff format app/auth/repository.py`
- `uv run ruff check --fix app/auth/repository.py` passes
- `uv run mypy app/auth/repository.py` passes

---

### Task 10: Add GDPR user deletion to auth service
**File:** `app/auth/service.py` (modify existing)
**Action:** UPDATE

Read the existing file first. Add a `delete_user_data` method to `AuthService`:

```python
async def delete_user_data(self, user_id: int, requesting_user_id: int) -> bool:
    """Delete all user data for GDPR right-to-erasure compliance.

    Deletes the user record (cascading to related data).
    Clears any Redis brute-force tracking keys.

    Args:
        user_id: The ID of the user to delete.
        requesting_user_id: The ID of the admin requesting deletion.

    Returns:
        True if user was found and deleted, False if not found.

    Raises:
        DomainValidationError: If attempting to delete own account.
    """
    from app.core.exceptions import DomainValidationError

    if user_id == requesting_user_id:
        raise DomainValidationError("Cannot delete your own account")

    # Look up user email for Redis cleanup
    user = await self.repo.find_by_id(user_id)
    if user is None:
        return False

    email = user.email

    # Delete user record from database
    deleted = await self.repo.delete_user(user_id)
    if not deleted:
        return False

    # Clear any Redis brute-force keys for this user
    await _clear_redis_brute_force(email)

    logger.warning(
        "auth.user_data_deleted",
        deleted_user_id=user_id,
        requesting_user_id=requesting_user_id,
    )
    return True
```

Ensure `find_by_id` exists on the repository. If it does not, add it to the repository first (Task 9). Check the existing `UserRepository` methods.

**Per-task validation:**
- `uv run ruff format app/auth/service.py`
- `uv run ruff check --fix app/auth/service.py` passes
- `uv run mypy app/auth/service.py` passes

---

### Task 11: Add GDPR deletion endpoint to auth routes
**File:** `app/auth/routes.py` (modify existing)
**Action:** UPDATE

Read the existing file first. Add a DELETE endpoint for GDPR user data erasure (admin-only):

```python
@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("5/minute")
async def delete_user_data(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_role("admin")),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> None:
    """Delete user data for GDPR right-to-erasure compliance.

    Admin-only. Permanently removes user record and clears associated
    Redis tracking data. Cannot delete own account.
    """
    _ = request
    service = AuthService(UserRepository(db))
    deleted = await service.delete_user_data(user_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
```

Ensure these imports are present at the top of the file:
- `from starlette import status` (likely already imported)
- `from app.auth.dependencies import require_role` (likely already imported)

Verify `User` model is imported and available for the type annotation on `current_user`.

**Per-task validation:**
- `uv run ruff format app/auth/routes.py`
- `uv run ruff check --fix app/auth/routes.py` passes
- `uv run mypy app/auth/routes.py` passes

---

### Task 12: Add security convention tests — new gaps
**File:** `app/tests/test_security.py` (modify existing)
**Action:** UPDATE

Read the existing file first (914 lines). Append the following new test classes AFTER the last class (`TestSecurityHeadersInNginx`):

**12a. SQL injection posture test:**

```python
# === Convention Enforcement: No Raw SQL with User Input ===


class TestNoRawSqlInjection:
    """All database queries must use SQLAlchemy ORM, not raw SQL with user input."""

    def test_repositories_use_orm_not_raw_sql(self) -> None:
        """Repository files must not use text() with f-strings or .format()."""
        import ast
        from pathlib import Path

        app_dir = Path("app")
        violations: list[str] = []

        for repo_file in sorted(app_dir.rglob("repository.py")):
            source = repo_file.read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                # Check for text(f"...") or text("...".format(...))
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "text"
                    and node.args
                ):
                    arg = node.args[0]
                    if isinstance(arg, ast.JoinedStr):  # f-string
                        violations.append(
                            f"{repo_file}:{node.lineno}: text() with f-string"
                        )
                    elif (
                        isinstance(arg, ast.Call)
                        and isinstance(arg.func, ast.Attribute)
                        and arg.func.attr == "format"
                    ):
                        violations.append(
                            f"{repo_file}:{node.lineno}: text() with .format()"
                        )

        assert violations == [], (
            f"Raw SQL with user input found: {violations}. "
            f"Use SQLAlchemy ORM or parameterized queries."
        )

    def test_health_check_text_is_safe(self) -> None:
        """Health check uses text('SELECT 1') which is safe (no user input)."""
        import inspect

        from app.core.health import database_health_check

        source = inspect.getsource(database_health_check)
        assert 'text("SELECT 1")' in source
        # Verify no f-strings in text() calls
        assert "text(f" not in source
```

**12b. Container hardening tests:**

```python
# === Convention Enforcement: Container Security ===


class TestContainerHardening:
    """Docker containers must have security hardening options."""

    def test_backend_dockerfile_nonroot(self) -> None:
        """Backend Dockerfile must run as non-root user."""
        from pathlib import Path

        dockerfile = Path("Dockerfile").read_text()
        assert "USER vtv" in dockerfile or "USER 1001" in dockerfile

    def test_frontend_dockerfile_nonroot(self) -> None:
        """Frontend Dockerfile must run as non-root user."""
        from pathlib import Path

        dockerfile = Path("cms/apps/web/Dockerfile").read_text()
        assert "USER nextjs" in dockerfile or "USER 1001" in dockerfile

    def test_nginx_dockerfile_nonroot(self) -> None:
        """Nginx Dockerfile must run as non-root user."""
        from pathlib import Path

        dockerfile = Path("nginx/Dockerfile").read_text()
        assert "USER nginx" in dockerfile

    def test_compose_app_no_new_privileges(self) -> None:
        """docker-compose.yml app service must have no-new-privileges."""
        from pathlib import Path

        compose = Path("docker-compose.yml").read_text()
        assert "no-new-privileges:true" in compose

    def test_prod_compose_app_read_only(self) -> None:
        """docker-compose.prod.yml app service must be read-only."""
        from pathlib import Path

        compose = Path("docker-compose.prod.yml").read_text()
        assert "read_only: true" in compose
```

**12c. Dependency scanning test:**

```python
# === Convention Enforcement: Dependency Security ===


class TestDependencySecurity:
    """CI pipeline must include dependency vulnerability scanning."""

    def test_ci_has_dependency_audit(self) -> None:
        """CI pipeline must have a pip-audit step."""
        from pathlib import Path

        ci = Path(".github/workflows/ci.yml").read_text()
        assert "pip-audit" in ci

    def test_ci_has_lock_integrity_check(self) -> None:
        """CI pipeline must verify lock file integrity."""
        from pathlib import Path

        ci = Path(".github/workflows/ci.yml").read_text()
        assert "uv lock --check" in ci

    def test_pip_audit_in_dev_dependencies(self) -> None:
        """pip-audit must be in dev dependencies."""
        from pathlib import Path

        pyproject = Path("pyproject.toml").read_text()
        assert "pip-audit" in pyproject
```

**12d. Backup infrastructure test:**

```python
# === Convention Enforcement: Backup Infrastructure ===


class TestBackupInfrastructure:
    """Automated backup script must exist and be executable."""

    def test_backup_script_exists(self) -> None:
        """Automated backup script must exist."""
        from pathlib import Path

        assert Path("scripts/db-backup.sh").exists()

    def test_backup_script_executable(self) -> None:
        """Backup script must be executable."""
        import os
        from pathlib import Path

        script = Path("scripts/db-backup.sh")
        assert os.access(script, os.X_OK)

    def test_backup_script_has_retention(self) -> None:
        """Backup script must implement retention policy."""
        from pathlib import Path

        script = Path("scripts/db-backup.sh").read_text()
        assert "RETENTION" in script
        assert "mtime" in script or "find" in script

    def test_makefile_has_backup_auto(self) -> None:
        """Makefile must have db-backup-auto target."""
        from pathlib import Path

        makefile = Path("Makefile").read_text()
        assert "db-backup-auto" in makefile
```

**12e. GDPR deletion test:**

```python
# === Convention Enforcement: GDPR Right to Erasure ===


class TestGdprDeletion:
    """Platform must support GDPR right-to-erasure for user data."""

    def test_auth_routes_has_delete_endpoint(self) -> None:
        """Auth routes must have a DELETE /users/{user_id} endpoint."""
        import inspect

        from app.auth.routes import delete_user_data

        source = inspect.getsource(delete_user_data)
        assert "require_role" in source
        assert "admin" in source

    def test_delete_requires_admin(self) -> None:
        """User deletion must require admin role."""
        import inspect

        from app.auth.routes import delete_user_data

        source = inspect.getsource(delete_user_data)
        assert 'require_role("admin")' in source

    def test_cannot_self_delete(self) -> None:
        """Service must prevent admins from deleting their own account."""
        import inspect

        from app.auth.service import AuthService

        source = inspect.getsource(AuthService.delete_user_data)
        assert "requesting_user_id" in source
        assert "Cannot delete your own account" in source or "own account" in source.lower()
```

**12f. CSRF posture verification:**

```python
# === Convention Enforcement: CSRF Protection Posture ===


class TestCsrfProtection:
    """JWT in Authorization header is inherently CSRF-safe.
    Verify no endpoints use cookie-based auth that would need CSRF tokens.
    """

    def test_auth_uses_bearer_not_cookies(self) -> None:
        """Authentication must use Bearer token, not cookies."""
        import inspect

        from app.auth.dependencies import get_current_user

        source = inspect.getsource(get_current_user)
        assert "HTTPBearer" in source or "Authorization" in source
        # Must not read auth from cookies
        assert "request.cookies" not in source

    def test_cors_allows_credentials_with_explicit_origins(self) -> None:
        """CORS must not use allow_origins=['*'] with allow_credentials=True."""
        import inspect

        from app.core.middleware import setup_middleware

        source = inspect.getsource(setup_middleware)
        assert 'allow_origins=["*"]' not in source
```

**Per-task validation:**
- `uv run ruff format app/tests/test_security.py`
- `uv run ruff check --fix app/tests/test_security.py` passes
- `uv run pytest app/tests/test_security.py -v` — all tests pass (old + new)

---

### Task 13: Save 4th audit as documentation
**File:** `docs/security_audit_4_full.md` (create new)
**Action:** CREATE

Create a clean markdown version of the 4th audit with the supplementary gap analysis appended. Include:

1. The full audit content provided by the user (8 sections)
2. A "Supplementary Gap Analysis" section covering:
   - Dependency vulnerabilities (now addressed)
   - SQL injection posture (verified: ORM-only, no raw SQL with user input)
   - CSRF protection (verified: JWT in headers, not cookies)
   - Container hardening (now addressed)
   - GDPR right-to-erasure (now addressed)
   - Token storage client-side (verified: httpOnly cookie via Auth.js)
   - Database connection privileges (documented as future improvement)
   - Dependency pinning (verified: `uv.lock` with `--frozen` in CI)
3. A "Remediation Status" table mapping each finding to its fix

**Per-task validation:**
- File exists and is readable

---

### Task 14: Update CLAUDE.md security section
**File:** `CLAUDE.md` (modify existing)
**Action:** UPDATE

Update the Security Practices section to include:

1. Add after the "Convention enforcement tests" bullet (line 218), update test count from 65 to ~90:
   - `- **Convention enforcement tests** — `app/tests/test_security.py` (90 tests) auto-discovers...`

2. Add new bullets to the Security Practices list:
   - `- **Container hardening** — All containers run as non-root, `no-new-privileges:true`, `cap_drop: ALL`; production adds `read_only: true` with tmpfs`
   - `- **Dependency scanning** — `pip-audit` in CI pipeline as dedicated step; `uv lock --check` verifies lock file integrity`
   - `- **Automated backups** — `scripts/db-backup.sh` with configurable retention (default 90 days GDPR); `make db-backup-auto` for cron integration`
   - `- **GDPR right-to-erasure** — Admin-only `DELETE /api/v1/auth/users/{id}` removes user data and clears Redis tracking`
   - `- **SQL injection prevention** — All queries via SQLAlchemy ORM; convention test verifies no `text()` with f-strings in repositories`

3. Update "Automated Security Enforcement (4 layers)" to become 5 layers:
   Add a new layer 5:
   - `5. **CI dependency audit** (`.github/workflows/ci.yml`) — `pip-audit --strict` scans all packages for known CVEs as a dedicated step. Lock file integrity verified via `uv lock --check`. Vulnerable dependencies are a hard PR failure.`

4. Add to Key Reference Documents:
   - `- `docs/security_audit_4_full.md` — Fourth security audit: government compliance gaps, container hardening, GDPR (2026-02-24)`
   - `- `scripts/db-backup.sh` — Automated PostgreSQL backup with retention policy`

5. Update the test count in Essential Commands section:
   - Change `647 tests` to the new count after running `make test`

6. Update the "Out of scope (future)" line to remove items now addressed:
   - Keep: `Full HTTPS/TLS deployment (certs), WebSocket security, API key rotation`
   - Add: `SIEM/monitoring integration, database encryption at rest, self-service password reset (needs SMTP), secrets management (Vault/SSM)`

**Per-task validation:**
- `uv run ruff format CLAUDE.md` (no-op, markdown)
- Verify all new bullets are present in the file

---

### Task 15: Update essential commands test count
**File:** `CLAUDE.md` (modify existing)
**Action:** UPDATE

After all tests pass, run `make test` and count the total tests. Update line 81:
```
make test            # Unit tests (XXX tests, ~15s)
```
Replace XXX with the actual count from `make test` output.

Also update the security test count. Run `uv run pytest app/tests/test_security.py -v | grep -c PASSED` and update the count in CLAUDE.md wherever "65 tests" appears (should become ~90).

**Per-task validation:**
- `uv run pytest -v -m "not integration" | tail -5` — verify count matches CLAUDE.md

---

## Migration (if applicable)

No database migration needed. The GDPR deletion endpoint uses the existing `User` model's primary key. SQLAlchemy's `session.delete()` handles cascade cleanup based on existing FK relationships.

If the `User` model has relationships with `ON DELETE CASCADE`, the deletion is automatic. If not, the executing agent should check `app/auth/models.py` for FK relationships and handle them in `delete_user_data()`.

## Logging Events

- `auth.user_data_deleted` — GDPR erasure completed (warning level, includes deleted_user_id, requesting_user_id)
- `auth.user_data_delete_failed` — If deletion fails (error level, includes user_id, error)

## Testing Strategy

### Unit Tests
**Location:** `app/tests/test_security.py`
- `TestNoRawSqlInjection` (2 tests) — AST-parsed verification of no raw SQL with user input in repositories
- `TestContainerHardening` (5 tests) — Dockerfile and compose security verification
- `TestDependencySecurity` (3 tests) — CI pipeline dependency audit verification
- `TestBackupInfrastructure` (4 tests) — Backup script existence and features
- `TestGdprDeletion` (3 tests) — GDPR deletion endpoint, admin-only, self-delete prevention
- `TestCsrfProtection` (2 tests) — Bearer auth verification, no cookie auth

### Integration Tests
**Location:** `app/auth/tests/test_service.py` (if time permits, optional)
- Test `delete_user_data` with mock DB and Redis
- Test self-deletion prevention raises `DomainValidationError`

### Edge Cases
- Empty/null inputs — Deletion of non-existent user returns 404
- Self-deletion — Returns 422 (DomainValidationError)
- Non-admin deletion attempt — Returns 403 (RBAC enforcement)

## Acceptance Criteria

This feature is complete when:
- [ ] `pip-audit` runs in CI as a dedicated step (hard PR failure on CVEs)
- [ ] `uv lock --check` runs in CI (lock file integrity)
- [ ] All Dockerfiles run as non-root users
- [ ] `no-new-privileges:true` and `cap_drop: ALL` on all Docker services
- [ ] Production compose adds `read_only: true` for app and cms
- [ ] Automated backup script exists with 90-day retention
- [ ] GDPR deletion endpoint works (admin-only, prevents self-delete)
- [ ] ~25 new security convention tests pass
- [ ] No raw SQL with user input in any repository (convention test enforced)
- [ ] CSRF posture verified (JWT in headers, not cookies)
- [ ] 4th audit saved as documentation
- [ ] CLAUDE.md updated with all v4 changes
- [ ] All type checkers pass (mypy + pyright)
- [ ] All existing tests still pass (no regressions)
- [ ] No type suppressions added

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 15 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-5)
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

**Level 3: Unit Tests (security-specific)**
```bash
uv run pytest app/tests/test_security.py -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Dependency Audit**
```bash
uv run pip-audit --strict --desc
```

**Success definition:** Levels 1-5 exit code 0, all tests pass, zero errors or warnings.

## Dependencies

- Shared utilities used: `escape_like()` from `app/shared/utils`, `get_logger()` from `app/core/logging`
- Core modules used: `app/core/redis`, `app/core/exceptions`, `app/core/database`
- New dependencies: `pip-audit>=2.7.0` (dev only) — `uv add --dev pip-audit`
- New env vars: None (backup script uses existing Docker env vars)

## Known Pitfalls

The executing agent MUST follow these rules (in addition to all 59 rules in the plan template):

60. **Docker `cap_drop: ALL` breaks PostgreSQL** — PostgreSQL needs default Linux capabilities to function (CHOWN, SETUID, etc.). Only add `security_opt: no-new-privileges:true` to the `db` service, NOT `cap_drop: ALL`.
61. **nginx non-root needs `cap_net_bind_service`** — Port 80 requires this capability. Use `setcap` in Dockerfile AND `cap_add: NET_BIND_SERVICE` in compose.
62. **`read_only: true` breaks services needing temp files** — FastAPI/uvicorn and Next.js write temp files. Add `tmpfs: /tmp` when using read_only. Only use in production compose, not dev.
63. **pip-audit may find vulnerabilities in transitive deps** — If `pip-audit` fails due to a transitive dependency CVE with no fix available, add it to `.pip-audit-known-vulnerabilities` as a documented acceptance. Do NOT remove `--strict`.
64. **GDPR deletion must clear Redis keys** — User deletion is incomplete if brute-force tracking keys (`auth:failures:{email}`, `auth:lockout:{email}`) are left in Redis. Always call `_clear_redis_brute_force(email)` after DB deletion.
65. **`session.delete()` requires the object in session** — Must `select()` the user first, then `session.delete(user_obj)`. Cannot delete by ID directly.

## Notes

### Items Requiring User Decision (NOT in this plan)
These items were identified in the audit but require infrastructure/provider decisions:
- **SIEM/monitoring** — Needs provider choice (ELK, Datadog, Grafana Cloud)
- **Database encryption at rest** — Needs cloud provider decision (encrypted volumes, PostgreSQL TDE)
- **Self-service password reset** — Needs SMTP provider (SendGrid, AWS SES, Mailgun)
- **Let's Encrypt automation** — Needs domain name and DNS configuration
- **Centralized log aggregation** — Needs provider choice (often bundled with SIEM)
- **Secrets management** — Needs tool decision (HashiCorp Vault, AWS SSM)
- **Database connection privilege separation** — Read-only connection for queries (operational complexity vs security benefit trade-off)

### Verified Already Secure (no action needed)
- **SQL injection** — All repos use SQLAlchemy ORM. Only `text("SELECT 1")` in health checks and `text("'simple'")` for PostgreSQL full-text search config (neither accepts user input)
- **CSRF** — JWT in `Authorization` header (not cookies). Auth.js stores JWT in httpOnly cookie but the backend never reads auth from cookies
- **Token storage** — Auth.js v5 stores tokens in encrypted httpOnly session cookies (not localStorage)
- **Dependency pinning** — `uv.lock` with `--frozen` flag in CI prevents drift
- **Backend Dockerfile** — Already non-root (`USER vtv`, UID 1001)
- **Frontend Dockerfile** — Already non-root (`USER nextjs`, UID 1001)

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed the 4th audit document (`docs/security_audit_4.txt`)
- [ ] Understood which items are in-scope vs. require user decisions
- [ ] Clear on task execution order
- [ ] Validation commands are executable in this environment
