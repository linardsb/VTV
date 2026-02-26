# Plan: Docker Production Hardening

## Feature Metadata
**Feature Type**: Infrastructure Enhancement
**Estimated Complexity**: Medium
**Auth Required**: N/A (infrastructure)

## Feature Description

Harden the Docker deployment for production use while keeping local dev unchanged. Creates a `docker-compose.prod.yml` overlay, adds nginx security headers + gzip, disables `/docs` in production, adds download timeouts to migration script, and provides backup/restore make targets.

## Step-by-Step Tasks

### Task 1: Create `docker-compose.prod.yml`
**Action:** CREATE `docker-compose.prod.yml`
- Remove exposed DB/Redis ports
- Use env-var-based credentials (not hardcoded `postgres:postgres`)
- Increase resource limits for production load
- Mount TLS certs volume on nginx
- Set `ENVIRONMENT=production` on app service
- Remove dev volume mounts (`.:/app`) from app service

### Task 2: Create `.env.production.example`
**Action:** CREATE `.env.production.example`
- Template with all required production secrets
- Comments explaining each variable

### Task 3: Harden `nginx/nginx.conf`
**Action:** UPDATE `nginx/nginx.conf`
- Add gzip compression (JSON, JS, CSS, HTML, XML)
- Add security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy)
- Add response time to log format
- Add cache headers for Next.js static assets (`/_next/static/`)
- Add no-cache on API responses

### Task 4: Disable `/docs` in production — `app/main.py`
**Action:** UPDATE `app/main.py`
- Conditionally set `docs_url=None, openapi_url=None, redoc_url=None` when `ENVIRONMENT != "development"`
- Update root endpoint to hide docs URL in production

### Task 5: Harden `scripts/docker-migrate.py`
**Action:** UPDATE `scripts/docker-migrate.py`
- Add 120s timeout on GTFS download
- Add timing logs for migration and GTFS import durations
- Better error messages

### Task 6: Update `Makefile`
**Action:** UPDATE `Makefile`
- Add `docker-prod` target (uses both compose files)
- Add `docker-prod-down` target
- Add `db-backup` target (pg_dump to timestamped gzip)
- Add `db-restore` target

### Task 7: Update `.env.example`
**Action:** UPDATE `.env.example`
- Add `POSTGRES_PASSWORD` documentation
- Add reference to `.env.production.example`

## Validation

- `uv run ruff format . && uv run ruff check . && uv run mypy app/ && uv run pyright app/ && uv run pytest -v -m "not integration"`
- Manual: `make docker` still works unchanged for local dev
