# Execution Report: Security Hardening v5

**Plan:** `.agents/plans/security-hardening-v5.md`
**Date:** 2026-02-25
**Status:** Complete

## Summary

Remediated all 16 findings from the fifth security audit (`docs/security_audit_5.txt`). The audit identified runtime vulnerabilities that existed despite infrastructure being in place — functions implemented but never called, IP tracking using proxy IP instead of real client IP, and missing defensive validations on file uploads.

## Findings Addressed

### Critical (4)

| ID | Finding | Fix |
|----|---------|-----|
| CRIT-1 | Daily quota uses `request.client.host` (nginx proxy IP) | Changed to `_get_client_ip(request)` using X-Real-IP |
| CRIT-2 | `revoke_token()` exists but never called — no logout | Added `POST /api/v1/auth/logout` endpoint with token revocation |
| CRIT-3 | Refresh token never revoked after use (unlimited replay) | Added `revoke_token(payload.jti, ttl_seconds=604800)` in refresh endpoint |
| CRIT-4 | GTFS ZIP import reads entire file into memory | Added streaming 8KB chunked upload + ZIP bomb detection |

### High (5)

| ID | Finding | Fix |
|----|---------|-----|
| HIGH-1 | Email enumeration via timing attack | Added `_DUMMY_HASH` bcrypt constant for timing normalization |
| HIGH-2 | Token revocation fail-open with no logging | Added `warning`-level `auth.token.revocation_check_degraded` log event |
| HIGH-3 | Internal file paths exposed in API responses | Removed `file_path` from `DocumentResponse`, updated `has_file` computed field |
| HIGH-4 | No HTTP-to-HTTPS redirect | Added HTTP server block redirecting to HTTPS (except `/health` for Docker) |
| HIGH-5 | CSP allows unsafe-inline/unsafe-eval in script-src | Removed `unsafe-inline` and `unsafe-eval` from `script-src`; documented `style-src unsafe-inline` as accepted risk for Next.js |

### Medium (7)

| ID | Finding | Fix |
|----|---------|-----|
| MED-1 | PostgreSQL container runs as root with all capabilities | Added `cap_drop: ALL` with minimal `cap_add` for db service |
| MED-2 | `metadata_json` field accepts arbitrary strings | Added `@field_validator` with JSON parsing + 10K char limit |
| MED-3 | X-Request-ID not validated (log injection risk) | Added regex validation `^[a-zA-Z0-9\-_.]{1,64}$` with UUID fallback |
| MED-4 | Obsidian SSRF localhost check is case-sensitive | Added `.lower()` to hostname comparison |
| MED-5 | CSP script-src allows inline scripts | Tightened to `script-src 'self'` only |
| MED-6 | Docker volume mounts expose entire directories | Narrowed to specific subdirectories |
| MED-7 | Redis password is empty by default | Set non-empty default `devpassword` with env var interpolation |

## Files Modified

### Backend (13 files)
- `app/auth/routes.py` — Added logout endpoint, refresh token revocation, `REFRESH_TOKEN_TTL_SECONDS` constant
- `app/auth/service.py` — Added `_DUMMY_HASH` for timing attack prevention
- `app/auth/token.py` — Added degradation warning logging in `is_token_revoked()`
- `app/core/agents/routes.py` — Changed quota IP tracking to `_get_client_ip(request)`
- `app/core/agents/tools/transit/deps.py` — Added case-insensitive SSRF localhost check
- `app/core/logging.py` — Added `_SAFE_REQUEST_ID` regex and `set_request_id()` validation
- `app/knowledge/schemas.py` — Removed `file_path` from `DocumentResponse`, added `validate_metadata_json`
- `app/knowledge/tests/test_routes.py` — Removed `file_path` from mock data
- `app/schedules/gtfs_import.py` — Added `_validate_zip_safety()` with compression ratio/size checks
- `app/schedules/routes.py` — Added streaming chunked upload with `MAX_GTFS_UPLOAD_BYTES`
- `app/tests/test_security.py` — Added 10 new convention test classes (94 total tests)

### Infrastructure (2 files)
- `docker-compose.yml` — db `cap_drop: ALL`, narrowed volumes, Redis password
- `nginx/nginx.conf` — HTTP-to-HTTPS redirect, CSP tightening, HTTPS server block

### Frontend (5 files)
- `cms/.../documents/page.tsx` — Session hydration fix (wait for `authenticated` before API calls)
- `cms/.../drivers/page.tsx` — Same pattern
- `cms/.../routes/page.tsx` — Same pattern
- `cms/.../schedules/page.tsx` — Same pattern
- `cms/.../stops/page.tsx` — Same pattern

## Validation Results

| Check | Result |
|-------|--------|
| ruff format | PASS (203 files unchanged) |
| ruff check | PASS (0 violations in changeset) |
| mypy | PASS (0 errors, 193 files) |
| pyright | PASS (0 errors in changeset) |
| pytest (unit) | PASS (678 passed, 2 pre-existing failures*) |
| pytest (integration) | PASS (19 passed) |
| Security lint (Bandit) | PASS (0 violations) |
| Security conventions | PASS (94 passed) |
| Server health | PASS (healthy) |

*Pre-existing failures in untracked features (skills, stops) — not regressions from this changeset.

## Code Review

Review performed and saved to `.agents/code-reviews/all-review.md`.

**Results:** 8 issues total — 0 Critical, 0 High, 0 Medium, 8 Low (all acceptable for merge)

**Review fixes applied:**
- Simplified logout endpoint (removed redundant HTTPException raises)
- Added `.lower()` to SSRF localhost hostname comparison
- Added `auth.logout_started` logging event
- Extracted `REFRESH_TOKEN_TTL_SECONDS` constant (replaced magic number 604800)
- Extracted `MAX_GTFS_UPLOAD_BYTES` module constant
- Replaced fragile string-split with YAML parsing in container hardening test
- Added CSP `unsafe-inline` accepted risk comment in nginx.conf

## Root Cause Analysis

The recurring audit pattern (functions implemented but not wired to endpoints) was caused by:

1. **Infrastructure-first implementation** — Previous audits focused on creating the security infrastructure (`revoke_token()`, `is_token_revoked()`) without verifying the complete call chain from HTTP endpoint to function
2. **Missing integration tests** — Convention tests verified function existence but not function invocation at runtime
3. **Fix:** Added 10 new convention test classes that verify not just existence but actual usage patterns (e.g., `TestLogoutEndpointExists` checks both route presence AND `revoke_token` call in source)
