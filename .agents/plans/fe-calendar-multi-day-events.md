# Plan: Fix Calendar Multi-Day Event Distribution

## Feature Metadata
**Feature Type**: Enhancement (Bug Fix)
**Estimated Complexity**: Medium
**Route**: N/A — modifies existing dashboard calendar components
**Auth Required**: N/A — no route/auth changes
**Allowed Roles**: N/A — no RBAC changes

## Feature Description

All three calendar views (week, month, three-month) only assign events to their START date using `isSameDay(d, event.start)`. Multi-day events — vacations, sick days, multi-day maintenance windows — appear on a single day instead of spanning across all days they cover. This makes the calendar look "wacky and out of order" because, for example, a Monday–Friday vacation only shows a chip on Monday.

The fix changes the event-to-day bucketing logic in all three calendar views. Instead of matching `event.start` to one specific day, events are distributed across every day they overlap with. For the week view's timed events, start/end times are clipped to the visible range (06:00–22:00) per day so that midnight-crossing events render correctly in each day column.

**User-facing behavior after fix:**
- A 5-day vacation shows an all-day chip on each of the 5 day columns
- A night shift (21:00–07:00) shows as a timed block on both days: 21:00–22:00 on day 1, 06:00–07:00 on day 2
- Month and three-month views show event dots/badges on every day an event covers
- All existing visual styles remain unchanged

## Design System

### Master Rules (from MASTER.md)
- No visual style changes — keep all existing semantic tokens
- Calendar spacing tokens: `--spacing-row` (48px), `--spacing-cell` (6px), `--spacing-tight` (4px)

### Page Override
- None — no design system changes needed

### Tokens Used
- No new tokens. Existing tokens only.

## Components Needed

### Existing (no API changes)
- `CalendarEventCard` — receives same `CalendarEvent` object, no prop changes
- `AllDayChip` — receives same `CalendarEvent` object, no prop changes
- `GoalProgressBadge` — no changes
- `LiveTimeline` — no changes

### New shadcn/ui to Install
- None

### Custom Components to Create
- None

## i18n Keys
- None — no new user-facing strings

## Data Fetching
- No changes — `useCalendarEvents` already fetches events for a date range
- Events come from `/api/v1/events` with `start_date`/`end_date` filters
- The hook at `src/hooks/use-calendar-events.ts` needs no modification

## RBAC Integration
- No changes

## Sidebar Navigation
- No changes

## Relevant Files

