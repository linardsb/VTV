# Plan: Three-Month View Event Cards

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: N/A — modification of existing dashboard calendar component
**Auth Required**: N/A — existing auth applies
**Allowed Roles**: All (inherits from dashboard page)

## Feature Description

The current three-month calendar view (`ThreeMonthView`) displays mini-month grids where each day only shows a small dot indicating the presence of events. This is a significant information downgrade from the one-month view (`MonthView`), which shows rich event cards with colored category dots and truncated event titles inside each day cell.

This enhancement refactors the three-month view to match the one-month view's card-based event display pattern. Each of the three mini-month grids will show day cells with event cards containing category-colored dots and event titles — identical to the reference screenshot. Because three months of data must fit side-by-side, the visible event count per cell will be reduced (max 2 per cell vs 3 in month view) and font sizing will be slightly smaller.

The goal is visual parity: switching between month and 3-month views should feel like the same component at different scales, not two fundamentally different UIs. The reference design is the screenshot showing day "17" with "Morning Shift Handover" and "Trolleybus Line Maintenance" event cards with colored dots.

## Design System

### Master Rules (from MASTER.md)
- Spacing tokens via Tailwind arbitrary value syntax: `p-(--spacing-card)`, `gap-(--spacing-tight)`
- No hardcoded colors — use semantic tokens from `tokens.css`
- Font families: `--font-heading` for headings, `--font-body` for text
- WCAG compliant contrast ratios
- Transitions 150-300ms on interactive elements

### Page Override
- None — this is a dashboard component enhancement, not a new page

### Tokens Used
- `--spacing-card` (0.75rem / 12px) — mini-month internal padding
- `--spacing-cell` (0.375rem / 6px) — day cell padding
- `--spacing-tight` (0.25rem / 4px) — micro gaps between event items, grid gaps
- `--spacing-inline` (0.375rem / 6px) — icon-to-text gaps
- `--spacing-section` (1rem / 16px) — gap between the three month panels
- `--color-interactive` — today highlight color
- `--color-foreground` — primary text
- `--color-foreground-muted` — secondary text (event titles, weekday headers)
- `--color-border-subtle` — cell borders
- `--color-surface-raised` — card/cell backgrounds

## Components Needed

### Existing (shadcn/ui)
- None directly — this is a custom calendar component

### New shadcn/ui to Install
- None

### Custom Components to Create
- No new component files. The `MiniMonth` function component inside `three-month-view.tsx` will be refactored in-place.

## Architecture Analysis

### Current MonthView Pattern (the target pattern)
**File:** `cms/apps/web/src/components/dashboard/month-view.tsx`

Key structural elements:
1. **Grid layout:** `getMonthGrid()` returns `(Date | null)[][]` grouped by weeks
2. **Events lookup:** `eventsByDate` Map keyed by `"year-month-date"` string
3. **Day cell rendering:**
   - Outer `div` with border, rounded corners, padding, today highlight
   - Day number as `<p>` with conditional today styling
   - Event list: `flex flex-col gap-0.5` with max 3 visible events
   - Each event: colored dot (`size-1.5 rounded-full`) + truncated title (`text-[10px]`)
   - Overflow indicator: `+N more`
4. **Category dot colors:** `categoryDotColors` Record mapping category strings to Tailwind bg classes
5. **Full-height flex layout:** `flex h-full flex-col` with `flex-1` week rows

### Current ThreeMonthView Pattern (what needs to change)
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx`

Current structure:
1. **Grid layout:** `getMiniMonthDays()` returns flat `(Date | null)[]` array (NOT grouped by weeks)
2. **Events lookup:** Simple `hasEventsOnDay()` boolean check — no event details
3. **Day cell rendering:**
   - Single `div` with centered number
   - Just a tiny dot if events exist — no titles, no cards
   - Today: circular blue background
4. **No category info:** Only knows if events exist, not which events or their categories
5. **Three-column layout:** `grid grid-cols-1 sm:grid-cols-3`

### Gap Analysis

| Aspect | MonthView (target) | ThreeMonthView (current) | Change needed |
|--------|-------------------|-------------------------|---------------|
| Grid structure | Weeks array of arrays | Flat cell array | Restructure to weeks |
| Event data | Map of events per date | Boolean has/hasn't | Build events Map |
| Day cell | Border, padding, event cards | Centered number + dot | Full redesign |
| Event display | Colored dot + title text | Small indicator dot only | Add card rendering |
| Overflow | "+N more" text | None | Add overflow |
| Today highlight | Border + bg tint | Circular bg | Match month style |
| Empty cells | Bordered, opacity-40 | Empty div | Add border styling |
| Category colors | `categoryDotColors` map | None | Import/duplicate map |
| Max events/cell | 3 | 0 (just dot) | 2 (smaller space) |

## i18n Keys

No new i18n keys needed. The component already uses:
- `dashboard.weekdays.{mon,tue,wed,thu,fri,sat,sun}` — weekday headers
- `dashboard.months.{jan,...,dec}` — month names

## Data Fetching

No changes — events are already passed via `CalendarEvent[]` prop from parent `CalendarGrid` component, which receives `MOCK_EVENTS` from the dashboard page.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/dashboard/month-view.tsx` — **PRIMARY REFERENCE** — the exact pattern to replicate
- `cms/apps/web/src/types/dashboard.ts` — CalendarEvent type definition

