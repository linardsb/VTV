# Plan: Dashboard Enhancement — Driver Drag-and-Drop to Calendar

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: High
**Route**: `/[locale]/` (existing dashboard — no route change)
**Auth Required**: Yes
**Allowed Roles**: all authenticated (drag-and-drop restricted to admin, editor — event creation roles)

## Feature Description

The dashboard at `/[locale]/` currently renders a metrics panel (live vehicle stats) and an operations calendar (events from the API). Both pull real data but show empty states when the backend has no data. This enhancement adds a **driver roster panel** to the dashboard and enables **drag-and-drop scheduling**: users drag a driver card from the roster onto a calendar day, then choose from a set of action options in a dialog.

The driver roster displays a compact, scrollable list of all active drivers fetched from `GET /api/v1/drivers`. Each driver card is draggable (HTML5 Drag and Drop API — no new dependencies) and shows the driver's name, status badge, default shift, and employee number.

When a driver card is dropped onto a day cell in the Month or Week calendar view, a centered Dialog appears with five action options: **Assign Shift** (pre-fills the driver's default shift times), **Mark Leave** (all-day planned leave), **Mark Sick Day** (all-day sick status), **Schedule Training** (user picks a 2-hour time slot), and **Custom Event** (free-form with driver name pre-filled). Selecting an action creates an operational event via `POST /api/v1/events` with the appropriate category, priority, and time range, then refreshes the calendar. Only `admin` and `editor` roles can drag — other roles see the roster as read-only context.

## Design System

### Master Rules (from MASTER.md)
- Typography: Lexend headings, Source Sans 3 body, 16px+ base
- Spacing: Use compact dashboard tokens (`--spacing-card`, `--spacing-grid`, `--spacing-inline`)
- Colors: Semantic tokens only — no primitive Tailwind classes
- Transitions: 150–300ms on all hover/state changes
- Accessibility: 4.5:1 contrast, visible focus rings, cursor-pointer on clickable elements

### Page Override
- None exists — no `cms/design-system/vtv/pages/dashboard.md` file. Do NOT generate one during execution. Follow MASTER.md rules only.

### Tokens Used
- Surface: `bg-surface`, `bg-surface-raised`, `bg-card-bg`, `bg-background`
- Border: `border-border`, `border-border-subtle`, `border-card-border`, `border-interactive`
- Text: `text-foreground`, `text-foreground-muted`, `text-interactive`
- Status: `bg-status-ontime`, `bg-status-delayed`, `bg-status-critical` (driver status badges)
- Category: `bg-category-driver-shift`, `bg-category-maintenance` (event dots and cards)
- Interactive: `bg-interactive/10`, `bg-interactive/20` (drop zone highlight)
- Spacing: `--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight`, `--spacing-section`

## Components Needed

### Existing (shadcn/ui — already installed)
- `Dialog` / `DialogContent` / `DialogHeader` / `DialogTitle` / `DialogDescription` — drop action dialog
- `Button` — action buttons, dialog actions
- `Badge` — driver status/shift badges
- `Skeleton` — loading states for driver roster
- `ScrollArea` — scrollable driver roster list
- `Select` / `SelectTrigger` / `SelectContent` / `SelectItem` — time picker in training/custom actions
- `Input` — custom event title/description
- `Label` — form labels in dialog

### New shadcn/ui to Install
- None — all required components already installed.

### Custom Components to Create
- `DashboardContent` at `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — client wrapper orchestrating metrics, roster, calendar, and DnD state
- `DriverRoster` at `cms/apps/web/src/components/dashboard/driver-roster.tsx` — compact scrollable list of draggable driver cards
- `DriverDropDialog` at `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` — action selection and event creation dialog

### Custom Hooks to Create
- `useDriversSummary` at `cms/apps/web/src/hooks/use-drivers-summary.ts` — lightweight hook fetching active drivers for the roster panel

## i18n Keys

### Latvian (`lv.json`) — add under `"dashboard"` namespace
```json
{
  "dashboard": {
    "roster": {
      "title": "Vadītāji",
      "empty": "Nav pieejamu vadītāju",
      "loading": "Ielādē vadītājus...",
      "dragHint": "Velciet uz kalendāru, lai plānotu",
      "shift": "Maiņa",
      "employee": "Nr."
    },
    "dropAction": {
      "title": "Plānot vadītāju",
      "description": "Izvēlieties darbību priekš {name} uz {date}",
      "assignShift": "Piešķirt maiņu",
      "assignShiftDesc": "Ieplānot {shift} maiņu šajā dienā",
      "markLeave": "Atzīmēt atvaļinājumu",
      "markLeaveDesc": "Reģistrēt plānotu prombūtni visa diena",
      "markSick": "Atzīmēt slimību",
      "markSickDesc": "Reģistrēt slimības dienu",
      "scheduleTraining": "Ieplānot apmācību",
      "scheduleTrainingDesc": "Pievienot apmācības sesiju (2 stundas)",
      "customEvent": "Brīvs notikums",
      "customEventDesc": "Izveidot pielāgotu notikumu ar vadītāja vārdu",
      "startTime": "Sākuma laiks",
      "endTime": "Beigu laiks",
      "eventTitle": "Notikuma nosaukums",
      "save": "Saglabāt",
      "cancel": "Atcelt",
      "saving": "Saglabā...",
      "created": "Notikums veiksmīgi izveidots",
      "createError": "Neizdevās izveidot notikumu",
      "shiftMorning": "Rīta (05:00–13:00)",
      "shiftAfternoon": "Pēcpusdienas (13:00–21:00)",
      "shiftEvening": "Vakara (17:00–01:00)",
      "shiftNight": "Nakts (22:00–06:00)"
    }
  }
}
```

### English (`en.json`) — add under `"dashboard"` namespace
```json
{
  "dashboard": {
    "roster": {
      "title": "Drivers",
      "empty": "No available drivers",
      "loading": "Loading drivers...",
      "dragHint": "Drag onto calendar to schedule",
      "shift": "Shift",
      "employee": "No."
    },
    "dropAction": {
      "title": "Schedule Driver",
      "description": "Choose an action for {name} on {date}",
      "assignShift": "Assign Shift",
      "assignShiftDesc": "Schedule {shift} shift on this day",
      "markLeave": "Mark Leave",
      "markLeaveDesc": "Record planned absence for the full day",
      "markSick": "Mark Sick Day",
      "markSickDesc": "Record a sick day",
      "scheduleTraining": "Schedule Training",
      "scheduleTrainingDesc": "Add a training session (2 hours)",
      "customEvent": "Custom Event",
      "customEventDesc": "Create a custom event with driver name",
      "startTime": "Start time",
      "endTime": "End time",
      "eventTitle": "Event title",
      "save": "Save",
      "cancel": "Cancel",
      "saving": "Saving...",
      "created": "Event created successfully",
      "createError": "Failed to create event",
      "shiftMorning": "Morning (05:00–13:00)",
      "shiftAfternoon": "Afternoon (13:00–21:00)",
      "shiftEvening": "Evening (17:00–01:00)",
      "shiftNight": "Night (22:00–06:00)"
    }
  }
}
```

## Data Fetching

- **Drivers roster**: `GET /api/v1/drivers?active_only=true&page_size=100` via `fetchDrivers` from `@/lib/drivers-client.ts`. Fetched client-side in `useDriversSummary` hook. Polls every 120s.
- **Calendar events**: Already fetched via `useCalendarEvents` hook (events-sdk, 60s polling). Needs a `refetch()` method added so the drop dialog can trigger a refresh after creating an event.
- **Event creation**: `POST /api/v1/events/` via `createEvent` from `@/lib/events-sdk.ts`. Called from the `DriverDropDialog` component.
- **Dashboard metrics**: Already fetched via `useDashboardMetrics` hook (30s polling). No changes needed.
- **CRITICAL — Server/client boundary:**
  - All new code is client-side (hooks + components with `"use client"`)
  - Uses `authFetch` for drivers (works in client context via `getSession()`)
  - Uses `@vtv/sdk` for events (already configured with JWT interceptor)

## RBAC Integration

- **No middleware changes** — dashboard is the default authenticated page, not matched by middleware
- **Frontend role gating**: The driver roster's drag functionality and drop dialog are only enabled for `admin` and `editor` roles (which can `POST /api/v1/events/`). Other roles see the roster as read-only reference. Check via `session?.user?.role`.

## Sidebar Navigation

- **No changes** — dashboard already has its sidebar entry as the first nav item

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/apps/web/CLAUDE.md` — Frontend-specific conventions, React 19 anti-patterns
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Current dashboard server component
- `cms/apps/web/src/components/dashboard/calendar-panel.tsx` — CalendarPanel pattern (client wrapper)
- `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — CalendarGrid (view switching)
- `cms/apps/web/src/components/dashboard/month-view.tsx` — Month grid (primary drop target)
- `cms/apps/web/src/components/dashboard/week-view.tsx` — Week grid (secondary drop target)
- `cms/apps/web/src/components/dashboard/calendar-event.tsx` — CalendarEventCard styling
- `cms/apps/web/src/hooks/use-calendar-events.ts` — Calendar event fetching hook
- `cms/apps/web/src/hooks/use-dashboard-metrics.ts` — Dashboard metrics hook pattern
- `cms/apps/web/src/lib/events-sdk.ts` — Events API client (createEvent function)
- `cms/apps/web/src/lib/drivers-client.ts` — Drivers API client (fetchDrivers function)
- `cms/apps/web/src/types/driver.ts` — Driver interface
- `cms/apps/web/src/types/event.ts` — EventCreate, OperationalEvent interfaces
- `cms/apps/web/src/types/dashboard.ts` — CalendarEvent, CalendarViewMode types

### Files to Modify
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Restructure to use DashboardContent
- `cms/apps/web/src/components/dashboard/calendar-panel.tsx` — Accept onDayDrop callback
- `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — Pass onDayDrop to views
- `cms/apps/web/src/components/dashboard/month-view.tsx` — Add drop zone handlers
- `cms/apps/web/src/components/dashboard/week-view.tsx` — Add drop zone handlers
- `cms/apps/web/src/hooks/use-calendar-events.ts` — Add refetch() to returned value
- `cms/apps/web/messages/lv.json` — Add roster + dropAction i18n keys
- `cms/apps/web/messages/en.json` — Add roster + dropAction i18n keys

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Common violations and their fixes:

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400`, `text-slate-400` | `text-foreground-muted` |
| `text-white` (on colored bg) | `text-interactive-foreground` |
| `bg-blue-600`, `bg-blue-500` | `bg-interactive` |
| `bg-green-500`, `bg-emerald-500` | `bg-status-ontime` |
| `bg-amber-500`, `bg-yellow-500` | `bg-status-delayed` |
| `bg-red-500`, `bg-red-600` | `bg-status-critical` |
| `bg-gray-100`, `bg-slate-100` | `bg-surface` |
| `border-gray-200` | `border-border` |

## React 19 Coding Rules

- **No `setState` in `useEffect`** — use `key` prop for remount
- **No component definitions inside components** — extract to module scope
- **No `Math.random()` in render** — use `useId()` or stable keys
- **No named Tailwind container sizes** — use `sm:max-w-[32rem]` not `sm:max-w-lg`
- **Hook ordering**: `useMemo`/`useCallback` MUST come AFTER their dependencies from `useState`
- **Const placeholders**: annotate as `string` to avoid TS2367

## TypeScript Security Rules

- **Never `as` cast session roles** — validate with `Array.includes()` before using
- **Clear `.next` cache** if module resolution errors persist after source fix

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: i18n Keys — Latvian
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add the following keys under the existing `"dashboard"` object, AFTER the existing `"months"` block:

```json
"roster": {
  "title": "Vadītāji",
  "empty": "Nav pieejamu vadītāju",
  "loading": "Ielādē vadītājus...",
  "dragHint": "Velciet uz kalendāru, lai plānotu",
  "shift": "Maiņa",
  "employee": "Nr."
},
"dropAction": {
  "title": "Plānot vadītāju",
  "description": "Izvēlieties darbību priekš {name} uz {date}",
  "assignShift": "Piešķirt maiņu",
  "assignShiftDesc": "Ieplānot {shift} maiņu šajā dienā",
  "markLeave": "Atzīmēt atvaļinājumu",
  "markLeaveDesc": "Reģistrēt plānotu prombūtni visa diena",
  "markSick": "Atzīmēt slimību",
  "markSickDesc": "Reģistrēt slimības dienu",
  "scheduleTraining": "Ieplānot apmācību",
  "scheduleTrainingDesc": "Pievienot apmācības sesiju (2 stundas)",
  "customEvent": "Brīvs notikums",
  "customEventDesc": "Izveidot pielāgotu notikumu ar vadītāja vārdu",
  "startTime": "Sākuma laiks",
  "endTime": "Beigu laiks",
  "eventTitle": "Notikuma nosaukums",
  "save": "Saglabāt",
  "cancel": "Atcelt",
  "saving": "Saglabā...",
  "created": "Notikums veiksmīgi izveidots",
  "createError": "Neizdevās izveidot notikumu",
  "shiftMorning": "Rīta (05:00–13:00)",
  "shiftAfternoon": "Pēcpusdienas (13:00–21:00)",
  "shiftEvening": "Vakara (17:00–01:00)",
  "shiftNight": "Nakts (22:00–06:00)"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: i18n Keys — English
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add matching keys under `"dashboard"`, AFTER the existing `"months"` block:

```json
"roster": {
  "title": "Drivers",
  "empty": "No available drivers",
  "loading": "Loading drivers...",
  "dragHint": "Drag onto calendar to schedule",
  "shift": "Shift",
  "employee": "No."
},
"dropAction": {
  "title": "Schedule Driver",
  "description": "Choose an action for {name} on {date}",
  "assignShift": "Assign Shift",
  "assignShiftDesc": "Schedule {shift} shift on this day",
  "markLeave": "Mark Leave",
  "markLeaveDesc": "Record planned absence for the full day",
  "markSick": "Mark Sick Day",
  "markSickDesc": "Record a sick day",
  "scheduleTraining": "Schedule Training",
  "scheduleTrainingDesc": "Add a training session (2 hours)",
  "customEvent": "Custom Event",
  "customEventDesc": "Create a custom event with driver name",
  "startTime": "Start time",
  "endTime": "End time",
  "eventTitle": "Event title",
  "save": "Save",
  "cancel": "Cancel",
  "saving": "Saving...",
  "created": "Event created successfully",
  "createError": "Failed to create event",
  "shiftMorning": "Morning (05:00–13:00)",
  "shiftAfternoon": "Afternoon (13:00–21:00)",
  "shiftEvening": "Evening (17:00–01:00)",
  "shiftNight": "Night (22:00–06:00)"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Create useDriversSummary Hook
**File:** `cms/apps/web/src/hooks/use-drivers-summary.ts` (create)
**Action:** CREATE

Lightweight hook to fetch active drivers for the roster panel. Pattern follows `use-dashboard-metrics.ts`.

```typescript
"use client";

import { useState, useEffect, useCallback } from "react";
import type { Driver } from "@/types/driver";
import { authFetch } from "@/lib/auth-fetch";

interface UseDriversSummaryResult {
  drivers: Driver[];
  isLoading: boolean;
}

const POLL_INTERVAL = 120_000; // 2 minutes

export function useDriversSummary(): UseDriversSummaryResult {
  const apiBase = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await authFetch(
        `${apiBase}/api/v1/drivers?active_only=true&page_size=100`,
      );
      if (res.ok) {
        const data = (await res.json()) as { items: Driver[] };
        setDrivers(data.items);
      }
    } catch {
      // Silently fall back — roster stays empty
    } finally {
      setIsLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [load]);

  return { drivers, isLoading };
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 4: Enhance useCalendarEvents — Add refetch
**File:** `cms/apps/web/src/hooks/use-calendar-events.ts` (modify)
**Action:** UPDATE

Add a `refetch` method to the returned object so the drop dialog can trigger a calendar refresh after creating an event.

Change the return statement from:
```typescript
return { events, isLoading };
```
to:
```typescript
return { events, isLoading, refetch: load };
```

Also update the `useCalendarEvents` return type — the function signature should make the refetch available.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 5: Update CalendarGrid — Accept onDayDrop Callback
**File:** `cms/apps/web/src/components/dashboard/calendar-grid.tsx` (modify)
**Action:** UPDATE

Add an optional `onDayDrop` prop to `CalendarGridProps`:
```typescript
interface CalendarGridProps {
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
}
```

Pass `onDayDrop` through to `MonthView` and `WeekView`:
```tsx
{view === "month" && (
  <MonthView currentDate={currentDate} events={events} onDayDrop={onDayDrop} />
)}
{view === "week" && (
  <WeekView currentDate={currentDate} events={events} onDayDrop={onDayDrop} />
)}
```

Do NOT pass `onDayDrop` to `ThreeMonthView` or `YearView` — they are too compact for useful drop targets.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 6: Update CalendarPanel — Accept and Forward onDayDrop
**File:** `cms/apps/web/src/components/dashboard/calendar-panel.tsx` (modify)
**Action:** UPDATE

Add props and forward to CalendarGrid:

```typescript
interface CalendarPanelProps {
  onDayDrop?: (date: Date, driverJson: string) => void;
  refetchTrigger?: number;  // increment to force refetch
}
```

Accept these props and pass `onDayDrop` to `<CalendarGrid>`. Also use `refetchTrigger` as a dependency in a separate effect that calls the hook's `refetch()` — or simpler: pass refetchTrigger as part of the date range memo dependency to force a re-run. Actually the simplest approach is: accept `onDayDrop` and also expose a way for the parent to trigger refetch. Since we added `refetch` to the hook in Task 4, pass `refetch` up to the parent via a callback ref pattern. Or simply: pass the `refetch` function from the hook upward via a `refetchRef`:

```tsx
export function CalendarPanel({ onDayDrop, refetchRef }: CalendarPanelProps) {
  const { events, refetch } = useCalendarEvents(dateRange.start, dateRange.end);

  // Expose refetch to parent via ref
  useEffect(() => {
    if (refetchRef) {
      refetchRef.current = refetch;
    }
  }, [refetch, refetchRef]);

  return <CalendarGrid events={events} onDayDrop={onDayDrop} />;
}
```

Where `CalendarPanelProps` becomes:
```typescript
interface CalendarPanelProps {
  onDayDrop?: (date: Date, driverJson: string) => void;
  refetchRef?: React.RefObject<(() => Promise<void>) | null>;
}
```

**IMPORTANT**: This pattern avoids `setState` in `useEffect` (React 19 anti-pattern). The ref assignment is not a state update — it's a ref mutation.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: Update MonthView — Add Drop Zone Handlers
**File:** `cms/apps/web/src/components/dashboard/month-view.tsx` (modify)
**Action:** UPDATE

Add `onDayDrop` to `MonthViewProps`:
```typescript
interface MonthViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
}
```

Add a `dragOverDate` state at the top of `MonthView` (for visual highlight):
```typescript
const [dragOverDate, setDragOverDate] = useState<string | null>(null);
```

On each day cell `<div>`, add drag event handlers:
```tsx
onDragOver={(e) => {
  if (!onDayDrop) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "copy";
  setDragOverDate(dateKey);
}}
onDragLeave={() => setDragOverDate(null)}
onDrop={(e) => {
  e.preventDefault();
  setDragOverDate(null);
  const driverJson = e.dataTransfer.getData("application/vtv-driver");
  if (driverJson && onDayDrop && day) {
    onDayDrop(day, driverJson);
  }
}}
```

Add a visual highlight class to the day cell when it's the drag-over target:
```typescript
dragOverDate === dateKey && "ring-2 ring-interactive bg-interactive/10"
```

Add this class to the existing `cn()` call on the day cell div.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 8: Update WeekView — Add Drop Zone Handlers
**File:** `cms/apps/web/src/components/dashboard/week-view.tsx` (modify)
**Action:** UPDATE

Same pattern as MonthView. Add `onDayDrop` to `WeekViewProps`:
```typescript
interface WeekViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
}
```

Add `dragOverDay` state:
```typescript
const [dragOverDay, setDragOverDay] = useState<number | null>(null);
```

On each day column `<div>` (the ones with `key={`col-${dayIdx}`}`), add drop handlers:
```tsx
onDragOver={(e) => {
  if (!onDayDrop) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "copy";
  setDragOverDay(dayIdx);
}}
onDragLeave={() => setDragOverDay(null)}
onDrop={(e) => {
  e.preventDefault();
  setDragOverDay(null);
  const driverJson = e.dataTransfer.getData("application/vtv-driver");
  if (driverJson && onDayDrop) {
    onDayDrop(weekDays[dayIdx], driverJson);
  }
}}
```

Add visual highlight when `dragOverDay === dayIdx`:
```typescript
dragOverDay === dayIdx && "bg-interactive/10"
```

Also add a highlight to the day header cell for the same column when dragging over.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 9: Create DriverRoster Component
**File:** `cms/apps/web/src/components/dashboard/driver-roster.tsx` (create)
**Action:** CREATE

Compact scrollable panel displaying active drivers as draggable cards. Key requirements:

- Props: `drivers: Driver[]`, `isLoading: boolean`, `canDrag: boolean` (role-gated)
- Import `useTranslations` from `next-intl`; namespace is `"dashboard"`
- Each driver card:
  - `draggable={canDrag}` attribute
  - `onDragStart` handler: `e.dataTransfer.setData("application/vtv-driver", JSON.stringify(driver))` + `e.dataTransfer.effectAllowed = "copy"`
  - Shows: `first_name + " " + last_name`, employee_number, status badge (color-coded), default_shift label
  - `cursor-grab` when `canDrag` is true
- Status badge colors follow driver-table.tsx pattern:
  - available → `bg-status-ontime/15 text-status-ontime`
  - on_duty → `bg-foreground/10 text-foreground`
  - on_leave → `bg-status-delayed/15 text-status-delayed`
  - sick → `bg-status-critical/15 text-status-critical`
- Loading state: 4 skeleton cards using `<Skeleton className="h-14 rounded-lg" />`
- Empty state: centered message with `text-foreground-muted`
- Section header: "Vadītāji" / "Drivers" with driver count badge
- Hint text below header: "Drag onto calendar to schedule" (when canDrag)
- Use `ScrollArea` from shadcn for scrollable list
- Semantic spacing: `p-(--spacing-card)`, `gap-(--spacing-inline)`, `gap-(--spacing-tight)`
- DO NOT define any sub-components inside the `DriverRoster` function — extract helper components (like a `DriverRosterCard`) to module scope

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 10: Create DriverDropDialog Component
**File:** `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` (create)
**Action:** CREATE

Dialog shown when a driver is dropped onto a calendar day. Key requirements:

- Props:
  ```typescript
  interface DriverDropDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    driver: Driver | null;
    targetDate: Date | null;
    onEventCreated: () => void; // callback to refresh calendar
  }
  ```
- Uses `Dialog` + `DialogContent` (width: default `sm:max-w-[32rem]`)
- Dialog header shows driver name and formatted target date
- Five action buttons displayed as a vertical list of selectable cards:
  1. **Assign Shift** — icon: `Clock`, creates event with category `"driver-shift"`, priority `"medium"`. Uses driver's `default_shift` to determine times:
     - morning: 05:00–13:00
     - afternoon: 13:00–21:00
     - evening: 17:00–01:00 (next day)
     - night: 22:00–06:00 (next day)
     - Title: `"{DriverName} — {ShiftLabel}"`
  2. **Mark Leave** — icon: `CalendarOff`, creates event with category `"driver-shift"`, priority `"low"`, times 00:00–23:59, title: `"{DriverName} — Atvaļinājums/Leave"`
  3. **Mark Sick Day** — icon: `Thermometer`, creates event with category `"driver-shift"`, priority `"high"`, times 00:00–23:59, title: `"{DriverName} — Slimība/Sick"`
  4. **Schedule Training** — icon: `GraduationCap`, creates event with category `"maintenance"`, priority `"medium"`, default 09:00–11:00, title: `"{DriverName} — Apmācība/Training"`
  5. **Custom Event** — icon: `Pencil`, opens a mini-form with title input, start time, end time, then creates with category `"driver-shift"`, priority `"medium"`

- When user clicks an action (except Custom Event), immediately create the event via `createEvent` from `@/lib/events-sdk.ts` and close the dialog
- For Custom Event, show inline form fields (title, start time, end time) with a Save button
- Show toast on success/failure via `sonner`
- `onEventCreated` is called after successful creation to trigger calendar refresh
- Use `useTranslations("dashboard")` for all text
- Shift time mapping helper at module scope (not inside component):
  ```typescript
  const SHIFT_TIMES: Record<string, { start: string; end: string; nextDay: boolean }> = {
    morning: { start: "05:00", end: "13:00", nextDay: false },
    afternoon: { start: "13:00", end: "21:00", nextDay: false },
    evening: { start: "17:00", end: "01:00", nextDay: true },
    night: { start: "22:00", end: "06:00", nextDay: true },
  };
  ```
- Build ISO datetime strings from targetDate + time: `new Date(year, month, day, hours, minutes).toISOString()`
- DO NOT define sub-components inside the function — extract `ActionCard` to module scope:
  ```typescript
  function ActionCard({ icon, title, description, onClick }: {
    icon: React.ReactNode;
    title: string;
    description: string;
    onClick: () => void;
  }) { ... }
  ```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 11: Create DashboardContent Client Wrapper
**File:** `cms/apps/web/src/components/dashboard/dashboard-content.tsx` (create)
**Action:** CREATE

Client component that orchestrates the entire dashboard: metrics, driver roster, calendar, and drag-and-drop state.

```
"use client"
```

- Imports: `useSession` from `next-auth/react`, `useRef`, `useState`, `useCallback`
- Uses `useDriversSummary` for driver data
- State management:
  - `dropDriver: Driver | null` — the driver being dropped
  - `dropDate: Date | null` — the target calendar date
  - `dialogOpen: boolean` — controls DriverDropDialog visibility
- `calendarRefetchRef` — a `useRef<(() => Promise<void>) | null>(null)` to hold the CalendarPanel's refetch function
- `handleDayDrop` callback:
  ```typescript
  const handleDayDrop = useCallback((date: Date, driverJson: string) => {
    try {
      const driver = JSON.parse(driverJson) as Driver;
      setDropDriver(driver);
      setDropDate(date);
      setDialogOpen(true);
    } catch { /* ignore malformed data */ }
  }, []);
  ```
- `handleEventCreated` callback:
  ```typescript
  const handleEventCreated = useCallback(() => {
    setDialogOpen(false);
    void calendarRefetchRef.current?.();
  }, []);
  ```
- Role check: `const canSchedule = ["admin", "editor"].includes(session?.user?.role ?? "");`
  - Use runtime validation: `const validRoles = ["admin", "editor"]; const canSchedule = validRoles.includes(session?.user?.role as string ?? "");`
- Layout structure:
  ```
  <div className="space-y-(--spacing-section)">
    {/* Page header (title + manage routes link) — from existing page.tsx */}
    {/* Metrics panel */}
    <DashboardMetrics />
    {/* Main area: driver roster sidebar + calendar */}
    <div className="flex min-h-[calc(100vh-14rem)] gap-(--spacing-grid)">
      {/* Left: driver roster (fixed width ~16rem on desktop, hidden on mobile) */}
      <div className="hidden w-64 shrink-0 lg:block">
        <DriverRoster drivers={...} isLoading={...} canDrag={canSchedule} />
      </div>
      {/* Right: calendar (flex-1) */}
      <div className="min-w-0 flex-1">
        <CalendarPanel onDayDrop={canSchedule ? handleDayDrop : undefined} refetchRef={calendarRefetchRef} />
      </div>
    </div>
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
- Remove `ResizablePanelGroup` from the dashboard layout — replace with flexbox. The resizable panels added unnecessary complexity for what is fundamentally a sidebar + main content layout. The metrics panel no longer needs to be resizable.
- Props: `locale: string` (for the "manage routes" link href)

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 12: Update Dashboard Page — Use DashboardContent
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` (modify)
**Action:** UPDATE

Replace the current inline JSX with the new `DashboardContent` wrapper. The page remains a **server component** — it renders one client component:

```tsx
import { getTranslations } from "next-intl/server";
import { DashboardContent } from "@/components/dashboard/dashboard-content";

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  // Pre-translate the page title server-side
  const t = await getTranslations("dashboard");

  return <DashboardContent locale={locale} title={t("title")} />;
}
```

The `DashboardContent` component now owns the page header, metrics, roster, and calendar. Pass `title` as a pre-translated string prop from the server component so the client component doesn't need `getTranslations`.

**However**, `DashboardContent` also needs translations for inline text. It should use `useTranslations("dashboard")` client-side. The `title` prop is actually unnecessary since `useTranslations` works in client components too (messages are provided by `NextIntlClientProvider` in layout.tsx). So simplify:

```tsx
import { DashboardContent } from "@/components/dashboard/dashboard-content";

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return <DashboardContent locale={locale} />;
}
```

The `DashboardContent` client component handles all translations internally via `useTranslations`.

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

- [ ] Dashboard renders at `/lv` with metrics, driver roster, and calendar
- [ ] Driver roster shows active drivers fetched from API (or skeleton during load)
- [ ] Driver cards are draggable for admin/editor roles
- [ ] Dropping a driver on a month-view day cell opens the action dialog
- [ ] Dropping a driver on a week-view day column opens the action dialog
- [ ] "Assign Shift" creates an event with correct shift times from driver's default_shift
- [ ] "Mark Leave" creates an all-day driver-shift event
- [ ] "Mark Sick Day" creates an all-day driver-shift event with high priority
- [ ] "Schedule Training" creates a 2-hour maintenance event
- [ ] "Custom Event" shows inline form and creates event with user-provided data
- [ ] Calendar refreshes after event creation (new event appears)
- [ ] Toast notifications appear for success/error
- [ ] Viewer/dispatcher roles see the roster but cannot drag
- [ ] i18n keys present in both lv.json and en.json
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] Drop zone visual feedback (ring highlight) on dragOver
- [ ] No regressions in existing dashboard functionality (metrics, calendar navigation)

## Acceptance Criteria

This feature is complete when:
- [ ] Dashboard at `/lv` shows metrics + driver roster + calendar with DnD
- [ ] All 5 drop actions work and create events via API
- [ ] RBAC enforced — only admin/editor can drag-and-drop
- [ ] Both languages have complete translations
- [ ] Design system rules followed (MASTER.md, semantic tokens only)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`

## Security Checklist
- [ ] Session role validated at runtime with `Array.includes()` (no `as` cast)
- [ ] Event creation uses `createEvent` from events-sdk (inherits JWT auth)
- [ ] No hardcoded credentials
- [ ] No `dangerouslySetInnerHTML`
- [ ] Driver data from API treated as external input (no unsafe casts)
