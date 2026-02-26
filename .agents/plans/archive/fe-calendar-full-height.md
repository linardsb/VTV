# Plan: Full-Height Calendar Grid for Month and Three-Month Views

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: `/[locale]/(dashboard)` (existing dashboard page)
**Auth Required**: Yes (existing)
**Allowed Roles**: admin, dispatcher, editor, viewer (no change)

## Feature Description

The week view calendar already fills the available vertical space because its CSS grid rows have explicit heights (`h-(--spacing-row)`) totaling enough content to scroll. However, the month view and three-month view do NOT fill their available height — they use fixed `min-h-18` cells (month) or `h-8 w-8` cells (three-month) that leave large empty whitespace below the calendar.

This enhancement makes the month view and three-month view fill the full available height of the calendar panel. The grid cells should stretch vertically to consume all space, just as a real calendar application would display (like Google Calendar or Outlook). The CalendarGrid orchestrator component must pass height constraints downward so each view can fill the container.

The key architectural change: CalendarGrid becomes a flex-column container where the header takes its natural height and the active view fills the remaining space. Each view then uses CSS to distribute that space across its grid rows.

## Design System

### Master Rules (from MASTER.md)
- Spacing: Use semantic tokens via Tailwind arbitrary syntax — `p-(--spacing-card)` not `p-3`
- Colors: No hardcoded colors — use semantic tokens from `tokens.css`
- Typography: `font-heading` for headings, `text-heading` for heading font size
- Compact spacing tokens for dashboard density (--spacing-card, --spacing-cell, --spacing-tight, --spacing-grid)

### Page Override
- None — this is an enhancement to existing dashboard components, no new page override needed

### Tokens Used
- `--spacing-card` (0.75rem / 12px) — calendar container padding
- `--spacing-cell` (0.375rem / 6px) — day cell padding
- `--spacing-tight` (0.25rem / 4px) — micro gaps
- `--spacing-grid` (0.75rem / 12px) — grid gap between cards
- `--spacing-inline` (0.375rem / 6px) — icon-to-text gaps
- `--spacing-section` (1rem / 16px) — gap between major sections
- Semantic color tokens: `border-border`, `border-border-subtle`, `bg-surface-raised`, `text-foreground`, `text-foreground-muted`, `bg-interactive`

## Components Needed

### Existing (no new components needed)
- `CalendarGrid` at `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — orchestrator (MODIFY)
- `MonthView` at `cms/apps/web/src/components/dashboard/month-view.tsx` — month calendar (MODIFY)
- `ThreeMonthView` at `cms/apps/web/src/components/dashboard/three-month-view.tsx` — 3-month calendar (MODIFY)
- `CalendarHeader` at `cms/apps/web/src/components/dashboard/calendar-header.tsx` — no changes needed

### New shadcn/ui to Install
- None

### Custom Components to Create
- None

## i18n Keys

No new i18n keys needed — this is a layout/CSS-only enhancement to existing components.

## Data Fetching

No changes — this enhancement is purely visual layout. No new API calls or data fetching.

## RBAC Integration

No changes — existing dashboard RBAC applies.

## Sidebar Navigation

No changes — existing dashboard nav entry applies.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/dashboard/week-view.tsx` — Reference for how a view fills space with a grid