### Files to Modify
- `cms/apps/web/src/components/dashboard/three-month-view.tsx` — **ONLY FILE MODIFIED**

### Files NOT to Modify
- `calendar-grid.tsx` — no changes needed, already passes events correctly
- `month-view.tsx` — reference only, do not modify
- `page.tsx` — dashboard page, no changes needed
- `tokens.css` — no new tokens needed

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
This plan modifies a SINGLE FILE: `cms/apps/web/src/components/dashboard/three-month-view.tsx`

All changes are in one file, so this is structured as logical steps within that file.

---

### Task 1: Read Reference Files
**Action:** READ (do not modify)

Read these files to understand the patterns before making any changes:

1. `cms/apps/web/src/components/dashboard/month-view.tsx` — the event card pattern to replicate
2. `cms/apps/web/src/components/dashboard/three-month-view.tsx` — the file to modify
3. `cms/apps/web/src/types/dashboard.ts` — CalendarEvent interface

**Understand these critical patterns from MonthView:**
- `getMonthGrid()` function: returns `(Date | null)[][]` (array of week arrays)
- `eventsByDate` useMemo: builds `Map<string, CalendarEvent[]>` keyed by `"year-month-date"`
- `categoryDotColors` record: maps event category → Tailwind bg class
- Day cell structure: border + padding wrapper → day number → event cards with dot + title
- Today styling: `border-interactive bg-interactive/10` on cell, `font-semibold text-interactive` on number
- Empty cell styling: `opacity-40` with border
- Event card: `flex items-center gap-(--spacing-tight)` → dot (`size-1.5 rounded-full`) + title (`truncate text-[10px]`)
- Overflow: `+N more` text in `text-[10px] text-foreground-muted`

**No validation needed for this step.**

---

### Task 2: Replace Grid Helper Function
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx` (modify)
**Action:** UPDATE

Replace the `getMiniMonthDays` function with a weeks-based grid function that matches MonthView's `getMonthGrid` pattern. Also remove the `hasEventsOnDay` function since it will no longer be needed.

**Remove these two functions:**
```typescript
// REMOVE this function entirely
function getMiniMonthDays(year: number, month: number): (Date | null)[] {
  // ... flat cell array
}

