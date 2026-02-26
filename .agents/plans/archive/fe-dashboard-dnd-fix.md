# Plan: Fix Dashboard Drag-and-Drop (Session 1 of 4)

## Feature Metadata
**Feature Type**: Bug Fix + Enhancement
**Estimated Complexity**: Low-Medium
**Route**: `/[locale]/` (dashboard — existing page)
**Auth Required**: Yes
**Allowed Roles**: admin, editor, dispatcher

## Feature Description

The dashboard's driver-to-calendar drag-and-drop feature is completely broken — dragging a driver card onto any calendar day does nothing. No visual highlight, no dialog.

Three bugs were found through code analysis:

1. **PRIMARY BUG**: Type validation in `handleDayDrop` checks `typeof id !== "string"` but `Driver.id` is `number`. After `JSON.parse()`, the id is a number, so the check ALWAYS fails and the function silently returns. The dialog never opens.
2. **ROLE BUG**: `SCHEDULE_ROLES = ["admin", "editor"]` excludes dispatchers — the primary day-to-day schedulers. When logged in as dispatcher, `canSchedule` is false, making `canDrag` false (cards not draggable) and `onDayDrop` undefined (no drop targets).
3. **MISSING DROP SUPPORT**: `ThreeMonthView` and `YearView` don't accept `onDayDrop` prop. `CalendarGrid` doesn't forward it to these views. Drop only works on WeekView and MonthView.

**Note on YearView**: Year view cells are 16px squares (`size-4`) — too small for reliable drop targets. This plan intentionally skips drop support for YearView. ThreeMonthView cells are large enough (aspect-square with day numbers).

## Design System

### Master Rules (from MASTER.md)
- Transitions: 150-300ms for all state changes
- Focus rings: 3px for WCAG AAA compliance
- No hardcoded colors — semantic tokens only

### Page Override
None — dashboard uses MASTER.md rules.

### Tokens Used
- `--color-interactive` / `bg-interactive/10` — drag-over highlight (already used in MonthView/WeekView)
- `ring-interactive` — drag-over ring indicator
- `border-border-subtle` — day cell borders
- `--spacing-tight`, `--spacing-card`, `--spacing-cell` — existing spacing tokens

## Components Needed

### Existing (no changes)
- `DriverRoster` — drag source (already works correctly with `draggable` + `dataTransfer`)
- `DriverDropDialog` — action picker dialog (works correctly once drop fires)
- `WeekView` — already has drop handlers (will work once Bug 1 is fixed)
- `MonthView` — already has drop handlers (will work once Bug 1 is fixed)

### Modified
- `DashboardContent` — fix type validation + add dispatcher role
- `ThreeMonthView` — add drop handler support
- `CalendarGrid` — forward `onDayDrop` to ThreeMonthView

### New Components
None.

### New shadcn/ui to Install
None.

## i18n Keys

No new i18n keys needed — all drag-and-drop strings already exist in `dashboard.roster.*` and `dashboard.dropAction.*`.

## Data Fetching

No changes — existing `useDriversSummary()` hook and `useCalendarEvents()` hook remain unchanged.

## RBAC Integration

No middleware changes needed — the dashboard is accessible to all authenticated users. The `SCHEDULE_ROLES` array controls drag-and-drop permission client-side.

## Sidebar Navigation

No changes.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/apps/web/CLAUDE.md` — Frontend conventions, React 19 anti-patterns

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/dashboard/month-view.tsx` — Reference drop handler implementation (lines 126-140)
- `cms/apps/web/src/components/dashboard/week-view.tsx` — Reference drop handler implementation (lines 137-151)

### Files to Modify
- `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — Bug 1 (type check) + Bug 2 (roles)
- `cms/apps/web/src/components/dashboard/three-month-view.tsx` — Bug 3 (add drop support)
- `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — Bug 3 (forward prop)

### Files to Read (context only, no modifications)
- `cms/apps/web/src/components/dashboard/driver-roster.tsx` — Drag source implementation
- `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` — Dialog that opens on drop
- `cms/apps/web/src/types/driver.ts` — `Driver.id` is `number` (confirms Bug 1)
- `cms/apps/web/src/types/dashboard.ts` — `CalendarEvent` type
- `cms/apps/web/src/components/dashboard/year-view.tsx` — Intentionally skipped (cells too small)

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities.

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `bg-blue-600`, `bg-blue-500` | `bg-interactive` |
| `bg-gray-100` | `bg-surface` |
| `border-gray-200` | `border-border` |
| `ring-blue-500` | `ring-interactive` |

