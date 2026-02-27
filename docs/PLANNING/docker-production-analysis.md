# Docker & Production Deployment Analysis

> Generated: 2026-02-27

## Project Size on Disk

**Total: ~1.9 GB** (mostly generated artifacts)

| Directory | Size | Description |
|-----------|------|-------------|
| `cms/node_modules/` | 663 MB | npm dependencies |
| `.venv/` | 571 MB | Python virtual environment |
| `cms/apps/web/.next/` | 469 MB | Next.js build cache |
| `.mypy_cache/` | 196 MB | MyPy type-check cache |
| `.git/` | 33 MB | Git history |
| **Source code** (`app/` + `cms/apps/web/src/`) | **~7 MB** | Actual application code |

## Docker Image Sizes

| Image | Base Image | Measured Size |
|-------|------------|---------------|
| **vtv-backend** (FastAPI + Gunicorn) | `python:3.12-slim-bookworm` (189 MB) | ~600 MB (estimated) |
| **vtv-cms** (Next.js standalone) | `node:22-alpine` (230 MB) | **339 MB** (confirmed) |
| **vtv-nginx** (Brotli + reverse proxy) | `nginx:1.27-alpine` (75 MB) | ~80 MB (estimated) |
| **pgvector/pgvector:pg18** | — | 630 MB |
| **redis:7-alpine** | — | 61 MB |
| **Full stack total** | — | **~1.7 GB** |

### Why the Backend is ~600 MB

Heavy ML/AI dependencies: PyMuPDF, Pillow, pydantic-ai, openai, google-genai, pgvector, pytesseract, python-docx. Could be reduced to ~250 MB by splitting AI tools into a separate microservice.

### Build Strategy

All images use **multi-stage builds**:
- **Backend**: `uv` builder stage installs deps → `python:3.12-slim-bookworm` runtime copies only `.venv`
- **CMS**: deps stage → build stage → `node:22-alpine` runner copies only `.next/standalone` + `.next/static` + `public`
- **Nginx**: builder compiles Brotli modules → runtime copies only `.so` files

Requires **BuildKit** (`DOCKER_BUILDKIT=1`) for the backend's `--mount=type=cache` directives.

## Production Resource Allocation

### Development (`docker-compose.yml`)

| Service | CPU | Memory | Notes |
|---------|-----|--------|-------|
| Backend | 1.0 | 512 MB | Single uvicorn with `--reload` |
| CMS | 0.5 | 512 MB | Next.js standalone |
| PostgreSQL | 0.5 | 256 MB | pgvector enabled |
| Redis | 0.25 | 128 MB | Password-protected |
| Nginx | 0.25 | 128 MB | Brotli + gzip compression |
| **Total** | **2.5** | **1.5 GB** | |

### Production (`docker-compose.prod.yml`)

| Service | CPU | Memory | Notes |
|---------|-----|--------|-------|
| Backend | 2.0 | 1 GB | 4 Gunicorn/Uvicorn workers (~200 MB each) |
| CMS | 1.0 | 1 GB | Single Node.js process |
| PostgreSQL | 2.0 | 1 GB | Connection pooling (pool_size=3, max_overflow=5) |
| Redis | 0.5 | 256 MB | GTFS-RT cache, sub-ms reads |
| Nginx | 0.5 | 256 MB | Auto worker_processes |
| **Total** | **6.0** | **3.5 GB** | |

## Production Security Hardening

- **Non-root users** in all containers (`vtv:1001`, `nextjs:1001`, `nginx`)
- **Read-only filesystem** — backend + CMS set `read_only: true`, only `/tmp` writable via tmpfs
- **Capability dropping** — `cap_drop: ALL` with minimal `cap_add` per service
- **`no-new-privileges`** — prevents privilege escalation in all containers
- **No exposed ports** — only nginx exposes 80/443; backend and CMS are internal-only
- **Health checks** — all services have Docker healthchecks with proper `depends_on` ordering
- **External volume protection** — `postgres_data` is `external: true` (survives `docker compose down -v`)

## Nginx Production Features

- **Rate limiting**: 30 req/s API, 2 req/s LLM chat, 60 req/s health
- **Connection limits**: 20 per IP
- **Compression**: Brotli (15-25% better than gzip) with gzip fallback
- **HTTP/2** on HTTPS
- **Smart caching**:
  - Stops: `private, max-age=300, stale-while-revalidate=600` (5 min)
  - Agencies: `private, max-age=3600` (1 hour)
  - Routes: `private, max-age=60, stale-while-revalidate=300` (1 min)
  - Static assets: `public, max-age=31536000, immutable` (1 year)
  - General API: `no-store`
- **Security headers**: CSP, HSTS (2 years + preload), X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, Permissions-Policy
- **Upstream keepalive**: 32 connections to FastAPI, 16 to Next.js
- **Body size limits**: 1 MB default, 10 MB for GTFS import, 52 MB for knowledge uploads

## Throughput Estimates

With 4 Uvicorn workers and ~30ms average API response time:

| Metric | Value |
|--------|-------|
| **Sustained throughput** | ~130 req/s |
| **Burst capacity** | ~200 req/s (with nginx burst buffers) |
| **LLM endpoint** | 2 req/s per IP (rate limited) |
| **Concurrent users** | ~100-200 comfortable |

## Recommended Server Specs

| Tier | Specs | Cost (Hetzner/DO) | Use Case |
|------|-------|-------------------|----------|
| **Minimum** | 4 vCPU / 4 GB RAM | ~$20/mo | Development, staging |
| **Recommended** | 4 vCPU / 8 GB RAM | ~$40/mo | Production (current scale) |
| **Growth** | 8 vCPU / 16 GB RAM | ~$80/mo | Higher concurrency, more workers |

## Optimization Opportunities

| Optimization | Impact | Effort |
|--------------|--------|--------|
| Split AI deps into separate service | Backend image 600→250 MB | Medium |
| Add CDN (Cloudflare) for static assets | Lower latency, offload nginx | Low |
| Alpine base for backend | Image 600→~450 MB | Low (test compatibility) |
| Implement Docker Swarm / K8s | HA, auto-scaling | High (not needed at current scale) |
| Add Prometheus + Grafana | Infrastructure monitoring | Medium |
| Pre-compress static assets (Brotli .br files) | Nginx serves pre-compressed, saves CPU | Low |

## Bottom Line

The stack is **well-architected for small-to-medium production deployment**. Runs comfortably on a single 4-core / 8 GB VPS. Image sizes are typical for Python + Node.js applications. Security hardening is thorough (non-root, read-only, capability dropping, rate limiting). Suitable for Latvia's municipal transit operations scale (dozens of dispatchers/admins, hundreds of daily users).
