# ADR-0004: Application-Level Rate Limiting with slowapi

## Status

Accepted

## Context

VTV exposes API endpoints with vastly different cost profiles:

| Endpoint | Cost | Target Rate |
|----------|------|-------------|
| `/api/v1/chat/completions` | LLM inference (~$0.01/call, 2-10s latency) | 10/minute |
| `/api/v1/transit/vehicles` | Redis read (~0.1ms) | 30/minute |
| `/api/v1/health` | In-memory check (~0.01ms) | 60/minute |
| Default CRUD endpoints | DB query (~5ms) | 120/minute |

Rate limiting at the **reverse proxy only** (nginx) was rejected because:

- nginx `limit_req` operates on URL patterns, not semantic endpoints. A single `location /api/` block can't distinguish between a $0.01 LLM call and a free health check.
- nginx rate limiting is per-worker (each nginx worker has its own counter zone), though shared memory zones mitigate this.
- Changing rate limits requires nginx config reload, not application config change.

Rate limiting at the **application only** was also rejected - nginx provides a coarse defense-in-depth layer against volumetric abuse that shouldn't reach the Python process at all.

## Decision

We use a **two-layer approach**:

**Layer 1 - slowapi (application-level):** `slowapi>=0.1.9` with Redis-backed storage for cross-worker enforcement. Rate limits are per-endpoint decorators (`@limiter.limit("10/minute")`) configured in `app/core/rate_limit.py`. IP extraction uses `X-Real-IP` header (not `X-Forwarded-For`, which is client-spoofable). Falls back to in-memory storage when Redis is unavailable.

**Layer 2 - nginx (reverse proxy):** Coarse rate limiting zones in `nginx/nginx.conf` - 30 req/s general API, 2 req/s LLM endpoint, 60 req/s health. This catches volumetric abuse before it reaches Python.

Rate limit values are configurable via `app/core/config.py` settings (`rate_limit_chat`, `rate_limit_transit`, `rate_limit_health`, `rate_limit_default`).

## Consequences

**Easier:**
- Per-endpoint semantic rate limits: the LLM endpoint has 10/min while health has 60/min
- Rate limit changes deploy with the application, no nginx reload needed
- Cross-worker enforcement via Redis - 4 Gunicorn workers share one counter
- Defense-in-depth: volumetric attacks are stopped at nginx before reaching Python

**Harder:**
- Two rate limit configurations to maintain (slowapi + nginx)
- Must keep nginx limits looser than slowapi limits to avoid false positives at the proxy layer
- `Request` parameter required on every rate-limited route function (ruff ARG001 exception configured)