Drag-over visual feedback must use the same pattern as MonthView:
```
ring-2 ring-interactive bg-interactive/10
```

## React 19 Coding Rules

- **No `setState` in `useEffect`** — use `key` prop for remounting
- **No component definitions inside components** — `MiniMonth` in `three-month-view.tsx` is already correctly extracted at module scope
- **Hook ordering**: `useState` before `useMemo`/`useCallback`

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Fix type validation in handleDayDrop
**File:** `cms/apps/web/src/components/dashboard/dashboard-content.tsx` (modify)
**Action:** UPDATE

This is the PRIMARY bug. The `handleDayDrop` callback at line 44-62 validates the parsed driver JSON. Line 50 checks:
```ts
typeof (parsed as Record<string, unknown>).id !== "string"
```

But `Driver.id` is type `number` (see `cms/apps/web/src/types/driver.ts` line 2). After `JSON.parse()`, the id field is a JavaScript number. The check `typeof id !== "string"` evaluates to `true` (because typeof number === "number", not "string"), so the `if` block ALWAYS enters and `return` is called. The dialog never opens.

**Change line 50 from:**
```ts
typeof (parsed as Record<string, unknown>).id !== "string" ||
```

**To:**
```ts
typeof (parsed as Record<string, unknown>).id !== "number" ||
```

No other changes to this function. The `first_name` and `last_name` checks on lines 51-52 are correct (they are strings).

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
```

---

### Task 2: Add dispatcher to SCHEDULE_ROLES
**File:** `cms/apps/web/src/components/dashboard/dashboard-content.tsx` (modify)
**Action:** UPDATE

Line 26 currently reads:
```ts
const SCHEDULE_ROLES = ["admin", "editor"];
```

Dispatchers are the primary day-to-day schedulers and must be able to drag-and-drop drivers onto the calendar.

**Change to:**
```ts
const SCHEDULE_ROLES = ["admin", "editor", "dispatcher"];
```

This affects:
- `canSchedule` (line 42) — enables the drop handler on calendar views
- `canDrag` passed to `DriverRoster` (line 118) — makes driver cards draggable

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
```

---

