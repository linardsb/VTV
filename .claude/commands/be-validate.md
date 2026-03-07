---
description: Run all VTV quality checks — formatting, linting, type checking, and tests
argument-hint:
allowed-tools: Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pyright:*), Bash(uv run pytest:*), Bash(curl:*), Bash(docker-compose:*)
---

Run all VTV quality checks in sequence and report a pass/fail scorecard.

# Validate — Run Full VTV Validation Suite

## Step 0: Use jCodeMunch for Convention Checks

If the project is indexed via jcodemunch, **use jcodemunch tools in Step 10**:
- `search_symbols` → find route functions missing `current_user` dependency (auth check)
- `get_file_outline` → scan models for `TimestampMixin` inheritance without reading full files
- `search_symbols` → verify `rate_limit` usage across route modules

## INPUT

No arguments needed. Runs all validation commands against the current codebase state.

## PROCESS

Run each command in order. Report results for each before moving to the next.

### 1. Format

```bash
uv run ruff format .
```

### 2. Lint

```bash
uv run ruff check .
```

### 3. Type Check — MyPy

```bash
uv run mypy app/
```

### 4. Type Check — Pyright

```bash
uv run pyright app/
```

### 5. Tests (unit)

```bash
uv run pytest -v -m "not integration"
```

### 6. Tests (integration — only if Docker is running)

```bash
docker-compose ps 2>/dev/null && uv run pytest -v -m integration || echo "Skipped — Docker not running"
```

### 7. SDK Sync Check (optional — only if FastAPI is running)

```bash
curl -sf http://localhost:8123/openapi.json > /dev/null 2>&1 && echo "FastAPI running — checking SDK sync" || echo "Skipped — FastAPI not running"
```

If FastAPI is running:
1. Fetch the live OpenAPI spec: `curl -s http://localhost:8123/openapi.json`
2. Compare against `cms/packages/sdk/openapi.json` (if it exists)
3. If the specs differ (or `cms/packages/sdk/openapi.json` doesn't exist), warn:
   ```
   SDK out of sync — run: cd cms && pnpm --filter @vtv/sdk generate-sdk
   ```
4. This is a WARNING (soft gate) — does not block the commit, but should be addressed

### 8. Server Validation (optional — only if Docker is running)

```bash
docker-compose ps 2>/dev/null
```

If services are running, test endpoints:

```bash
curl -s http://localhost:8123/health
curl -s -o /dev/null -w "%{http_code}" http://localhost:8123/docs
```

### 9. Security Lint (Ruff Bandit rules)

```bash
uv run ruff check app/ --select=S --no-fix
```

This runs Bandit-equivalent security rules (S101-S701) to catch:
- assert in production code (S101)
- hardcoded passwords (S105)
- exec/eval usage (S102)
- insecure temp files (S108)
- SQL injection patterns (S608)

### 10. Security Convention Tests

```bash
uv run pytest app/tests/test_security.py -v
```

Run the security convention test suite separately and report results. These tests enforce:
- All endpoints require authentication (auto-discovery scan)
- Security logging uses warning+ level (no debug in except blocks)
- JWT uses HS256 algorithm (not "none")
- Bcrypt uses 12+ rounds
- Password complexity on correct schema (PasswordResetRequest, not LoginRequest)
- Nginx has all required security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options)

If any convention test fails, it indicates a security regression that must be fixed before committing.

Steps 9-10 are **hard gates** — security lint violations or convention test failures MUST be fixed before committing. These are not warnings.

**Note:** For comprehensive infrastructure security checks (Docker hardening, nginx headers), run `make security-audit-full`. Steps 9-10 cover application-level security; the full audit also validates container and proxy configuration.

## OUTPUT

```
Validation Results:
  1. Ruff format:          PASS / FAIL
  2. Ruff check:           PASS / FAIL  [N issues]
  3. MyPy:                 PASS / FAIL  [N errors]
  4. Pyright:              PASS / FAIL  [N errors]
  5. Pytest (unit):        PASS / FAIL  [X passed, Y failed]
  6. Pytest (integration): PASS / FAIL / SKIPPED (Docker not running)
  7. SDK sync:             IN SYNC / OUT OF SYNC / SKIPPED (FastAPI not running)
  8. Server:               PASS / FAIL / SKIPPED (Docker not running)
  --- Security Gates ---
  9. Security lint:        PASS / FAIL  [N violations]
 10. Security conventions: PASS / FAIL  [X passed, Y failed]

Overall: ALL PASS / X FAILURES / Y WARNINGS
```

If any step fails, list the specific errors with file paths and line numbers so they can be fixed.

**Next steps:**
- If all checks pass: Run `/commit` to commit changes, or `/review [path]` for architectural review
- If checks fail: Fix the reported issues and re-run `/be-validate`
