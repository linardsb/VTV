# Plan: Dashboard Resizable Panel Layout

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: `/[locale]/(dashboard)/` (existing page)
**Auth Required**: Yes
**Allowed Roles**: all authenticated (unchanged)

## Feature Description

The dashboard currently has a rigid layout: metric cards at the top, then a fixed-width driver roster (256px) beside the calendar panel. This enhancement replaces the static layout with three resizable panels separated by drag handles, matching the pattern already established on the Routes page (`ResizablePanelGroup` from `react-resizable-panels`).

The three resizable zones are:
1. **Top panel** — Analytics metric cards (Active Vehicles, On-Time Performance, Delayed Routes, Active Routes)
2. **Bottom-left panel** — Driver roster (scrollable list of draggable driver cards)
3. **Bottom-right panel** — Operations calendar (week/month/3-month/year views)

The layout structure is a **nested ResizablePanelGroup**: an outer vertical group splits top (metrics) from bottom, and an inner horizontal group splits the bottom into left (drivers) and right (calendar). Both split boundaries have visible drag handles (`ResizableHandle withHandle`).

On mobile (`< 768px` via `useIsMobile`), resizable panels are not used — the layout falls back to a vertical stack (metrics → calendar), hiding the driver roster as it does today. This preserves touch usability.

**Critical constraint**: Content inside each panel must remain readable and responsive at any panel size. The metric cards adapt from 4-column to 2-column to 1-column based on panel width. The driver roster scrolls vertically. The calendar grid already handles overflow.

## Design System

### Master Rules (from MASTER.md)
- Spacing: `--spacing-grid` (12px) for gap between panels, `--spacing-card` (12px) for internal padding
- Typography: Lexend headings at 18px, Source Sans 3 body at 16px
- Cards: 12px border-radius, card-border/card-bg tokens, shadow-md on hover
- Transitions: 150-300ms for all state changes
- No primitive color classes — semantic tokens only

### Page Override
- None exists for dashboard — no `design-system/vtv/pages/dashboard.md`

### Tokens Used
- `--spacing-grid`: 12px — gap between panels
- `--spacing-section`: 16px — section spacing
- `--spacing-card`: 12px — card internal padding
- `--spacing-tight`: 4px — micro gaps
- `--spacing-inline`: 6px — icon-to-text gaps
- `--color-card-bg`, `--color-card-border` — panel backgrounds
- `--color-border`, `--color-border-subtle` — handle and divider colors
- `--color-foreground`, `--color-foreground-muted` — text hierarchy

## Components Needed

### Existing (already installed)
- `ResizablePanelGroup` — outer vertical + inner horizontal groups (from `@/components/ui/resizable`)
- `ResizablePanel` — three panels (metrics, drivers, calendar)
- `ResizableHandle` — two drag handles (horizontal + vertical), both `withHandle`
- `ScrollArea` — already used by DriverRoster, will add to DashboardMetrics for overflow
- `Skeleton` — loading states (already used)

### New shadcn/ui to Install
- None — all components already available

### Custom Components to Create
- None — this modifies only `dashboard-content.tsx` and `dashboard-metrics.tsx`

## i18n Keys

No new i18n keys needed. This is a pure layout enhancement — all existing translations remain unchanged.

## Data Fetching

No changes to data fetching. All existing hooks remain:
- `useDashboardMetrics()` — SWR, 30s refresh
- `useCalendarEvents()` — SWR via @vtv/sdk, 60s refresh
- `useDriversSummary()` — SWR, 120s refresh

## RBAC Integration

No changes. Dashboard is accessible to all authenticated users. No middleware update needed.

## Sidebar Navigation

No changes. Dashboard is already the default route.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — **KEY REFERENCE** for ResizablePanelGroup pattern (nested horizontal panels with mobile fallback)
- `cms/apps/web/src/components/ui/resizable.tsx` — Component wrappers (prop: `orientation`, not `direction`)

