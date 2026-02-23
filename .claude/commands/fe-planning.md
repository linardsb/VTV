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
- **Verify component prop APIs from installed versions**: When the plan includes code snippets using third-party component props, check the actual TypeScript definitions in `node_modules/{pkg}/dist/*.d.ts` — not from memory or external docs. Package major versions rename props (e.g., `react-resizable-panels` v4 uses `orientation` not `direction`). Run `grep` on the `.d.ts` files to confirm prop names before writing code snippets.

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

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Common violations and their fixes:

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400`, `text-slate-400` | `text-foreground-subtle` |
| `text-white` (on colored bg) | `text-interactive-foreground` / `text-primary-foreground` |
| `text-blue-*`, `text-red-*`, `text-green-*` | `text-primary`, `text-error`, `text-success` |
| `text-amber-*`, `text-emerald-*`, `text-purple-*` | `text-category-*`, `text-transport-*` |
| `bg-blue-600`, `bg-blue-500` | `bg-primary` or `bg-interactive` |
| `bg-red-500`, `bg-red-600` | `bg-destructive` |
| `bg-red-50` | `bg-error-bg` |
| `bg-green-500`, `bg-emerald-500` | `bg-success` or `bg-status-ontime` |
| `bg-amber-400`, `bg-amber-500` | `bg-category-route-change` or `bg-status-delayed` |
| `bg-purple-600` | `bg-transport-tram` |
| `bg-gray-100`, `bg-slate-100` | `bg-surface` / `bg-muted` |
| `border-gray-200` | `border-border` |
| `border-red-200` | `border-error-border` |
| `border-blue-*`, `border-amber-*`, `border-emerald-*`, `border-purple-*` | `border-transport-*`, `border-category-*` |

**Full semantic token reference** (check `cms/packages/ui/src/tokens.css`):
- **Surface**: `bg-surface`, `bg-surface-raised`, `bg-background`
- **Interactive**: `bg-interactive`, `text-interactive`, `text-interactive-foreground`
- **Error**: `bg-error-bg`, `border-error-border`, `text-error`
- **Status**: `text-status-ontime`, `text-status-delayed`, `text-status-critical`
- **Transport**: `bg-transport-bus`, `bg-transport-trolleybus`, `bg-transport-tram` (+ `text-` and `border-` variants)
- **Calendar**: `bg-category-maintenance`, `bg-category-route-change`, `bg-category-driver-shift`, `bg-category-service-alert`

Exception: Inline HTML strings (e.g., Leaflet `L.divIcon`) may use hex colors since Tailwind classes don't work there. GTFS route color data values (hex stored in DB) are also acceptable.

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
- [ ] All cookies set with `SameSite=Lax` (or `Strict` for auth cookies)
- [ ] Redirects preserve user's current locale (extract from pathname, validate against allowed list)
- [ ] No hardcoded credentials — use env vars for all secrets
- [ ] File uploads validate type AND size client-side before sending
- [ ] Auth tokens stored in httpOnly cookies only (never localStorage)
- [ ] No `dangerouslySetInnerHTML` without DOMPurify sanitization
- [ ] External links use `rel="noopener noreferrer"`
- [ ] User input displayed via React JSX (auto-escaped), never string interpolation

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
