---
description: Diagnose and fix frontend bugs, review findings, TypeScript errors, or design system violations
argument-hint: [description of issue] e.g. "TypeScript error in fleet map component" or "design system violation in geofences page"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(pnpm:*), Bash(npx:*), mcp__jcodemunch__search_symbols, mcp__jcodemunch__find_references, mcp__jcodemunch__get_file_outline, mcp__jcodemunch__get_symbol_source
---

@.claude/commands/_shared/tailwind-token-map.md
@.claude/commands/_shared/frontend-security.md
@.claude/commands/_shared/security-contexts.md

# Frontend Code Review Fix — Diagnose and Fix Issues

Find, diagnose, and fix frontend bugs, code review findings, or quality issues.

## Trigger

Use when: bug report, failing Playwright test, code review comment, TypeScript error, ESLint violation, design system violation, i18n gap, accessibility issue, or any frontend issue that needs fixing rather than new feature development.

**Difference from `/code-review-fix`:** That command takes a review file and works through findings by priority. This command accepts any issue description and diagnoses from scratch.

## Process

### 1. Understand the Issue

Read the user's description (from `$ARGUMENTS` or conversation). Classify:
- **Bug**: unexpected behaviour, runtime error, visual glitch
- **Code review finding**: style, architecture, design system, performance issue
- **Test failure**: failing Playwright test or component test
- **TypeScript error**: type-check failure
- **Design system violation**: hardcoded colors, forbidden Tailwind primitives, non-semantic tokens
- **i18n issue**: missing translation keys, hardcoded strings
- **Accessibility issue**: missing ARIA labels, alt text, form labels

### 2. Reproduce / Locate

**jCodeMunch** (repo from `list_repos`) for component/hook tracing:
- `search_symbols(query, kind)` — find related components/hooks/types
- `find_references(symbol_name)` — trace imports and usage across pages
- `get_file_outline(file_path)` — understand component structure before reading
- `get_symbol_source(symbol_name)` — read just the specific component/hook

Only `Read` the full file when you need to edit it.

**Direct diagnosis by issue type:**
- **Bugs:** Trace the failing path: page → components → hooks → types → API calls
- **Test failures:** Run the specific Playwright test:
  ```bash
  cd cms && pnpm --filter @vtv/web e2e --grep "{test_name}"
  ```
- **TypeScript errors:** Run type-check:
  ```bash
  cd cms && pnpm --filter @vtv/web type-check
  ```
- **Lint errors:** Run ESLint:
  ```bash
  cd cms && pnpm --filter @vtv/web lint
  ```
- **Design system violations:** Grep for forbidden primitives using patterns from `_shared/tailwind-token-map.md`:
  ```bash
  grep -rn "text-gray-\|bg-gray-\|border-gray-\|bg-blue-\|text-blue-" cms/apps/web/src/{target_path}
  ```

### 3. Root Cause Analysis

- Trace the issue to its root cause — don't patch symptoms
- Check if the same pattern exists elsewhere (grep for similar code)
- Identify the minimal set of files that need changes
- For security issues, check the relevant security context from `_shared/security-contexts.md`

### 4. Fix

Apply the fix following VTV frontend conventions:
- **Semantic tokens only** — Reference `_shared/tailwind-token-map.md` for forbidden → allowed mappings
- **i18n** — `useTranslations` for all user-visible text, keys in both `lv.json` and `en.json`
- **API calls** — Use `authFetch` or `@vtv/sdk` wrappers, never raw `fetch`
- **React 19** — No `setState` in `useEffect`, no component definitions inside components
- **Server components** — Default to server components, add `'use client'` only when needed
- **shadcn/ui + CVA** — Use existing components with `cn()` for class merging
- **RBAC** — Middleware route protection + role-based UI gating (admin, dispatcher, editor, viewer)
- **Design system** — MASTER.md rules, transport-domain colors for bus/tram/trolleybus
- **No `as any`** — Use proper types or `as unknown as CorrectType` with justification
- **No `dangerouslySetInnerHTML`** — Use DOMPurify if absolutely necessary

Don't over-engineer — fix the issue, nothing more.

### 5. Verify

Run the frontend validation pyramid on the changes:

```bash
# TypeScript type check
cd cms && pnpm --filter @vtv/web type-check

# Lint
cd cms && pnpm --filter @vtv/web lint

# Build (catches SSR issues, import errors)
cd cms && pnpm --filter @vtv/web build
```

Additionally, grep changed files for design system violations:
- Hardcoded colors (hex, rgb, hsl, oklch)
- Forbidden Tailwind primitives (from `_shared/tailwind-token-map.md`)
- `as any` casts
- Missing `authFetch` usage

Fix any issues introduced by the change. Repeat until all checks pass.

### 6. Report

Summarise:
- **Root cause**: what was wrong and why
- **Fix**: what was changed and in which files
- **Verification**: which checks passed
- **Risk**: any side effects or areas to watch

## Rules

- Fix the root cause, not the symptom
- Don't refactor unrelated code while fixing a bug
- Don't add features — only fix the reported issue
- If the fix requires architectural changes, flag it and suggest `/fe-planning` instead
- Run verification on every file you touch — never skip type checks
- Check the loaded `_shared/tailwind-token-map.md` before writing any Tailwind classes
- Check the loaded `_shared/frontend-security.md` before touching auth or API code
