# Cloudflare Deployment Plan — VTV CMS Frontend

**Date:** 2026-02-25
**Status:** Research complete, waiting for vinext maturity
**Source:** [Cloudflare Blog — Vinext](https://blog.cloudflare.com/vinext/)

## Background

The VTV CMS frontend (Next.js 16 + React 19, Turborepo monorepo) is a candidate for Cloudflare edge deployment. Two paths exist:

1. **Vinext** — Complete Next.js reimplementation on Vite, native CF Workers. Experimental (released Feb 2025).
2. **@cloudflare/next-on-pages** — Stable CF adapter that wraps standard Next.js output. Production-ready.

## What is Vinext

Vinext reimplements the Next.js API surface on Vite (not a wrapper like OpenNext). Drop-in replacement: swap `next` with `vinext` in scripts. Builds with Vite + Rolldown, runs natively on Cloudflare Workers (workerd runtime).

**Key claims:**
- 94% Next.js 16 API coverage
- 4.4x faster production builds (1.67s vs 7.38s with Turbopack)
- 57% smaller client bundles (72.9 KB vs 168.9 KB gzipped)
- Single-command deploy: `vinext deploy`
- Dev server runs in workerd too (dev/prod parity)
- 1,700+ Vitest tests, 380 Playwright E2E tests

**Limitations:**
- Experimental, less than a week old at time of announcement
- No static pre-rendering at build time (TPR is the alternative)
- Monorepo/Turborepo support not explicitly documented
- 6% API surface gap (check README for specifics)

## VTV CMS Compatibility Assessment

### Current Architecture

- 9 pages, 8 are `"use client"` (pure client-side React + fetch)
- 1 API route (Auth.js catch-all `/api/auth/[...nextauth]`)
- Auth.js v5 with Credentials provider (JWT via backend API)
- next-intl v4 for i18n (lv/en), cookie-based locale detection
- Turborepo monorepo: `@vtv/web` (Next.js), `@vtv/ui` (CSS only), `@vtv/sdk` (fetch-based API client)
- `output: "standalone"` in next.config.ts
- Leaflet maps with `ssr: false` dynamic imports

### Hard Blockers (fixable, ~1 hour total)

| # | Issue | File | Fix |
|---|-------|------|-----|
| 1 | `Buffer.from()` — Node.js global | `auth.ts:39` | Replace with `atob()` + base64url decode |
| 2 | `output: "standalone"` | `next.config.ts` | Remove (vinext/CF adapter handles output) |
| 3 | `next/font/google` needs FS | `app/layout.tsx` | Switch to `next/font/local` with self-hosted files |

### Functional Gaps (need design decisions)

| # | Issue | Recommendation |
|---|-------|----------------|
| 4 | In-memory `loginAttempts` Map in `auth.ts` | **Remove** — backend already has Redis brute-force protection. Stateless Workers make the frontend Map ineffective |
| 5 | `cookies()` in server component layouts | Test under vinext/CF adapter. Fallback: move cookie reads to middleware, pass via headers |
| 6 | Auth.js v5 + Credentials provider on Workers | Moderate risk — `authorize()` is just a `fetch()`, `jose` is Web Crypto compatible. Beta-on-beta concern |
| 7 | next-intl `getRequestConfig` uses `cookies()` | Derive locale from URL path (`/lv/`, `/en/`) instead of cookie to avoid `cookies()` dependency |

### Already Compatible (no changes needed)

- All 8 dashboard pages — pure client-side React
- `@vtv/sdk` — uses `fetch()`, no Node APIs
- Leaflet/react-leaflet — already `ssr: false` dynamic imports
- Auth.js catch-all API route — single route, minimal surface
- No `next/image`, no `generateStaticParams`, no legacy SSR patterns
- Middleware RBAC — pure request/response manipulation
- Environment variables (`AUTH_SECRET`, `NEXT_PUBLIC_AGENT_URL`) — standard CF secrets/vars

## Benefits

| Benefit | Impact |
|---------|--------|
| Edge-close latency | CMS users in Latvia served from nearest CF edge node |
| Build speed | 4.4x faster production builds (CI pipeline improvement) |
| Bundle size | 57% smaller client bundles (better for mobile dispatchers) |
| No server management | Eliminates CMS Docker container, nginx frontend proxy |
| Cost | CF Workers free tier (100k req/day) covers internal CMS usage |
| Dev/prod parity | `vinext dev` runs in workerd locally |
| Single-command deploy | `vinext deploy` replaces Docker build + registry + orchestration |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Vinext is experimental (<1 week old) | **HIGH** | Wait for maturity (target Q2 2026 re-evaluation) |
| 94% API coverage gap | Medium | Check README known limitations before migrating |
| Monorepo support unconfirmed | Medium | VTV monorepo is simple (CSS + fetch SDK), likely fine |
| Backend still needs hosting | N/A | Only the frontend moves to CF. Backend (FastAPI + PostgreSQL + Redis) stays on current infra |
| CF platform coupling | Low | Vinext claims portability (30-min Vercel PoC). Minimal CF-specific bindings needed |

## Migration Plan

### Phase 0: Wait (now - Q2 2026)

Vinext is too new. Monitor for:
- Monorepo/Turborepo support confirmation
- Auth.js v5 compatibility reports from community
- next-intl compatibility
- Known limitations list shrinking
- Production success stories beyond early adopters

### Phase 1: Edge-Ready Prep (~2-4 hours)

These changes are good hygiene regardless of deployment target:

1. **Replace `Buffer.from()` with `atob()`** in `cms/apps/web/auth.ts`
   ```ts
   // Before (Node.js only)
   const payload = JSON.parse(Buffer.from(token.split(".")[1], "base64").toString());

   // After (Web API, works everywhere)
   const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, '+').replace(/_/g, '/')));
   ```

2. **Remove in-memory `loginAttempts` Map** from `cms/apps/web/auth.ts`
   - Backend Redis brute-force protection (5 attempts / 15-min lockout) is the real defense
   - Frontend Map was defense-in-depth but breaks on stateless edge

3. **Switch `next/font/google` to `next/font/local`** in `cms/apps/web/src/app/layout.tsx`
   - Download Lexend and Source Sans 3 font files
   - Reference via `next/font/local` with explicit file paths

4. **Derive locale from URL path** in `cms/apps/web/src/i18n/request.ts`
   - Locale is already in the URL (`/lv/`, `/en/`)
   - Removes `cookies()` dependency from i18n config

### Phase 2: Test Migration (~1 day)

```bash
cd cms/apps/web
npm install vinext
npx vinext init
vinext dev                # Test locally in workerd
vinext build              # Verify production build
```

Run Playwright E2E suite against vinext dev server. Target: all 81 tests pass.

### Phase 3: Deploy (~1 hour)

```bash
vinext deploy
```

- Set `AUTH_SECRET` and `NEXT_PUBLIC_AGENT_URL` as CF Worker secrets
- Point DNS to the Worker
- Verify auth flow, RBAC, i18n, all page functionality

### Alternative: @cloudflare/next-on-pages (stable, available now)

If Cloudflare hosting is needed before vinext matures:
- Production-ready, maintained by Cloudflare
- Same blockers to fix (Buffer, fonts, cookies)
- Same benefits (edge deployment, no server management)
- Misses Vite build speed and bundle size improvements
- Well-documented migration path with community support

## Architecture Impact

```
Current:                          After CF Migration:

[nginx :80] ──┬── [cms :3000]    [CF Workers] ── VTV CMS (edge)
               ├── [app :8123]              │
               └── ...                      ▼ fetch()
                                  [Origin Server]
[Docker: 5 containers]            ├── [app :8123] (FastAPI)
                                  ├── [db] (PostgreSQL)
                                  └── [redis] (cache)

                                  [Docker: 3-4 containers]
```

The CMS container and its nginx routing are eliminated. The frontend becomes a globally distributed edge application. The backend API remains on origin infrastructure.

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-25 | Research vinext, defer migration | Too experimental. App is 90% client-side so migration will be straightforward when ready |
| | Phase 1 prep approved | Edge-ready changes improve code quality regardless of deployment target |