The executing agent MUST read these files before starting implementation:

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/apps/web/CLAUDE.md` — Frontend conventions, React 19 anti-patterns

### Files to Modify
- `cms/apps/web/src/components/dashboard/week-view.tsx` — Event bucketing + time clipping + layout algorithm
- `cms/apps/web/src/components/dashboard/month-view.tsx` — Event bucketing
- `cms/apps/web/src/components/dashboard/three-month-view.tsx` — Event bucketing

### Files to Read (context only — do not modify)
- `cms/apps/web/src/components/dashboard/calendar-event.tsx` — CalendarEventCard (unchanged)
- `cms/apps/web/src/types/dashboard.ts` — CalendarEvent type (unchanged)
- `cms/apps/web/src/hooks/use-calendar-events.ts` — Data fetching (unchanged)

## Design System Color Rules

No color changes in this plan. The executor MUST NOT alter any existing color tokens,
category styles, or visual styling. This plan only changes event arrangement logic.

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount
- **No component definitions inside components** — extract all sub-components to module scope
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies**
- This plan does NOT add new component definitions or hooks — it modifies existing `useMemo` bodies

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE

---

### Task 1: Add TimedSlice interface and update eventsByDay in week-view

**File:** `cms/apps/web/src/components/dashboard/week-view.tsx` (modify)
**Action:** UPDATE

This is the core fix. The `eventsByDay` computation currently uses `isSameDay(d, event.start)`
which only assigns events to their start date. Replace with an overlap check that distributes
events across all days they cover.

**Step 1a: Add `TimedSlice` interface after the existing `LayoutedEvent` interface (around line 46)**

Add this new interface right after `LayoutedEvent`:

```tsx
/** A timed event clipped to a single day's visible range */
interface TimedSlice {
  event: CalendarEvent;
  /** Minutes from midnight, clipped to [START_HOUR*60, END_HOUR*60] */
  startMin: number;
  /** Minutes from midnight, clipped to [START_HOUR*60, END_HOUR*60] */
  endMin: number;
}
```

**Step 1b: Update the `eventsByDay` Map type**

Change the Map value type from `{ allDay: CalendarEvent[]; timed: CalendarEvent[] }` to
`{ allDay: CalendarEvent[]; timed: TimedSlice[] }`.

The full replacement for the `eventsByDay` useMemo (lines 150–167):

```tsx
const eventsByDay = useMemo(() => {
  const map = new Map<number, { allDay: CalendarEvent[]; timed: TimedSlice[] }>();
  for (let i = 0; i < 7; i++) {
    map.set(i, { allDay: [], timed: [] });
  }

  const visibleStartMin = START_HOUR * 60;
  const visibleEndMin = END_HOUR * 60;

  for (const event of events) {
    for (let i = 0; i < 7; i++) {
      const dayStart = new Date(weekDays[i]);
      dayStart.setHours(0, 0, 0, 0);
      const dayEnd = new Date(dayStart);
      dayEnd.setHours(23, 59, 59, 999);

      // Check if event overlaps with this day
      if (event.start <= dayEnd && event.end > dayStart) {
        const bucket = map.get(i)!;

        if (isAllDayEvent(event)) {
          bucket.allDay.push(event);
        } else {
          // Clip the event's time to this day's visible range (START_HOUR–END_HOUR)
          const dayVisibleStart = new Date(weekDays[i]);
          dayVisibleStart.setHours(START_HOUR, 0, 0, 0);
          const dayVisibleEnd = new Date(weekDays[i]);
          dayVisibleEnd.setHours(END_HOUR, 0, 0, 0);

          const clipStartMs = Math.max(event.start.getTime(), dayVisibleStart.getTime());
          const clipEndMs = Math.min(event.end.getTime(), dayVisibleEnd.getTime());

          if (clipEndMs > clipStartMs) {
            const clippedStart = new Date(clipStartMs);
            const clippedEnd = new Date(clipEndMs);
            bucket.timed.push({
              event,
              startMin: clippedStart.getHours() * 60 + clippedStart.getMinutes(),
              endMin: clippedEnd.getHours() * 60 + clippedEnd.getMinutes(),
            });
          }
        }
      }
    }
  }

  return map;
}, [events, weekDays]);
```

**Key behavioral changes:**
- Multi-day all-day events now appear in every day column they cover
- Multi-day timed events (e.g., night shifts crossing midnight) appear in both day columns
- Timed events are clipped to the visible 06:00–22:00 range per day
- Zero-duration clips (event doesn't actually fall in visible hours) are skipped

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` — verify TimedSlice type is compatible
- Note: This task will cause type errors in `layoutEvents` and rendering code until Tasks 2–3 are done.
  The executor should complete Tasks 1–3 before running validation.

---

### Task 2: Update layoutEvents to work with TimedSlice

**File:** `cms/apps/web/src/components/dashboard/week-view.tsx` (modify)
**Action:** UPDATE

The `layoutEvents` function currently takes `CalendarEvent[]` and extracts start/end hours
from the raw event times. Update it to take `TimedSlice[]` and use the pre-clipped
`startMin`/`endMin` values.

**Replace the entire `LayoutedEvent` interface and `layoutEvents` function (lines 46–103) with:**

```tsx
interface LayoutedSlice {
  slice: TimedSlice;
  column: number;
  totalColumns: number;
}

/** Assign side-by-side columns to overlapping timed event slices */
function layoutEvents(slices: TimedSlice[]): LayoutedSlice[] {
  if (slices.length === 0) return [];

  const sorted = [...slices].sort(
    (a, b) => a.startMin - b.startMin || (b.endMin - b.startMin) - (a.endMin - a.startMin)
  );

  const columns: { end: number; slices: TimedSlice[] }[] = [];
  const sliceColumns = new Map<TimedSlice, number>();

  for (const slice of sorted) {
    let placed = false;
    for (let c = 0; c < columns.length; c++) {
      if (slice.startMin >= columns[c].end) {
        columns[c].end = slice.endMin;
        columns[c].slices.push(slice);
        sliceColumns.set(slice, c);
        placed = true;
        break;
      }
    }
    if (!placed) {
      sliceColumns.set(slice, columns.length);
      columns.push({
        end: slice.endMin,
        slices: [slice],
      });
    }
  }

  // For each slice, find how many columns overlap at that time
  return sorted.map((slice) => {
    let maxCols = 1;
    for (const other of sorted) {
      if (other.startMin < slice.endMin && other.endMin > slice.startMin) {
        const col = sliceColumns.get(other)!;
        if (col + 1 > maxCols) maxCols = col + 1;
      }
    }
    return {
      slice,
      column: sliceColumns.get(slice)!,
      totalColumns: maxCols,
    };
  });
}
```

