---
description: Research frontend codebase and create a self-contained page/feature implementation plan
argument-hint: [page-description] e.g. add routes management page
allowed-tools: Read, Glob, Grep, Write
---

Research the frontend codebase and produce a self-contained plan that `/fe-execute` can follow without additional context.

@CLAUDE.md
@cms/design-system/vtv/MASTER.md

# Fe-Planning — Create Frontend Implementation Plan

## INPUT

**Feature request:** $ARGUMENTS

Make sure the structured planning is between 400 to 600 lines.

You are creating a detailed implementation plan that ANOTHER AGENT will execute without seeing this conversation. The plan must be completely self-contained with explicit file paths, exact component patterns, and unambiguous steps.

**The test:** Could a developer who knows nothing about this page implement it from the plan alone? If yes, an agent can too.

## PROCESS

### 1. Understand the feature

- Architecture rules and conventions are loaded via `@CLAUDE.md` above
- Design system rules are loaded via `@cms/design-system/vtv/MASTER.md` above
- Read `reference/PRD.md` if the feature relates to product requirements
- Explore existing pages under `cms/apps/web/src/app/[locale]/` to understand established patterns
- Read `cms/apps/web/middleware.ts` to see current RBAC route matchers

### 2. Research existing frontend code

- Identify which existing components this page will use
- List all `cms/apps/web/src/components/ui/*.tsx` — note available shadcn/ui components
- Check `cms/packages/ui/src/tokens.css` for available design tokens
- Read existing pages for patterns:
  - `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — dashboard pattern (server component, i18n, semantic tokens)
  - `cms/apps/web/src/app/[locale]/login/page.tsx` — client component pattern (forms, auth)
- Read `cms/apps/web/messages/lv.json` and `en.json` for existing i18n key structure
- Read `cms/apps/web/src/app/[locale]/layout.tsx` for sidebar nav structure
- Check `cms/apps/web/package.json` for installed dependencies; note any new packages needed

### 3. Check design system overrides

- List files in `cms/design-system/vtv/pages/` — check if a page override already exists for this feature
- If no override exists, note that `/fe-execute` should generate one using the ui-ux-pro-max skill
- If an override exists, read it and incorporate its rules into the plan

### 4. Plan the page

Design the complete page following VTV frontend conventions:
- **Route**: `cms/apps/web/src/app/[locale]/(dashboard)/{page}/page.tsx`
- **Layout**: Optional `layout.tsx` if the page needs sub-navigation or nested routes
- **Components**: Which shadcn/ui components to use, any new custom components needed
- **i18n**: Keys for both `lv.json` and `en.json` (page title, nav label, table headers, button labels, etc.)
- **Data fetching**: Server components for initial data, client components for interactivity
- **RBAC**: Which roles can access, middleware matcher pattern to add
- **Sidebar nav**: Entry to add in locale layout

### 5. Write the plan

Create the plan file at `.agents/plans/fe-{page-name}.md` using this template:

```markdown
# Plan: [Page/Feature Name]

## Feature Metadata
**Feature Type**: [New Page / Enhancement / Component]
**Estimated Complexity**: [Low / Medium / High]
**Route**: `/[locale]/(dashboard)/[page-name]`
**Auth Required**: [Yes / No]
**Allowed Roles**: [admin, dispatcher, editor, viewer]

## Feature Description

[2-3 paragraphs: what this page does, the problem it solves, and user-facing behavior.]

## Design System

### Master Rules (from MASTER.md)
- [Key spacing, typography, color rules that apply]

### Page Override
- [Rules from page-specific override, or "None — generate during execution using ui-ux-pro-max"]

### Tokens Used
- [List specific semantic tokens from tokens.css: --color-surface-*, --color-text-*, --spacing-*, etc.]

## Components Needed

### Existing (shadcn/ui)
- `Button` — [usage context]
- `Table` — [usage context]
- [etc.]

### New shadcn/ui to Install
- `DataTable` — `npx shadcn@latest add data-table`
- [etc.]

### Custom Components to Create
- `{ComponentName}` at `cms/apps/web/src/components/{path}.tsx` — [purpose]

