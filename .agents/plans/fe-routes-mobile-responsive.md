# Plan: Routes Page Mobile Responsive Layout

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: `/[locale]/(dashboard)/routes`
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer

## Feature Description

The routes page (`/routes`) currently uses a horizontal `ResizablePanelGroup` layout with a fixed-width filter sidebar (`w-60`), a route table, and a Leaflet map panel side by side. This layout breaks on mobile screens (< 768px) because the resizable panels, filter sidebar, and multi-column table all assume desktop-width viewports.

This enhancement makes the routes page fully responsive by:
1. Replacing the horizontal resizable panel layout with a stacked vertical layout on mobile, using tab-based navigation to switch between Table and Map views
2. Converting the fixed-width filter sidebar into a collapsible Sheet overlay on mobile
3. Simplifying the route table to show fewer columns on small screens
4. Making the app-level sidebar navigation collapse into a hamburger menu on mobile
5. Adding necessary i18n keys for new mobile UI labels (tab names, filter toggle)

The mobile breakpoint is 768px, matching the existing `useIsMobile()` hook in `src/hooks/use-mobile.ts`.

## Design System

### Master Rules (from MASTER.md)
- Responsive: 375px, 768px, 1024px, 1440px breakpoints
- 44x44px minimum touch targets for mobile
- `prefers-reduced-motion` respected
- No horizontal scroll on mobile
- No content hidden behind fixed navbars
- Focus states visible for keyboard navigation

### Page Override
- None exists for routes page. No need to generate one for this responsive-only change.

### Tokens Used
- `--spacing-page` (1rem) — main content padding
- `--spacing-grid` (0.75rem) — gap between sections
- `--spacing-card` (0.75rem) — card/panel internal padding
- `--spacing-tight` (0.25rem) — micro gaps
- `--spacing-inline` (0.375rem) — icon-to-text gaps
- `--color-surface` — filter sheet background
- `--color-foreground-muted` — secondary text
- `--color-border` — dividers
- `--color-interactive` — active tab indicator

## Components Needed

### Existing (shadcn/ui)
- `Sheet` — mobile filter overlay (already used in RouteDetail/RouteForm)
- `Button` — filter toggle, tab buttons
- `Badge` — status badges in table

### New shadcn/ui to Install
- `Tabs` — `npx shadcn@latest add tabs` — for Table/Map view switching on mobile

### Custom Components to Create
- None. All changes are modifications to existing components.

### Existing Hooks Used
- `useIsMobile()` from `src/hooks/use-mobile.ts` — 768px breakpoint detection

## i18n Keys

### Latvian (`lv.json`)
Add under the existing `"routes"` object:
```json
{
  "routes": {
    "mobile": {
      "tableTab": "Tabula",
      "mapTab": "Karte",
      "showFilters": "Filtri"
    }
  }
}
```

### English (`en.json`)
Add under the existing `"routes"` object:
```json
{
  "routes": {
    "mobile": {
      "tableTab": "Table",
      "mapTab": "Map",
      "showFilters": "Filters"
    }
  }
}
```

## Data Fetching

No changes to data fetching. This is a pure layout/UI enhancement.

## RBAC Integration

No changes needed. The routes page already has proper RBAC via middleware.

## Sidebar Navigation

No changes to sidebar entries. The sidebar itself will become responsive (collapsible on mobile).

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/apps/web/CLAUDE.md` — Frontend-specific conventions and React 19 anti-patterns
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/hooks/use-mobile.ts` — Mobile detection hook (768px breakpoint)
- `cms/apps/web/src/components/ui/sidebar.tsx` — shadcn sidebar with mobile Sheet pattern
- `cms/apps/web/src/components/ui/sheet.tsx` — Sheet component used for overlays

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add Latvian mobile translations
- `cms/apps/web/messages/en.json` — Add English mobile translations
- `cms/apps/web/src/app/[locale]/layout.tsx` — Make sidebar responsive (hamburger on mobile)
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Mobile layout with tabs
- `cms/apps/web/src/components/routes/route-filters.tsx` — Accept `isMobile` prop, render as Sheet on mobile
- `cms/apps/web/src/components/routes/route-table.tsx` — Hide columns on mobile, adjust padding

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367

See `cms/apps/web/CLAUDE.md` -> "React 19 Anti-Patterns" for full examples.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

### Task 0: Install Tabs component
**Action:** INSTALL

Run:
```bash
cd /Users/Berzins/Desktop/VTV/cms && npx shadcn@latest add tabs
```

This installs the Tabs, TabsList, TabsTrigger, TabsContent components from shadcn/ui.

