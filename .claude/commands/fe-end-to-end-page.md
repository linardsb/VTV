---
description: Autonomously develop a complete frontend page through all 6 phases (prime, plan, execute, validate, report, commit)
argument-hint: [page-description] e.g. add routes management page
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(pnpm:*), Bash(node:*), Bash(npx:*), Bash(git:*)
---

Run the complete frontend page lifecycle autonomously: prime → plan → execute → validate → report → commit.

@CLAUDE.md
@cms/design-system/vtv/MASTER.md

# Fe-End-to-End-Page — Full Autonomous Frontend Page Lifecycle

## INPUT

**Page request:** $ARGUMENTS

You will autonomously develop this page from research through commit. Follow each phase completely before moving to the next.

## PROCESS

### Phase 1: Prime

```
!git status
```

Load frontend understanding. Architecture and design system context are loaded via `@` references above.

**For all pages:**
- List all files in `cms/design-system/vtv/` to see master doc + page overrides
- Read `cms/packages/ui/src/tokens.css` for the three-tier design token system
- List all `cms/apps/web/src/components/ui/*.tsx` to inventory shadcn/ui components
- List all pages at `cms/apps/web/src/app/[locale]/**/*.tsx`
- Read `cms/apps/web/messages/lv.json` and `en.json` for i18n structure
- Read `cms/apps/web/middleware.ts` for current RBAC route matchers
- Read `cms/apps/web/src/app/[locale]/layout.tsx` for sidebar nav structure
- Check if `@vtv/sdk` has generated client code: `cms/packages/sdk/src/client/`

### Phase 2: Plan

Create a detailed implementation plan:

- Design the page following VTV frontend conventions
- Identify which shadcn/ui components to use (existing vs new to install)
- Plan i18n keys for both Latvian and English
- Design RBAC integration (middleware matcher, role permissions)
- Plan sidebar navigation entry (icon, label, position)
- Check for design system page override, or note one should be generated
- Plan data fetching strategy (server vs client components)
- Save plan to `.agents/plans/fe-[page-name].md`
- Plan must be detailed enough for another agent to execute (400-600 lines)

### Phase 3: Execute

Implement the plan step by step:

- Create all files following VTV frontend conventions
- Use semantic design tokens from `tokens.css` (no hardcoded colors)
- Use `useTranslations` from `next-intl` for all user-visible text
- Server components by default, `'use client'` only when needed
- shadcn/ui components with CVA variants where appropriate
- `cn()` utility for conditional class merging
- Proper TypeScript types on all components and functions
- Accessibility: ARIA labels, alt text, keyboard navigation
- Follow MASTER.md design system rules (spacing, typography, color)
- Add i18n keys to both `lv.json` and `en.json`
- Update middleware with route matcher and role permissions
- Add sidebar navigation entry in locale layout

### Phase 4: Validate

ALL hard gates must pass before proceeding to commit:

```bash
cd cms && pnpm --filter @vtv/web type-check
```

```bash
cd cms && pnpm --filter @vtv/web lint
```

```bash
cd cms && pnpm --filter @vtv/web build
```

**Soft gate checks (warnings, don't block commit):**

- **Design system compliance**: Grep for hardcoded hex colors, `rgb()`, `hsl()` in new `.tsx` files. Also scan for ALL Tailwind primitive color classes (`text-gray-`, `text-slate-`, `text-blue-`, `text-red-`, `text-amber-`, `text-emerald-`, `text-purple-`, `bg-blue-`, `bg-red-`, `bg-green-`, `bg-amber-`, `bg-emerald-`, `bg-purple-`, `bg-gray-`, `bg-slate-`, `text-white`, `border-gray-`, `border-slate-`, `border-blue-`, `border-red-`, `border-amber-`). Replace with semantic tokens from `tokens.css` if found.
- **i18n completeness**: Compare keys in `lv.json` and `en.json` — flag any mismatches.
- **Accessibility spot-check**: Check for `<img` without `alt`, `<button` without `aria-label` (when no visible text), `<input` without `<label` or `aria-label`.

Fix any hard gate failures before moving on. Do not proceed to commit with failing checks.

**Error recovery rules:**
- **CRITICAL: After ANY code edit to fix a validation error, re-run from Level 1 (type-check).** Code changes to fix build errors can introduce new TypeScript errors.
- If a check fails, attempt to fix the issue, then re-run ALL checks from Level 1
- Maximum 3 fix attempts per check
- If still failing after 3 attempts: STOP the entire pipeline and report to the user
  - Do NOT proceed to Phase 5 (Execution Report)
  - Report: which phase failed, what was attempted, exact errors

### Phase 5: Execution Report

Generate a brief execution report comparing implementation vs plan.
Save to `.agents/execution-reports/fe-[page-name].md`.
Note any divergences and their reasons.

### Phase 6: Commit

Stage and commit with conventional format:

- Stage all new and modified files explicitly (not `git add .`)
- Use conventional commit: `feat(cms): [description]`
- Include `Co-Authored-By: Claude <noreply@anthropic.com>`

## OUTPUT

Present a final summary:

**Page:** [name]
**Plan:** `.agents/plans/fe-[page-name].md`

**Files Created:**
- [list with paths]

**Files Modified:**
- [list with paths]

**Validation Results:**
- TypeScript: PASS
- Lint: PASS
- Build: PASS
- Design system: PASS / WARN [N violations]
- i18n completeness: PASS / WARN [N missing keys]
- Accessibility: PASS / WARN [N issues]

**Commit:** `[hash]` — `[commit message]`

**Optional follow-ups:**
- Run architectural review: `/fe-review [path]`
- Process improvement: `/system-review .agents/plans/fe-[page-name].md .agents/execution-reports/fe-[page-name].md`
