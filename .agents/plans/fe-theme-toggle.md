# Plan: Dark/Light Theme Toggle

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Low
**Route**: N/A — global UI control (sidebar widget)
**Auth Required**: Yes (visible in authenticated sidebar only)
**Allowed Roles**: admin, dispatcher, editor, viewer

## Feature Description

Add a theme toggle to the VTV CMS sidebar that allows users to switch between light mode, dark mode, and system preference. The toggle will appear in the sidebar footer alongside the existing locale toggle.

The VTV frontend already has `next-themes` installed (v0.4.6) but not wired up, complete `.dark` CSS variable blocks in both `globals.css` and `tokens.css`, and the Tailwind v4 custom variant `@custom-variant dark (&:is(.dark *))` configured. The only missing pieces are:

1. A `ThemeProvider` wrapping the application
2. A `ThemeToggle` UI component in the sidebar
3. i18n keys for theme labels

The toggle will use an inline icon-based design matching the existing `LocaleToggle` pattern — three small Lucide icons (Sun, Moon, Monitor) in a radio group, with the active option visually highlighted. This keeps the sidebar footer compact and consistent.

## Design System

### Master Rules (from MASTER.md)
- `border-radius: 0` on all components (sharp corners)
- Semantic tokens only — no hardcoded colors
- Cursor pointer on all clickable elements
- Hover states with smooth transitions (150-300ms)
- Focus states visible for keyboard navigation

### Page Override
- None — this is a global sidebar widget, not a page

### Tokens Used
- `text-foreground` — active icon color
- `text-foreground-muted` — inactive icon color
- `hover:text-foreground` — hover state for inactive icons
- `border-border` — separator between icons (if using divider pattern)
- `--spacing-tight` — gap between icons (4px)

## Components Needed

### Existing (shadcn/ui)
- None directly used — the toggle is a custom inline widget

### New shadcn/ui to Install
- None

### Custom Components to Create
- `ThemeProvider` at `cms/apps/web/src/components/theme-provider.tsx` — Client component wrapping `next-themes` `ThemeProvider`
- `ThemeToggle` at `cms/apps/web/src/components/theme-toggle.tsx` — Client component with 3-option inline icon toggle (Sun/Moon/Monitor)

## i18n Keys

### Latvian (`lv.json`)
```json
{
  "theme": {
    "toggle": "Mainīt tēmu",
    "light": "Gaišs",
    "dark": "Tumšs",
    "system": "Sistēma"
  }
}
```

### English (`en.json`)
```json
{
  "theme": {
    "toggle": "Toggle theme",
    "light": "Light",
    "dark": "Dark",
    "system": "System"
  }
}
```

## Data Fetching

- No API calls — theme preference is stored client-side by `next-themes` (localStorage key `theme`)
- No server/client boundary concerns for data fetching

## RBAC Integration

- No middleware changes needed — the toggle is embedded in the sidebar, which is only rendered for authenticated users
- No new route to protect

## Sidebar Navigation

