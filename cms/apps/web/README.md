# @vtv/web — VTV Transit Operations CMS

Next.js 16 application for managing Riga's municipal bus operations. Part of the VTV Turborepo monorepo (`cms/`).

## Quick Start

```bash
# From the cms/ root
pnpm install
pnpm --filter @vtv/web dev
```

Visit `http://localhost:3000`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 16.1.6 (App Router) |
| UI | React 19.2.3 |
| Styling | Tailwind CSS v4 + design tokens |
| Components | shadcn/ui + Class Variance Authority |
| Auth | Auth.js v5 with 4-role RBAC |
| i18n | next-intl (Latvian + English) |
| API Client | @vtv/sdk (OpenAPI-generated) |

## Pages

| Page | Route | Auth | Roles |
|------|-------|------|-------|
| Dashboard | `/(dashboard)` | Yes | All |
| Login | `/login` | No | — |
| Unauthorized | `/unauthorized` | No | — |

Additional pages (routes, stops, schedules, GTFS, users, AI chat) are planned per the PRD and referenced in middleware RBAC rules.

## Development Commands

```bash
pnpm --filter @vtv/web dev          # Dev server (port 3000)
pnpm --filter @vtv/web build        # Production build
pnpm --filter @vtv/web type-check   # TypeScript strict check
pnpm --filter @vtv/web lint         # ESLint
```

## Workspace Dependencies

- **@vtv/ui** — Design tokens (`tokens.css`)
- **@vtv/sdk** — TypeScript API client (generated from FastAPI OpenAPI spec)
- **@vtv/typescript-config** — Shared tsconfig presets

## Design System

Uses a three-tier design token system defined in `@vtv/ui`:
- Primitive → Semantic → Component tokens
- OKLCH color space for perceptual uniformity
- Master rules in `cms/design-system/vtv/MASTER.md`

All styling uses semantic tokens — no hardcoded hex/rgb colors.

## i18n

- Primary locale: Latvian (`lv`)
- Secondary locale: English (`en`)
- Messages in `messages/lv.json` and `messages/en.json`
- All user-visible text via `useTranslations()` from `next-intl`

## Auth & RBAC

Four roles: `admin`, `dispatcher`, `editor`, `viewer`. Route protection is enforced in `middleware.ts` with role-based matchers. Defense-in-depth pattern with both middleware and component-level checks.
