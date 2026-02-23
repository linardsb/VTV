# Execution Report: API Security Hardening (Phases 1 & 2)

**Plan:** `.agents/plans/async-crafting-pond.md`
**Date:** 2026-02-23
**Scope:** Phase 1 (JWT Authentication) + Phase 2 (RBAC)

## Summary

Implemented JWT authentication on all 60+ backend endpoints and role-based access control. Previously, the backend was completely open — anyone with the URL could call any endpoint. Now all endpoints require a valid Bearer token, and write operations are restricted by role.

## Deliverables

### New Files (5)
| File | Purpose |
|------|---------|
| `app/auth/token.py` | JWT creation/validation (access + refresh tokens, TokenPayload model) |
| `app/auth/dependencies.py` | FastAPI auth dependencies (`get_current_user`, `require_role()`) |
| `app/auth/tests/test_token.py` | Token creation, decoding, expiry, invalid token tests |
| `app/auth/tests/test_dependencies.py` | Auth dependency and role checking tests |
| `cms/apps/web/src/lib/auth-fetch.ts` | Centralized authenticated fetch wrapper for all API clients |

### Modified Files (41)
- `pyproject.toml` — Added `python-jose[cryptography]`
- `app/core/config.py` — JWT settings (secret, algorithm, access/refresh expiry)
- `app/auth/schemas.py` — Token fields on LoginResponse, RefreshRequest/Response
- `app/auth/service.py` — Token issuance on login, refresh_access_token()
- `app/auth/routes.py` — `/refresh` endpoint, protected `/seed` with admin guard
- `app/main.py` — JWT secret startup validation
- All 7 feature `routes.py` files — Added `Depends(get_current_user)` or `Depends(require_role(...))`
- All 6 frontend API clients — Replaced `fetch()` with `authFetch()`
- `cms/apps/web/auth.ts` — Store backend access_token in Auth.js JWT session
- Test files — Auth-aware test setup, 55 new tests

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| `test_seed_requires_auth` returned 200 instead of 401 | Other test modules set `app.dependency_overrides[get_current_user]` at module level on the shared global `app` object. Overrides persisted across test modules. | Created pytest fixture that saves/clears/restores `dependency_overrides` |
| HTTPBearer returned 403 for missing Authorization header | FastAPI's `HTTPBearer(auto_error=True)` default returns 403 (per framework design), but RFC 7235 requires 401 for missing authentication | Changed to `HTTPBearer(auto_error=False)` with custom 401 + `WWW-Authenticate: Bearer` header |
| Role names leaked in error detail | `require_role()` returned `"Requires one of roles: admin, editor"` — tells attackers which roles exist | Changed to generic `"Insufficient permissions"` |
| Unsafe role cast in auth.ts | `token.role as VTVRole` had no runtime validation — malformed JWT could inject arbitrary role | Added `validRoles.includes()` check with fallback to `"viewer"` |
| `authFetch` broke all CRUD in client components | `authFetch` imported server-only `auth()` at top level. Client components (`'use client'`) like document upload form and drivers page couldn't resolve the import — Next.js Turbopack errored with "Module not found" for client bundle. | Replaced static `import { auth }` with dynamic `await import("../../auth")` on server and `await import("next-auth/react").getSession()` on client, using `typeof window` to detect context |
| Stale Turbopack cache showed wrong import path | After fixing `auth-fetch.ts` import path, dev server still showed old `../../../auth` error | Cleared `.next` cache directory and restarted dev server |

## Divergences from Plan

| Plan | Actual | Reason |
|------|--------|--------|
| Phase 3 (HTTPS/TLS, Redis brute-force) | Deferred | Phase 1+2 provide the critical security layer; Phase 3 is infrastructure hardening |
| Phase 4 (Token revocation, security headers) | Deferred | Not needed for MVP; lightweight JTI revocation can be added later |
| Middleware-based auth approach considered | Dependency injection chosen | FastAPI DI is more granular, testable, and idiomatic |

## Validation Results

- **Tests:** 609 passing (55 new auth tests)
- **Ruff format:** Clean
- **Ruff check:** Clean
- **MyPy:** 0 issues
- **Pyright:** 0 errors
- **E2E:** 66 passed, 4 failed (pre-existing UI timing issues, not auth-related), 5 skipped