**Per-task validation:**
- Verify `cms/apps/web/src/components/ui/tabs.tsx` exists after installation
- `pnpm --filter @vtv/web type-check` passes

---

### Task 1: Add Latvian mobile i18n keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add a `"mobile"` key inside the existing `"routes"` object, after the existing `"map"` section:

```json
"mobile": {
  "tableTab": "Tabula",
  "mapTab": "Karte",
  "showFilters": "Filtri"
}
```

Also add a `"menu"` key inside the existing `"nav"` object (for the mobile hamburger):

```json
"nav": {
  ...existing keys...,
  "menu": "Izvēlne"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- JSON is valid (no trailing commas, proper nesting)

---

### Task 2: Add English mobile i18n keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add matching keys in the English file:

Inside `"routes"`:
```json
"mobile": {
  "tableTab": "Table",
  "mapTab": "Map",
  "showFilters": "Filters"
}
```

Inside `"nav"`:
```json
"nav": {
  ...existing keys...,
  "menu": "Menu"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- JSON is valid

---

### Task 3: Make app sidebar responsive
**File:** `cms/apps/web/src/app/[locale]/layout.tsx` (modify)
**Action:** UPDATE

The current `Sidebar` component renders a fixed `w-60` aside. On mobile (< 768px), it should be hidden and replaced by a hamburger menu button that opens a Sheet overlay.

**Changes to make:**

1. Add `"use client"` directive to the `Sidebar` component extraction. Since the layout itself is a server component (`async function LocaleLayout`), extract the entire client portion into a separate wrapper. The simplest approach: convert the layout to wrap children in a `ClientShell` component.

2. Create a new client component `MobileNav` at the top of the layout file (or inline). Actually, the cleanest approach is:
   - Keep `LocaleLayout` as the server component (it fetches messages)
   - The `Sidebar` function is already a client-boundary component (it uses `useTranslations`)
   - But it's defined inside the server component file without `"use client"` — it works because `NextIntlClientProvider` wraps it

3. **Revised approach** (simplest, minimal changes):
   - Add the `useIsMobile` hook import and `Sheet` imports to the layout file
   - The `Sidebar` component is a nested function component inside the server layout file. Since it uses `useTranslations`, it only works because it's inside `NextIntlClientProvider`. However, hooks like `useIsMobile` and `useState` require a client component boundary.
   - **Solution:** Extract `Sidebar` into its own file `cms/apps/web/src/components/app-sidebar.tsx` as a `"use client"` component. This is the cleanest approach.

**Create new file:** `cms/apps/web/src/components/app-sidebar.tsx`
```tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useIsMobile } from "@/hooks/use-mobile";
import { LocaleToggle } from "@/components/locale-toggle";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

const navItems = [
  { key: "dashboard", href: "", enabled: true },
  { key: "routes", href: "/routes", enabled: true },
  { key: "stops", href: "/stops", enabled: false },
  { key: "schedules", href: "/schedules", enabled: false },
  { key: "gtfs", href: "/gtfs", enabled: false },
  { key: "users", href: "/users", enabled: false },
  { key: "chat", href: "/chat", enabled: false },
] as const;

interface AppSidebarProps {
  locale: string;
}

function NavContent({ locale }: { locale: string }) {
  const t = useTranslations("nav");

  return (
    <>
      <nav aria-label="Main navigation">
        <p className="text-sm font-semibold text-foreground-muted mb-(--spacing-card)">
          VTV
        </p>
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.key}>
              {item.enabled ? (
                <Link
                  href={`/${locale}${item.href}`}
                  className="block rounded-md px-3 py-2 text-sm font-medium text-foreground hover:bg-surface-raised transition-colors"
                >
                  {t(item.key)}
                </Link>
              ) : (
                <span className="block rounded-md px-3 py-2 text-sm text-foreground-muted cursor-not-allowed opacity-50">
                  {t(item.key)}
                </span>
              )}
            </li>
          ))}
        </ul>
      </nav>
      <div className="mt-auto pt-(--spacing-card)">
        <LocaleToggle />
      </div>
    </>
  );
}

export function AppSidebar({ locale }: AppSidebarProps) {
  const isMobile = useIsMobile();
  const t = useTranslations("nav");
  const [open, setOpen] = useState(false);

  if (isMobile) {
    return (
      <>
        <header className="flex items-center justify-between border-b border-border bg-surface px-(--spacing-page) py-(--spacing-card)">
          <p className="text-sm font-semibold text-foreground">VTV</p>
          <Button
            variant="ghost"
            size="sm"
            className="size-10 p-0"
            onClick={() => setOpen(true)}
            aria-label={t("menu")}
          >
            <Menu className="size-5" />
          </Button>
        </header>
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetContent side="left" className="w-[280px] flex flex-col p-4">
            <SheetHeader>
              <SheetTitle className="sr-only">{t("menu")}</SheetTitle>
            </SheetHeader>
            <NavContent locale={locale} />
          </SheetContent>
        </Sheet>
      </>
    );
  }

  return (
    <aside className="flex w-60 flex-col border-r border-border bg-surface p-4">
      <NavContent locale={locale} />
    </aside>
  );
}
```

**Then update `layout.tsx`:**
- Remove the inline `Sidebar` function definition and all its imports (`Link`, `LocaleToggle`)
- Import `AppSidebar` from `@/components/app-sidebar`
- Replace `<Sidebar locale={locale} />` with `<AppSidebar locale={locale} />`
- Change the outer div from `flex min-h-screen` to `flex min-h-screen flex-col md:flex-row` so mobile stacks vertically
- Update `<main>` to be `flex-1 overflow-auto p-(--spacing-page)` (add `overflow-auto`)

The simplified `layout.tsx` should look like:
```tsx
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { AppSidebar } from "@/components/app-sidebar";

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const messages = await getMessages();

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <div className="flex min-h-screen flex-col md:flex-row">
        <AppSidebar locale={locale} />
        <main id="main-content" className="flex-1 overflow-auto p-(--spacing-page)">
          {children}
        </main>
      </div>
    </NextIntlClientProvider>
  );
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 4: Make RouteFilters responsive
**File:** `cms/apps/web/src/components/routes/route-filters.tsx` (modify)
**Action:** UPDATE

The filter sidebar is currently a fixed `w-60` aside. On mobile, it should render inside a Sheet overlay triggered by a button in the routes page header.

**Changes:**

1. Add an `asSheet` prop to `RouteFiltersProps`:
```tsx
interface RouteFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: RouteType | null;
  onTypeFilterChange: (type: RouteType | null) => void;
  statusFilter: "all" | "active" | "inactive";
  onStatusFilterChange: (status: "all" | "active" | "inactive") => void;
  resultCount: number;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}
