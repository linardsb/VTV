---
paths:
  - "app/**/*.py"
  - "alembic/**/*.py"
---

# Backend Rules

## Middleware & Rate Limiting

- `BodySizeLimitMiddleware` (100KB), `RequestLoggingMiddleware` (correlation IDs), `CORSMiddleware`
- Rate limiting via slowapi with Redis storage (cross-worker enforcement, in-memory fallback)
- Rate limits: auth (10/min login, 30/min refresh, 5/min seed), chat (10/min), transit (30/min), knowledge (10-30/min), schedules (5-30/min), drivers (10-30/min), events (10-30/min), skills (5-30/min), health (60/min)
- Query quota: 50/day per IP for LLM chat endpoint (`app.core.agents.quota`)

## Docker Services

- `db` (PostgreSQL + pgvector), `redis` (vehicle position cache + rate limiting + leader election)
- `migrate` (Alembic auto-migration, runs once), `app` (Gunicorn + 4 UvicornWorkers in production, single uvicorn with --reload in dev)
- `cms` (Next.js), `nginx` (reverse proxy on port 80, Brotli + gzip compression, upstream keepalive)
- Services start in dependency order with healthchecks. All behind nginx.

## Configuration

Environment variables via Pydantic Settings (`app.core.config`). Key settings: `DATABASE_URL` (required), `REDIS_URL`, `JWT_SECRET_KEY` (required in production), `TRANSIT_FEEDS_JSON`, `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`, `OBSIDIAN_API_KEY`, `DEMO_USER_PASSWORD`, `DB_POOL_SIZE`/`DB_POOL_MAX_OVERFLOW`/`DB_POOL_RECYCLE`, `POLLER_LEADER_LOCK_TTL`. Full list in `.env.example` and `app/core/config.py`.
