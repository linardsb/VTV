---
description: Execute a VTV frontend implementation plan file step by step
argument-hint: [path-to-plan] e.g. .agents/plans/fe-routes.md
allowed-tools: Read, Write, Edit, Bash(pnpm:*), Bash(node:*), Bash(npx:*)
---

Implement a frontend plan file step by step following VTV frontend conventions, then validate.

@CLAUDE.md
@cms/design-system/vtv/MASTER.md

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
- CRITICAL — Forbidden Tailwind primitive classes (use semantic alternatives):
  - **NEVER use `text-gray-*`, `text-slate-*`, `text-zinc-*`** → use `text-foreground`, `text-foreground-muted`, or `text-foreground-subtle`
  - **NEVER use `bg-blue-*`, `bg-red-*`, `bg-green-*`, `bg-yellow-*`** → use `bg-primary`, `bg-destructive`, `bg-success`, `bg-warning` (or their `-foreground` variants for text on those backgrounds)
  - **NEVER use `text-white` on colored backgrounds** → use `text-primary-foreground`, `text-destructive-foreground`, etc.
  - **NEVER use `border-gray-*`, `border-slate-*`** → use `border-border` or `border-border-subtle`
  - **NEVER use `bg-gray-*`, `bg-slate-*`** → use `bg-surface`, `bg-surface-secondary`, `bg-muted`, `bg-selected-bg`
  - **NEVER use `text-blue-*`, `text-red-*`, `text-green-*`, `text-amber-*`, `text-emerald-*`, `text-purple-*`** → use `text-primary`, `text-error`, `text-success`, `text-transport-*`, `text-category-*`
  - **NEVER use `bg-amber-*`, `bg-emerald-*`, `bg-purple-*`, `bg-orange-*`** → use `bg-category-route-change`, `bg-category-driver-shift`, `bg-transport-tram`, `bg-category-service-alert`
  - **NEVER use `border-blue-*`, `border-red-*`, `border-amber-*`, `border-emerald-*`, `border-purple-*`** → use `border-error-border`, `border-transport-*`, `border-category-*`
  - **NEVER use `bg-red-50`, `border-red-200`, `text-red-700`** → use `bg-error-bg`, `border-error-border`, `text-error`
  - **Common mapping table:**
    | Forbidden | Use Instead |
    |-----------|-------------|
    | `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
    | `text-gray-400`, `text-slate-400` | `text-foreground-subtle` |
    | `text-white` (on colored bg) | `text-interactive-foreground` / `text-primary-foreground` |
    | `bg-blue-600`, `bg-blue-500` | `bg-primary` or `bg-interactive` |
    | `bg-red-500`, `bg-red-600` | `bg-destructive` or `bg-error` |
    | `bg-green-500`, `bg-emerald-500` | `bg-success` or `bg-status-ontime` |
    | `bg-amber-500`, `bg-yellow-500` | `bg-warning` or `bg-status-delayed` |
    | `border-gray-200` | `border-border` |
    | `border-red-200` | `border-error-border` |
    | `bg-gray-100`, `bg-slate-100` | `bg-surface` or `bg-surface-secondary` |
    | `bg-red-50` | `bg-error-bg` |
    | `text-red-700`, `text-red-600` | `text-error` |
    | `bg-blue-400` | `bg-category-maintenance` |
    | `bg-amber-400` | `bg-category-route-change` |
    | `bg-emerald-500` | `bg-category-driver-shift` or `bg-transport-trolleybus` |
    | `bg-purple-600` | `bg-transport-tram` |
    | `text-blue-600` | `text-transport-bus` or `text-interactive` |
    | `text-emerald-500` | `text-transport-trolleybus` or `text-status-ontime` |
    | `text-purple-600` | `text-transport-tram` |
  - If unsure about the correct semantic token, check `cms/packages/ui/src/tokens.css` before writing the class
  - Exception: Inline HTML strings (e.g., Leaflet `L.divIcon` html) may use hex colors since Tailwind classes don't work there — but prefer CSS variables when possible
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
- If a check fails, attempt to fix the issue and re-run that specific check
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

Grep for common violations in new/modified `.tsx` files:

- Search for hardcoded hex colors (`#[0-9a-fA-F]{3,8}`) — except inside inline HTML strings for Leaflet icons
- Search for hardcoded `rgb()` or `hsl()` values
- Search for `style={{ color:` with string literals (should use `var(--color-*)`)
- **Search for ALL Tailwind primitive color classes** — this is the most common violation:
  - **Neutral text**: `text-gray-`, `text-slate-`, `text-zinc-`, `text-neutral-` → `text-foreground-*`
  - **Colored text**: `text-blue-`, `text-red-`, `text-green-`, `text-amber-`, `text-emerald-`, `text-purple-`, `text-orange-` → `text-primary`, `text-error`, `text-success`, `text-transport-*`, `text-category-*`
  - **White text**: `text-white` paired with colored backgrounds → `text-interactive-foreground`, `text-primary-foreground`, `text-destructive-foreground`
  - **Primary backgrounds**: `bg-blue-`, `bg-red-`, `bg-green-`, `bg-yellow-`, `bg-gray-`, `bg-slate-` → `bg-primary`, `bg-destructive`, `bg-success`, `bg-warning`, `bg-surface-*`, `bg-muted`
  - **Domain backgrounds**: `bg-amber-`, `bg-emerald-`, `bg-purple-`, `bg-orange-` → `bg-category-*`, `bg-transport-*`
  - **Error states**: `bg-red-50` → `bg-error-bg`, `border-red-200` → `border-error-border`, `text-red-700` → `text-error`
  - **Primary borders**: `border-gray-`, `border-slate-` → `border-border`
  - **Colored borders**: `border-blue-`, `border-red-`, `border-amber-`, `border-emerald-`, `border-purple-` → `border-error-border`, `border-transport-*`, `border-category-*`
- Verify semantic tokens are used: `--color-surface-*`, `--color-text-*`, `--color-border-*`

If violations found, fix them by replacing with the appropriate semantic class. Use the mapping table from Step 2.

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