```

2. Extract the filter content into a separate function `FilterContent` at module scope (NOT inside `RouteFilters` — React 19 anti-pattern #2):

```tsx
interface FilterContentProps {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: RouteType | null;
  onTypeFilterChange: (type: RouteType | null) => void;
  statusFilter: "all" | "active" | "inactive";
  onStatusFilterChange: (status: "all" | "active" | "inactive") => void;
  resultCount: number;
}

function FilterContent({ search, onSearchChange, typeFilter, onTypeFilterChange, statusFilter, onStatusFilterChange, resultCount }: FilterContentProps) {
  const t = useTranslations("routes");
  // ... all the existing filter JSX (search input, type toggle group, status select, result count)
}
```

3. In `RouteFilters`, conditionally render:
   - If `asSheet` is true: render `<Sheet>` with `FilterContent` inside `SheetContent`
   - If `asSheet` is false/undefined: render the existing `<aside>` wrapping `FilterContent`

Add necessary imports: `Sheet`, `SheetContent`, `SheetHeader`, `SheetTitle` from `@/components/ui/sheet`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 5: Make RouteTable responsive
**File:** `cms/apps/web/src/components/routes/route-table.tsx` (modify)
**Action:** UPDATE

On mobile, the table has too many columns. Hide the Agency and Type columns on small screens using Tailwind responsive classes.

**Changes:**

1. On the `<TableHead>` and `<TableCell>` for the **Type** column, add `className="hidden sm:table-cell w-32"` (hide below 640px)

2. On the `<TableHead>` and `<TableCell>` for the **Agency** column, add `className="hidden md:table-cell w-44"` (hide below 768px)

3. The pagination footer: on mobile, simplify by hiding individual page number links and only showing prev/next. Wrap the page number `PaginationItem` elements with `className="hidden sm:inline-flex"` on the `PaginationItem`.

4. The pagination info text (`"Showing X-Y of Z"`) should be hidden on very small screens: add `className="hidden xs:block text-xs text-foreground-muted"` — or simpler, just use `hidden sm:block`.

Specific class changes:
- Type column `<TableHead>`: change `className="w-32"` to `className="hidden sm:table-cell w-32"`
- Type column `<TableCell>`: add `className="hidden sm:table-cell"`
- Agency column `<TableHead>`: change `className="w-44"` to `className="hidden md:table-cell w-44"`
- Agency column `<TableCell>`: change `className="text-foreground-muted"` to `className="hidden md:table-cell text-foreground-muted"`
- Pagination info `<p>`: add `hidden sm:block` to existing classes
- Page number `<PaginationItem>` wrappers (not prev/next): add `className="hidden sm:inline-flex"`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: Make Routes page layout responsive with tab switching
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` (modify)
**Action:** UPDATE