### Files to Modify
- `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — Main layout refactor
- `cms/apps/web/src/components/dashboard/dashboard-metrics.tsx` — Make responsive to constrained height

### Files to Read (understand current structure)
- `cms/apps/web/src/components/dashboard/calendar-panel.tsx` — Props interface
- `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — Internal layout (already `flex h-full flex-col`)
- `cms/apps/web/src/components/dashboard/driver-roster.tsx` — Props interface (already `flex h-full flex-col` with ScrollArea)
- `cms/apps/web/src/components/dashboard/metric-card.tsx` — Card component (takes icon, title, value, subtitle)
- `cms/apps/web/src/hooks/use-mobile.ts` — `useIsMobile()` hook (768px breakpoint)

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Common violations and their fixes:

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400`, `text-slate-400` | `text-foreground-subtle` |
| `text-white` (on colored bg) | `text-interactive-foreground` / `text-primary-foreground` |
| `bg-gray-100`, `bg-slate-100` | `bg-surface` / `bg-muted` |
| `border-gray-200` | `border-border` |

**Full semantic token reference** (check `cms/packages/ui/src/tokens.css`):
- **Surface**: `bg-surface`, `bg-surface-raised`, `bg-background`
- **Card**: `bg-card-bg`, `border-card-border`
- **Interactive**: `bg-interactive`, `text-interactive-foreground`

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **No named Tailwind container sizes** — `max-w-lg` etc. are broken in this project; use explicit rem values: `sm:max-w-[32rem]`
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies**

## TypeScript Security Rules

- **Never use `as` casts on JWT token claims without runtime validation** — The existing `userRole` cast uses `(session?.user?.role as string) ?? ""` which is already in place — do not change it.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

---

### Task 1: Read all relevant files

**Action:** READ (research)

Before making any changes, read every file listed in "Relevant Files" above. Specifically:

1. Read `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — current layout
2. Read `cms/apps/web/src/components/dashboard/dashboard-metrics.tsx` — current metrics grid
3. Read `cms/apps/web/src/components/dashboard/driver-roster.tsx` — verify props
4. Read `cms/apps/web/src/components/dashboard/calendar-panel.tsx` — verify props
5. Read `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — verify internal layout
6. Read `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — reference pattern for ResizablePanelGroup usage
7. Read `cms/apps/web/src/components/ui/resizable.tsx` — verify component exports and prop names
8. Read `cms/apps/web/src/hooks/use-mobile.ts` — verify hook export name

**Per-task validation:** None (read-only step)

---

### Task 2: Update DashboardMetrics for panel-aware responsiveness

**File:** `cms/apps/web/src/components/dashboard/dashboard-metrics.tsx` (modify)
**Action:** UPDATE

The metrics grid currently uses `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4` which works for the full page width. Inside a resizable panel, viewport-based breakpoints (`sm:`, `lg:`) won't respond to the panel width — they respond to the overall viewport. Since CSS container queries are the proper solution but would add complexity, the simplest approach is:

