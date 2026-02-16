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
  - Server components by default, client components only when needed (`'use client'`)
  - shadcn/ui components with CVA variants where appropriate
  - `cn()` utility for conditional class merging
  - Proper TypeScript types on all components and functions
  - Accessibility: ARIA labels, alt text, keyboard navigation
  - Follow MASTER.md design system rules (spacing, typography, color)

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

Grep for common violations:

- Search for hardcoded hex colors (`#[0-9a-fA-F]{3,8}`) in new/modified `.tsx` files
- Search for hardcoded `rgb()` or `hsl()` values
- Search for `style={{ color:` with string literals (should use `var(--color-*)`)
- Verify semantic tokens are used: `--color-surface-*`, `--color-text-*`, `--color-border-*`

If violations found, fix them by replacing with the appropriate design token.

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
