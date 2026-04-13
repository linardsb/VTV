---
paths:
  - "app/**/*.py"
  - "alembic/**/*.py"
---

# Backend Rules

## Middleware & Rate Limiting

- `BodySizeLimitMiddleware` (100KB), `RequestLoggingMiddleware` (correlation IDs), `RateLimitIdentityMiddleware` (JWT decode for per-user bucketing), `CORSMiddleware`
- Rate limiting via slowapi with Redis storage (cross-worker enforcement, in-memory fallback)
- Per-user rate limit bucketing (OPS-4.1): `RateLimitIdentityMiddleware` decodes JWT to populate `request.state.rate_limit_user_id/role`. Key function `_user_or_ip_key` returns `user:{id}:{role}` or `ip:{ip}:anonymous`. Role-based tier default limits via `_dynamic_tier_limit` (admin 1000/min, dispatcher 300/min, editor 100/min, viewer 50/min, anonymous 30/min). Sub-bucket keys for chat and analytics endpoints.
- Rate limits: auth (10/min login, 30/min refresh, 5/min seed), chat (10/min sub-bucket), transit (30/min), knowledge (10-30/min), schedules (5-30/min), drivers (10-30/min), events (10-30/min), skills (5-30/min), health (60/min), analytics export (5/hour sub-bucket)
- Query quota: 50/day per IP for LLM chat endpoint (`app.core.agents.quota`)

## Docker Services

- `db` (PostgreSQL + pgvector), `redis` (vehicle position cache + rate limiting + leader election)
- `migrate` (Alembic auto-migration, runs once), `app` (Gunicorn + 4 UvicornWorkers in production, single uvicorn with --reload in dev)
- `cms` (Next.js), `nginx` (reverse proxy on port 80, Brotli + gzip compression, upstream keepalive)
- Services start in dependency order with healthchecks. All behind nginx.

## Configuration

Environment variables via Pydantic Settings (`app.core.config`). Key settings: `DATABASE_URL` (required), `REDIS_URL`, `JWT_SECRET_KEY` (required in production), `TRANSIT_FEEDS_JSON`, `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`, `OBSIDIAN_API_KEY`, `DEMO_USER_PASSWORD`, `DB_POOL_SIZE`/`DB_POOL_MAX_OVERFLOW`/`DB_POOL_RECYCLE`, `POLLER_LEADER_LOCK_TTL`. Full list in `.env.example` and `app/core/config.py`.
