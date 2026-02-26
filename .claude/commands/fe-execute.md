---
description: Execute a VTV frontend implementation plan file step by step
argument-hint: [path-to-plan] e.g. .agents/plans/fe-routes.md
allowed-tools: Read, Write, Edit, Bash(pnpm:*), Bash(node:*), Bash(npx:*)
---

Implement a frontend plan file step by step following VTV frontend conventions, then validate.

@cms/design-system/vtv/MASTER.md
@.claude/commands/_shared/tailwind-token-map.md
@.claude/commands/_shared/frontend-security.md

# Fe-Execute — Implement Frontend Plan

## INPUT

**Plan file:** $ARGUMENTS

Read the plan file completely before writing any code.

## PROCESS

### 0. Pre-flight checks

Before reading the plan, verify the environment is ready:
- Verify the plan file at `$ARGUMENTS` exists and is readable
- Verify `.agents/plans/` directory exists
- Check that Node.js is available: `node --version`
- Check that pnpm is available: `pnpm --version`
- Verify the frontend workspace exists: `ls cms/apps/web/package.json`
- Verify `node_modules` exists: `ls cms/apps/web/node_modules/.package-lock.json` — if missing, run `cd cms && pnpm install`
- Verify `.env.local` exists: `ls cms/apps/web/.env.local` — if missing, create it from `.env.example` (generate AUTH_SECRET with `openssl rand -base64 32`)

If any pre-flight check fails, STOP and tell the user what's missing.

### 1. Read and understand the plan

- Read the entire plan file from `$ARGUMENTS`
- Identify all files to create and modify
- Note the implementation order and dependencies between steps
- Read all files listed in the "Relevant Files" section
- Read all "Pattern Files" to understand established conventions

### 2. Implement each step

Follow the plan's implementation steps in exact order. For each step:

- Create or modify the specified file
- If you need to deviate from the plan, document why in the output
- Follow VTV frontend conventions:
  - Use semantic design tokens from `tokens.css` (no hardcoded colors)
  - Use `useTranslations` from `next-intl` for all user-visible text
- CRITICAL — Tailwind token rules are loaded via `@_shared/tailwind-token-map.md`. Use the mapping table above for all color decisions. If unsure, check `cms/packages/ui/src/tokens.css`.
  - Server components by default, client components only when needed (`'use client'`)
  - shadcn/ui components with CVA variants where appropriate
  - `cn()` utility for conditional class merging
  - Proper TypeScript types on all components and functions
  - Accessibility: ARIA labels, alt text, keyboard navigation
  - Follow MASTER.md design system rules (spacing, typography, color)
- CRITICAL — React 19 anti-patterns (see `cms/apps/web/CLAUDE.md` for full details):
  - **NEVER use `setState` inside `useEffect`** — This is the #1 most common error. React 19's `react-hooks/set-state-in-effect` rule WILL fail the lint check. Instead of loading data in useEffect and calling setState with the result, use one of these patterns:
    - **Event handler pattern** (preferred): Load data on user action (button click, expand toggle) rather than on mount
    - **Key prop remount pattern**: Pass a `key` prop that changes when you want to re-initialize, and compute initial state from props
    - **useSWR/useQuery pattern**: Use a data-fetching library that manages state externally
    - If you write `useEffect(() => { fetch(...).then(data => setData(data)) }, [])` — STOP and refactor to an event handler or key pattern BEFORE proceeding
  - **Never** define component functions inside other components — extract to module scope
  - **Never** use `Math.random()` in render paths
  - When using const placeholders for runtime values (e.g. `const ROLE = "admin"`), annotate as `string` to avoid TS2367 literal narrowing errors
- CRITICAL — Hook ordering and shared type ripple effects:
  - **`useMemo`/`useCallback` MUST come AFTER the `useState` declarations they depend on** — TypeScript enforces block-scoped variable ordering (TS2448). If a new memo depends on state like `typeFilter`, place it AFTER the `useState<...>(null)` line, not before.
  - **When adding a field to a shared interface** (e.g., adding `routeType` to `BusPosition`), you MUST update ALL files that construct objects of that type — mock data files, test factories, inline literals. Search with `Grep` for the type name constructor pattern (e.g., `BusPosition`) to find all consumers before editing.