// REMOVE this function entirely
function hasEventsOnDay(events: CalendarEvent[], date: Date): boolean {
  return events.some((e) => isSameDay(e.start, date));
}
```

**Add this function (copied from month-view.tsx — identical logic):**
```typescript
function getMonthGrid(year: number, month: number): (Date | null)[][] {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const startOffset = (firstDay.getDay() + 6) % 7;

  const weeks: (Date | null)[][] = [];
  let currentWeek: (Date | null)[] = [];

  for (let i = 0; i < startOffset; i++) {
    currentWeek.push(null);
  }

  for (let day = 1; day <= lastDay.getDate(); day++) {
    currentWeek.push(new Date(year, month, day));
    if (currentWeek.length === 7) {
      weeks.push(currentWeek);
      currentWeek = [];
    }
  }

  if (currentWeek.length > 0) {
    while (currentWeek.length < 7) {
      currentWeek.push(null);
    }
    weeks.push(currentWeek);
  }

  return weeks;
}
```

**Add the category dot color map (same as month-view.tsx):**
```typescript
const categoryDotColors: Record<string, string> = {
  maintenance: "bg-blue-400",
  "route-change": "bg-amber-400",
  "driver-shift": "bg-emerald-500",
  "service-alert": "bg-red-500",
};
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 3: Refactor MiniMonth Component
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx` (modify)
**Action:** UPDATE

Replace the entire `MiniMonth` component with a new version that matches MonthView's day cell pattern. Key differences from MonthView:
- Max 2 visible events per cell (not 3) — less horizontal space available
- Text sizing `text-[9px]` for event titles (not `text-[10px]`) — tighter fit
- Day number uses `text-xs` (same as current)
- Dot size `size-1` (not `size-1.5`) — proportionally smaller

**Replace the entire MiniMonth function component with:**

```typescript
function MiniMonth({
  year,
  month,
  events,
  today,
}: {
  year: number;
  month: number;
  events: CalendarEvent[];
  today: Date;
}) {
  const t = useTranslations("dashboard");
  const weeks = useMemo(() => getMonthGrid(year, month), [year, month]);

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const event of events) {
      const eventDate = event.start;
      if (
        eventDate.getFullYear() === year &&
        eventDate.getMonth() === month
      ) {
        const key = `${eventDate.getFullYear()}-${eventDate.getMonth()}-${eventDate.getDate()}`;
        if (!map.has(key)) map.set(key, []);
        map.get(key)!.push(event);
      }
    }
    return map;
  }, [events, year, month]);

  return (
    <div className="flex h-full flex-col">
      <h3 className="mb-(--spacing-tight) shrink-0 text-center font-heading text-sm font-semibold text-foreground">
        {t(`months.${MONTH_KEYS[month]}`)} {year}
      </h3>

      {/* Weekday headers */}
      <div className="grid shrink-0 grid-cols-7 gap-px">
        {WEEKDAY_KEYS.map((key) => (
          <div
            key={key}
            className="py-0.5 text-center text-[9px] font-medium text-foreground-muted"
          >
            {t(`weekdays.${key}`)}
          </div>
        ))}
      </div>

      {/* Day grid — each week row stretches equally */}
      <div className="flex min-h-0 flex-1 flex-col gap-px">
        {weeks.map((week, weekIdx) => (
          <div
            key={weekIdx}
            className="grid min-h-0 flex-1 grid-cols-7 gap-px"
          >
            {week.map((day, dayIdx) => {
              if (!day) {
                return (
                  <div
                    key={`empty-${dayIdx}`}
                    className="overflow-hidden rounded-sm border border-border-subtle opacity-40"
                  />
                );
              }

              const isToday = isSameDay(day, today);
              const dateKey = `${day.getFullYear()}-${day.getMonth()}-${day.getDate()}`;
              const dayEvents = eventsByDate.get(dateKey) ?? [];
              const visibleEvents = dayEvents.slice(0, 2);
              const overflow = dayEvents.length - 2;

              return (
                <div
                  key={day.getDate()}
                  className={cn(
                    "overflow-hidden rounded-sm border border-border-subtle p-px transition-colors duration-200",
                    isToday && "border-interactive bg-interactive/10"
                  )}
                >
                  <p
                    className={cn(
                      "text-[10px] leading-none text-foreground",
                      isToday && "font-semibold text-interactive"
                    )}
                  >
                    {day.getDate()}
                  </p>
                  {visibleEvents.length > 0 && (
                    <div className="mt-px flex flex-col gap-0">
                      {visibleEvents.map((event) => (
                        <div
                          key={event.id}
                          className="flex items-center gap-0.5"
                        >
                          <div
                            className={cn(
                              "size-1 shrink-0 rounded-full",
                              categoryDotColors[event.category]
                            )}
                          />
                          <span className="truncate text-[8px] leading-tight text-foreground-muted">
                            {event.title}
                          </span>
                        </div>
                      ))}
                      {overflow > 0 && (
                        <span className="text-[8px] leading-tight text-foreground-muted">
                          +{overflow}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Key design decisions for the 3-month scale:**
- `p-px` on day cells (1px padding) — much tighter than month view's `p-(--spacing-tight)` because 3 grids share horizontal space
- `gap-px` between cells (1px) — tighter than month view's `gap-(--spacing-tight)`
- `text-[8px]` for event titles — smaller than month view's `text-[10px]`
- `text-[10px]` for day numbers — smaller than month view's `text-sm`
- `size-1` dots — smaller than month view's `size-1.5`
- Max 2 events per cell — fewer than month view's 3
- `overflow` shows `+N` (short) not `+N more` — saves space
- `gap-0` between event rows — zero gap to maximize density
- `leading-tight` and `leading-none` — compact line heights

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 4: Verify ThreeMonthView Wrapper (no changes expected)
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx` (verify)
**Action:** VERIFY

The `ThreeMonthView` export function should remain unchanged. Verify it still looks like:

```typescript
export function ThreeMonthView({ currentDate, events }: ThreeMonthViewProps) {
  const months = useMemo(() => {
    const result: { year: number; month: number }[] = [];
    for (let offset = -1; offset <= 1; offset++) {
      const d = new Date(
        currentDate.getFullYear(),
        currentDate.getMonth() + offset,
        1
      );
      result.push({ year: d.getFullYear(), month: d.getMonth() });
    }
    return result;
  }, [currentDate]);

  const today = new Date();

  return (
    <div className="grid h-full grid-cols-1 gap-(--spacing-section) p-(--spacing-card) sm:grid-cols-3">
      {months.map(({ year, month }) => (
        <MiniMonth
          key={`${year}-${month}`}
          year={year}
          month={month}
          events={events}
          today={today}
        />
      ))}
    </div>
  );
}
```

This already passes `events` to each `MiniMonth`, and the grid layout is correct. No changes needed.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 5: Verify Complete File Structure
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx`
**Action:** VERIFY

After all changes, the complete file should have this structure (top to bottom):

1. `"use client";` directive
2. Imports: `useMemo` from react, `useTranslations` from next-intl, `cn` from utils, `CalendarEvent` type
3. `ThreeMonthViewProps` interface
4. `WEEKDAY_KEYS` constant
5. `MONTH_KEYS` constant
6. `categoryDotColors` constant — **NEW** (copied from month-view.tsx)
7. `isSameDay()` helper — **EXISTING** (unchanged)
8. `getMonthGrid()` helper — **NEW** (replaces getMiniMonthDays, copied from month-view.tsx)
9. `MiniMonth` component — **REWRITTEN** (weeks-based grid with event cards)
10. `ThreeMonthView` export — **UNCHANGED**

**Removed items:**
- `getMiniMonthDays()` function — replaced by `getMonthGrid()`
- `hasEventsOnDay()` function — no longer needed

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: Full Build Validation
**Action:** VALIDATE

Run the complete validation pyramid:

```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web lint
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web build
```

All three must exit with code 0 and zero errors.

**If type-check fails:** Check that `CalendarEvent` import is correct and that `eventsByDate` Map types are properly inferred.

**If lint fails:** Check for unused imports (the old `hasEventsOnDay` may leave orphaned imports) and ensure no hardcoded color values outside the `categoryDotColors` map.

**If build fails:** Check for SSR issues — the component is `"use client"` so this should not be an issue. Look for any missing exports or circular dependencies.

---

### Task 7: Visual Verification (Manual)
**Action:** VERIFY

After build passes, describe what the 3-month view should look like:

**Each mini-month grid:**
- Month name + year as heading (centered, `font-heading`, semibold)
- 7-column weekday headers (Mon–Sun, tiny text)
- Day grid with 4-6 week rows, each row stretching equally to fill vertical space
- Each day cell has:
  - Border (subtle), rounded corners
  - Day number (top-left)
  - Up to 2 event cards: colored dot + truncated title
  - `+N` overflow if more than 2 events
  - Today: blue border + light blue background tint
  - Empty/padding days: bordered with 40% opacity

**Three grids side-by-side on sm+ screens, stacked on mobile.**

The visual result should match the reference screenshot pattern — colored dots with event titles visible in each day cell, just at a smaller scale than the month view.

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

- [ ] 3-month view shows event cards with colored dots and titles (not just dots)
- [ ] Day cells have borders, padding, and today highlighting matching month view style
- [ ] Max 2 events visible per cell with "+N" overflow indicator
- [ ] Category dot colors match month view (blue=maintenance, amber=route-change, emerald=driver-shift, red=service-alert)
- [ ] Empty/padding cells show with reduced opacity
- [ ] Today cell has interactive border + background tint
- [ ] Month headings centered with correct font
- [ ] Weekday headers visible and properly aligned
- [ ] Three months display side-by-side on sm+ screens
- [ ] No hardcoded colors — only semantic tokens and the shared categoryDotColors map
- [ ] Events truncate properly when titles are long
- [ ] Full-height flex layout fills available vertical space
- [ ] No regressions in month view, week view, or year view
- [ ] All validation levels pass (type-check, lint, build)

## Acceptance Criteria

This feature is complete when:
- [ ] 3-month view renders event cards identical in style to the month view (colored dots + titles)
- [ ] Scale is appropriately smaller (8px text, 1px dots, 2 max events) for the tighter space
- [ ] All three validation levels pass with zero errors
- [ ] No changes to any other files besides `three-month-view.tsx`
- [ ] Switching between month and 3-month views feels like the same component at different scales
- [ ] Ready for `/commit`

## Summary of Changes

| Aspect | Files Modified | Files Created |
|--------|---------------|---------------|
| Component refactor | 1 (`three-month-view.tsx`) | 0 |
| i18n | 0 | 0 |
| Middleware/RBAC | 0 | 0 |
| Sidebar nav | 0 | 0 |
| Design tokens | 0 | 0 |

**Total: 1 file modified, 0 files created.**

This is a focused component enhancement — the only file that changes is `three-month-view.tsx`. The MonthView pattern is replicated at a smaller scale, using the same helper functions, same event data structures, and same rendering patterns.