**Key changes from the old version:**
- Input type: `CalendarEvent[]` → `TimedSlice[]`
- Return type: `LayoutedEvent` → `LayoutedSlice`
- Uses `slice.startMin`/`slice.endMin` (pre-clipped integers) instead of extracting hours from `event.start`/`event.end`
- Column assignment uses the Map with `TimedSlice` references (object identity) instead of `event.id` strings — this is correct because each slice is a unique object even if two slices reference the same event (on different days)
- The old `LayoutedEvent` interface is removed (replaced by `LayoutedSlice`)

**Per-task validation:**
- Do not validate yet — Task 3 must update the rendering code first

---

### Task 3: Update timed event rendering to use LayoutedSlice

**File:** `cms/apps/web/src/components/dashboard/week-view.tsx` (modify)
**Action:** UPDATE

Update the timed events rendering block (around lines 299–331) to use the new `LayoutedSlice` type
and draw events using clipped time data.

**Replace the timed events overlay block inside each day column.** Find the comment
`{/* Timed events overlay — side-by-side for overlaps */}` and replace the entire map block:

```tsx
{/* Timed events overlay — side-by-side for overlaps */}
{layoutEvents(eventsByDay.get(dayIdx)?.timed ?? []).map(({ slice, column, totalColumns }) => {
  // COUPLING: 48px must match --spacing-row token in tokens.css (3rem = 48px at 16px base)
  const ROW_HEIGHT_PX = 48;
  const topPx =
    ((slice.startMin - START_HOUR * 60) / 60) * ROW_HEIGHT_PX;
  const heightPx =
    ((slice.endMin - slice.startMin) / 60) * ROW_HEIGHT_PX;
  const widthPct = 100 / totalColumns;
  const leftPct = column * widthPct;

  return (
    <div
      key={`${slice.event.id}-${dayIdx}`}
      className="absolute overflow-hidden"
      style={{
        top: `${topPx}px`,
        height: `${heightPx}px`,
        left: `${leftPct}%`,
        width: `${widthPct}%`,
      }}
    >
      <CalendarEventCard
        event={slice.event}
        onClick={onEventClick ? () => onEventClick(slice.event) : undefined}
        onDriverClick={onDriverClick ? () => onDriverClick(slice.event) : undefined}
      />
    </div>
  );
})}
```

**Key changes from the old version:**
- Destructures `{ slice, column, totalColumns }` instead of `{ event, column, totalColumns }`
- Uses `slice.startMin` and `slice.endMin` for positioning instead of extracting from `event.start`/`event.end`
- React key changed from `event.id` to `${slice.event.id}-${dayIdx}` — same event can appear on multiple days so the key must include the day index
- `CalendarEventCard` receives `slice.event` (the original event) — the card displays the event's real full time range, even if the visual block is clipped to one day

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

Both must pass with 0 errors. If type errors appear, verify that:
1. `TimedSlice` interface is defined before `layoutEvents` function
2. `LayoutedSlice` interface is defined (replaces old `LayoutedEvent`)
3. The `eventsByDay` Map value type matches `{ allDay: CalendarEvent[]; timed: TimedSlice[] }`

---

### Task 4: Fix month-view event bucketing for multi-day events

**File:** `cms/apps/web/src/components/dashboard/month-view.tsx` (modify)
**Action:** UPDATE

The month view's `eventsByDate` useMemo (inside the `MonthView` component, around lines 76–84)
only adds events to their start date. Replace with a loop that distributes each event across
all days it covers.

**Replace the `eventsByDate` useMemo body with:**

