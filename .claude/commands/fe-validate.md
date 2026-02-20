---
description: Run all VTV frontend quality checks — TypeScript, lint, build, design system, i18n, accessibility
argument-hint:
allowed-tools: Read, Glob, Grep, Bash(pnpm:*), Bash(node:*), Bash(npx:*)
---

Run all VTV frontend quality checks in sequence and report a pass/fail scorecard.

# Fe-Validate — Run Full VTV Frontend Validation Suite

## INPUT

No arguments needed. Runs all validation commands against the current frontend codebase state.

## PROCESS

### 0. Pre-flight checks

Before running validation, verify the environment:
- Verify `node_modules` exists: `ls cms/apps/web/node_modules/.package-lock.json` — if missing, run `cd cms && pnpm install`
- Verify `.env.local` exists: `ls cms/apps/web/.env.local` — if missing, create it from `.env.example` (generate AUTH_SECRET with `openssl rand -base64 32`)

Run each check in order. Report results for each before moving to the next.

### 1. TypeScript Type Check

```bash
cd cms && pnpm --filter @vtv/web type-check
```

### 2. Lint

```bash
cd cms && pnpm --filter @vtv/web lint
```

### 3. Build

```bash
cd cms && pnpm --filter @vtv/web build
```

### 4. Design System Compliance

Scan all `.tsx` files under `cms/apps/web/src/` for design system violations:

- **Hardcoded colors**: Search for hex colors (`#[0-9a-fA-F]{3,8}`), `rgb(`, `hsl(`, `oklch(` in style attributes and className strings
- **Tailwind primitive color classes** (most common violation — LLMs default to these):
  - Search for `text-gray-`, `text-slate-`, `text-zinc-`, `text-neutral-` → should be `text-foreground`, `text-foreground-muted`, `text-foreground-subtle`
  - Search for `bg-blue-`, `bg-red-`, `bg-green-`, `bg-yellow-`, `bg-gray-`, `bg-slate-` → should be `bg-primary`, `bg-destructive`, `bg-success`, `bg-warning`, `bg-surface-*`, `bg-muted`
  - Search for `text-white` in className (on colored backgrounds) → should be `text-primary-foreground`, `text-destructive-foreground`, etc.
  - Search for `border-gray-`, `border-slate-` → should be `border-border`
  - Exceptions: shadcn/ui primitive files in `components/ui/`, inline HTML strings for Leaflet icons
- **Hardcoded spacing**: Search for inline `style` with pixel values for margin/padding that should use design tokens
- **Token usage**: Verify pages use semantic tokens (`--color-surface-*`, `--color-text-*`, `--color-border-*`, `--spacing-*`) from `cms/packages/ui/src/tokens.css`

Report violations with file paths and line numbers. Minor violations in third-party or auto-generated component files (e.g., shadcn/ui primitives) are acceptable.

### 5. i18n Completeness

- Read `cms/apps/web/messages/lv.json` and `cms/apps/web/messages/en.json`
- Compare top-level keys: every key in `lv.json` must exist in `en.json` and vice versa
- Compare nested keys recursively
- Report any missing keys with their path (e.g., `routes.title` missing in `en.json`)

### 6. Accessibility Spot-Check

Scan `.tsx` files under `cms/apps/web/src/app/` for common accessibility issues:

- `<img` tags without `alt` attribute
- `<button` without `aria-label` (when no visible text child)
- `<input` without associated `<label` or `aria-label`
- `<a` tags without `href` or with `href="#"`
- Missing `role` attributes on interactive custom components

Report findings with file paths and line numbers.

## OUTPUT

```
Frontend Validation Results:
  1. TypeScript:          PASS / FAIL  [N errors]
  2. Lint:                PASS / FAIL  [N issues]
  3. Build:               PASS / FAIL
  4. Design system:       PASS / WARN  [N violations]
  5. i18n completeness:   PASS / FAIL  [N missing keys]
  6. Accessibility:       PASS / WARN  [N issues]

Overall: ALL PASS / X FAILURES / Y WARNINGS
```

Checks 1-3 are **hard gates** — must pass before committing.
Checks 4-6 are **soft gates** — warnings are reported but don't block commits. Fix them when practical.

If any hard gate fails, list the specific errors with file paths and line numbers so they can be fixed.

**Next steps:**
- If all hard gates pass: Run `/commit` to commit changes
- If hard gates fail: Fix the reported issues and re-run `/fe-validate`
- If soft gates warn: Consider fixing before commit, or address in a follow-up
