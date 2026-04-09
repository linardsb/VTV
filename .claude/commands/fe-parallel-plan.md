---
description: Parallel frontend research + test scout + TypeScript baseline, then merge into implementation plan
argument-hint: [feature-description] e.g. add fleet telemetry dashboard page
allowed-tools: Read, Glob, Grep, Write, Agent, Bash(pnpm:*), mcp__jcodemunch__get_repo_outline, mcp__jcodemunch__get_file_outline, mcp__jcodemunch__get_file_tree, mcp__jcodemunch__search_symbols, mcp__jcodemunch__find_references, mcp__jdocmunch__search_sections, mcp__jdocmunch__get_section
---

@CLAUDE.md
@cms/design-system/vtv/MASTER.md
@.claude/commands/_shared/tailwind-token-map.md
@.claude/commands/_shared/frontend-security.md
@.claude/commands/_shared/security-contexts.md

# Frontend Parallel Plan — Concurrent Research + Planning

Replaces the sequential `/fe-prime` → `/fe-planning` flow with parallel agent execution.
Three agents run simultaneously, then results merge into a single implementation plan.

## Input

The user provides:
- **Feature description** — what to build (from `$ARGUMENTS`)
- **Plan filename** — where to save (default: `.agents/plans/fe-{feature-slug}.md`)

## Execution

Launch **three agents in parallel** using the Agent tool:

### Agent 1: Researcher (subagent_type: Explore)
```
Research the VTV frontend codebase for implementing: {feature description}

Using jCodeMunch (repo from list_repos):
1. get_file_tree({ "path_prefix": "cms/apps/web/src/app" }) — map all routes/pages
2. get_file_tree({ "path_prefix": "cms/apps/web/src/components" }) — map component tree
3. search_symbols for components/hooks related to: {feature keywords}
4. get_file_outline on the most relevant files found
5. find_references for key components/hooks that will need modification
6. get_file_outline on cms/apps/web/src/app/[locale]/layout.tsx, cms/apps/web/middleware.ts, cms/apps/web/src/lib/auth-fetch.ts

Using jDocMunch (repo: local/VTV):
1. search_sections({ "query": "{feature keywords}", "doc_path": "CLAUDE.md" }) — architecture context
2. search_sections({ "query": "frontend", "doc_path": "CLAUDE.md" }) — frontend conventions
3. search_sections({ "query": "{feature keywords}", "doc_path": "reference/PRD.md" }) — product context

Write a structured research summary including:
- Relevant files and their roles (with file:line references)
- Key components/hooks to modify or extend
- Existing patterns to follow (authFetch, SDK wrappers, SWR hooks, Dialog vs Sheet)
- Tailwind semantic token conventions observed
- RBAC route protection patterns (middleware matcher)
- Sidebar navigation structure
- Dependencies and imports needed
```

### Agent 2: Test Scout (subagent_type: Explore)
```
Find all test files and patterns related to: {feature description}

1. Glob for Playwright test files: cms/apps/web/e2e/**/*.spec.ts
2. Glob for component tests: cms/apps/web/src/**/__tests__/*.test.{ts,tsx}
3. Read Playwright config and test setup files for existing patterns
4. Search for test patterns using Grep:
   - Existing page object patterns
   - Mock patterns and MSW handlers
   - Authentication state reuse (setup project)
5. Check cms/apps/web/src/types/ for existing TypeScript types relevant to this feature
6. Check SDK types: cms/packages/sdk/src/ for API types

Write a structured summary including:
- Related Playwright test files found
- Existing test utilities and page object patterns
- Mock patterns used in this area
- TypeScript types that can be reused (from SDK and local types)
- Test conventions specific to this feature area
```

### Agent 3: TypeScript Baseline (subagent_type: general-purpose)
```
Run TypeScript and lint baseline on the VTV frontend:

1. Run: cd cms && pnpm --filter @vtv/web type-check 2>&1 | tail -20
2. Count current errors
3. Also run: cd cms && pnpm --filter @vtv/web lint 2>&1 | tail -20
4. Report the baseline error counts for both
```

## After All Agents Complete

Combine all three agent results and write the implementation plan following the `/fe-planning` format:

```markdown
# Plan: {Feature Name}

## Context
{Why this change is needed — from user's feature description}

## Security Context Assessment
{Which of CTX-RBAC/INPUT/FILE/AUTH/AGENT apply — from _shared/security-contexts.md}

## Research Summary
{From Agent 1 — relevant files, components/hooks, patterns, RBAC config}

## Test Landscape
{From Agent 2 — existing Playwright tests, SDK types, test patterns}

## Type Check Baseline
{From Agent 3 — current tsc/eslint error counts}

## Design System
{Rules from MASTER.md that apply to this page/feature}
{Semantic tokens to use — from _shared/tailwind-token-map.md}
{Transport-domain colors if applicable}

## i18n Keys
```json
// lv.json additions
{ "{feature}": { "title": "...", "description": "..." } }

// en.json additions
{ "{feature}": { "title": "...", "description": "..." } }
```

## RBAC
- Middleware matcher update: `"/{locale}/{feature}"` → minimum role: {role}
- Sidebar nav entry placement

## Files to Create/Modify
| Action | File | Purpose |
|--------|------|---------|
| CREATE | `cms/apps/web/src/app/[locale]/(dashboard)/{feature}/page.tsx` | Page component |
| UPDATE | `cms/apps/web/messages/lv.json` | i18n keys |
| UPDATE | `cms/apps/web/messages/en.json` | i18n keys |
| UPDATE | `cms/apps/web/middleware.ts` | RBAC route |

## Implementation Steps
1. {Step with exact instructions}
   **Validation:** `cd cms && pnpm --filter @vtv/web type-check`
2. ...

## Preflight Warnings
{Any hardcoded assertions, snapshot tests, or fragile patterns found by Agent 2}

## Security Checklist
- [ ] No `as any` casts
- [ ] API calls use `authFetch` or `@vtv/sdk`
- [ ] No `dangerouslySetInnerHTML` without DOMPurify
- [ ] No hardcoded API URLs
- [ ] No tokens in localStorage

## Verification
- [ ] `cd cms && pnpm --filter @vtv/web type-check` passes
- [ ] `cd cms && pnpm --filter @vtv/web lint` passes
- [ ] `cd cms && pnpm --filter @vtv/web build` passes
- [ ] Semantic Tailwind tokens only (no primitives)
- [ ] i18n keys in both lv.json and en.json
- [ ] TypeScript errors ≤ baseline ({N} errors before)
```

Save to `.agents/plans/fe-{feature-slug}.md`.

## Rules

- All three agents MUST run in parallel — do not wait for one before starting another
- The plan file must not exceed 700 lines (use compact descriptions, tables, `file:line` refs)
- Use semantic Tailwind tokens — NEVER primitive colors (check `_shared/tailwind-token-map.md`)
- Use `authFetch` or SDK wrappers for API calls
- React 19: No setState in useEffect, no component defs inside components, hook ordering rules
- i18n: All user-visible text via `useTranslations`, keys in both lv.json and en.json
- RBAC: Every new page needs middleware route + sidebar nav + role gating
- Security contexts from `_shared/security-contexts.md` must be assessed for every plan
