# Plan: Improve Active/Selected State Visibility

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Low
**Route**: N/A (cross-component styling fix)
**Auth Required**: N/A
**Allowed Roles**: N/A

## Feature Description

The sidebar navigation links and route filter toggle items currently lack clear visual distinction when active or selected. From the user's screenshot, "Panelis" (active page) looks identical to "Maršruti" in the sidebar, and selected filter items like "Tramvajs" are barely distinguishable from unselected ones. The selected table row also uses a subtle `bg-surface-raised` that blends with the white background.

This enhancement adds strong, consistent active/selected state styling using the existing design token system — specifically `--color-interactive` (blue-600) for active indicators and `--color-brand-muted` (navy-100) for selected backgrounds.

**Three areas to fix:**
1. **Sidebar navigation** — Add active page indicator (left border + background + bold text)
2. **Route filter toggle group** — Make selected filter item visually distinct (background + text color change)
3. **Route table selected row** — Strengthen the selected row highlight (left border + stronger background)

## Design System

### Master Rules (from MASTER.md)
- Use semantic tokens from tokens.css, never hardcode colors
- CTA/Accent color: `--color-interactive` (blue-600) for interactive elements
- Brand muted: `--color-brand-muted` (navy-100) for subtle active backgrounds
- Focus ring: `--color-focus-ring` (blue-500) for accessibility

### Page Override
- None — this is a cross-component styling fix

### Tokens Used
- `--color-interactive` (oklch blue-600) — Active indicator borders and text
- `--color-brand-muted` (oklch navy-100) — Active/selected background tint
- `--color-foreground` (slate-900) — Active text (already used)
- `--color-surface-raised` (white) — Current selected bg (too subtle, will be replaced)
- `--color-border` (slate-200) — Existing border token

## Components Needed

### Existing (no new installs)
- All changes are to existing components — no new shadcn/ui components needed

### Custom Components to Create
- None

## i18n Keys

No new i18n keys needed — this is a pure styling change.

## Data Fetching

N/A — no data changes.

## RBAC Integration

N/A — no route changes.

## Sidebar Navigation