- No new nav link — the toggle is placed in the sidebar footer section alongside `LocaleToggle`, not as a navigation item

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/locale-toggle.tsx` — Inline toggle pattern (FOLLOW THIS PATTERN for `ThemeToggle`)
- `cms/apps/web/src/app/layout.tsx` — Root layout where `ThemeProvider` must be added
- `cms/apps/web/src/app/[locale]/layout.tsx` — Locale layout (reference only, do NOT modify)

### Files to Modify
- `cms/apps/web/src/app/layout.tsx` — Add `ThemeProvider` wrapper
- `cms/apps/web/src/components/app-sidebar.tsx` — Add `ThemeToggle` to footer
- `cms/apps/web/messages/lv.json` — Add Latvian theme translations
- `cms/apps/web/messages/en.json` — Add English theme translations

### Files to Create
- `cms/apps/web/src/components/theme-provider.tsx` — ThemeProvider client component
- `cms/apps/web/src/components/theme-toggle.tsx` — ThemeToggle client component

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

- **Never use `as` casts on JWT token claims without runtime validation** — JWT payloads are untrusted input.
- **Clear `.next` cache when module resolution errors persist after fixing imports** — Turbopack caches module resolution aggressively. If you fix an import path but the dev server still shows the old "Module not found" error: `rm -rf cms/apps/web/.next` and restart the dev server.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

---

### Task 1: Add Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add a new top-level `"theme"` key with the following structure. Place it alphabetically among the existing top-level keys (after `"stops"` and before `"users"`, or wherever alphabetical order dictates):

```json
"theme": {
  "toggle": "Mainīt tēmu",
  "light": "Gaišs",
  "dark": "Tumšs",
  "system": "Sistēma"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- Verify the JSON is valid (no trailing commas, matching braces)

---

### Task 2: Add English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add a matching `"theme"` key at the same position:

```json
"theme": {
  "toggle": "Toggle theme",
  "light": "Light",
  "dark": "Dark",
  "system": "System"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- Verify the JSON is valid

---

### Task 3: Create ThemeProvider Component
**File:** `cms/apps/web/src/components/theme-provider.tsx` (create)
**Action:** CREATE

Create a client component that wraps the `next-themes` `ThemeProvider`. This is a thin wrapper that re-exports the provider as a client component for use in the server-rendered root layout.

```tsx
"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
```

Key configuration:
- `attribute="class"` — Adds/removes `class="dark"` on `<html>`, which matches the existing `.dark` CSS variable blocks in `globals.css` and `tokens.css`, and the Tailwind v4 `@custom-variant dark (&:is(.dark *))` configuration
- `defaultTheme="system"` — Respects user's OS preference on first visit
- `enableSystem` — Enables the "system" option that follows OS preference
- `disableTransitionOnChange` — Prevents flash of unstyled content during theme switches (avoids a brief transition of all colors when toggling)

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 4: Create ThemeToggle Component
**File:** `cms/apps/web/src/components/theme-toggle.tsx` (create)
**Action:** CREATE

Create a client component that renders an inline icon toggle matching the `LocaleToggle` pattern. Read `cms/apps/web/src/components/locale-toggle.tsx` first to match its exact styling patterns.

The toggle displays three Lucide icons in a row separated by `|` dividers, just like `LocaleToggle` shows `LV | EN`:

```
☀ | ☾ | 🖥  (conceptual — actual icons are Lucide SVGs)
```

Implementation:

```tsx
"use client";

import { useTheme } from "next-themes";
import { Sun, Moon, Monitor } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

const themes = [
  { key: "light", icon: Sun },
  { key: "dark", icon: Moon },
  { key: "system", icon: Monitor },
] as const;

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const t = useTranslations("theme");

  return (
    <div
      className="flex items-center gap-(--spacing-tight)"
      role="radiogroup"
      aria-label={t("toggle")}
    >
      {themes.map((item, i) => {
        const Icon = item.icon;
        const isActive = theme === item.key;

        return (
          <span
            key={item.key}
            className="flex items-center gap-(--spacing-tight)"
          >
            {i > 0 && (
              <span
                className="text-xs text-foreground-muted"
                aria-hidden="true"
              >
                |
              </span>
            )}
            <button
              type="button"
              role="radio"
              aria-checked={isActive}
              aria-label={t(item.key)}
              onClick={() => setTheme(item.key)}
              className={cn(
                "cursor-pointer transition-colors duration-200",
                isActive
                  ? "text-foreground"
                  : "text-foreground-muted hover:text-foreground"
              )}
            >
              <Icon className="size-3.5" />
            </button>
          </span>
        );
      })}
    </div>
  );
}
```

Key design decisions:
- **Matches `LocaleToggle` pattern exactly**: same `role="radiogroup"`, same `|` dividers, same `gap-(--spacing-tight)`, same semantic color classes, same transition duration
- **Icons at `size-3.5`** (14px): matches the text-xs size used in `LocaleToggle` for visual consistency
- **Three options**: Light (Sun), Dark (Moon), System (Monitor) — standard `next-themes` theme values
- **`aria-label` on each button**: uses translated theme name for screen readers
- **`aria-label` on container**: uses translated "Toggle theme" for the radiogroup
- **No hydration mismatch**: `useTheme()` returns `undefined` for `theme` on server render. The `cn()` class logic handles `undefined` gracefully — `undefined === "light"` is `false`, so all icons render as inactive during SSR, which is correct (no mismatch)

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 5: Add ThemeProvider to Root Layout
**File:** `cms/apps/web/src/app/layout.tsx` (modify)
**Action:** UPDATE

Import and wrap `{children}` with the `ThemeProvider` component inside `<body>`:

Before:
```tsx
<body className="min-h-screen font-body antialiased">
  <a href="#main-content" className="skip-link">
    {skipLinkText[locale] ?? skipLinkText.lv}
  </a>
  {children}
