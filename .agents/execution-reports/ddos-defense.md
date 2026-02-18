# Execution Report: DDoS Defense

**Plan:** `.agents/plans/be-ddos-defense.md`
**Status:** Complete (Phase 1 + Phase 2)
**Date:** 2026-02-18

## Summary

Implemented defense-in-depth DDoS protection across the entire VTV stack:
- **Phase 1**: Singleton caches (TransitService, AgentService), request size limits, slowapi rate limiting, daily query quota
- **Phase 2**: Security headers (Next.js CSP/HSTS), login brute-force protection, Docker non-root user + resource limits, nginx reverse proxy

## Files Created (4)

| File | Purpose |
|------|---------|
| `app/core/rate_limit.py` | slowapi Limiter with X-Forwarded-For IP extraction |
| `app/core/agents/quota.py` | Daily per-IP query quota tracker (50/day, auto-reset) |
| `nginx/nginx.conf` | Reverse proxy with rate limiting zones and connection limits |
| `nginx/Dockerfile` | nginx:1.27-alpine image |

## Files Modified (17)

| File | Change |
|------|--------|
| `pyproject.toml` | Added slowapi dependency, mypy overrides, per-file-ignores |
| `app/core/config.py` | Rate limit and quota settings |
| `.env.example` | Documented rate limit, quota, AUTH_SECRET env vars |
| `app/transit/service.py` | Singleton pattern, persistent GTFS-RT client |
| `app/core/agents/service.py` | Singleton pattern, resilient close |
| `app/main.py` | Lifespan cleanup, rate limiter registration |
| `app/core/agents/schemas.py` | Message count limit (20), content length validator (4000) |
| `app/core/middleware.py` | BodySizeLimitMiddleware (100KB) |
| `app/core/agents/routes.py` | Rate limits (10/min chat, 60/min models), quota check |
| `app/transit/routes.py` | Rate limit (30/min) |
| `app/core/health.py` | Rate limits (60/min), 10s DB health cache |
| `cms/apps/web/next.config.ts` | Security headers (CSP, HSTS, X-Frame-Options, etc.) |
| `cms/apps/web/auth.ts` | Login brute-force protection (5 attempts = 15min lockout) |
| `docker-compose.yml` | AUTH_SECRET env var, resource limits, nginx service, internal ports |
| `Dockerfile` | Non-root user (vtv, UID 1001) |
| `app/core/agents/tests/test_quota.py` | 5 new quota tests |
| `app/core/tests/test_middleware.py` | 2 new body size tests |

## Validation Results

| Check | Result |
|-------|--------|
| Ruff format | PASS |
| Ruff check | PASS |
| MyPy | PASS (0 errors, 71 files) |
| Pyright | PASS (0 errors) |
| Pytest (unit) | PASS (205 passed, 9 deselected) |
| Frontend type-check | PASS |
| Frontend lint | PASS |

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| `max_length=4000` on ChatMessage.content broke agent responses | TestModel tool output exceeds 4000 chars; constraint applied to both input AND output messages | Moved validation from ChatMessage field to ChatCompletionRequest field_validator (input only) |
| Health tests fail with `isinstance(request, Request)` check | slowapi validates request type; MagicMock fails this check | Set `limiter.enabled = False` in tests, pass `request=None` |
| `RuntimeError: Event loop is closed` in lifespan test | TestClient closes event loop before singleton cleanup in lifespan shutdown | Added try/except RuntimeError in close functions |
| Ruff ARG001 on `request: Request` parameters | slowapi requires request as first route param but ruff flags it unused | Added per-file-ignores for ARG001 in pyproject.toml |
| Pyright errors on `@limiter.limit()` decorators | slowapi lacks py.typed marker | Added file-level pyright ignore directives for untyped decorator/member |
| Ruff E402 in transit test_routes.py | Import after `limiter.enabled = False` assignment | Moved imports before the assignment |

## Deviations from Plan

1. **Content length validation location**: Plan specified `max_length=4000` on `ChatMessage.content` field. Changed to `field_validator` on `ChatCompletionRequest` because the agent's tool output responses legitimately exceed 4000 characters.
2. **Resilient singleton close**: Added `try/except RuntimeError` in `close_transit_service()` and `AgentService.close()` to handle event loop already closed during test teardown. Not in original plan.