This is the main task. On mobile, replace the side-by-side `ResizablePanelGroup` with a tabbed interface (Table | Map).

**Changes:**

1. Add imports:
```tsx
import { useIsMobile } from "@/hooks/use-mobile";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Filter } from "lucide-react";  // for filter toggle button
```

2. Inside `RoutesPage`, add:
```tsx
const isMobile = useIsMobile();
const [filterSheetOpen, setFilterSheetOpen] = useState(false);
```

3. **Mobile header**: On mobile, the header should include a filter toggle button. Modify the header section:

```tsx
<div className="flex items-center justify-between">
  <div>
    <h1 className="font-heading text-heading font-semibold text-foreground">
      {t("title")}
    </h1>
    <p className="hidden sm:block text-sm text-foreground-muted">{t("description")}</p>
  </div>
  <div className="flex items-center gap-(--spacing-inline)">
    {isMobile && (
      <Button
        variant="outline"
        size="sm"
        className="cursor-pointer"
        onClick={() => setFilterSheetOpen(true)}
        aria-label={t("mobile.showFilters")}
      >
        <Filter className="mr-1 size-4" aria-hidden="true" />
        {t("mobile.showFilters")}
      </Button>
    )}
    {!IS_READ_ONLY && (
      <Button className="cursor-pointer" onClick={handleCreate}>
        <Plus className="mr-2 size-4" aria-hidden="true" />
        <span className="hidden sm:inline">{t("actions.create")}</span>
        <span className="sm:hidden sr-only">{t("actions.create")}</span>
      </Button>
    )}
  </div>
</div>
```

Note: For the create button on very small screens, we keep the Plus icon visible but can also keep the text. The `hidden sm:inline` + `sr-only` ensures the button stays accessible. Alternatively, keep text always visible since it's short. Simplest: just keep the text always visible.

Revised simpler approach for create button — just keep as-is, it's already fine.

4. **Layout body**: Replace the current `ResizablePanelGroup` with a conditional:

```tsx
{isMobile ? (
  <>
    {/* Mobile filter sheet */}
    <RouteFilters
      search={search}
      onSearchChange={setSearch}
      typeFilter={typeFilter}
      onTypeFilterChange={setTypeFilter}
      statusFilter={statusFilter}
      onStatusFilterChange={setStatusFilter}
      resultCount={filtered.length}
      asSheet
      sheetOpen={filterSheetOpen}
      onSheetOpenChange={setFilterSheetOpen}
    />

    {/* Mobile tabs: Table | Map */}
    <Tabs defaultValue="table" className="flex min-h-0 flex-1 flex-col">
      <TabsList className="w-full">
        <TabsTrigger value="table" className="flex-1 cursor-pointer">
          {t("mobile.tableTab")}
        </TabsTrigger>
        <TabsTrigger value="map" className="flex-1 cursor-pointer">
          {t("mobile.mapTab")}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="table" className="flex-1 overflow-hidden rounded-lg border border-border mt-(--spacing-tight)">
        <RouteTable
          routes={filtered}
          selectedRouteId={selectedRouteId}
          onSelectRoute={handleSelectRoute}
          onEditRoute={handleEdit}
          onDeleteRoute={handleDeleteRequest}
          onDuplicateRoute={handleDuplicate}
          isReadOnly={IS_READ_ONLY}
        />
      </TabsContent>
      <TabsContent value="map" className="flex-1 overflow-hidden rounded-lg border border-border mt-(--spacing-tight)">
        <RouteMap
          buses={MOCK_BUS_POSITIONS}
          selectedRouteId={selectedRouteId}
          onSelectRoute={handleSelectRoute}
        />
      </TabsContent>
    </Tabs>
  </>
) : (
  <ResizablePanelGroup
    orientation="horizontal"
    className="min-h-0 flex-1 overflow-hidden rounded-lg border border-border"
  >
    <ResizablePanel defaultSize={60} minSize={40}>
      <div className="flex h-full">
        <RouteFilters
          search={search}
          onSearchChange={setSearch}
          typeFilter={typeFilter}
          onTypeFilterChange={setTypeFilter}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          resultCount={filtered.length}
        />
        <RouteTable
          routes={filtered}
          selectedRouteId={selectedRouteId}
          onSelectRoute={handleSelectRoute}
          onEditRoute={handleEdit}
          onDeleteRoute={handleDeleteRequest}
          onDuplicateRoute={handleDuplicate}
          isReadOnly={IS_READ_ONLY}
        />
      </div>
    </ResizablePanel>
    <ResizableHandle withHandle />
    <ResizablePanel defaultSize={40} minSize={25}>
      <RouteMap
        buses={MOCK_BUS_POSITIONS}
        selectedRouteId={selectedRouteId}
        onSelectRoute={handleSelectRoute}
      />
    </ResizablePanel>
  </ResizablePanelGroup>
)}
```