```tsx
const eventsByDate = useMemo(() => {
  const map = new Map<string, CalendarEvent[]>();
  for (const event of events) {
    // Walk from event start date to event end date, adding to each day
    const cursor = new Date(event.start);
    cursor.setHours(0, 0, 0, 0);
    const endDay = new Date(event.end);
    endDay.setHours(0, 0, 0, 0);

    while (cursor <= endDay) {
      const key = `${cursor.getFullYear()}-${cursor.getMonth()}-${cursor.getDate()}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(event);
      cursor.setDate(cursor.getDate() + 1);
    }
  }
  return map;
}, [events]);
```

**Behavioral change:**
- A vacation event Mon–Fri now shows a dot/badge in each of the 5 day cells
- A sick day event spanning 2 days shows on both day cells
- Short events (within a single day) behave identically to before — the cursor loop runs once

**Edge case handling:**
- Event ending at midnight (00:00): `endDay` is set to midnight of that day, so `cursor <= endDay` includes the start day but the end day at 00:00 means the cursor starts at 00:00 of start day and the end day cursor matches. Actually wait — if event ends at 00:00 on Tue, endDay would be Tue 00:00. cursor starts at Mon 00:00, then increments to Tue 00:00, and `cursor <= endDay` is true, so event shows on both Mon and Tue. For an event ending exactly at midnight, it arguably shouldn't show on the next day. To handle this: if `event.end` has hours=0 and minutes=0, subtract 1 day from endDay.

Add this refinement to the cursor calculation:

```tsx
const endDay = new Date(event.end);
// If event ends exactly at midnight, it doesn't extend into that day
if (endDay.getHours() === 0 && endDay.getMinutes() === 0) {
  endDay.setDate(endDay.getDate() - 1);
}
endDay.setHours(0, 0, 0, 0);
```

**Full corrected replacement:**

```tsx
const eventsByDate = useMemo(() => {
  const map = new Map<string, CalendarEvent[]>();
  for (const event of events) {
    const cursor = new Date(event.start);
    cursor.setHours(0, 0, 0, 0);
    const endDay = new Date(event.end);
    // If event ends exactly at midnight, it doesn't extend into that day
    if (endDay.getHours() === 0 && endDay.getMinutes() === 0) {
      endDay.setDate(endDay.getDate() - 1);
    }
    endDay.setHours(0, 0, 0, 0);

    while (cursor <= endDay) {
      const key = `${cursor.getFullYear()}-${cursor.getMonth()}-${cursor.getDate()}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(event);
      cursor.setDate(cursor.getDate() + 1);
    }
  }
  return map;
}, [events]);
```

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

Both must pass with 0 errors.

---

### Task 5: Fix three-month-view event bucketing for multi-day events

**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx` (modify)
**Action:** UPDATE

The three-month view's `eventsByDate` useMemo (inside the `MiniMonth` component, around lines 92–106)
has the same single-day bucketing bug. Replace with the same multi-day distribution pattern.

**Replace the `eventsByDate` useMemo body with:**

```tsx
const eventsByDate = useMemo(() => {
  const map = new Map<string, CalendarEvent[]>();
  for (const event of events) {
    const cursor = new Date(event.start);
    cursor.setHours(0, 0, 0, 0);
    const endDay = new Date(event.end);
    // If event ends exactly at midnight, it doesn't extend into that day
    if (endDay.getHours() === 0 && endDay.getMinutes() === 0) {
      endDay.setDate(endDay.getDate() - 1);
    }
    endDay.setHours(0, 0, 0, 0);

    while (cursor <= endDay) {
      // Only include days that fall within this mini-month
      if (cursor.getFullYear() === year && cursor.getMonth() === month) {
        const key = `${cursor.getFullYear()}-${cursor.getMonth()}-${cursor.getDate()}`;
        if (!map.has(key)) map.set(key, []);
        map.get(key)!.push(event);
      }
      cursor.setDate(cursor.getDate() + 1);
    }
  }
  return map;
}, [events, year, month]);
```

**Behavioral change:**
- Multi-day events spanning across months now show dots in each month's cells correctly
- The existing `year`/`month` filter is preserved (only includes days within this mini-month)
- Short single-day events behave identically to before

**Note:** The three-month view's `MiniMonth` component receives ALL events and filters by
year/month. The cursor loop naturally skips days outside the target month via the
`cursor.getFullYear() === year && cursor.getMonth() === month` check.

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

Both must pass with 0 errors.

---

### Task 6: Apply midnight boundary fix to week-view all-day overlap check

**File:** `cms/apps/web/src/components/dashboard/week-view.tsx` (modify)
**Action:** UPDATE

Add the same midnight boundary handling to the week-view's overlap check (from Task 1).
If an event ends exactly at midnight (00:00), it shouldn't count as overlapping with that
next day.

In the `eventsByDay` useMemo (modified in Task 1), find the overlap check:

```tsx
if (event.start <= dayEnd && event.end > dayStart) {
```

Replace with:

```tsx
// If event ends exactly at midnight, use the previous day's end as effective end
const effectiveEnd = (event.end.getHours() === 0 && event.end.getMinutes() === 0)
  ? new Date(event.end.getTime() - 1)
  : event.end;

if (event.start <= dayEnd && effectiveEnd > dayStart) {
```

Move this calculation ABOVE the inner `for` loop so it's computed once per event, not once per day:

**Full corrected eventsByDay structure (showing where `effectiveEnd` goes):**

```tsx
for (const event of events) {
  // If event ends exactly at midnight, it doesn't extend into that day
  const effectiveEnd = (event.end.getHours() === 0 && event.end.getMinutes() === 0)
    ? new Date(event.end.getTime() - 1)
    : event.end;

  for (let i = 0; i < 7; i++) {
    const dayStart = new Date(weekDays[i]);
    dayStart.setHours(0, 0, 0, 0);
    const dayEnd = new Date(dayStart);
    dayEnd.setHours(23, 59, 59, 999);

    if (event.start <= dayEnd && effectiveEnd > dayStart) {
      // ... rest of bucketing logic unchanged
```

**Also update the timed event clipping to use `effectiveEnd`:**

```tsx
const clipEndMs = Math.min(effectiveEnd.getTime(), dayVisibleEnd.getTime());
```

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

---

### Task 7: Remove unused LayoutedEvent interface

**File:** `cms/apps/web/src/components/dashboard/week-view.tsx` (modify)
**Action:** UPDATE

If Task 2 didn't fully remove the old `LayoutedEvent` interface (lines 46–50), verify it's gone.
The old interface:

```tsx
interface LayoutedEvent {
  event: CalendarEvent;
  column: number;
  totalColumns: number;
}
```

Should be completely replaced by `LayoutedSlice` and `TimedSlice` from Tasks 1–2.
Grep the file for `LayoutedEvent` — it should return zero results.

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
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

- [ ] Multi-day all-day events show chips on each day column in week view
- [ ] Multi-day timed events show blocks on each day (clipped to 06:00–22:00) in week view
- [ ] Overlapping events still render side-by-side correctly
- [ ] Events ending at midnight don't bleed into the next day
- [ ] Month view shows event dots on all days an event covers
- [ ] Three-month view shows event dots on all days an event covers
- [ ] Single-day events behave identically to before (no regression)
- [ ] No hardcoded colors — all styling uses existing semantic tokens
- [ ] No new lint warnings or type errors
- [ ] CalendarEventCard visual appearance unchanged
- [ ] AllDayChip visual appearance unchanged
- [ ] LiveTimeline (current time indicator) unaffected
- [ ] Drag-and-drop functionality preserved

## Acceptance Criteria

This feature is complete when:
- [ ] Multi-day events display across all days they cover in all 3 calendar views
- [ ] Timed events crossing midnight render correctly on both day columns
- [ ] Events ending exactly at midnight don't show on the next day
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No visual regressions in existing single-day events
- [ ] No regressions in drag-and-drop, event click, driver click handlers
- [ ] Ready for `/commit`

## Security Checklist

- [x] No new API calls — no security surface change
- [x] No user input handling changes
- [x] No localStorage/cookie changes
- [x] No external links added
- [x] No `dangerouslySetInnerHTML` usage

## Notes for Executor

1. **Complete Tasks 1–3 together before validating** — Task 1 changes the Map type which
   breaks the rendering code until Task 3 fixes it. Run validation after Task 3.

2. **The `TimedSlice` interface uses object identity in Maps** — The `sliceColumns` Map in
   `layoutEvents` uses `TimedSlice` object references as keys. This works because each slice
   is a fresh object created in the `eventsByDay` computation. Do NOT deduplicate or reuse
   slice objects.

3. **CalendarEventCard receives the ORIGINAL event** — The card still shows the event's
   real full time range (e.g., "21:00 – 07:00") even when the visual block is clipped to
   one day's column. This is intentional — it gives context about the full event duration.

4. **Performance consideration** — The new bucketing iterates `events × 7 days` for week view
   and `events × days_per_event` for month/three-month. With typical event counts (<100),
   this is negligible.

5. **Test with these scenarios:**
   - Single-day event (e.g., 09:00–11:00 on Monday) — should behave exactly as before
   - Multi-day all-day event (e.g., vacation Mon–Fri) — chip on each day
   - Night shift crossing midnight (e.g., 21:00 Mon – 07:00 Tue) — blocks on both days
   - Event ending at exactly midnight — should NOT appear on the next day
   - Week boundary: event starting Friday, ending next Monday — only Fri/Sat/Sun show in current week