- CRITICAL — Server/client boundary for API clients:
  - **`authFetch` uses dynamic imports for dual-context** — it detects `typeof window === "undefined"` and dynamically imports `auth()` (server) or `getSession()` from `next-auth/react` (client). This means `authFetch` works in BOTH server and client components. However, NEVER statically import server-only functions like `auth()` in files that may be imported by `"use client"` components — always use dynamic `await import()` with runtime context detection
  - **When creating new shared fetch/API wrappers**, always consider both server and client usage. If a wrapper calls server-only functions (like Auth.js `auth()`), it MUST use dynamic imports with `typeof window` detection — static imports will break the entire client-side bundle with "Module not found" errors that are hard to debug
  - **API client files called from client-side hooks** (e.g., `use-calendar-events.ts`, `use-vehicle-positions.ts`) can use `authFetch` (which handles dual-context internally), or use plain `fetch()` for public endpoints
  - **Rule of thumb:** For authenticated endpoints, use `authFetch` (works everywhere). For public endpoints called from client hooks, plain `fetch()` is simpler. NEVER create a new wrapper that statically imports `auth()` without dynamic import protection
- CRITICAL — TypeScript `as` casts on untrusted data:
  - **Never use `as` casts on JWT token claims without runtime validation** — JWT payloads are untrusted input. `token.role as VTVRole` is unsafe — a malformed or tampered JWT could inject any string. Always validate with `Array.includes()` and provide a safe fallback: `validRoles.includes(token.role as string) ? (token.role as VTVRole) : "viewer"`
  - This applies to ANY data from external sources: API responses, URL params, localStorage, cookies. Validate before casting
- CRITICAL — Stale Turbopack/Next.js cache:
  - **If module resolution errors persist after fixing imports**, clear the Next.js cache: `rm -rf cms/apps/web/.next` and restart the dev server. Turbopack caches module resolution and may serve stale errors even after the source file is corrected. Always clear `.next` when you see "Module not found" errors that contradict the actual file contents

### 3. Run per-task validation

After each task that creates or modifies a `.tsx` or `.ts` file, run:

```bash
cd cms && pnpm --filter @vtv/web type-check
```

Fix any TypeScript errors before proceeding to the next task.

### 4. Validate — ALL must pass

Run each command in sequence. Fix any issues before moving to the next:

```bash
cd cms && pnpm --filter @vtv/web type-check
```

```bash
cd cms && pnpm --filter @vtv/web lint
```

```bash
cd cms && pnpm --filter @vtv/web build
```

**Error recovery rules:**
- **CRITICAL: After ANY code edit to fix a validation error, re-run from Level 1 (type-check).** Code changes to fix build errors can introduce new TypeScript errors.
- If a check fails, attempt to fix the issue, then re-run ALL checks from Level 1
- Maximum 3 fix attempts per check before stopping
- If you cannot fix after 3 attempts, STOP and report the failures to the user with:
  - Which check failed
  - What you tried
  - The exact error output
  - Do NOT proceed to post-implementation checks with failing validation

### 5. Post-implementation checks

Verify:
- [ ] i18n keys present in both `lv.json` and `en.json` with matching structure
- [ ] Middleware updated with correct route matcher and role permissions
- [ ] Sidebar nav link added with icon, label, and correct href
- [ ] No hardcoded colors — all styling uses semantic tokens or Tailwind theme classes
- [ ] No missing `alt` text on images
- [ ] No missing `aria-label` on interactive elements without visible labels
- [ ] Design tokens from `tokens.css` used consistently
- [ ] Page follows MASTER.md spacing and typography rules

### 6. Design system compliance scan

Scan new/modified `.tsx` files using the rules from the loaded `@_shared/tailwind-token-map.md` reference. Check for all forbidden classes listed in the "Full Forbidden Classes by Category" section. If violations found, fix them using the mapping table.

### 7. Automated security verification

Run the security scans and verify the checklist from the loaded `@_shared/frontend-security.md` reference. Fix any violations immediately before proceeding.

## OUTPUT

Report to the user:
- Files created (with paths)
- Files modified (with paths)
- Components used (shadcn/ui + custom)
- i18n keys added (count per language)
- Validation results (pass/fail for each of the 3 checks)
- Any deviations from the plan and why
- Design system compliance (pass/fail)
- Suggested next step: `/fe-validate` for full check, then `/commit`
