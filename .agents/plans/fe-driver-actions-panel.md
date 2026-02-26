# Plan: Driver Actions Panel (Calendar Event Enhancement)

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: N/A (enhances existing Dashboard page at `/[locale]/`)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer (view-only for viewer)

## Feature Description

When a user clicks on a driver's event in the calendar day/week view, the current EventGoalPanel opens showing goal progress. This enhancement adds a **new interaction**: clicking the **driver name** within the event card opens a **Driver Actions Panel** — a dialog showing all actions available for that driver.

The Driver Actions Panel shows:
1. **Driver info header** — name, employee number, status badge, default shift
2. **All events for this driver today** — fetched via `GET /api/v1/events/?driver_id={id}&start_date=...&end_date=...`, each event shown as a compact card
3. **Quick actions** — the same 5 action cards from the existing DriverDropDialog (Assign Shift, Mark Leave, Mark Sick, Schedule Training, Custom Event), allowing dispatchers to add new events for this driver directly

This requires:
- Regenerating the SDK to pick up `driver_id` on events and the `by-driver` endpoint
- Adding `driver_id` to the frontend event types (`OperationalEvent`, `EventCreate`, `CalendarEvent`)
- Passing `driver_id` when creating events from DriverDropDialog
- Making the driver name clickable in CalendarEventCard
- Building the new DriverActionsPanel dialog
- A new `useDriverEvents` SWR hook to fetch events for a specific driver on a specific day

## Design System

### Master Rules (from MASTER.md)
- All spacing via design tokens: `p-(--spacing-card)`, `gap-(--spacing-grid)`, etc.
- Typography: Lexend for headings, Source Sans 3 for body
- Cards: `rounded-lg`, `bg-surface`, `shadow-(--shadow-sm)` with hover transitions
- Buttons: `cursor-pointer` on all clickable elements, 200ms transitions
- Modals: `Dialog` (not Sheet), max-width `sm:max-w-[36rem]` for wide content
- Focus states visible for keyboard navigation

### Page Override
- Dashboard page override at `cms/design-system/vtv/pages/dashboard.md` — check if it exists, follow its rules if so

### Tokens Used
- `bg-surface`, `bg-surface-raised`, `bg-background` — surfaces
- `text-foreground`, `text-foreground-muted`, `text-foreground-subtle` — text hierarchy
- `border-border`, `border-border-subtle` — borders
- `bg-interactive/10`, `text-interactive` — action card icons
- `bg-status-ontime`, `bg-status-delayed`, `bg-status-critical` — status indicators
- `bg-category-driver-shift/10`, `border-l-category-driver-shift` — event category styling
- `--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight` — spacing

## Components Needed

### Existing (shadcn/ui)
- `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription` — modal wrapper
- `Button` — action buttons, close
- `Separator` — visual dividers
- `Badge` — driver status, shift badge (already installed)
- `ScrollArea` — scrollable event list if many events

### New shadcn/ui to Install
- `ScrollArea` — `npx shadcn@latest add scroll-area` (check if already installed first)

### Custom Components to Create
- `DriverActionsPanel` at `cms/apps/web/src/components/dashboard/driver-actions-panel.tsx` — the main dialog
- `DriverEventCard` (inline in driver-actions-panel.tsx) — compact event card for the "today's events" list

### Custom Hooks to Create
- `useDriverEvents` at `cms/apps/web/src/hooks/use-driver-events.ts` — SWR hook to fetch events for a specific driver on a specific day

## i18n Keys

### English (`en.json`)
```json
{
  "dashboard": {
    "driverActions": {
      "title": "Driver Actions",
      "subtitle": "{name} — {date}",
      "employeeNumber": "No. {number}",
      "shift": "Default shift: {shift}",
      "todayEvents": "Events Today",
      "noEvents": "No events scheduled for this day",
      "addAction": "Quick Actions",
      "editEvent": "Edit",
      "viewGoals": "Goals",
      "eventTime": "{start} – {end}",
      "allDay": "All day"
    }
  }
}
```

### Latvian (`lv.json`)
```json
{
  "dashboard": {
    "driverActions": {
      "title": "Vadītāja darbības",
      "subtitle": "{name} — {date}",
      "employeeNumber": "Nr. {number}",
      "shift": "Noklusējuma maiņa: {shift}",
      "todayEvents": "Šodienas notikumi",
      "noEvents": "Šajā dienā nav ieplānotu notikumu",
      "addAction": "Ātrās darbības",
      "editEvent": "Rediģēt",
      "viewGoals": "Mērķi",
      "eventTime": "{start} – {end}",
      "allDay": "Visu dienu"
    }
  }
}
```