No new nav items — only styling changes to existing nav links.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/packages/ui/src/tokens.css` — Design token definitions (semantic tier)
- `cms/apps/web/src/components/locale-toggle.tsx` — Example of `usePathname` usage

### Files to Modify
- `cms/apps/web/src/components/app-sidebar.tsx` — Add active page detection and styling
- `cms/apps/web/src/components/routes/route-table.tsx` — Strengthen selected row styling
- `cms/apps/web/src/components/routes/route-filters.tsx` — Strengthen selected toggle item styling

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first in the component body.
- **Shared type changes require ripple-effect tasks** — When adding a field to a shared interface, the plan MUST include tasks to update ALL files that construct objects of that type.

See `cms/apps/web/CLAUDE.md` -> "React 19 Anti-Patterns" for full examples.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add active page detection and styling to sidebar navigation
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify)
**Action:** UPDATE

The sidebar `NavContent` component currently renders all enabled nav links with identical styling:
```tsx
className="block rounded-md px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-raised transition-colors"
```

There is NO active page detection. All links look the same regardless of current route.

**Changes required:**

1. Import `usePathname` from `next/navigation` in the `NavContent` component (NOT in `AppSidebar` — `NavContent` is the component that renders the links).

2. Inside `NavContent`, call `usePathname()` to get the current path. Determine if a nav item is active by comparing:
   - For dashboard (href=""): pathname equals `/${locale}` exactly (no trailing segments)
   - For other items: pathname starts with `/${locale}${item.href}`

3. Replace the single className string on the enabled `<Link>` with conditional styling using `cn()`:

   **Base classes (always applied):**
   ```
   block rounded-md px-3 py-2 text-sm transition-colors
   ```

   **Active classes (when item matches current route):**
   ```
   bg-interactive/10 text-interactive font-semibold border-l-[3px] border-interactive pl-[9px]
   ```
   Note: `pl-[9px]` compensates for the 3px left border so text stays aligned (12px original padding - 3px border = 9px).

   **Inactive classes (when item does NOT match current route):**
   ```
   font-medium text-foreground hover:bg-surface-raised
   ```

4. Import `cn` from `@/lib/utils` (if not already imported).

**Current NavContent signature (for reference):**
```tsx
function NavContent({ locale }: { locale: string }) {
  const t = useTranslations("nav");
  // ... renders nav items
}
```

**Expected result after changes:**
```tsx
function NavContent({ locale }: { locale: string }) {
  const t = useTranslations("nav");
  const pathname = usePathname();

  return (
    <>
      <nav aria-label="Main navigation">
        <p className="text-sm font-semibold text-foreground-muted mb-(--spacing-card)">
          VTV
        </p>
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = item.href === ""
              ? pathname === `/${locale}` || pathname === `/${locale}/`
              : pathname.startsWith(`/${locale}${item.href}`);

            return (
              <li key={item.key}>
                {item.enabled ? (
                  <Link
                    href={`/${locale}${item.href}`}
                    className={cn(
                      "block rounded-md px-3 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-interactive/10 text-interactive font-semibold border-l-[3px] border-interactive pl-[9px]"
                        : "font-medium text-foreground hover:bg-surface-raised"
                    )}
                    aria-current={isActive ? "page" : undefined}
                  >
                    {t(item.key)}
                  </Link>
                ) : (
                  <span className="block rounded-md px-3 py-2 text-sm text-foreground-muted cursor-not-allowed opacity-50">
                    {t(item.key)}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="mt-auto pt-(--spacing-card)">
        <LocaleToggle />
      </div>
    </>
  );
}
```

**Key details:**
- `bg-interactive/10` uses Tailwind's opacity modifier on the `--color-interactive` token (blue-600 at 10% opacity) — gives a clear blue tint
- `text-interactive` uses the interactive color for the text
- `border-l-[3px] border-interactive` adds a prominent left accent bar
- `aria-current="page"` added for accessibility — screen readers announce the current page
- `pl-[9px]` is a compensating padding: the default `px-3` (12px) minus the 3px border width = 9px, so text stays vertically aligned with inactive items

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 2: Strengthen selected route table row styling
**File:** `cms/apps/web/src/components/routes/route-table.tsx` (modify)
**Action:** UPDATE

The current selected row styling is too subtle:
```tsx
selectedRouteId === route.id && "bg-surface-raised"
```

`bg-surface-raised` maps to pure white (`oklch(1 0 0)`) which is barely visible against the white table background.

**Change the className on the `<TableRow>` (around line 154) from:**
```tsx
className={cn(
  "cursor-pointer transition-colors",
  selectedRouteId === route.id && "bg-surface-raised"
)}
```

**To:**
```tsx
className={cn(
  "cursor-pointer transition-colors",
  selectedRouteId === route.id
    ? "bg-interactive/10 border-l-[3px] border-l-interactive"
    : "border-l-[3px] border-l-transparent"
)}
```

**Key details:**
- `bg-interactive/10` — blue-600 at 10% opacity gives a clear blue tint on selected rows (matches sidebar active style)
- `border-l-[3px] border-l-interactive` — left accent border on selected row for instant recognition
- `border-l-[3px] border-l-transparent` — invisible border on unselected rows prevents layout shift when selection changes
- Consistent visual language: blue-tinted background + left border = "selected" across the entire app

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 3: Strengthen selected filter toggle item styling
**File:** `cms/apps/web/src/components/routes/route-filters.tsx` (modify)
**Action:** UPDATE

The `ToggleGroupItem` uses shadcn's default toggle variants which apply `data-[state=on]:bg-accent data-[state=on]:text-accent-foreground`. The `accent` color maps to shadcn defaults (gray), making it barely visible.

**Override the toggle item styling** by adding custom className to each `ToggleGroupItem` in `FilterContent`. The current items look like:
```tsx
<ToggleGroupItem value="all" className="w-full justify-start text-sm">
```

**Change ALL four `ToggleGroupItem` elements** to include active state overrides:
```tsx
<ToggleGroupItem
  value="all"
  className="w-full justify-start text-sm data-[state=on]:bg-interactive/10 data-[state=on]:text-interactive data-[state=on]:font-semibold"
>
```

Apply the same className pattern to all four items (value="all", value="3", value="11", value="0").

**The exact className for each ToggleGroupItem:**
```
w-full justify-start text-sm data-[state=on]:bg-interactive/10 data-[state=on]:text-interactive data-[state=on]:font-semibold
```

**Key details:**
- `data-[state=on]` is the Radix UI data attribute for the active toggle state — it's already set by the ToggleGroup primitive
- `data-[state=on]:bg-interactive/10` — blue tint on active (consistent with sidebar and table)
- `data-[state=on]:text-interactive` — blue text on active
- `data-[state=on]:font-semibold` — bold text for extra emphasis
- These override the default `data-[state=on]:bg-accent` from the toggle variants

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

- [ ] Sidebar nav: active page has blue left border + blue background tint + blue text
- [ ] Sidebar nav: inactive pages have no border, default text color, hover effect still works
- [ ] Sidebar nav: `aria-current="page"` set on active link
- [ ] Route table: selected row has blue left border + blue background tint
- [ ] Route table: unselected rows have transparent border (no layout shift)
- [ ] Filter toggles: selected item has blue background tint + blue text + bold
- [ ] Filter toggles: unselected items retain default appearance
- [ ] No hardcoded colors — all styling uses semantic tokens (`interactive` maps to `--color-interactive`)
- [ ] Visual consistency: all three areas use the same blue-tinted pattern for "active/selected"
- [ ] Mobile: sidebar Sheet nav also shows active state correctly (same NavContent component)

## Acceptance Criteria

This feature is complete when:
- [ ] Active sidebar nav item is clearly distinguishable from inactive items
- [ ] Selected route table row is clearly distinguishable from unselected rows
- [ ] Selected filter toggle item is clearly distinguishable from unselected items
- [ ] Consistent visual language across all three areas (blue tint + left border where applicable)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Accessibility improved with `aria-current="page"` on active nav
- [ ] Ready for `/commit`
