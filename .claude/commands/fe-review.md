---
description: Review frontend code against all 8 VTV frontend quality standards
argument-hint: [file-or-directory] e.g. cms/apps/web/src/app/[locale]/(dashboard)/routes/
allowed-tools: Read, Glob, Grep, Write
---

Review frontend code against VTV's 8 frontend quality standards and produce a findings table with fix suggestions.

@CLAUDE.md
@cms/design-system/vtv/MASTER.md

# Fe-Review — Frontend Code Review Against VTV Standards

## INPUT

**Target:** $ARGUMENTS

## PROCESS

Read all files in the target path. For each file, check against VTV's frontend standards in this order:

### 1. TypeScript Quality (CRITICAL)

- All components and functions have proper TypeScript types
- Props interfaces defined for all components
- No `any` types without justification
- No `// @ts-ignore` or `// @ts-expect-error` suppressions without explanation
- Server vs client component boundary is correct (`'use client'` only where needed)
- Async server components typed correctly

### 2. Design System Compliance (CRITICAL)

- No hardcoded colors (hex `#xxx`, `rgb()`, `hsl()`, `oklch()`) in style attributes or className strings
- **No Tailwind primitive color classes** — scan for ALL color families: `text-gray-`, `text-slate-`, `text-blue-`, `text-red-`, `text-amber-`, `text-emerald-`, `text-purple-`, `bg-blue-`, `bg-red-`, `bg-green-`, `bg-amber-`, `bg-emerald-`, `bg-purple-`, `bg-gray-`, `bg-slate-`, `text-white` (on colored backgrounds), `border-gray-`, `border-slate-`, `border-blue-`, `border-red-`. Must use semantic alternatives: `text-foreground-*`, `text-interactive-foreground`, `text-error`, `text-transport-*`, `text-category-*`, `bg-primary`, `bg-destructive`, `bg-error-bg`, `bg-transport-*`, `bg-category-*`, `border-border`, `border-error-border`
- Semantic tokens used from `tokens.css` (`--color-surface-*`, `--color-text-*`, `--color-border-*`, `--color-transport-*`, `--color-category-*`, `--color-error-*`)
- Spacing follows the design system scale (not arbitrary pixel values)
- Typography follows MASTER.md rules (font sizes, weights, line heights)
- Component tokens used where available (`--button-bg`, etc.)
- Third-party/shadcn primitive files are exempt from token checks
- GTFS route color data values (hex stored in DB) are acceptable

### 3. Component Patterns

- shadcn/ui components used correctly (not reimplemented)
- CVA (Class Variance Authority) used for component variants
- `cn()` utility used for conditional class merging (not manual string concatenation)
- Components are appropriately decomposed (not monolithic 500+ line files)
- Reusable components extracted when pattern appears 3+ times

### 4. Internationalization (i18n)

- All user-visible text uses `useTranslations` from `next-intl` (no hardcoded strings)
- Translation keys exist in both `lv.json` and `en.json`
- Keys match between both language files (no missing translations)
- Key naming follows established conventions (`page.section.label`)
- No concatenated translations (use ICU message format for plurals, variables)

### 5. Accessibility (a11y)

- `<img` tags have `alt` attributes (meaningful, not just "image")
- `<button` elements have visible text or `aria-label`
- `<input` elements have associated `<label` or `aria-label`/`aria-labelledby`
- `<a` tags have meaningful `href` (not `href="#"`)
- Interactive custom components have appropriate `role` attributes
- Color contrast: text on backgrounds uses semantic token pairs that meet WCAG AA
- Focus indicators: interactive elements have visible focus rings
- Skip links present in layout

### 6. RBAC & Auth

- Page routes are protected in `middleware.ts` with correct role permissions
- Role-based UI elements (buttons, nav items) check user role before rendering
- No sensitive data exposed to unauthorized roles
- Unauthorized access redirects correctly

### 7. Data Fetching & Performance

- Server components used for initial data loading (not client-side fetch on mount)
- Client components only wrap interactive sections, not entire pages
- Loading states implemented (Suspense boundaries, skeletons)
- No unnecessary `'use client'` directives on components that could be server components
- Images use `next/image` for optimization
- No N+1 data fetching patterns

### 8. Security

- No hardcoded secrets, API keys, or credentials
- No hardcoded demo credentials in auth flows — passwords must come from env vars
- User input sanitized before rendering (XSS prevention)
- External URLs use `rel="noopener noreferrer"` on `target="_blank"` links
- No `dangerouslySetInnerHTML` without sanitization
- Form submissions validate input client-side and rely on server-side validation
- File uploads: client-side size validation before upload (50MB limit)
- Auth tokens stored via httpOnly cookies (Auth.js), never localStorage

## OUTPUT

Present findings in this format:

### Frontend Review: `[target path]`

**Summary:** [1-2 sentence overall assessment]

| File:Line | Standard | Issue | Suggestion | Priority |
|-----------|----------|-------|------------|----------|
| `path:42` | Design System | Hardcoded color `#333` | Use `var(--color-text-primary)` | Critical |
| `path:15` | i18n | Hardcoded string "Submit" | Use `t('form.submit')` | High |
| `path:88` | a11y | `<img` missing alt text | Add descriptive `alt` attribute | Medium |
| `path:3`  | TypeScript | Missing Props interface | Add `interface PageProps` | Medium |

**Priority Guide:**
- **Critical**: Design system violations, security issues, missing RBAC
- **High**: Missing i18n, no TypeScript types, broken accessibility
- **Medium**: Component pattern issues, performance concerns, missing loading states
- **Low**: Style nits, minor improvements

**Stats:**
- Files reviewed: [X]
- Issues: [N] total — [A] Critical, [B] High, [C] Medium, [D] Low

Save the review to `.agents/code-reviews/fe-[target-name]-review.md`.

**Next step:** To fix issues: `/code-review-fix .agents/code-reviews/fe-[target-name]-review.md`