## Data Fetching

- **API endpoints**:
  - `GET /api/v1/events/?driver_id={id}&start_date=...&end_date=...` — fetch all events for a driver on a given day
  - `POST /api/v1/events/` — create event (existing, needs `driver_id` added to body)
  - `PATCH /api/v1/events/{id}` — update event (existing)
  - `GET /api/v1/drivers/{id}` — fetch full driver profile (for header info)
- **Server vs Client**: All client-side (dashboard is interactive, uses SWR)
- **Loading states**: Skeleton pulse for event list while loading
- **CRITICAL — Server/client boundary for API clients:**
  - `authFetch` (from `src/lib/auth-fetch.ts`) uses dynamic imports for dual-context support
  - The new `useDriverEvents` hook will use the events-sdk's `fetchEvents` function with `driver_id` filter param
  - The SDK needs regeneration first to include `driver_id` on event types

## RBAC Integration

- No new routes — this enhances the existing Dashboard page
- Action cards (Assign Shift, Mark Leave, etc.) only visible to `admin`, `dispatcher`, `editor` roles
- Viewers can see the driver info + event list but not the quick actions section

## Sidebar Navigation

- No changes — this is an enhancement to the existing Dashboard page

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` — Dialog with event data pattern (closest pattern to follow)
- `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` — Action cards + event creation pattern
- `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — State management, event handlers, dialog orchestration
- `cms/apps/web/src/hooks/use-calendar-events.ts` — SWR hook pattern for events

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add Latvian translations
- `cms/apps/web/messages/en.json` — Add English translations
- `cms/apps/web/src/types/event.ts` — Add `driver_id` field to types
- `cms/apps/web/src/types/dashboard.ts` — Add `driver_id` to `CalendarEvent`
- `cms/apps/web/src/hooks/use-calendar-events.ts` — Map `driver_id` in `toCalendarEvent`
- `cms/apps/web/src/lib/events-sdk.ts` — Add `driver_id` to `fetchEvents` params and `createEvent`/`updateEvent` body
- `cms/apps/web/src/components/dashboard/calendar-event.tsx` — Make driver name clickable
- `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — Add driver actions panel state + handler
- `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` — Pass `driver_id` when creating events

### Files to Create
- `cms/apps/web/src/components/dashboard/driver-actions-panel.tsx` — New driver actions dialog
- `cms/apps/web/src/hooks/use-driver-events.ts` — SWR hook for driver's events

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Common violations and their fixes:

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400`, `text-slate-400` | `text-foreground-subtle` |
| `text-white` (on colored bg) | `text-interactive-foreground` / `text-primary-foreground` |
| `text-blue-*`, `text-red-*`, `text-green-*` | `text-primary`, `text-error`, `text-success` |
| `text-amber-*`, `text-emerald-*`, `text-purple-*` | `text-category-*`, `text-transport-*` |
| `bg-blue-600`, `bg-blue-500` | `bg-primary` or `bg-interactive` |
| `bg-red-500`, `bg-red-600` | `bg-destructive` |
| `bg-red-50` | `bg-error-bg` |
| `bg-green-500`, `bg-emerald-500` | `bg-success` or `bg-status-ontime` |
| `bg-amber-400`, `bg-amber-500` | `bg-category-route-change` or `bg-status-delayed` |
| `bg-purple-600` | `bg-transport-tram` |
| `bg-gray-100`, `bg-slate-100` | `bg-surface` / `bg-muted` |
| `border-gray-200` | `border-border` |
| `border-red-200` | `border-error-border` |
| `border-blue-*`, `border-amber-*`, `border-emerald-*`, `border-purple-*` | `border-transport-*`, `border-category-*` |

**Full semantic token reference** (check `cms/packages/ui/src/tokens.css`):
- **Surface**: `bg-surface`, `bg-surface-raised`, `bg-background`
- **Interactive**: `bg-interactive`, `text-interactive`, `text-interactive-foreground`
- **Error**: `bg-error-bg`, `border-error-border`, `text-error`
- **Status**: `text-status-ontime`, `text-status-delayed`, `text-status-critical`
- **Transport**: `bg-transport-bus`, `bg-transport-trolleybus`, `bg-transport-tram` (+ `text-` and `border-` variants)
- **Calendar**: `bg-category-maintenance`, `bg-category-route-change`, `bg-category-driver-shift`, `bg-category-service-alert`