</body>
```

After:
```tsx
import { ThemeProvider } from "@/components/theme-provider";
// ... (add import at top of file)

<body className="min-h-screen font-body antialiased">
  <ThemeProvider>
    <a href="#main-content" className="skip-link">
      {skipLinkText[locale] ?? skipLinkText.lv}
    </a>
    {children}
  </ThemeProvider>
</body>
```

Key notes:
- `suppressHydrationWarning` is already on the `<html>` element — this is required by `next-themes` and is already present
- The `ThemeProvider` is a client component, but since it only wraps children (doesn't fetch data), it won't de-opt the children from server rendering
- Place the skip link INSIDE the provider so it's accessible from any child component

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 6: Add ThemeToggle to Sidebar
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify)
**Action:** UPDATE

Import `ThemeToggle` and place it in the sidebar footer alongside `LocaleToggle`. Read the file first to find the exact location.

Add import at the top of the file:
```tsx
import { ThemeToggle } from "@/components/theme-toggle";
```

In the `NavContent` component, find the `<div className="mt-2">` that wraps `<LocaleToggle />` (around line 99) and add `ThemeToggle` next to it. Both toggles should sit on the same row for a compact sidebar footer:

Before:
```tsx
<div className="mt-2">
  <LocaleToggle />
</div>
```

After:
```tsx
<div className="mt-2 flex items-center justify-between px-3">
  <ThemeToggle />
  <LocaleToggle />
</div>
```

This places the theme toggle (☀ | ☾ | 🖥) on the left and the locale toggle (LV | EN) on the right within the same row. The `px-3` matches the padding used by the logout button and user info section above. The `justify-between` spreads them across the available width.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

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

- [ ] Theme toggles correctly between light, dark, and system modes
- [ ] Theme preference persists across page refreshes (localStorage)
- [ ] No flash of wrong theme on page load (FOUC)
- [ ] Dark mode CSS variables from `globals.css` activate when dark theme is set
- [ ] Dark mode CSS variables from `tokens.css` activate when dark theme is set
- [ ] Sidebar footer shows both ThemeToggle and LocaleToggle on the same row
- [ ] Theme toggle is accessible: `role="radiogroup"`, `aria-checked`, `aria-label` on each button
- [ ] i18n keys present in both lv.json and en.json
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] All three theme options work: light forces light, dark forces dark, system follows OS
- [ ] Mobile sidebar (Sheet) also shows the theme toggle correctly
- [ ] No hydration warnings in console
- [ ] Design tokens from tokens.css used (not arbitrary Tailwind values)

## Acceptance Criteria

This feature is complete when:
- [ ] ThemeProvider wraps the application at the root layout level
- [ ] Theme toggle appears in sidebar footer for all authenticated users
- [ ] Three theme options work correctly: Light, Dark, System
- [ ] Theme persists via localStorage across sessions
- [ ] Both languages have complete theme translations
- [ ] Design system rules followed (sharp corners, semantic tokens)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`

## Implementation Summary

| Action | Count |
|--------|-------|
| Files to create | 2 (`theme-provider.tsx`, `theme-toggle.tsx`) |
| Files to modify | 4 (`layout.tsx`, `app-sidebar.tsx`, `lv.json`, `en.json`) |
| New dependencies | 0 (`next-themes` already installed) |
| Middleware changes | 0 |
| New routes | 0 |
| i18n keys | 4 per language (8 total) |
