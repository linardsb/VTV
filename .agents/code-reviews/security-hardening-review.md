# Code Review: Security Hardening v3

**Date:** 2026-02-23
**Scope:** All files modified/created during security hardening implementation (20 files)
**Reviewer:** Automated review against VTV's 8 quality standards

## Summary

Strong security hardening implementation covering JWT revocation, Redis brute-force tracking, CORS restrictions, health endpoint redaction, nginx CSP/HTTPS, and Docker credential interpolation. One **critical design flaw** — password complexity validation on the LoginRequest schema locks out all existing users with weak passwords (including demo users with default password "admin"). Two high-priority issues in logging severity and missing test coverage for cross-request state.

---

## Findings

| # | File:Line | Issue | Suggestion | Priority |
|---|-----------|-------|------------|----------|
| 1 | `app/auth/schemas.py:41-45` | Password complexity validator on `LoginRequest` blocks login for existing users with weak passwords. Demo users (password "admin") return 422 instead of authenticating. Login should accept ANY password and let the service layer verify it against the hash. | Remove `@field_validator("password")` from `LoginRequest`. Keep it on `PasswordResetRequest` only. Complexity should be enforced on password CREATION/RESET, not on login. | **Critical** |
| 2 | `app/auth/service.py:53` | `logger.debug("auth.redis_brute_force_unavailable")` — Redis unavailability is a security degradation (brute-force protection falls to DB-only). Debug level won't appear in production logs. | Change to `logger.warning("auth.redis_brute_force_unavailable", email=email)` | High |
| 3 | `app/auth/service.py:67` | `logger.debug("auth.redis_clear_unavailable")` — same issue as #2. | Change to `logger.warning("auth.redis_clear_unavailable", email=email)` | High |
| 4 | `app/auth/token.py:88-89` | `revoke_token` exception handler logs warning without error details. | Add `error=str(e), error_type=type(e).__name__` to the log call. | Medium |
| 5 | `app/auth/service.py:108-111` | When DB lockout expires (`locked_until` cleared), Redis lockout key is NOT explicitly cleared. Both use same LOCKOUT_DURATION TTL so they expire ~simultaneously, but a small race window exists. | After clearing `user.locked_until = None` on line 110, also call `await _clear_redis_brute_force(email)` to ensure both layers are in sync. | Medium |
| 6 | `CLAUDE.md:205` | "Out of scope (future)" still lists "Redis-backed brute-force tracking" and "token revocation" — both are now implemented. | Update CLAUDE.md Security Practices section to reflect implemented features and remove from "Out of scope". | Medium |
| 7 | `app/auth/tests/test_service.py` | No test for brute-force lockout persisting ACROSS multiple authenticate() calls (state accumulation across 5 failures). Current test starts at `failed_attempts=4`. | Add test: start at 0 attempts, call authenticate 5 times with wrong password, verify 6th raises `AccountLockedError`. | Medium |
| 8 | `app/auth/tests/test_service.py` | No test for `reset_password` method. | Add `TestResetPassword` class testing: happy path, user not found, Redis clear called. | Medium |
| 9 | `app/core/agents/routes.py:48` | No logging when quota is exceeded — only HTTP 429 is returned. | Add `logger.warning("agent.quota_exceeded_http", client_ip=client_ip)` before the HTTPException raise for audit trail. | Medium |
| 10 | `app/auth/tests/test_routes.py:184-192` | `test_login_is_public` sends password "TestPass1234" — this tests schema acceptance but no longer tests that a truly weak password still reaches the auth service. After fix #1, re-add a weak password test. | After removing complexity from LoginRequest, change back to `"test"` and verify it gets 401 (from service), not 422 (from schema). | Low |
| 11 | `app/core/middleware.py:56-62` | Upload path allowlist is hard-coded in middleware. | Consider moving to `settings.upload_paths` for configurability; low urgency since paths are stable. | Low |

---

## Stats

- **Files reviewed:** 20
- **Issues:** 11 total — 1 Critical, 2 High, 6 Medium, 2 Low

## Standards Scorecard

| Standard | Score | Notes |
|----------|-------|-------|
| 1. Type Safety | 9/10 | Pre-existing pyright suppressions (slowapi); no new suppressions added |
| 2. Pydantic Schemas | 6/10 | Critical: complexity validator on wrong schema (LoginRequest vs PasswordResetRequest) |
| 3. Structured Logging | 7/10 | Redis unavailability logged at debug instead of warning; missing error details |
| 4. Database Patterns | 9/10 | Correct async/await, proper repository pattern |
| 5. Architecture | 9/10 | Clean vertical slices, proper dependency injection |
| 6. Docstrings | 9/10 | Comprehensive Google-style docstrings throughout |
| 7. Testing | 7/10 | 50 security tests, but missing reset_password and cross-request brute-force tests |
| 8. Security | 8/10 | Strong implementation; Redis/DB lockout race window is minor |

## Next Step

Fix issues: `/code-review-fix .agents/code-reviews/security-hardening-review.md`