Exception: Inline HTML strings (e.g., Leaflet `L.divIcon`) may use hex colors since Tailwind classes don't work there.

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first
- **No named Tailwind container sizes** — `max-w-sm`, `max-w-lg` etc. collapse to ~50px. Use explicit rem values: `sm:max-w-[28rem]`, `sm:max-w-[32rem]`, `sm:max-w-[36rem]`

## TypeScript Security Rules

- **Never use `as` casts on JWT token claims without runtime validation**
- **Clear `.next` cache when module resolution errors persist after fixing imports** — `rm -rf cms/apps/web/.next`

---

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Regenerate SDK
**Action:** REGENERATE

The SDK is stale — it doesn't include `driver_id` on `EventResponse` or the `by-driver` endpoint.

1. Ensure the backend is running on port 8123 (`make dev-be` or check it's already running)
2. Run: `cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/sdk refresh`
3. Verify the generated `cms/packages/sdk/src/client/types.gen.ts` now has `driver_id` on `EventResponse`:
   - Search for `EventResponse` type — it should now include `driver_id?: number | null`
4. Verify `cms/packages/sdk/src/client/sdk.gen.ts` has the by-driver endpoint function

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes (SDK types imported across the app)

---

### Task 2: Add `driver_id` to Frontend Event Types
**File:** `cms/apps/web/src/types/event.ts` (modify)
**Action:** UPDATE

Add `driver_id` field to all relevant types:

1. `OperationalEvent` — add `driver_id: number | null;` (after `goals` field)
2. `EventCreate` — add `driver_id?: number | null;` (optional, after `goals` field)
3. `EventUpdate` — add `driver_id?: number | null;` (optional, after `goals` field)

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Add `driver_id` to CalendarEvent Type
**File:** `cms/apps/web/src/types/dashboard.ts` (modify)
**Action:** UPDATE

Add to `CalendarEvent` interface:
```typescript
driver_id?: number | null;
```

Place it after the `goals` field.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 4: Update `toCalendarEvent` Mapping
**File:** `cms/apps/web/src/hooks/use-calendar-events.ts` (modify)
**Action:** UPDATE

In the `toCalendarEvent` function, add the `driver_id` mapping:

```typescript
function toCalendarEvent(event: OperationalEvent): CalendarEvent {
  return {
    id: String(event.id),
    title: event.title,
    start: new Date(event.start_datetime),
    end: new Date(event.end_datetime),
    priority: event.priority,
    category: event.category,
    description: event.description ?? undefined,
    goals: event.goals ?? undefined,
    driver_id: event.driver_id,       // <-- ADD THIS LINE
  };
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 5: Update events-sdk.ts — Add `driver_id` Support
**File:** `cms/apps/web/src/lib/events-sdk.ts` (modify)
**Action:** UPDATE

**5a.** In `fetchEvents`, add `driver_id` to the params type and pass it to the SDK:

```typescript
export async function fetchEvents(params: {
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  driver_id?: number;          // <-- ADD
}): Promise<PaginatedEvents> {
  const { data, error, response } = await listEventsApiV1EventsGet({
    query: {
      page: params.page,
      page_size: params.page_size,
      start_date: params.start_date ?? null,
      end_date: params.end_date ?? null,
      driver_id: params.driver_id ?? null,   // <-- ADD
    },
  });
  // ... rest unchanged
```

**5b.** In `updateEvent`, add `driver_id` to the conditional body builder:

After the line `if (eventData.goals !== undefined) body.goals = eventData.goals;` add:
```typescript
if (eventData.driver_id !== undefined) body.driver_id = eventData.driver_id;
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 6: Pass `driver_id` When Creating Events
**File:** `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` (modify)
**Action:** UPDATE

In every event creation call, add `driver_id: driver.id` to the `EventCreate` object.

**6a.** `handleMarkLeave` (around line 144): add `driver_id: driver.id` to the object passed to `handleCreate`
**6b.** `handleMarkSick` (around line 156): add `driver_id: driver.id`
**6c.** `handleCustomSubmit` (around line 174): add `driver_id: driver.id`
**6d.** `handleGoalsSave` — shift branch (around line 193): add `driver_id: driver.id`
**6e.** `handleGoalsSave` — training branch (around line 208): add `driver_id: driver.id`

Example for handleMarkLeave:
```typescript
void handleCreate({
  title: t("dropAction.eventTitleLeave", { name: driverName }),
  description: t("dropAction.eventDesc", { number: driver.employee_number }),
  start_datetime: buildDatetime(targetDate, "00:00", false),
  end_datetime: buildDatetime(targetDate, "23:59", false),
  priority: "low",
  category: "driver-shift",
  driver_id: driver.id,            // <-- ADD to all 5 creation calls
});
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: Add i18n Keys — Latvian
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add inside `"dashboard"` object, after the `"goals"` block:

```json
"driverActions": {
  "title": "Vadītāja darbības",
  "subtitle": "{name} — {date}",
  "employeeNumber": "Nr. {number}",
  "shift": "Noklusējuma maiņa: {shift}",
  "todayEvents": "Šodienas notikumi",
  "noEvents": "Šajā dienā nav ieplānotu notikumu",
  "addAction": "Ātrās darbības",
  "editEvent": "Rediģēt",
  "viewGoals": "Mērķi",
  "eventTime": "{start} – {end}",
  "allDay": "Visu dienu"
}
```

**Per-task validation:**
- Valid JSON (no trailing commas, proper nesting)

---

### Task 8: Add i18n Keys — English
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add inside `"dashboard"` object, after the `"goals"` block:

```json
"driverActions": {
  "title": "Driver Actions",
  "subtitle": "{name} — {date}",
  "employeeNumber": "No. {number}",
  "shift": "Default shift: {shift}",
  "todayEvents": "Events Today",
  "noEvents": "No events scheduled for this day",
  "addAction": "Quick Actions",
  "editEvent": "Edit",
  "viewGoals": "Goals",
  "eventTime": "{start} – {end}",
  "allDay": "All day"
}
```

**Per-task validation:**
- Valid JSON (no trailing commas, proper nesting)
- `pnpm --filter @vtv/web type-check` passes

---

### Task 9: Create `useDriverEvents` Hook
**File:** `cms/apps/web/src/hooks/use-driver-events.ts` (create)
**Action:** CREATE

Create a SWR hook that fetches all events for a specific driver on a specific date.

```typescript
"use client";

import { useMemo, useCallback } from "react";
import useSWR from "swr";
import { useSession } from "next-auth/react";
import type { CalendarEvent } from "@/types/dashboard";
import type { OperationalEvent } from "@/types/event";
import { fetchEvents } from "@/lib/events-sdk";

function toCalendarEvent(event: OperationalEvent): CalendarEvent {
  return {
    id: String(event.id),
    title: event.title,
    start: new Date(event.start_datetime),
    end: new Date(event.end_datetime),
    priority: event.priority,
    category: event.category,
    description: event.description ?? undefined,
    goals: event.goals ?? undefined,
    driver_id: event.driver_id,
  };
}

interface DriverEventsResult {
  items: OperationalEvent[];
  total: number;
}

/**
 * Fetch all events for a specific driver on a given date.
 * Returns empty array when driverId is null (disabled).
 */
export function useDriverEvents(driverId: number | null, date: Date | null) {
  const { status } = useSession();

  // Build start/end of day for the target date
  const startOfDay = useMemo(() => {
    if (!date) return null;
    const d = new Date(date);
    d.setHours(0, 0, 0, 0);
    return d;
  }, [date]);

  const endOfDay = useMemo(() => {
    if (!date) return null;
    const d = new Date(date);
    d.setHours(23, 59, 59, 999);
    return d;
  }, [date]);

  const swrKey =
    status === "authenticated" && driverId && startOfDay && endOfDay
      ? `driver-events:${String(driverId)}:${startOfDay.toISOString()}`
      : null;

  const { data, isLoading, mutate } = useSWR<DriverEventsResult>(
    swrKey,
    async () =>
      fetchEvents({
        driver_id: driverId!,
        page_size: 100,
        start_date: startOfDay!.toISOString(),
        end_date: endOfDay!.toISOString(),
      }),
    {
      fallbackData: { items: [], total: 0 },
    },
  );

  const events = useMemo(
    () => (data?.items ?? []).map(toCalendarEvent),
    [data],
  );

  const refetch = useCallback(async () => {
    await mutate();
  }, [mutate]);

  return { events, isLoading, refetch };
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Make Driver Name Clickable in CalendarEventCard
**File:** `cms/apps/web/src/components/dashboard/calendar-event.tsx` (modify)
**Action:** UPDATE

Add a new prop `onDriverClick` and make the title line split into a clickable driver name portion.

**Current title (line 47):**
```tsx
<p className="truncate font-medium text-foreground">{event.title}</p>
```

**Strategy:** Event titles follow the pattern `"{name} - {action}"` (e.g., "Uldis Grīnbergs - Morning Shift"). Split on ` - ` to extract the driver name. If the title doesn't contain ` - `, the whole title is non-clickable (it's not a driver event).

**Updated interface:**
```typescript
interface CalendarEventCardProps {
  event: CalendarEventType;
  onClick?: () => void;
  onDriverClick?: () => void;
}
```

**Updated title rendering (replace the `<p>` on line 47):**
```tsx
{(() => {
  const dashIndex = event.title.indexOf(" - ");
  if (dashIndex === -1 || !onDriverClick) {
    return <p className="truncate font-medium text-foreground">{event.title}</p>;
  }
  const driverName = event.title.slice(0, dashIndex);
  const rest = event.title.slice(dashIndex);
  return (
    <p className="truncate font-medium text-foreground">
      <span
        role="button"
        tabIndex={0}
        className="cursor-pointer underline decoration-foreground-subtle/40 underline-offset-2 transition-colors duration-200 hover:text-interactive hover:decoration-interactive"
        onClick={(e) => {
          e.stopPropagation();
          onDriverClick();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.stopPropagation();
            onDriverClick();
          }
        }}
      >
        {driverName}
      </span>
      {rest}
    </p>
  );
})()}
```

**IMPORTANT:** The `e.stopPropagation()` is critical — it prevents the parent card's `onClick` (which opens the goal panel) from also firing when clicking the driver name.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 11: Create DriverActionsPanel Component
**File:** `cms/apps/web/src/components/dashboard/driver-actions-panel.tsx` (create)
**Action:** CREATE

Create the main dialog component. This dialog shows:
1. Driver info header (name, employee number, status, shift)
2. Today's events list (via `useDriverEvents` hook)
3. Quick actions (reuses the same action cards pattern from DriverDropDialog)

The component receives:
- `driverId: number | null` — the driver to show actions for
- `driverName: string` — display name
- `date: Date | null` — the day the event was clicked on
- `open: boolean` / `onOpenChange` — dialog state
- `onEventClick: (event: CalendarEvent) => void` — when user clicks an event in the list, open the goal panel
- `onEventCreated: () => void` — refetch calendar after creating an event

**Structure:**

```typescript
"use client";

import { useState, useCallback } from "react";
import { useTranslations, useLocale } from "next-intl";
import { useSession } from "next-auth/react";
import { toast } from "sonner";
import {
  Clock,
  CalendarOff,
  Thermometer,
  GraduationCap,
  Pencil,
  Target,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";
import type { EventCreate, EventGoals } from "@/types/event";
import { createEvent } from "@/lib/events-sdk";
import { useDriverEvents } from "@/hooks/use-driver-events";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { GoalProgressBadge } from "./goal-progress-badge";

// -- Types --
interface DriverActionsPanelProps {
  driverId: number | null;
  driverName: string;
  date: Date | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEventClick: (event: CalendarEvent) => void;
  onEventCreated: () => void;
}

// RBAC: roles that can create events
const SCHEDULE_ROLES = ["admin", "editor", "dispatcher"];

// Shift times (same as driver-drop-dialog.tsx)
const SHIFT_TIMES: Record<string, { start: string; end: string; nextDay: boolean }> = {
  morning: { start: "05:00", end: "13:00", nextDay: false },
  afternoon: { start: "13:00", end: "21:00", nextDay: false },
  evening: { start: "17:00", end: "01:00", nextDay: true },
  night: { start: "22:00", end: "06:00", nextDay: true },
};

function buildDatetime(date: Date, time: string, nextDay: boolean): string {
  const [hours, minutes] = time.split(":").map(Number);
  const d = new Date(date);
  if (nextDay) d.setDate(d.getDate() + 1);
  d.setHours(hours, minutes, 0, 0);
  return d.toISOString();
}

function formatTime(date: Date, locale: string): string {
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", hour12: false });
}

// Category color styles (same as calendar-event.tsx)
const categoryStyles: Record<string, string> = {
  maintenance: "border-l-2 border-l-category-maintenance bg-category-maintenance/10",
  "route-change": "border-l-2 border-l-category-route-change bg-category-route-change/10",
  "driver-shift": "border-l-2 border-l-category-driver-shift bg-category-driver-shift/10",
  "service-alert": "border-l-2 border-l-category-service-alert bg-category-service-alert/10",
};

// -- Sub-components (module scope, not inside main component) --

function DriverEventCard({
  event,
  locale,
  onClickEvent,
  onClickGoals,
  tActions,
}: {
  event: CalendarEvent;
  locale: string;
  onClickEvent: () => void;
  onClickGoals: () => void;
  tActions: (key: string, values?: Record<string, string>) => string;
}) {
  const isAllDay =
    event.start.getHours() === 0 &&
    event.start.getMinutes() === 0 &&
    event.end.getHours() === 23 &&
    event.end.getMinutes() === 59;

  return (
    <div
      className={cn(
        "flex items-center justify-between rounded-md p-(--spacing-cell)",
        categoryStyles[event.category] ?? "bg-surface"
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">
          {event.title}
        </p>
        <p className="text-xs text-foreground-muted">
          {isAllDay
            ? tActions("allDay")
            : tActions("eventTime", {
                start: formatTime(event.start, locale),
                end: formatTime(event.end, locale),
              })}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-(--spacing-tight)">
        {event.goals && event.goals.items.length > 0 && (
          <button
            type="button"
            onClick={onClickGoals}
            className="cursor-pointer rounded-md p-1 text-foreground-muted transition-colors duration-200 hover:bg-surface hover:text-interactive"
            title={tActions("viewGoals")}
          >
            <Target className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

function ActionCard({
  icon,
  title,
  description,
  onClick,
  disabled,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex w-full items-center gap-(--spacing-inline) rounded-lg border border-border-subtle p-(--spacing-card) text-left transition-colors duration-200 hover:border-border hover:bg-surface cursor-pointer",
        disabled && "pointer-events-none opacity-50"
      )}
    >
      <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-interactive/10 text-interactive">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-foreground-muted">{description}</p>
      </div>
    </button>
  );
}

// -- Main component --

export function DriverActionsPanel({
  driverId,
  driverName,
  date,
  open,
  onOpenChange,
  onEventClick,
  onEventCreated,
}: DriverActionsPanelProps) {
  const t = useTranslations("dashboard");
  const tDrop = useTranslations("dashboard.dropAction");
  const tActions = useTranslations("dashboard.driverActions");
  const locale = useLocale();
  const { data: session } = useSession();

  const [isSaving, setIsSaving] = useState(false);

  const userRole: string = (session?.user?.role as string) ?? "";
  const canSchedule = SCHEDULE_ROLES.includes(userRole);

  const { events: driverEvents, isLoading, refetch } = useDriverEvents(
    open ? driverId : null,
    date,
  );

  const formattedDate = date
    ? date.toLocaleDateString(locale, {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "";

  const handleCreate = useCallback(
    async (eventData: EventCreate) => {
      setIsSaving(true);
      try {
        await createEvent(eventData);
        toast.success(tDrop("created"));
        onEventCreated();
        await refetch();
      } catch {
        toast.error(tDrop("createError"));
      } finally {
        setIsSaving(false);
      }
    },
    [tDrop, onEventCreated, refetch],
  );

  function handleAssignShift() {
    if (!driverId || !date) return;
    const times = SHIFT_TIMES.morning; // Default to morning
    void handleCreate({
      title: `${driverName} - ${tDrop("shiftMorning")}`,
      start_datetime: buildDatetime(date, times.start, false),
      end_datetime: buildDatetime(date, times.end, times.nextDay),
      priority: "medium",
      category: "driver-shift",
      driver_id: driverId,
    });
  }

  function handleMarkLeave() {
    if (!driverId || !date) return;
    void handleCreate({
      title: tDrop("eventTitleLeave", { name: driverName }),
      start_datetime: buildDatetime(date, "00:00", false),
      end_datetime: buildDatetime(date, "23:59", false),
      priority: "low",
      category: "driver-shift",
      driver_id: driverId,
    });
  }

  function handleMarkSick() {
    if (!driverId || !date) return;
    void handleCreate({
      title: tDrop("eventTitleSick", { name: driverName }),
      start_datetime: buildDatetime(date, "00:00", false),
      end_datetime: buildDatetime(date, "23:59", false),
      priority: "high",
      category: "driver-shift",
      driver_id: driverId,
    });
  }

  function handleScheduleTraining() {
    if (!driverId || !date) return;
    void handleCreate({
      title: tDrop("eventTitleTraining", { name: driverName }),
      start_datetime: buildDatetime(date, "09:00", false),
      end_datetime: buildDatetime(date, "11:00", false),
      priority: "medium",
      category: "maintenance",
      driver_id: driverId,
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[36rem]">
        <DialogHeader>
          <DialogTitle>{tActions("title")}</DialogTitle>
          <DialogDescription>
            {tActions("subtitle", { name: driverName, date: formattedDate })}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-(--spacing-grid)">
          {/* Driver events for this day */}
          <div>
            <p className="mb-(--spacing-tight) text-sm font-medium text-foreground">
              {tActions("todayEvents")}
            </p>
            {isLoading ? (
              <div className="flex flex-col gap-(--spacing-tight)">
                {[1, 2].map((i) => (
                  <div
                    key={`skeleton-${String(i)}`}
                    className="h-12 animate-pulse rounded-md bg-surface"
                  />
                ))}
              </div>
            ) : driverEvents.length === 0 ? (
              <p className="py-(--spacing-card) text-center text-sm text-foreground-muted">
                {tActions("noEvents")}
              </p>
            ) : (
              <div className="flex flex-col gap-(--spacing-tight)">
                {driverEvents.map((event) => (
                  <DriverEventCard
                    key={event.id}
                    event={event}
                    locale={locale}
                    onClickEvent={() => onEventClick(event)}
                    onClickGoals={() => {
                      onOpenChange(false);
                      onEventClick(event);
                    }}
                    tActions={tActions}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Quick actions — only for scheduling roles */}
          {canSchedule && (
            <>
              <Separator />
              <div>
                <p className="mb-(--spacing-tight) text-sm font-medium text-foreground">
                  {tActions("addAction")}
                </p>
                <div className="flex flex-col gap-(--spacing-tight)">
                  <ActionCard
                    icon={<Clock className="size-4" />}
                    title={tDrop("assignShift")}
                    description={tDrop("assignShiftDesc", { shift: tDrop("shiftMorning") })}
                    onClick={handleAssignShift}
                    disabled={isSaving}
                  />
                  <ActionCard
                    icon={<CalendarOff className="size-4" />}
                    title={tDrop("markLeave")}
                    description={tDrop("markLeaveDesc")}
                    onClick={handleMarkLeave}
                    disabled={isSaving}
                  />
                  <ActionCard
                    icon={<Thermometer className="size-4" />}
                    title={tDrop("markSick")}
                    description={tDrop("markSickDesc")}
                    onClick={handleMarkSick}
                    disabled={isSaving}
                  />
                  <ActionCard
                    icon={<GraduationCap className="size-4" />}
                    title={tDrop("scheduleTraining")}
                    description={tDrop("scheduleTrainingDesc")}
                    onClick={handleScheduleTraining}
                    disabled={isSaving}
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

**Key design decisions:**
- Reuses existing i18n keys from `dropAction` namespace for action card labels (DRY)
- New `driverActions` namespace only for panel-specific strings
- `DriverEventCard` and `ActionCard` extracted to module scope (React 19 rule)
- Clicking an event's goals icon closes this panel and opens the EventGoalPanel
- Quick actions section hidden for `viewer` role via RBAC check
- Loading state uses skeleton animation (not spinner)
- `useDriverEvents` only fetches when dialog is open (`open ? driverId : null`)

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 12: Thread `onDriverClick` Through Calendar Views
**Files:** Multiple calendar view files (modify)
**Action:** UPDATE

The `onDriverClick` callback needs to flow from `DashboardContent` through CalendarPanel → CalendarGrid → WeekView/MonthView → CalendarEventCard.

**12a. CalendarPanel** (`cms/apps/web/src/components/dashboard/calendar-panel.tsx`):
- Add prop: `onDriverClick?: (event: CalendarEvent) => void`
- Pass it to `CalendarGrid`

**12b. CalendarGrid** (`cms/apps/web/src/components/dashboard/calendar-grid.tsx`):
- Add prop: `onDriverClick?: (event: CalendarEvent) => void`
- Pass it to `WeekView`, `MonthView` (and any other views that render `CalendarEventCard`)

**12c. WeekView** (`cms/apps/web/src/components/dashboard/week-view.tsx`):
- Add prop: `onDriverClick?: (event: CalendarEvent) => void`
- Pass to `CalendarEventCard` as: `onDriverClick={onDriverClick ? () => onDriverClick(event) : undefined}`

**12d. MonthView** (`cms/apps/web/src/components/dashboard/month-view.tsx`):
- Same pattern as WeekView

**12e. CalendarEventCard** (`cms/apps/web/src/components/dashboard/calendar-event.tsx`):
- Already updated in Task 10 to accept and use `onDriverClick` prop

Read each file first to find the exact prop threading locations. Follow the existing `onEventClick` prop threading pattern — it's identical.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 13: Wire DriverActionsPanel into DashboardContent
**File:** `cms/apps/web/src/components/dashboard/dashboard-content.tsx` (modify)
**Action:** UPDATE

**13a.** Add imports at top:
```typescript
import { DriverActionsPanel } from "./driver-actions-panel";
```

**13b.** Add state for the driver actions panel (after the goalPanelOpen state block around line 42):
```typescript
const [driverPanelEvent, setDriverPanelEvent] = useState<CalendarEvent | null>(null);
const [driverPanelOpen, setDriverPanelOpen] = useState(false);
```

**13c.** Add handler (after `handleGoalsUpdated`):
```typescript
const handleDriverClick = useCallback((event: CalendarEvent) => {
  setDriverPanelEvent(event);
  setDriverPanelOpen(true);
}, []);
```

**13d.** Add handler for when an event is created from the driver panel:
```typescript
const handleDriverPanelEventCreated = useCallback(() => {
  void calendarRefetchRef.current?.();
}, []);
```

**13e.** Pass `onDriverClick={handleDriverClick}` to both `CalendarPanel` instances (mobile and desktop, around lines 103-107 and 141-145).

**13f.** Add the `DriverActionsPanel` component at the end of the JSX (after EventGoalPanel, around line 168):
```tsx
{/* Driver actions panel */}
<DriverActionsPanel
  driverId={driverPanelEvent?.driver_id ?? null}
  driverName={driverPanelEvent?.title.split(" - ")[0] ?? ""}
  date={driverPanelEvent ? driverPanelEvent.start : null}
  open={driverPanelOpen}
  onOpenChange={setDriverPanelOpen}
  onEventClick={(event) => {
    setDriverPanelOpen(false);
    setSelectedEvent(event);
    setGoalPanelOpen(true);
  }}
  onEventCreated={handleDriverPanelEventCreated}
/>
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 14: Check ScrollArea Installation
**Action:** VERIFY

Check if `scroll-area` component exists:
```bash
ls cms/apps/web/src/components/ui/scroll-area.tsx
```

If it doesn't exist, install it:
```bash
cd /Users/Berzins/Desktop/VTV/cms/apps/web && npx shadcn@latest add scroll-area
```

(The DriverActionsPanel may benefit from ScrollArea if a driver has many events, but the initial implementation uses a simple flex column. This task is a precaution — skip if not needed.)

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

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

- [ ] Clicking event card still opens EventGoalPanel (unchanged behavior)
- [ ] Clicking driver name in event card opens DriverActionsPanel
- [ ] DriverActionsPanel shows all events for that driver on that day
- [ ] Quick action cards create events with `driver_id` set
- [ ] Quick actions hidden for viewer role
- [ ] Events created from DriverDropDialog now include `driver_id`
- [ ] i18n keys present in both lv.json and en.json
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] Accessibility: all interactive elements have roles, labels, keyboard support
- [ ] `e.stopPropagation()` on driver name click prevents double-dialog

## Security Checklist
- [x] No hardcoded credentials
- [x] Auth tokens via httpOnly cookies (Auth.js)
- [x] No `dangerouslySetInnerHTML`
- [x] User input displayed via React JSX (auto-escaped)
- [x] RBAC enforced — quick actions only for scheduling roles

## Acceptance Criteria

This feature is complete when:
- [ ] Clicking driver name in calendar event card opens the Driver Actions Panel
- [ ] Panel shows driver's events for that day (fetched via `driver_id` filter)
- [ ] Quick actions allow creating new events for the driver (with `driver_id`)
- [ ] Clicking an event in the panel opens the goal panel
- [ ] All existing events created via DriverDropDialog now include `driver_id`
- [ ] Both languages (lv/en) have complete translations
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing dashboard functionality
- [ ] Ready for `/commit`