5. The `TabsContent` for the map needs a minimum height on mobile so the map renders properly. Add `min-h-[400px]` or use `h-[calc(100vh-200px)]`:

```tsx
<TabsContent value="map" className="min-h-[50vh] flex-1 overflow-hidden rounded-lg border border-border mt-(--spacing-tight)">
```

6. **Important Tailwind v4 note**: Ensure `TabsContent` has proper `data-[state=active]` styles. shadcn Tabs already handles this — inactive tabs get `hidden`. Verify the tab content takes full height by checking the installed tabs component.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 7: Adjust RouteMap height for mobile
**File:** `cms/apps/web/src/components/routes/route-map.tsx` (modify)
**Action:** UPDATE

The map container uses `h-full w-full` which works when the parent has explicit height. On mobile inside a TabsContent, ensure the map has a minimum height.

**Changes:**
- Change the outer div from `className="relative h-full w-full bg-surface"` to `className="relative h-full min-h-[50vh] w-full bg-surface"`
- This ensures the map is visible even when the parent doesn't have an explicit pixel height

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 8: Adjust RouteDetail Sheet for mobile
**File:** `cms/apps/web/src/components/routes/route-detail.tsx` (modify)
**Action:** UPDATE

The detail sheet has `className="w-[400px] sm:w-[400px]"` which is wider than most mobile screens.

**Changes:**
- Change `className="w-[400px] overflow-y-auto sm:w-[400px]"` to `className="w-full overflow-y-auto sm:w-[400px]"`
- This makes the sheet full-width on mobile and 400px on desktop

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 9: Adjust RouteForm Sheet for mobile
**File:** `cms/apps/web/src/components/routes/route-form.tsx` (modify)
**Action:** UPDATE

Same issue as RouteDetail — the form sheet is fixed at 400px.

**Changes:**
- Change `className="w-[400px] overflow-y-auto sm:w-[400px]"` to `className="w-full overflow-y-auto sm:w-[400px]"`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 10: Final validation and build
**Action:** VALIDATE

Run the full 3-level validation pyramid:

```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web lint
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web build
```

If any errors occur, fix them before proceeding. Common issues to watch for:
- Unused imports after refactoring (remove them)
- Missing `"use client"` on new client components
- `useIsMobile` returns `boolean` (may be `false` on SSR initial render — this is fine, the hook handles hydration)
- Tabs component import paths — verify the installed component exports match

---

## Final Validation (3-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: TypeScript**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
```

**Level 2: Lint**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web lint
```

**Level 3: Build**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web build
```

**Success definition:** All 3 levels exit code 0, zero errors.

## Post-Implementation Checks

- [ ] Routes page renders correctly at desktop widths (> 768px) — no regression
- [ ] Routes page renders stacked layout with tabs at mobile widths (< 768px)
- [ ] Table tab shows simplified table (hidden Type/Agency columns on small screens)
- [ ] Map tab shows full Leaflet map with min-height
- [ ] Filter button opens Sheet overlay on mobile
- [ ] Sidebar collapses to hamburger menu on mobile
- [ ] Sheet menus (detail, form, filters) are full-width on mobile
- [ ] i18n keys present in both lv.json and en.json
- [ ] No horizontal scroll on mobile viewport
- [ ] Touch targets are at least 44x44px
- [ ] No hardcoded colors — all styling uses semantic tokens or Tailwind responsive prefixes
- [ ] `prefers-reduced-motion` respected (no new animations added)
- [ ] Build passes with 0 errors

## Acceptance Criteria

This feature is complete when:
- [ ] Routes page is fully usable on 375px mobile viewport
- [ ] Desktop layout (ResizablePanelGroup) is unchanged — no regression
- [ ] Mobile layout uses Tab switching between Table and Map views
- [ ] Filters accessible via Sheet overlay on mobile
- [ ] App sidebar collapses to hamburger on mobile
- [ ] Both languages have complete translations for new mobile UI labels
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages (dashboard, login)
- [ ] Ready for `/commit`
