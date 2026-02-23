# Review: API Security Hardening (Phases 1 & 2)

**Date:** 2026-02-23
**Scope:** JWT Authentication + RBAC implementation across backend and frontend
**Files reviewed:** 28 (5 new, 23 modified)

**Summary:** Solid security implementation that correctly protects all 60+ endpoints with JWT auth and role-based access control. Clean dependency injection pattern, proper token handling, and good test coverage. A few medium-priority issues around logging completeness, token payload information disclosure, and documentation staleness.

## Findings

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `app/auth/dependencies.py:80` | `require_role()` error detail leaks valid role names: `"Requires one of roles: admin, editor"` | Return generic `"Insufficient permissions"` message. Attackers shouldn't learn which roles exist from error responses. Log the details server-side (which it already does). | High |
| `app/auth/routes.py:56-61` | Missing `_started`/`_completed` logging pair on refresh endpoint | Add `auth.token.refresh_started` / `auth.token.refresh_completed` structured log events to match logging standard | Medium |
| `app/auth/service.py:78` | `create_access_token` receives `user.id` which is `Mapped[int]` — SQLAlchemy attribute, not plain `int` at runtime | Works in practice but add a comment or explicit `int(user.id)` cast for clarity, since `token.py:create_access_token` expects `int` | Low |
| `app/auth/token.py:41` | `dict[str, Any]` payload type — `Any` used for JWT payload dict values | Justified here since JWT payload values are mixed types (str, datetime, int). Add a brief inline comment `# JWT payload values are heterogeneous` | Low |
| `app/auth/token.py:95` | `float(payload["exp"])` — assumes `exp` is numeric, but malformed tokens could have non-numeric exp | Already caught by `(JWTError, KeyError, ValueError)` exception handler — good. No change needed. | Low |
| `cms/apps/web/auth.ts:130` | `token.role as VTVRole` — unsafe cast without validation | Add runtime check: `if (["admin","dispatcher","editor","viewer"].includes(token.role as string))` before casting. Prevents invalid role from backend propagating silently. | Medium |
| `cms/apps/web/src/lib/auth-fetch.ts:24` | `await auth()` called on every API request — no caching | Auth.js `auth()` reads the JWT cookie and decodes it each time. Acceptable for server components but could add latency on pages with many API calls. Add a comment noting this is intentional (session is cheap to decode). | Low |
| `app/auth/tests/test_routes.py:19-31` | Fixture saves/restores `app.dependency_overrides` — fragile pattern tied to test execution order | Consider using `conftest.py` with `autouse=True` session-scoped fixture that ensures clean state. Current approach works but is a maintenance concern if more test files add module-level overrides. | Low |
| `CLAUDE.md:111` | Auth feature description outdated: says `(2 endpoints, bcrypt, brute-force lockout)` | Update to `(4 endpoints: login, refresh, seed; JWT auth, bcrypt, brute-force lockout, RBAC dependencies)` | Medium |
| `CLAUDE.md:200` | Security section still says `Out of scope (future): Backend API authentication (JWT/token)` | Remove this line — JWT auth is now implemented | High |
| `app/auth/schemas.py:20-21` | `access_token` and `refresh_token` returned in login response body | Industry best practice is httpOnly cookies for refresh tokens (XSS-resistant). Current approach sends refresh token to JS-accessible Auth.js storage. Acceptable for MVP since Auth.js JWT strategy encrypts the cookie, but document the trade-off. | Medium |
| `app/core/config.py:117` | `jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"` with `# noqa: S105` | Default is intentional for dev, and startup validation catches it in production. Good. Ensure `docker-compose.yml` injects `JWT_SECRET_KEY` from env. | Low |
| `app/auth/dependencies.py:19` | `security = HTTPBearer()` — returns 403 (not 401) when no Bearer token provided | This is FastAPI default behavior. HTTPBearer with `auto_error=True` (default) raises 403 for missing header. Consider `HTTPBearer(auto_error=False)` + custom 401 response for missing token (vs 401 for invalid token). Currently all auth test expectations use 403 for missing header. | Medium |
| `app/auth/routes.py:46-64` | Refresh endpoint validates refresh token then calls service — two decode operations possible | Current flow: `decode_token()` in route + `service.refresh_access_token()` which calls `repo.find_by_id()`. Refresh token is decoded once in routes, user lookup done in service. Clean separation. No issue. | Low |
| `app/stops/routes.py:38` | `_current_user: User = Depends(get_current_user)` — user object fetched but unused | The underscore prefix correctly signals it's unused. The DB lookup is an intentional auth side-effect. Consider a lighter `verify_token_only` dependency for read endpoints if DB lookup becomes a performance concern. | Low |
| `cms/apps/web/auth.ts:136` | `signIn: "/lv/login"` hardcoded locale in redirect | Already flagged in existing docs as known issue. Locale-aware redirect is handled by middleware. | Low |

## Priority Summary

- **Critical**: 0
- **High**: 2
- **Medium**: 5
- **Low**: 9

## What's Done Well

1. **Complete endpoint coverage** — Every route file has auth dependencies with correct RBAC roles
2. **Clean dependency injection** — `get_current_user` and `require_role()` factory pattern follows FastAPI best practices
3. **Token separation** — Access tokens (30min, carry role) vs refresh tokens (7 days, no role) is correct design
4. **Startup validation** — Production fails hard on default JWT secret
5. **Frontend integration** — Single `authFetch()` wrapper for all 6 API clients eliminates auth header duplication
6. **Test coverage** — 55 new auth-specific tests (token, dependencies, routes, service) plus protected endpoint verification
7. **Structured logging** — Security events follow `domain.component.action_state` pattern consistently
8. **Defense in depth** — Frontend brute-force (Auth.js) + backend brute-force (User model) + rate limiting (slowapi)

## Stats

- Files reviewed: 28
- Issues: 16 total — 0 Critical, 2 High, 5 Medium, 9 Low

## Next Step

To fix issues: `/code-review-fix .agents/code-reviews/api-security-hardening-review.md`
