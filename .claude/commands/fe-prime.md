---
description: Load full VTV frontend context into the current session
argument-hint:
allowed-tools: Read, Glob, Grep, Bash(pnpm:*), Bash(ls:*)
---

Load complete VTV frontend context — design system, components, pages, i18n, RBAC — for the current session.

@CLAUDE.md
@cms/design-system/vtv/MASTER.md

# Fe-Prime — Load VTV Frontend Context

## Step 0: Index and Use jCodeMunch

Run `index_folder` on this project root if not already indexed. Then **use jcodemunch tools throughout this prime**:
- `get_file_tree` → Step 3 (inventory `cms/apps/web/src/components/ui/`) and Step 4 (inventory pages)
- `get_file_outline` → Step 6 (scan `middleware.ts` and layout for RBAC/nav without full read)
- `search_symbols` → Step 3 (find custom components), Step 7 (check SDK generated types)

## INPUT

You are priming yourself with a complete understanding of the VTV frontend. Read everything before producing output.

## PROCESS

### 1. Read core documentation

The two core docs are loaded via `@` references above. Review them for:
- `CLAUDE.md` — project architecture, conventions, commands (both backend and frontend sections)
- `cms/design-system/vtv/MASTER.md` — global design system rules, spacing, typography, color system

### 2. Inventory design system

- List all files in `cms/design-system/vtv/` to see master doc + page overrides
- Read `cms/packages/ui/src/tokens.css` for the three-tier design token system (primitive → semantic → component)
- Note which pages have design system overrides vs which use only MASTER.md rules

### 3. Inventory components

- List all files in `cms/apps/web/src/components/ui/*.tsx`
- Count installed shadcn/ui components
- Note any custom (non-shadcn) components

### 4. Inventory pages

- List all files matching `cms/apps/web/src/app/[locale]/**/*.tsx`
- Identify which pages exist (login, dashboard, unauthorized, etc.)
- Cross-reference with planned pages from PRD: routes, stops, schedules, GTFS, users, AI chat

### 5. Check i18n state

- Read `cms/apps/web/messages/lv.json` — Latvian translations
- Read `cms/apps/web/messages/en.json` — English translations
- Compare keys: identify missing translations in either language
- Note nav labels, page titles, and form labels defined

### 6. Check auth and RBAC

- Read `cms/apps/web/middleware.ts` for route matchers and role permissions
- Read `cms/apps/web/src/app/[locale]/layout.tsx` for sidebar nav structure
- Note which routes require which roles (admin, dispatcher, editor, viewer)

### 7. Check package state

- Read `cms/apps/web/package.json` for installed dependencies and scripts
- Read `cms/turbo.json` for Turborepo pipeline configuration
- Check if `@vtv/sdk` has generated client code: `cms/packages/sdk/src/client/`

### 8. Assess current state

```
!git status
```

```
!git log --oneline -5
```

```
!ls cms/apps/web/src/app/\[locale\]/
```

## OUTPUT

Present a scannable summary using this structure:

**Project:** VTV Frontend — [one-line description]

**Architecture:** Next.js App Router | React 19 | Tailwind v4 | shadcn/ui | Turborepo monorepo

**Tech Stack:**
- Runtime: [Node.js version, Next.js version, React version]
- Styling: [Tailwind version, design token system]
- Auth: [Auth.js version, RBAC roles]
- i18n: [next-intl, supported locales]
- Build: [Turborepo, pnpm workspaces]

**Pages Implemented:**
- [page name] — [route path] — [auth required? roles?]

**Pages Planned (from PRD/middleware):**
- [page name] — [expected route] — [status: not started]

**Components Available:**
- shadcn/ui: [list of installed components]
- Custom: [list of custom components, if any]

**Design System:**
- Master rules: [key constraints — spacing scale, color system, typography]
- Page overrides: [list of pages with design overrides]
- Token tiers: [primitive → semantic → component]

**i18n Coverage:**
- Languages: [lv, en]
- Key count: [N keys per language]
- Missing: [any keys in one language but not the other]

**RBAC Mapping:**
| Route | Roles |
|-------|-------|
| /dashboard | all authenticated |
| /routes | admin, dispatcher |
| ... | ... |

**SDK State:** [generated / placeholder only]

**Current Branch:** [branch name]
**Recent Changes:** [last 3 commits, one line each]

**Validation Commands:**
```
cd cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint && pnpm --filter @vtv/web build
```

**Next steps:**
- To plan a new page: `/fe-planning [page description]`
- To scaffold a page quickly: `/fe-create-page [page-name]`
- To run quality checks: `/fe-validate`
