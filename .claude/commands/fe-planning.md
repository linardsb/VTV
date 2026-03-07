---
description: Research frontend codebase and create a self-contained page/feature implementation plan
argument-hint: [page-description] e.g. add routes management page
allowed-tools: Read, Glob, Grep, Write, mcp__jcodemunch__get_repo_outline, mcp__jcodemunch__get_file_outline, mcp__jcodemunch__get_file_tree, mcp__jcodemunch__search_symbols
---

Research the frontend codebase and produce a self-contained plan that `/fe-execute` can follow without additional context.

@CLAUDE.md
@cms/design-system/vtv/MASTER.md
@.claude/commands/_shared/tailwind-token-map.md
@.claude/commands/_shared/frontend-security.md
@.claude/commands/_shared/security-contexts.md

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

**Token-efficient exploration (use jCodeMunch when the repo is indexed):**
- Use `get_file_tree` to map `cms/apps/web/src/` structure instead of multiple Glob calls
- Use `get_file_outline` to discover component exports and hook signatures — only `Read` the specific sections that need exact patterns in the plan
- Use `search_symbols` to find existing components, hooks, or utilities by name
- Fall back to `Read` for i18n JSON files, config files, and when you need exact code for the plan's code snippets

- Identify which existing components this page will use
- List all `cms/apps/web/src/components/ui/*.tsx` — note available shadcn/ui components
- Check `cms/packages/ui/src/tokens.css` for available design tokens
- Read existing pages for patterns:
  - `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — dashboard pattern (server component, i18n, semantic tokens)
  - `cms/apps/web/src/app/[locale]/login/page.tsx` — client component pattern (forms, auth)
- Read `cms/apps/web/messages/lv.json` and `en.json` for existing i18n key structure
- Read `cms/apps/web/src/app/[locale]/layout.tsx` for sidebar nav structure
- Check `cms/apps/web/package.json` for installed dependencies; note any new packages needed
- **Verify component prop APIs from installed versions**: When the plan includes code snippets using third-party component props, check the actual TypeScript definitions in `node_modules/{pkg}/dist/*.d.ts` — not from memory or external docs. Package major versions rename props (e.g., `react-resizable-panels` v4 uses `orientation` not `direction`). Run `grep` on the `.d.ts` files to confirm prop names before writing code snippets.

### 3. Security Context Assessment

Using the loaded `@_shared/security-contexts.md` reference, detect which security contexts apply to this frontend feature:

1. **Match** the feature description against frontend-relevant contexts:
   - **CTX-RBAC** — Almost always active for new pages (middleware route protection, role-based UI gating)
   - **CTX-INPUT** — Active if the page has forms, search, or filters (XSS prevention, input validation)
   - **CTX-FILE** — Active if the page has file uploads (client-side type + size validation)
   - **CTX-AUTH** — Active if the page modifies login/session flow (token handling, cookie security)
   - **CTX-AGENT** — Active if the page displays AI-generated content (output sanitization)
2. **List** active contexts in the plan (see template below)
3. **Add** context-specific tasks inline with the implementation tasks they protect

Note: CTX-INFRA is backend-only. Frontend security patterns from `@_shared/frontend-security.md` always apply regardless of contexts.

### 4. Check design system overrides

- List files in `cms/design-system/vtv/pages/` — check if a page override already exists for this feature
- If no override exists, note that `/fe-execute` should generate one using the ui-ux-pro-max skill
- If an override exists, read it and incorporate its rules into the plan

### 5. Plan the page

Design the complete page following VTV frontend conventions:
- **Route**: `cms/apps/web/src/app/[locale]/(dashboard)/{page}/page.tsx`
- **Layout**: Optional `layout.tsx` if the page needs sub-navigation or nested routes
- **Components**: Which shadcn/ui components to use, any new custom components needed
- **i18n**: Keys for both `lv.json` and `en.json` (page title, nav label, table headers, button labels, etc.)
- **Data fetching**: Server components for initial data, client components for interactivity
- **RBAC**: Which roles can access, middleware matcher pattern to add
- **Sidebar nav**: Entry to add in locale layout

### 6. Write the plan

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

## Security Contexts

**Active contexts** (detected from feature scope — see `_shared/security-contexts.md`):
- [CTX-XXX]: [Why this context applies — 1 sentence]

**Not applicable:** [List irrelevant contexts briefly]

Security requirements from active contexts are woven into the implementation tasks below.

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
- **CRITICAL — Server/client boundary for API clients:**
  - `authFetch` (from `src/lib/auth-fetch.ts`) uses dynamic imports for dual-context support: `auth()` on server, `getSession()` on client (detected via `typeof window`). This means `authFetch` works in both server and client components
  - **When creating NEW shared fetch/API wrappers**, NEVER statically import server-only functions (like Auth.js `auth()`). Always use dynamic `await import()` with `typeof window === "undefined"` detection. Static imports of server-only modules break the entire client-side bundle with "Module not found" errors
  - API client files called from client-side hooks can use `authFetch` (handles dual-context internally) or plain `fetch()` for public endpoints
  - Rule: For authenticated endpoints, use `authFetch`. For public endpoints from client hooks, plain `fetch()` is simpler. NEVER create a wrapper that statically imports `auth()`

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

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping table and forbidden class list are loaded via `@_shared/tailwind-token-map.md`. Key rules:
- Use the mapping table for all color decisions
- Check `cms/packages/ui/src/tokens.css` for available tokens
- Exception: Inline HTML strings (Leaflet) may use hex colors. GTFS route color data values are acceptable.

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first in the component body. TypeScript enforces block-scoped variable ordering (TS2448/TS2454). Plan tasks must respect declaration order.
- **Shared type changes require ripple-effect tasks** — When adding a field to a shared interface (e.g., `BusPosition`), the plan MUST include tasks to update ALL files that construct objects of that type (mock data files, test factories, etc.). Search for all usages with `Grep` before finalizing the plan.

See `cms/apps/web/CLAUDE.md` → "React 19 Anti-Patterns" for full examples.

## TypeScript Security Rules

- **Never use `as` casts on JWT token claims without runtime validation** — JWT payloads are untrusted input. `token.role as VTVRole` is unsafe — a malformed JWT could inject any string. Plan must specify `Array.includes()` validation with a safe fallback (e.g., default to `"viewer"`). Example: `validRoles.includes(token.role as string) ? (token.role as VTVRole) : "viewer"`. This applies to ALL external data: API responses, URL params, localStorage, cookies.
- **Clear `.next` cache when module resolution errors persist after fixing imports** — Turbopack caches module resolution aggressively. If you fix an import path but the dev server still shows the old "Module not found" error, the plan should note: `rm -rf cms/apps/web/.next` and restart the dev server.

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

## Security Checklist (verify before marking step complete)

Follow the security checklist from the loaded `@_shared/frontend-security.md` reference. All items must be verified.

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