### Task 3: Add drop support to ThreeMonthView
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx` (modify)
**Action:** UPDATE

Currently `ThreeMonthView` and its inner `MiniMonth` component have no drag-and-drop support. Day cells are plain `<div>` elements without any drag event handlers.

**Step 3a: Update ThreeMonthViewProps interface (line 8-11)**

Change:
```ts
interface ThreeMonthViewProps {
  currentDate: Date;
  events: CalendarEvent[];
}
```

To:
```ts
interface ThreeMonthViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
}
```

**Step 3b: Update MiniMonth component props (line 64-73)**

Add `onDayDrop` to MiniMonth's props:

Change the inline type at lines 66-73:
```ts
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
```

To:
```ts
function MiniMonth({
  year,
  month,
  events,
  today,
  onDayDrop,
}: {
  year: number;
  month: number;
  events: CalendarEvent[];
  today: Date;
  onDayDrop?: (date: Date, driverJson: string) => void;
}) {
```

**Step 3c: Add drag state to MiniMonth**

After line 76 (`const weeks = useMemo(...)`), add:
```ts
const [dragOverDate, setDragOverDate] = useState<string | null>(null);
```

Also add `useState` to the import on line 1:
```ts
import { useMemo, useState } from "react";
```

**Step 3d: Add drag handlers to day cells**

Currently the day cell (the `<div>` at lines 136-175 inside the `day` branch) is:
```tsx
<div
  key={day.getDate()}
  className={cn(
    "aspect-square overflow-hidden rounded-sm border border-border-subtle p-px transition-colors duration-200",
    isToday && "border-interactive bg-interactive/10"
  )}
>
```

Replace with:
```tsx
<div
  key={day.getDate()}
  className={cn(
    "aspect-square overflow-hidden rounded-sm border border-border-subtle p-px transition-colors duration-200",
    isToday && "border-interactive bg-interactive/10",
    dragOverDate === dateKey && "ring-2 ring-interactive bg-interactive/10"
  )}
  onDragOver={onDayDrop ? (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    setDragOverDate(dateKey);
  } : undefined}
  onDragLeave={onDayDrop ? () => setDragOverDate(null) : undefined}
  onDrop={onDayDrop ? (e) => {
    e.preventDefault();
    setDragOverDate(null);
    const driverJson = e.dataTransfer.getData("application/vtv-driver");
    if (driverJson) {
      onDayDrop(day, driverJson);
    }
  } : undefined}
>
```

**Step 3e: Pass onDayDrop to MiniMonth from ThreeMonthView**

In the `ThreeMonthView` component (line 186), update the destructured props:

Change:
```ts
export function ThreeMonthView({ currentDate, events }: ThreeMonthViewProps) {
```
To:
```ts
export function ThreeMonthView({ currentDate, events, onDayDrop }: ThreeMonthViewProps) {
```

Then in the JSX where `MiniMonth` is rendered (line 205-210), add the prop:

Change:
```tsx
<MiniMonth
  key={`${year}-${month}`}
  year={year}
  month={month}
  events={events}
  today={today}
/>
```

To:
```tsx
<MiniMonth
  key={`${year}-${month}`}
  year={year}
  month={month}
  events={events}
  today={today}
  onDayDrop={onDayDrop}
/>
```

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint
```

---

### Task 4: Forward onDayDrop to ThreeMonthView in CalendarGrid
**File:** `cms/apps/web/src/components/dashboard/calendar-grid.tsx` (modify)
**Action:** UPDATE

Currently line 36-37 renders ThreeMonthView WITHOUT onDayDrop:
```tsx
{view === "3month" && (
  <ThreeMonthView currentDate={currentDate} events={events} />
)}
```

**Change to:**
```tsx
{view === "3month" && (
  <ThreeMonthView currentDate={currentDate} events={events} onDayDrop={onDayDrop} />
)}
```

YearView is intentionally left without drop support — its 16px cells are too small for reliable drop targets.

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint
```

---

### Task 5: Final Validation (3-Level Pyramid)

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

---

## Post-Implementation Checks

- [ ] Bug 1 fixed: Dragging a driver onto a MonthView day opens the DriverDropDialog
- [ ] Bug 1 fixed: Dragging a driver onto a WeekView day opens the DriverDropDialog
- [ ] Bug 2 fixed: Dispatcher role can drag driver cards
- [ ] Bug 3 fixed: ThreeMonthView day cells highlight on drag-over (ring-2 ring-interactive)
- [ ] Bug 3 fixed: Dropping a driver on a ThreeMonthView day opens the DriverDropDialog
- [ ] YearView: No drag support (intentional — cells too small)
- [ ] No regressions: Calendar events still display correctly
- [ ] No regressions: Driver roster still loads and renders
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] All validation levels pass (type-check, lint, build)

## Acceptance Criteria

This session is complete when:
- [ ] Drag-and-drop works on WeekView, MonthView, and ThreeMonthView
- [ ] Admin, editor, AND dispatcher roles can drag
- [ ] Visual feedback (ring highlight) appears on drag-over for all supported views
- [ ] DriverDropDialog opens with correct driver + date on drop
- [ ] Event creation via dialog works (requires running backend)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] Ready for `/commit`

## Session Roadmap

This is **Session 1 of 4**. The full feature plan:

| Session | Scope | Type | Dependency |
|---------|-------|------|------------|
| **1 (this)** | Fix drag-and-drop bugs on all views + dispatcher role | FE bug fix | None |
| **2** | Backend: Add `goals` JSON field to events model, update schemas/routes | BE (`/be-planning`) | None |
| **3** | FE: Two-step dialog (pick action → add goals), route assignment dropdown, driver data pre-fill | FE (`/fe-planning`) | Session 2 |
| **4 (V2)** | FE: Calendar goal indicators, goal completion UI, checklist tracking | FE (`/fe-planning`) | Session 3 |

### Session 2 Backend Requirements (for `/be-planning`)
- Add `goals` JSONB column to `events` table (nullable, default null)
- Update `EventCreate`/`EventUpdate`/`EventResponse` Pydantic schemas to include `goals` field
- Goals schema: `{ items: [{ text: string, completed: boolean, type: "route"|"training"|"note"|"checklist" }], route_id?: number, transport_type?: string, vehicle_id?: string }`
- Backward compatible: existing events without goals return `goals: null`
- New Alembic migration

### Session 3 Frontend Scope (for `/fe-planning`)
- Two-step DriverDropDialog: action picker → goals form (shifts + training only)
- Route assignment dropdown (filtered to driver's `qualified_route_ids`)
- Transport type selector + optional vehicle number
- Pre-fill driver data (default shift, license warnings)
- Performance notes text field
- Driver roster sidebar enhancements (show qualified routes, license status)

### Session 4 Frontend Scope (V2, for `/fe-planning`)
- Mini cards on calendar days showing driver name + route + completion %
- Color-coded status: green (done), amber (in progress), gray (not started)
- Click event → goal completion view with checkable items
- "Today's Goals" dashboard panel
- Goal tracking on driver profile page (`/drivers`)
- Pre-filled checklist templates per action type
