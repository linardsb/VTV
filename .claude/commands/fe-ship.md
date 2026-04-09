---
description: Full frontend quality pipeline — validate, review, fix, validate
argument-hint:
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(pnpm:*), Bash(npx:*), mcp__jcodemunch__search_symbols, mcp__jcodemunch__find_references, mcp__jcodemunch__get_file_outline, mcp__jcodemunch__get_symbol_source
---

@.claude/commands/_shared/tailwind-token-map.md
@.claude/commands/_shared/frontend-security.md

# Frontend Ship — Full Quality Pipeline

Run the complete validate → review → fix → validate pipeline in one pass.

Use after completing a feature implementation (`/fe-execute`) to catch and fix all issues before commit.

## Phase 1: Initial Validation

Run `/fe-validate` — all 7 levels of the VTV frontend quality checks:

**Hard gates (must pass):**
1. TypeScript type-check (`pnpm --filter @vtv/web type-check`)
2. ESLint lint (`pnpm --filter @vtv/web lint`)
3. Next.js build (`pnpm --filter @vtv/web build`)
4. Security patterns (automated greps from `_shared/frontend-security.md`)

**Soft gates (warnings):**
5. Design system compliance (no hardcoded colors, forbidden Tailwind primitives)
6. i18n completeness (matching keys across lv/en)
7. Accessibility spot-check (alt text, ARIA labels, form labels)

If any hard gate fails, fix before moving to Phase 2.

## Phase 2: Code Review

Run `/fe-review` against the changed files (use `git diff --name-only` to identify them). Check all 8 VTV frontend quality standards:

1. **TypeScript Quality** — Proper types, no `any`, correct server/client boundaries
2. **Design System Compliance** — Semantic tokens from MASTER.md, no hardcoded colors, transport-domain colors for bus/tram/trolleybus
3. **Component Patterns** — shadcn/ui usage, CVA variants, `cn()` utility, appropriate decomposition
4. **Internationalization** — `useTranslations` for all visible text, keys match in both lv.json and en.json
5. **Accessibility** — Alt text, ARIA labels, form labels, focus indicators
6. **RBAC & Auth** — Middleware protection, role-based UI gating (admin/dispatcher/editor/viewer)
7. **Data Fetching & Performance** — Server components for data, Suspense boundaries, no unnecessary `'use client'`
8. **Security** — Context-aware checks (CTX-RBAC/INPUT/FILE/AUTH/AGENT)

Report all findings with severity (critical, warning, suggestion).

## Phase 3: Fix Review Findings

Run `/fe-code-review-fix` for **critical** findings from Phase 2 that violate codified project rules (CLAUDE.md, MASTER.md, `.claude/rules/frontend.md`).

- Fix critical findings that reference specific documented rules
- Optionally fix warnings if they match a documented convention and are trivial (<3 lines)
- Do NOT fix subjective opinions that don't reference a specific project rule

**Skip this phase** if Phase 2 found zero critical issues.

## Phase 4: Final Validation

Run `/fe-validate` again to confirm all fixes are clean. This is the gate — nothing ships if this fails.

If Phase 4 fails after fixes, iterate (fix → validate) until clean, **max 3 rounds**. If still failing after 3 rounds, stop and report the remaining issues for manual intervention.

## Output

End with a single summary table:

```
## Ship Report

| Phase | Result | Details |
|-------|--------|---------|
| 1. Validate | PASS/FAIL | {errors found / clean} |
| 2. Review | {N} critical, {N} warning, {N} suggestion | {key findings} |
| 3. Fix | {N} fixes applied | or "skipped — no critical issues" |
| 4. Validate | PASS/FAIL | {final gate result} |

**Status:** READY TO SHIP / BLOCKED — {reason}
```

## Rules

- Do NOT skip phases — run all 4 in order
- Do NOT commit — this pipeline validates only. User runs `/commit` separately
- If Phase 4 fails after 3 fix rounds, stop and report (don't loop forever)
- If a fix requires architectural changes, stop and recommend `/fe-planning` instead
- Design system violations (hardcoded colors, forbidden primitives) from Phase 2 are critical — must be fixed