1. Add `ScrollArea` import from `@/components/ui/scroll-area`
2. Wrap the entire metrics grid in a `ScrollArea` with `className="h-full"` so when the top panel is resized very short, the cards remain readable and scroll vertically
3. Change the outer wrapper from a bare `<div>` to have `className="h-full overflow-hidden"` wrapping the ScrollArea
4. Keep the existing grid layout (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`) — it already adapts to width at viewport breakpoints, which is acceptable
5. Apply the same ScrollArea wrapping to the loading skeleton state and the no-data state

**Current code** (the return block for the loaded state, lines 54-86):
```tsx
return (
    <div className="grid grid-cols-1 gap-(--spacing-grid) sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard ... />
      <MetricCard ... />
      <MetricCard ... />
      <MetricCard ... />
    </div>
  );
```

**New code** (wrap in height-aware container with scroll):
```tsx
return (
    <ScrollArea className="h-full">
      <div className="grid grid-cols-1 gap-(--spacing-grid) p-(--spacing-card) sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard ... />
        <MetricCard ... />
        <MetricCard ... />
        <MetricCard ... />
      </div>
    </ScrollArea>
  );
```

Apply the same `ScrollArea` wrapper to:
- The loading skeleton grid (lines 13-21) — wrap in `<ScrollArea className="h-full"><div className="grid ... p-(--spacing-card)">...</div></ScrollArea>`
- The no-data state grid (lines 23-51) — same treatment

**IMPORTANT**: Add `p-(--spacing-card)` to the inner grid div (not on the ScrollArea). This ensures padding is inside the scroll area so content doesn't touch edges. The `p-(--spacing-card)` replaces the external spacing that was previously provided by the parent `space-y-(--spacing-section)`.

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

---

### Task 3: Refactor DashboardContent with nested resizable panels

**File:** `cms/apps/web/src/components/dashboard/dashboard-content.tsx` (modify)
**Action:** UPDATE

This is the main task. Replace the current static layout with nested `ResizablePanelGroup`.

#### 3a: Add imports

Add these imports at the top of the file:

```tsx
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { useIsMobile } from "@/hooks/use-mobile";
```

#### 3b: Add mobile detection

Inside the `DashboardContent` component, after the existing hooks, add:

```tsx
const isMobile = useIsMobile();
```

#### 3c: Replace the layout JSX

The current layout structure (lines 62-108) is:

```tsx
<div className="space-y-(--spacing-section)">
  {/* Page header */}
  <div className="flex items-center justify-between">...</div>

  {/* Metrics panel */}
  <DashboardMetrics />

  {/* Main area: driver roster + calendar */}
  <div className="flex min-h-[calc(100vh-14rem)] gap-(--spacing-grid)">
    <div className="hidden w-64 shrink-0 lg:block">
      <DriverRoster ... />
    </div>
    <div className="min-w-0 flex-1">
      <CalendarPanel ... />
    </div>
  </div>

  {/* Drop action dialog */}
  <DriverDropDialog ... />
</div>
```

Replace with:

```tsx
<div className="flex h-[calc(100vh-var(--spacing-page)*2)] flex-col gap-(--spacing-grid)">
  {/* Page header */}
  <div className="flex shrink-0 items-center justify-between">
    <h1 className="font-heading text-heading font-semibold text-foreground">
      {t("title")}
    </h1>
    <Button asChild variant="outline" className="cursor-pointer">
      <Link href={`/${locale}/routes`}>
        {t("manageRoutes")}
        <ArrowRight className="ml-2 size-4" aria-hidden="true" />
      </Link>
    </Button>
  </div>

  {/* Resizable layout: desktop (panels) vs mobile (stacked) */}
  {isMobile ? (
    <div className="flex min-h-0 flex-1 flex-col gap-(--spacing-grid)">
      {/* Metrics — fixed height on mobile */}
      <DashboardMetrics />

      {/* Calendar takes remaining space */}
      <div className="min-h-0 flex-1">
        <CalendarPanel
          onDayDrop={canSchedule ? handleDayDrop : undefined}
          refetchRef={calendarRefetchRef}
        />
      </div>
    </div>
  ) : (
    <ResizablePanelGroup
      orientation="vertical"
      className="min-h-0 flex-1"
    >
      {/* TOP PANEL: Analytics metric cards */}
      <ResizablePanel defaultSize={20} minSize={10} maxSize={40}>
        <DashboardMetrics />
      </ResizablePanel>

      <ResizableHandle withHandle />

      {/* BOTTOM PANEL: Drivers + Calendar */}
      <ResizablePanel defaultSize={80} minSize={40}>
        <ResizablePanelGroup orientation="horizontal">
          {/* BOTTOM-LEFT: Driver roster */}
          <ResizablePanel defaultSize={25} minSize={15} maxSize={45}>
            <DriverRoster
              drivers={drivers}
              isLoading={driversLoading}
              canDrag={canSchedule}
            />
          </ResizablePanel>

          <ResizableHandle withHandle />

          {/* BOTTOM-RIGHT: Operations calendar */}
          <ResizablePanel defaultSize={75} minSize={40}>
            <CalendarPanel
              onDayDrop={canSchedule ? handleDayDrop : undefined}
              refetchRef={calendarRefetchRef}
            />
          </ResizablePanel>
        </ResizablePanelGroup>
      </ResizablePanel>
    </ResizablePanelGroup>
  )}

  {/* Drop action dialog */}
  <DriverDropDialog
    open={dialogOpen}
    onOpenChange={setDialogOpen}
    driver={dropDriver}
    targetDate={dropDate}
    onEventCreated={handleEventCreated}
  />
</div>
```

#### Key layout decisions explained:

1. **Outer container**: `h-[calc(100vh-var(--spacing-page)*2)]` fills the viewport minus the page padding (same pattern as routes page). `flex-col` stacks header above panels.

2. **Outer ResizablePanelGroup** (`orientation="vertical"`): Splits the page vertically — metrics on top, drivers+calendar on bottom. The horizontal handle between them lets users drag to resize vertically.

3. **Inner ResizablePanelGroup** (`orientation="horizontal"`): Splits the bottom area horizontally — driver roster on left, calendar on right. The vertical handle between them lets users drag to resize horizontally.

4. **Panel sizes**:
   - Top (metrics): `defaultSize={20}`, `minSize={10}`, `maxSize={40}` — starts at ~20% of available height, can shrink to 10% or grow to 40%
   - Bottom area: `defaultSize={80}`, `minSize={40}` — takes remaining space
   - Bottom-left (drivers): `defaultSize={25}`, `minSize={15}`, `maxSize={45}` — starts at 25% of bottom width
   - Bottom-right (calendar): `defaultSize={75}`, `minSize={40}` — takes remaining width

5. **Mobile fallback**: Uses `useIsMobile()` (768px breakpoint) to render a simple stacked layout without resize handles. Driver roster is omitted on mobile (same as current behavior since it was `hidden lg:block`).

6. **Content responsiveness**:
   - `DashboardMetrics` gets `ScrollArea` (from Task 2) so cards scroll when panel is short
   - `DriverRoster` already has `ScrollArea` and `flex h-full flex-col` — it adapts naturally
   - `CalendarGrid` already has `flex h-full flex-col overflow-hidden` — it adapts naturally

#### 3d: Remove the old DriverRoster wrapper

The old code had:
```tsx
<div className="hidden w-64 shrink-0 lg:block">
  <DriverRoster ... />
</div>
```

This is completely replaced by the `ResizablePanel` containing `DriverRoster` in the new layout. Make sure the old `<div className="hidden w-64 shrink-0 lg:block">` wrapper is removed entirely.

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
cd cms && pnpm --filter @vtv/web build
```

---

### Task 4: Verify CalendarGrid fills its panel correctly

**File:** `cms/apps/web/src/components/dashboard/calendar-grid.tsx` (check, modify only if needed)
**Action:** VERIFY / UPDATE (conditional)

Read the file and verify it has `flex h-full flex-col` on its outer div. Currently (line 21):
```tsx
<div className="flex h-full flex-col overflow-hidden rounded-lg border border-card-border bg-card-bg">
```

This is already correct — no changes needed IF it has `h-full`. If it does not have `h-full`, add it.

Also verify that `CalendarPanel` passes height down. The CalendarPanel component just renders `<CalendarGrid events={events} onDayDrop={onDayDrop} />` without a wrapping div, so the CalendarGrid already receives the full panel height. No changes needed.

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
```

---

### Task 5: Verify DriverRoster fills its panel correctly

**File:** `cms/apps/web/src/components/dashboard/driver-roster.tsx` (check, modify only if needed)
**Action:** VERIFY / UPDATE (conditional)

Read the file and verify the outer container has `flex h-full flex-col`. Currently (line 78):
```tsx
<div className="flex h-full flex-col rounded-lg border border-card-border bg-card-bg">
```

This is already correct. No changes needed.

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
```

---

### Task 6: Visual and functional testing checklist

**Action:** VERIFY

After all code changes, perform these manual checks:

1. **Desktop (≥768px)**: Verify both resize handles appear and are draggable
2. **Horizontal handle** (between metrics and drivers/calendar): Drag up and down — metrics cards should scroll when panel is too short, calendar should fill remaining space
3. **Vertical handle** (between drivers and calendar): Drag left and right — driver list scrolls, calendar adapts width
4. **Mobile (<768px)**: Verify stacked layout without resize handles — metrics on top, calendar below, no driver roster visible
5. **Content readability**: At every panel size above the minimum, all text should be readable (not truncated beyond names/badges which already use `truncate`)
6. **Drag-and-drop**: Driver cards should still be draggable onto calendar dates when user has admin/editor role

**Per-task validation (full 3-level pyramid):**

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

---

## Implementation Details: Complete File Diffs

### File 1: `cms/apps/web/src/components/dashboard/dashboard-metrics.tsx`

**Full target state after modification:**

```tsx
"use client";

import { Bus, Clock, AlertTriangle, MapPin } from "lucide-react";
import { useTranslations } from "next-intl";
import { useDashboardMetrics } from "@/hooks/use-dashboard-metrics";
import { MetricCard } from "./metric-card";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";

export function DashboardMetrics() {
  const { data, isLoading } = useDashboardMetrics();
  const t = useTranslations("dashboard");

  if (isLoading) {
    return (
      <ScrollArea className="h-full">
        <div className="grid grid-cols-1 gap-(--spacing-grid) p-(--spacing-card) sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={`skeleton-${String(i)}`} className="h-24 rounded-lg" />
          ))}
        </div>
      </ScrollArea>
    );
  }

  if (!data) {
    return (
      <ScrollArea className="h-full">
        <div className="grid grid-cols-1 gap-(--spacing-grid) p-(--spacing-card) sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            icon={<Bus className="size-5 text-foreground-muted" aria-hidden="true" />}
            title={t("metrics.activeVehicles")}
            value="—"
            subtitle={t("metrics.unavailable")}
          />
          <MetricCard
            icon={<Clock className="size-5 text-foreground-muted" aria-hidden="true" />}
            title={t("metrics.onTimePerformance")}
            value="—"
            subtitle={t("metrics.unavailable")}
          />
          <MetricCard
            icon={<AlertTriangle className="size-5 text-foreground-muted" aria-hidden="true" />}
            title={t("metrics.delayedRoutes")}
            value="—"
            subtitle={t("metrics.unavailable")}
          />
          <MetricCard
            icon={<MapPin className="size-5 text-foreground-muted" aria-hidden="true" />}
            title={t("metrics.activeRoutes")}
            value="—"
            subtitle={t("metrics.unavailable")}
          />
        </div>
      </ScrollArea>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="grid grid-cols-1 gap-(--spacing-grid) p-(--spacing-card) sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          icon={<Bus className="size-5 text-foreground-muted" aria-hidden="true" />}
          title={t("metrics.activeVehicles")}
          value={String(data.activeVehicles)}
          subtitle={t("metrics.onRoutes", { count: data.distinctRouteCount })}
        />
        <MetricCard
          icon={<Clock className="size-5 text-foreground-muted" aria-hidden="true" />}
          title={t("metrics.onTimePerformance")}
          value={`${String(data.onTimePercentage)}%`}
          subtitle={t("metrics.vehiclesOnTime", {
            count: data.onTimeCount,
            total: data.totalVehicles,
          })}
        />
        <MetricCard
          icon={<AlertTriangle className="size-5 text-foreground-muted" aria-hidden="true" />}
          title={t("metrics.delayedRoutes")}
          value={String(data.delayedRoutes)}
          subtitle={t("metrics.ofTotalRoutes", {
            total: data.distinctRouteCount,
          })}
        />
        <MetricCard
          icon={<MapPin className="size-5 text-foreground-muted" aria-hidden="true" />}
          title={t("metrics.activeRoutes")}
          value={String(data.activeRoutes)}
          subtitle={t("metrics.totalInSystem", { total: data.totalRoutes })}
        />
      </div>
    </ScrollArea>
  );
}
```

### File 2: `cms/apps/web/src/components/dashboard/dashboard-content.tsx`

**Full target state after modification:**

```tsx
"use client";

import { useRef, useState, useCallback } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { useIsMobile } from "@/hooks/use-mobile";
import { DashboardMetrics } from "./dashboard-metrics";
import { CalendarPanel } from "./calendar-panel";
import { DriverRoster } from "./driver-roster";
import { DriverDropDialog } from "./driver-drop-dialog";
import { useDriversSummary } from "@/hooks/use-drivers-summary";
import type { Driver } from "@/types/driver";

interface DashboardContentProps {
  locale: string;
}

const SCHEDULE_ROLES = ["admin", "editor"];

export function DashboardContent({ locale }: DashboardContentProps) {
  const t = useTranslations("dashboard");
  const { data: session } = useSession();
  const isMobile = useIsMobile();

  const { drivers, isLoading: driversLoading } = useDriversSummary();

  const [dropDriver, setDropDriver] = useState<Driver | null>(null);
  const [dropDate, setDropDate] = useState<Date | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const calendarRefetchRef = useRef<(() => Promise<void>) | null>(null);

  const userRole: string = (session?.user?.role as string) ?? "";
  const canSchedule = SCHEDULE_ROLES.includes(userRole);

  const handleDayDrop = useCallback((date: Date, driverJson: string) => {
    try {
      const parsed: unknown = JSON.parse(driverJson);
      if (
        typeof parsed !== "object" ||
        parsed === null ||
        typeof (parsed as Record<string, unknown>).id !== "string" ||
        typeof (parsed as Record<string, unknown>).first_name !== "string" ||
        typeof (parsed as Record<string, unknown>).last_name !== "string"
      ) {
        return;
      }
      setDropDriver(parsed as Driver);
      setDropDate(date);
      setDialogOpen(true);
    } catch {
      /* ignore malformed data */
    }
  }, []);

  const handleEventCreated = useCallback(() => {
    setDialogOpen(false);
    void calendarRefetchRef.current?.();
  }, []);

  return (
    <div className="flex h-[calc(100vh-var(--spacing-page)*2)] flex-col gap-(--spacing-grid)">
      {/* Page header */}
      <div className="flex shrink-0 items-center justify-between">
        <h1 className="font-heading text-heading font-semibold text-foreground">
          {t("title")}
        </h1>
        <Button asChild variant="outline" className="cursor-pointer">
          <Link href={`/${locale}/routes`}>
            {t("manageRoutes")}
            <ArrowRight className="ml-2 size-4" aria-hidden="true" />
          </Link>
        </Button>
      </div>

      {/* Resizable layout: desktop (panels) vs mobile (stacked) */}
      {isMobile ? (
        <div className="flex min-h-0 flex-1 flex-col gap-(--spacing-grid)">
          <DashboardMetrics />
          <div className="min-h-0 flex-1">
            <CalendarPanel
              onDayDrop={canSchedule ? handleDayDrop : undefined}
              refetchRef={calendarRefetchRef}
            />
          </div>
        </div>
      ) : (
        <ResizablePanelGroup
          orientation="vertical"
          className="min-h-0 flex-1"
        >
          {/* TOP PANEL: Analytics metric cards */}
          <ResizablePanel defaultSize={20} minSize={10} maxSize={40}>
            <DashboardMetrics />
          </ResizablePanel>

          <ResizableHandle withHandle />

          {/* BOTTOM PANEL: Drivers + Calendar */}
          <ResizablePanel defaultSize={80} minSize={40}>
            <ResizablePanelGroup orientation="horizontal">
              {/* BOTTOM-LEFT: Driver roster */}
              <ResizablePanel defaultSize={25} minSize={15} maxSize={45}>
                <DriverRoster
                  drivers={drivers}
                  isLoading={driversLoading}
                  canDrag={canSchedule}
                />
              </ResizablePanel>

              <ResizableHandle withHandle />

              {/* BOTTOM-RIGHT: Operations calendar */}
              <ResizablePanel defaultSize={75} minSize={40}>
                <CalendarPanel
                  onDayDrop={canSchedule ? handleDayDrop : undefined}
                  refetchRef={calendarRefetchRef}
                />
              </ResizablePanel>
            </ResizablePanelGroup>
          </ResizablePanel>
        </ResizablePanelGroup>
      )}

      {/* Drop action dialog */}
      <DriverDropDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        driver={dropDriver}
        targetDate={dropDate}
        onEventCreated={handleEventCreated}
      />
    </div>
  );
}
```

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

- [ ] Dashboard renders at `/lv/` and `/en/` without errors
- [ ] Horizontal resize handle visible between metrics cards and drivers/calendar area
- [ ] Vertical resize handle visible between driver roster and operations calendar
- [ ] Dragging horizontal handle resizes metrics panel height — cards scroll when panel is short
- [ ] Dragging vertical handle resizes driver roster width — driver cards adapt, calendar adapts
- [ ] Minimum panel sizes prevent panels from collapsing to unreadable widths/heights
- [ ] Mobile layout (<768px) shows stacked view without resize handles
- [ ] Driver drag-and-drop onto calendar still works for admin/editor roles
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] No regressions in existing dashboard functionality (metrics loading, calendar events, etc.)

## Acceptance Criteria

This feature is complete when:
- [ ] Three resizable panels are functional (metrics, drivers, calendar)
- [ ] Both resize handles are draggable with visible grip indicators
- [ ] Content in all panels remains readable and responsive at any valid panel size
- [ ] Mobile fallback provides a usable stacked layout
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`

## Security Checklist (verify before marking step complete)
- [ ] No new external data paths introduced — existing auth patterns preserved
- [ ] No hardcoded credentials
- [ ] No `dangerouslySetInnerHTML`
- [ ] Redirects preserve user's current locale