### Files to Modify
- `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — Make flex-column container, pass height to views
- `cms/apps/web/src/components/dashboard/month-view.tsx` — Full-height grid with stretching week rows
- `cms/apps/web/src/components/dashboard/three-month-view.tsx` — Full-height layout with stretching mini calendars
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Ensure calendar panel passes height correctly

## Architecture Analysis

### Current Height Flow (BROKEN for month/3-month)
```
ResizablePanelGroup (min-h-[calc(100vh-6rem)])
  └─ ResizablePanel (defaultSize=80%, no height constraint to children)
      └─ div.pt-(--spacing-grid) (no height constraint)
          └─ CalendarGrid (rounded-lg border, no height management)
              ├─ CalendarHeader (natural height ~48px)
              └─ MonthView (natural height from min-h-18 cells = ~400px, doesn't fill)
```

### Target Height Flow (FIXED)
```
ResizablePanelGroup (min-h-[calc(100vh-6rem)])
  └─ ResizablePanel (defaultSize=80%)
      └─ div.pt-(--spacing-grid) h-full (passes height)
          └─ CalendarGrid (h-full flex flex-col)
              ├─ CalendarHeader (shrink-0, natural height)
              └─ div.flex-1.min-h-0 (fills remaining space)
                  └─ MonthView (h-full, grid rows stretch with flex-1)
```

### Key CSS Technique
For month view: Use `flex flex-col h-full` on the container, then each week row gets `flex-1 min-h-0` to distribute space evenly. The 7-column grid inside each row stays as-is, but cells grow vertically.

For three-month view: The 3-column grid becomes `h-full` and each mini-month column uses `flex flex-col` with the day grid getting `flex-1`.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

---

### Task 1: Update Dashboard Page — Pass Height to Calendar Container
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` (modify)
**Action:** UPDATE

The `<div className="pt-(--spacing-grid)">` wrapping `<CalendarGrid>` inside the calendar `ResizablePanel` needs to pass height to its child. Add `h-full` so it fills the resizable panel.

**Current code (line 53):**
```tsx
<div className="pt-(--spacing-grid)">
  <CalendarGrid events={MOCK_EVENTS} />
</div>
```

**Change to:**
```tsx
<div className="h-full pt-(--spacing-grid)">
  <CalendarGrid events={MOCK_EVENTS} />
</div>
```

**What changed:** Added `h-full` to the wrapper div so it fills the ResizablePanel height and passes it down to CalendarGrid.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 2: Update CalendarGrid — Flex Column Layout with Height Pass-Through
**File:** `cms/apps/web/src/components/dashboard/calendar-grid.tsx` (modify)
**Action:** UPDATE

CalendarGrid must become a flex-column container so the CalendarHeader takes its natural height and the active view fills the remaining space.

**Current code (lines 19-41):**
```tsx
return (
  <div className="overflow-hidden rounded-lg border border-border bg-surface-raised">
    <CalendarHeader
      currentDate={currentDate}
      view={view}
      onViewChange={setView}
      onDateChange={setCurrentDate}
    />
    {view === "week" && (
      <WeekView currentDate={currentDate} events={events} />
    )}
    {view === "month" && (
      <MonthView currentDate={currentDate} events={events} />
    )}
    {view === "3month" && (
      <ThreeMonthView currentDate={currentDate} events={events} />
    )}
    {view === "year" && (
      <YearView currentDate={currentDate} events={events} />
    )}
  </div>
);
```

**Change to:**
```tsx
return (
  <div className="flex h-full flex-col overflow-hidden rounded-lg border border-border bg-surface-raised">
    <CalendarHeader
      currentDate={currentDate}
      view={view}
      onViewChange={setView}
      onDateChange={setCurrentDate}
    />
    <div className="min-h-0 flex-1">
      {view === "week" && (
        <WeekView currentDate={currentDate} events={events} />
      )}
      {view === "month" && (
        <MonthView currentDate={currentDate} events={events} />
      )}
      {view === "3month" && (
        <ThreeMonthView currentDate={currentDate} events={events} />
      )}
      {view === "year" && (
        <YearView currentDate={currentDate} events={events} />
      )}
    </div>
  </div>
);
```

**What changed:**
1. Added `flex h-full flex-col` to the outer container — makes it a flex column that fills parent height
2. Wrapped all view components in a `<div className="min-h-0 flex-1">` — this div takes all remaining space after CalendarHeader and allows views to fill it. `min-h-0` is critical to prevent flex children from overflowing (CSS flex min-height default is `min-content`).

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web build` passes

---

### Task 3: Update MonthView — Full-Height Grid with Stretching Rows
**File:** `cms/apps/web/src/components/dashboard/month-view.tsx` (modify)
**Action:** UPDATE

The month view must fill the container height. The weekday header row takes natural height, and the week rows distribute remaining space evenly. Each day cell stretches vertically to fill its row.

**Current code (lines 81-156):**
```tsx
return (
  <div className="p-(--spacing-card)">
    {/* Weekday headers */}
    <div className="grid grid-cols-7 gap-(--spacing-tight)">
      {WEEKDAY_KEYS.map((key) => (
        <div
          key={key}
          className="p-(--spacing-cell) text-center text-xs font-medium text-foreground-muted"
        >
          {t(`weekdays.${key}`)}
        </div>
      ))}
    </div>

    {/* Day grid */}
    {weeks.map((week, weekIdx) => (
      <div key={weekIdx} className="grid grid-cols-7 gap-(--spacing-tight)">
        {week.map((day, dayIdx) => {
          if (!day) {
            return (
              <div
                key={`empty-${dayIdx}`}
                className="min-h-18 rounded-sm border border-border-subtle p-(--spacing-tight) opacity-40"
              />
            );
          }

          const isToday = isSameDay(day, today);
          const dateKey = `${day.getFullYear()}-${day.getMonth()}-${day.getDate()}`;
          const dayEvents = eventsByDate.get(dateKey) ?? [];
          const visibleEvents = dayEvents.slice(0, 3);
          const overflow = dayEvents.length - 3;

          return (
            <div
              key={day.getDate()}
              className={cn(
                "min-h-18 rounded-sm border border-border-subtle p-(--spacing-tight) transition-colors duration-200",
                isToday && "border-interactive bg-interactive/10"
              )}
            >
              <p
                className={cn(
                  "text-sm text-foreground",
                  isToday && "font-semibold text-interactive"
                )}
              >
                {day.getDate()}
              </p>
              <div className="mt-(--spacing-tight) flex flex-col gap-0.5">
                {visibleEvents.map((event) => (
                  <div key={event.id} className="flex items-center gap-(--spacing-tight)">
                    <div
                      className={cn(
                        "size-1.5 shrink-0 rounded-full",
                        categoryDotColors[event.category]
                      )}
                    />
                    <span className="truncate text-[10px] text-foreground-muted">
                      {event.title}
                    </span>
                  </div>
                ))}
                {overflow > 0 && (
                  <span className="text-[10px] text-foreground-muted">
                    +{overflow} more
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    ))}
  </div>
);
```

**Change to:**
```tsx
return (
  <div className="flex h-full flex-col p-(--spacing-card)">
    {/* Weekday headers */}
    <div className="grid shrink-0 grid-cols-7 gap-(--spacing-tight)">
      {WEEKDAY_KEYS.map((key) => (
        <div
          key={key}
          className="p-(--spacing-cell) text-center text-xs font-medium text-foreground-muted"
        >
          {t(`weekdays.${key}`)}
        </div>
      ))}
    </div>

    {/* Day grid — each week row stretches equally */}
    <div className="flex min-h-0 flex-1 flex-col gap-(--spacing-tight)">
      {weeks.map((week, weekIdx) => (
        <div key={weekIdx} className="grid min-h-0 flex-1 grid-cols-7 gap-(--spacing-tight)">
          {week.map((day, dayIdx) => {
            if (!day) {
              return (
                <div
                  key={`empty-${dayIdx}`}
                  className="overflow-hidden rounded-sm border border-border-subtle p-(--spacing-tight) opacity-40"
                />
              );
            }

            const isToday = isSameDay(day, today);
            const dateKey = `${day.getFullYear()}-${day.getMonth()}-${day.getDate()}`;
            const dayEvents = eventsByDate.get(dateKey) ?? [];
            const visibleEvents = dayEvents.slice(0, 3);
            const overflow = dayEvents.length - 3;

            return (
              <div
                key={day.getDate()}
                className={cn(
                  "overflow-hidden rounded-sm border border-border-subtle p-(--spacing-tight) transition-colors duration-200",
                  isToday && "border-interactive bg-interactive/10"
                )}
              >
                <p
                  className={cn(
                    "text-sm text-foreground",
                    isToday && "font-semibold text-interactive"
                  )}
                >
                  {day.getDate()}
                </p>
                <div className="mt-(--spacing-tight) flex flex-col gap-0.5">
                  {visibleEvents.map((event) => (
                    <div key={event.id} className="flex items-center gap-(--spacing-tight)">
                      <div
                        className={cn(
                          "size-1.5 shrink-0 rounded-full",
                          categoryDotColors[event.category]
                        )}
                      />
                      <span className="truncate text-[10px] text-foreground-muted">
                        {event.title}
                      </span>
                    </div>
                  ))}
                  {overflow > 0 && (
                    <span className="text-[10px] text-foreground-muted">
                      +{overflow} more
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  </div>
);
```

**What changed:**
1. Outer div: `p-(--spacing-card)` → `flex h-full flex-col p-(--spacing-card)` — makes it fill parent and become flex column
2. Weekday header div: Added `shrink-0` — prevents header from shrinking when space is tight
3. Wrapped all week rows in a new `<div className="flex min-h-0 flex-1 flex-col gap-(--spacing-tight)">` — this container takes all remaining height after the weekday header
4. Each week row div: Changed from `grid grid-cols-7 gap-(--spacing-tight)` to `grid min-h-0 flex-1 grid-cols-7 gap-(--spacing-tight)` — `flex-1` distributes height evenly across week rows, `min-h-0` prevents overflow
5. Day cells: Replaced `min-h-18` with `overflow-hidden` — removes fixed minimum height (cells now stretch to fill row), adds overflow hidden to prevent content spilling
6. Empty cells: Same change — `min-h-18` → `overflow-hidden`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 4: Update ThreeMonthView — Full-Height Layout with Stretching Mini Calendars
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx` (modify)
**Action:** UPDATE

The three-month view must fill the container height. The 3-column grid should stretch to fill height, and each mini-month should distribute its vertical space across the day rows.

#### Part A: Update the MiniMonth sub-component

**Current MiniMonth code (lines 59-97):**
```tsx
return (
  <div>
    <h3 className="mb-(--spacing-inline) text-center font-heading text-sm font-semibold text-foreground">
      {t(`months.${MONTH_KEYS[month]}`)} {year}
    </h3>
    <div className="grid grid-cols-7 gap-0.5">
      {WEEKDAY_KEYS.map((key) => (
        <div
          key={key}
          className="flex h-6 items-center justify-center text-[10px] font-medium text-foreground-muted"
        >
          {t(`weekdays.${key}`)}
        </div>
      ))}
      {cells.map((date, i) => {
        if (!date) {
          return <div key={`empty-${i}`} className="h-8 w-8" />;
        }
        const isToday = isSameDay(date, today);
        const hasEvents = hasEventsOnDay(events, date);

        return (
          <div
            key={date.getDate()}
            className={cn(
              "flex h-8 w-8 flex-col items-center justify-center rounded-sm text-xs",
              isToday && "rounded-full bg-interactive font-semibold text-white"
            )}
          >
            <span>{date.getDate()}</span>
            {hasEvents && !isToday && (
              <div className="mt-0.5 size-1 rounded-full bg-interactive" />
            )}
          </div>
        );
      })}
    </div>
  </div>
);
```

**Change MiniMonth to:**
```tsx
return (
  <div className="flex h-full flex-col">
    <h3 className="mb-(--spacing-inline) shrink-0 text-center font-heading text-sm font-semibold text-foreground">
      {t(`months.${MONTH_KEYS[month]}`)} {year}
    </h3>
    <div className="grid min-h-0 flex-1 grid-cols-7 gap-0.5">
      {WEEKDAY_KEYS.map((key) => (
        <div
          key={key}
          className="flex items-center justify-center text-[10px] font-medium text-foreground-muted"
        >
          {t(`weekdays.${key}`)}
        </div>
      ))}
      {cells.map((date, i) => {
        if (!date) {
          return <div key={`empty-${i}`} />;
        }
        const isToday = isSameDay(date, today);
        const hasEvents = hasEventsOnDay(events, date);

        return (
          <div
            key={date.getDate()}
            className={cn(
              "flex flex-col items-center justify-center rounded-sm text-xs",
              isToday && "rounded-full bg-interactive font-semibold text-white"
            )}
          >
            <span>{date.getDate()}</span>
            {hasEvents && !isToday && (
              <div className="mt-0.5 size-1 rounded-full bg-interactive" />
            )}
          </div>
        );
      })}
    </div>
  </div>
);
```

**What changed in MiniMonth:**
1. Outer div: `<div>` → `<div className="flex h-full flex-col">` — fills parent height, flex column layout
2. h3: Added `shrink-0` — header doesn't shrink
3. Grid div: `grid grid-cols-7 gap-0.5` → `grid min-h-0 flex-1 grid-cols-7 gap-0.5` — grid fills remaining space, rows auto-distribute
4. Weekday header cells: Removed `h-6` — let grid handle height distribution
5. Day cells: Removed `h-8 w-8` fixed sizing — cells now stretch to fill grid row height
6. Empty cells: `h-8 w-8` → removed (just `<div key={...} />`) — no fixed sizing

#### Part B: Update the ThreeMonthView root component

**Current ThreeMonthView return (lines 116-128):**
```tsx
return (
  <div className="grid grid-cols-1 gap-(--spacing-section) p-(--spacing-card) sm:grid-cols-3">
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
```

**Change to:**
```tsx
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
```

**What changed in ThreeMonthView:**
1. Grid div: Added `h-full` — the 3-column grid now fills the full container height. CSS Grid will auto-distribute the single row to fill the height, and each MiniMonth (being `h-full`) will stretch to match.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes
- `cd cms && pnpm --filter @vtv/web build` passes

---

### Task 5: Visual Verification

After all code changes are complete, verify the following by inspecting the component structure:

1. **Height chain is unbroken:** Trace from `ResizablePanel` → wrapper div (`h-full`) → `CalendarGrid` (`h-full flex flex-col`) → flex-1 wrapper → view component (`h-full`) → grid rows (`flex-1`). Every link must pass height.

2. **No fixed heights remain in month/3-month:** Confirm `min-h-18` is removed from MonthView cells, `h-8 w-8` is removed from ThreeMonthView cells.

3. **Week view still works:** The WeekView was NOT modified. Confirm it still renders correctly — its `overflow-auto` handles its own height naturally.

4. **Year view still works:** The YearView was NOT modified. It sits inside the new `min-h-0 flex-1` wrapper in CalendarGrid, which should not break its existing scroll behavior.

5. **No hardcoded colors:** Verify all modified files use only semantic tokens — no hex values, no Tailwind color utilities like `bg-blue-500`.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes
- `cd cms && pnpm --filter @vtv/web build` passes

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

- [ ] Month view fills full available height in calendar panel
- [ ] Month view week rows are evenly distributed vertically
- [ ] Month view day cells stretch to fill their row height
- [ ] Three-month view fills full available height in calendar panel
- [ ] Three-month mini calendars stretch to fill container
- [ ] Three-month day cells stretch to fill their grid rows
- [ ] Week view is unaffected (still scrolls, still has proper hour rows)
- [ ] Year view is unaffected (still renders heat map grid)
- [ ] Calendar header still renders correctly at top
- [ ] View switching between all 4 modes works without layout jumps
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] Resizable panel handle still works to resize metrics/calendar split
- [ ] No overflow or content clipping on standard viewport sizes (1080p+)

## Acceptance Criteria

This feature is complete when:
- [ ] Month view fills the full available height of the calendar panel with evenly-distributed week rows
- [ ] Three-month view fills the full available height with stretched mini-calendar grids
- [ ] All 4 calendar view modes (week, month, 3-month, year) render correctly
- [ ] Height chain is unbroken from ResizablePanel through to grid cells
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing views (week, year)
- [ ] Ready for `/commit`

## Summary of Changes

| File | Action | Key Changes |
|------|--------|-------------|
| `page.tsx` | UPDATE | Add `h-full` to calendar wrapper div |
| `calendar-grid.tsx` | UPDATE | Add `flex h-full flex-col`, wrap views in `min-h-0 flex-1` container |
| `month-view.tsx` | UPDATE | `flex h-full flex-col`, week rows get `flex-1 min-h-0`, remove `min-h-18` from cells |
| `three-month-view.tsx` | UPDATE | Add `h-full` to grid, MiniMonth becomes `flex h-full flex-col`, remove fixed cell sizes |

**Total: 0 new files, 4 modified files**