## i18n Keys

### Latvian (`lv.json`)
```json
{
  "[page]": {
    "title": "[Latvian title]",
    "nav": "[Latvian nav label]",
    // ... all keys
  }
}
```

### English (`en.json`)
```json
{
  "[page]": {
    "title": "[English title]",
    "nav": "[English nav label]",
    // ... all keys
  }
}
```

## Data Fetching

- **API endpoints**: [list endpoints from @vtv/sdk or FastAPI backend]
- **Server vs Client**: [which data loads server-side vs client-side]
- **Loading states**: [skeleton patterns to use]

## RBAC Integration

- **Middleware matcher**: Add `"/[locale]/{page-name}"` to matcher config
- **Role permissions**: [which roles, reference existing middleware pattern]

## Sidebar Navigation

- **Label key**: `nav.{page-name}`
- **Icon**: [Lucide icon name]
- **Position**: [after which existing nav item]
- **Role visibility**: [which roles see this nav item]

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Server component with i18n pattern
- `cms/apps/web/src/app/[locale]/login/page.tsx` — Client component with form pattern
- `cms/apps/web/src/app/[locale]/layout.tsx` — Sidebar nav structure

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add Latvian translations
- `cms/apps/web/messages/en.json` — Add English translations
- `cms/apps/web/middleware.ts` — Add route matcher
- `cms/apps/web/src/app/[locale]/layout.tsx` — Add sidebar nav entry

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

CRITICAL: Every task MUST include a **Per-task validation** block:
1. `pnpm --filter @vtv/web type-check` — TypeScript check
2. `pnpm --filter @vtv/web lint` — ESLint/Biome check
3. `pnpm --filter @vtv/web build` — Next.js build (catches SSR issues)
Never omit type-check from per-task validation.

### Task 1: [i18n Keys]
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add keys:
- [exact keys with values]

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: [English i18n Keys]
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add matching keys:
- [exact keys with values]

---

### Task 3: [Page Component]
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/{page}/page.tsx` (create)
**Action:** CREATE

Create server component:
- Import `useTranslations` from next-intl
- Use semantic tokens from tokens.css (no hardcoded colors)
- Follow dashboard page pattern
- Include proper TypeScript types

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task N-1: [Middleware Update]
**File:** `cms/apps/web/middleware.ts` (modify)
**Action:** UPDATE

Add route matcher for `/{page-name}`:
- [exact matcher pattern]
- [role permissions]

---

### Task N: [Sidebar Nav Entry]
**File:** `cms/apps/web/src/app/[locale]/layout.tsx` (modify)
**Action:** UPDATE

Add nav link:
- [exact placement in sidebar]
- [icon, label key, href]

---

## Final Validation (3-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: TypeScript**
```bash
cd cms && pnpm --filter @vtv/web type-check
```

**Level 2: Lint**
```bash
cd cms && pnpm --filter @vtv/web lint
```

**Level 3: Build**
```bash
cd cms && pnpm --filter @vtv/web build
```

**Success definition:** All 3 levels exit code 0, zero errors.

## Post-Implementation Checks

- [ ] Page renders at correct route
- [ ] i18n keys present in both lv.json and en.json
- [ ] Middleware updated with correct role permissions
- [ ] Sidebar nav link added with correct icon and label
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] Accessibility: all interactive elements have labels, images have alt text
- [ ] Design tokens from tokens.css used (not arbitrary Tailwind values)

## Acceptance Criteria

This feature is complete when:
- [ ] Page accessible at `/{locale}/{page-name}`
- [ ] RBAC enforced — unauthorized roles redirected
- [ ] Both languages have complete translations
- [ ] Design system rules followed (MASTER.md + page override if applicable)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`
```

## OUTPUT

1. Save the plan to `.agents/plans/fe-{page-name}.md` (use kebab-case for the filename)
2. Report to the user:
   - Plan file location
   - Summary of what will be created
   - Number of new files and modified files
   - Components needed (existing vs new)
   - i18n keys planned
   - RBAC configuration
   - To execute: `/fe-execute .agents/plans/fe-{page-name}.md`
