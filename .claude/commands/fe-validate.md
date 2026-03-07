---
description: Run all VTV frontend quality checks — TypeScript, lint, build, design system, i18n, accessibility
argument-hint:
allowed-tools: Read, Glob, Grep, Bash(pnpm:*), Bash(node:*), Bash(npx:*)
---

@.claude/commands/_shared/tailwind-token-map.md
@.claude/commands/_shared/frontend-security.md

Run all VTV frontend quality checks in sequence and report a pass/fail scorecard.

# Fe-Validate — Run Full VTV Frontend Validation Suite

## Step 0: Use jCodeMunch for Design/i18n/a11y Checks

If the project is indexed via jcodemunch, **use jcodemunch tools in Steps 4-6**:
- `search_symbols` → find component exports to check for design system compliance
- `get_file_outline` → scan page components for accessibility patterns without full reads
- `search_text` → find hardcoded color values, missing i18n keys, `aria-label` gaps

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

Scan all `.tsx` files under `cms/apps/web/src/` using the rules from the loaded `@_shared/tailwind-token-map.md` reference:
- Check for hardcoded colors (hex, rgb, hsl, oklch)
- Check for ALL forbidden Tailwind primitive classes (see "Full Forbidden Classes by Category")
- Check for hardcoded spacing via inline `style` with pixel values
- Verify semantic tokens used from `tokens.css`
- Exceptions: shadcn/ui primitives in `components/ui/`, inline HTML for Leaflet, GTFS route color data

Report violations with file paths and line numbers.

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

### 7. Security Patterns (HARD GATE)

**7a. Automated pattern scan** — Run the security greps from the loaded `@_shared/frontend-security.md` reference. Each grep that returns results is a FAIL. Report file:line for each match.

**7b. Manual verification checklist** (report as WARN, not FAIL):
- [ ] Cookies use `SameSite=Lax` or `Strict`
- [ ] Redirects preserve locale
- [ ] External links use `rel="noopener noreferrer"`
- [ ] File uploads validate type AND size client-side

## OUTPUT

```
Frontend Validation Results:
  1. TypeScript:          PASS / FAIL  [N errors]
  2. Lint:                PASS / FAIL  [N issues]
  3. Build:               PASS / FAIL
  4. Security patterns:   PASS / FAIL  [N violations]
  --- Soft Gates ---
  5. Design system:       PASS / WARN  [N violations]
  6. i18n completeness:   PASS / FAIL  [N missing keys]
  7. Accessibility:       PASS / WARN  [N issues]

Overall: ALL PASS / X FAILURES / Y WARNINGS
```

Checks 1-4 are **hard gates** — must pass before committing.
Checks 5-7 are **soft gates** — warnings are reported but don't block commits. Fix them when practical.

If any hard gate fails, list the specific errors with file paths and line numbers so they can be fixed.

**Next steps:**
- If all hard gates pass: Run `/commit` to commit changes
- If hard gates fail: Fix the reported issues and re-run `/fe-validate`
- If soft gates warn: Consider fixing before commit, or address in a follow-up
