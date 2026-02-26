# Plan: Calendar Goal Indicators + Goal Tracking (Session 4 of 4)

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: High
**Route**: `/[locale]/` (dashboard — existing page)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor (scheduling); viewer (read-only)
**Session**: 4 of 4 (depends on Session 3 goal dialog — completed)

## Feature Description

Add visual goal tracking to the dashboard calendar. Events with goals display progress indicators — mini cards in month view showing driver name and completion fraction, colored progress bars in week view's event cards, and status dots in three-month view. Clicking any event opens a goal completion panel where dispatchers can toggle individual goal checkboxes and save progress back to the backend via `PATCH /api/v1/events/{id}`.

This makes goals visible and actionable directly from the calendar. Events without goals continue to render exactly as before — full backward compatibility.

## Design System

### Master Rules (from MASTER.md)
- **Typography**: Lexend for headings, Source Sans 3 for body
- **Spacing**: Compact dashboard-density tokens (`--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight`, `--spacing-cell`)
- **Buttons**: cursor:pointer on all clickable elements, 200ms transitions
- **Focus**: 3px focus rings for accessibility
- **Anti-patterns**: No emojis as icons, no hardcoded colors, no layout-shifting hovers

### Page Override
- None — dashboard follows MASTER.md rules directly.

### Tokens Used
- Surface: `bg-surface`, `bg-surface-raised`, `bg-card-bg`
- Borders: `border-border`, `border-border-subtle`, `border-card-border`
- Text: `text-foreground`, `text-foreground-muted`, `text-foreground-subtle`
- Interactive: `bg-interactive`, `text-interactive`, `bg-interactive/10`
- Status: `text-status-ontime`, `text-status-delayed`, `bg-status-ontime/15`, `bg-status-delayed/15`, `bg-foreground/10`
- Category: `bg-category-driver-shift`, `bg-category-maintenance`, `bg-category-route-change`, `bg-category-service-alert`
- Spacing: `--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight`, `--spacing-cell`

### Goal Status Colors (semantic tokens)
- **Not started** (0%): `text-foreground-muted` + `bg-foreground/10`
- **In progress** (1-99%): `text-status-delayed` + `bg-status-delayed/15`
- **Completed** (100%): `text-status-ontime` + `bg-status-ontime/15`

## Components Needed

### Existing (shadcn/ui — already installed)
- `Dialog` / `DialogContent` / `DialogHeader` / `DialogTitle` / `DialogDescription` — event goal panel
- `Button` — save, cancel buttons
- `Progress` — progress bar in goal panel (already in `ui/progress.tsx`)
- `Badge` — status badges
- `ScrollArea` — scrollable goal list if many items
- `Separator` — divider in goal panel

### New shadcn/ui to Install
- `Checkbox` — `npx shadcn@latest add checkbox` — goal item checkboxes

### Custom Components to Create
- `GoalProgressBadge` at `cms/apps/web/src/components/dashboard/goal-progress-badge.tsx` — reusable compact progress indicator (used in month/week/three-month views + goal panel)
- `EventGoalPanel` at `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` — dialog for viewing and toggling goal completion

## i18n Keys

### English (`en.json`)
Add to existing `dashboard.goals` object (merge, do not replace existing keys):
```json
"completed": "Completed",
"inProgress": "In Progress",
"notStarted": "Not Started",
"progress": "{done} of {total}",
"markDone": "Mark as done",
"eventDetail": "Event Details",
"updateSuccess": "Goals updated",
"updateError": "Failed to update goals",
"noGoals": "No goals set",
"goalProgress": "Goal Progress",
"close": "Close"
```

### Latvian (`lv.json`)
Add to existing `dashboard.goals` object (merge, do not replace existing keys):
```json
"completed": "Pabeigts",
"inProgress": "Procesā",
"notStarted": "Nav sākts",
"progress": "{done} no {total}",
"markDone": "Atzīmēt kā izpildītu",
"eventDetail": "Notikuma detaļas",
"updateSuccess": "Mērķi atjaunināti",
"updateError": "Neizdevās atjaunināt mērķus",
"noGoals": "Nav mērķu",
"goalProgress": "Mērķu progress",
"close": "Aizvērt"
```

## Data Fetching

- **API endpoints used**:
  - `GET /api/v1/events/` — existing, already fetches events with `goals` field (since Session 2)
  - `PATCH /api/v1/events/{id}` — update event goals (existing `updateEvent` in `events-sdk.ts`)
- **Server vs Client**: All client-side (calendar + goal panel are client components)
- **Optimistic UI**: When toggling a goal checkbox, update local state immediately. On save, call `updateEvent`. On error, revert state and show error toast.
- **SWR revalidation**: After successful goal save, call the calendar `refetch` function to refresh events.
- **CRITICAL — Server/client boundary**: All components are `'use client'`. The `updateEvent` function in `events-sdk.ts` uses `authFetch` which handles dual-context internally. No server-only imports needed.

## RBAC Integration

- **No changes needed** — the dashboard already enforces RBAC via middleware. Goal panel respects existing roles.

## Sidebar Navigation

- **No changes needed** — this is an enhancement to the existing dashboard.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules
- `cms/apps/web/CLAUDE.md` — Frontend conventions, React 19 anti-patterns, SWR patterns

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/dashboard/goals-form.tsx` — GoalsForm component (Session 3, reference for goal item patterns)
- `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` — DriverDropDialog (Session 3, shows Dialog usage pattern)
- `cms/apps/web/src/components/dashboard/calendar-event.tsx` — CalendarEventCard (being modified)
- `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — CalendarGrid (being modified)
- `cms/apps/web/src/components/dashboard/calendar-panel.tsx` — CalendarPanel (being modified)
- `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — DashboardContent (being modified)
- `cms/apps/web/src/components/dashboard/month-view.tsx` — MonthView (being modified)
- `cms/apps/web/src/components/dashboard/week-view.tsx` — WeekView (being modified)
- `cms/apps/web/src/components/dashboard/three-month-view.tsx` — ThreeMonthView (being modified)
- `cms/apps/web/src/lib/events-sdk.ts` — Events API (existing `updateEvent` function)
- `cms/apps/web/src/types/dashboard.ts` — CalendarEvent type (being modified)
- `cms/apps/web/src/types/event.ts` — EventGoals, GoalItem types (already exist from Session 3)
- `cms/apps/web/src/hooks/use-calendar-events.ts` — Calendar events hook (being modified)

### Files to Modify
- `cms/apps/web/src/types/dashboard.ts` — Add goals field to CalendarEvent
- `cms/apps/web/src/hooks/use-calendar-events.ts` — Map goals from API response
- `cms/apps/web/src/components/dashboard/calendar-event.tsx` — Add goal progress indicator + onClick
- `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — Add onEventClick prop
- `cms/apps/web/src/components/dashboard/calendar-panel.tsx` — Forward onEventClick
- `cms/apps/web/src/components/dashboard/month-view.tsx` — Add goal mini cards + event click
- `cms/apps/web/src/components/dashboard/week-view.tsx` — Forward event click to cards
- `cms/apps/web/src/components/dashboard/three-month-view.tsx` — Add goal status dots + event click
- `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — Host EventGoalPanel + wire refetch
- `cms/apps/web/messages/en.json` — Add goal tracking i18n keys
- `cms/apps/web/messages/lv.json` — Add goal tracking i18n keys

### Files to Create
- `cms/apps/web/src/components/ui/checkbox.tsx` — shadcn Checkbox component (via `npx shadcn@latest add checkbox`)
- `cms/apps/web/src/components/dashboard/goal-progress-badge.tsx` — Reusable progress badge
- `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` — Event goal completion dialog

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
| `bg-green-500`, `bg-emerald-500` | `bg-success` or `bg-status-ontime` |
| `bg-amber-400`, `bg-amber-500` | `bg-status-delayed` |
| `bg-gray-100`, `bg-slate-100` | `bg-surface` / `bg-muted` |
| `border-gray-200` | `border-border` |

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **No named Tailwind container sizes** — Use explicit rem values: `sm:max-w-[32rem]`, `sm:max-w-[36rem]`
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies**

## TypeScript Security Rules

- **Never use `as` casts on external data without runtime validation**
- **Clear `.next` cache when module resolution errors persist** — `rm -rf cms/apps/web/.next`

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD, RUN

---

### Task 1: Install Checkbox Component
**Action:** RUN

```bash
cd cms && npx shadcn@latest add checkbox --yes
```

Verify `cms/apps/web/src/components/ui/checkbox.tsx` was created.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: Add English i18n Keys for Goal Tracking
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add these keys to the EXISTING `dashboard.goals` object. Merge into the existing block — do NOT replace existing keys (title, subtitle, route, etc. must stay). Add after the existing `"tram": "Tram"` line:

```json
"completed": "Completed",
"inProgress": "In Progress",
"notStarted": "Not Started",
"progress": "{done} of {total}",
"markDone": "Mark as done",
"eventDetail": "Event Details",
"updateSuccess": "Goals updated",
"updateError": "Failed to update goals",
"noGoals": "No goals set",
"goalProgress": "Goal Progress",
"close": "Close"
```

**Per-task validation:**
- JSON is valid (no trailing commas, proper nesting)
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Add Latvian i18n Keys for Goal Tracking
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Mirror the English keys in the existing `dashboard.goals` object. Add after the existing `"tram": "Tramvajs"` line:

```json
"completed": "Pabeigts",
"inProgress": "Procesā",
"notStarted": "Nav sākts",
"progress": "{done} no {total}",
"markDone": "Atzīmēt kā izpildītu",
"eventDetail": "Notikuma detaļas",
"updateSuccess": "Mērķi atjaunināti",
"updateError": "Neizdevās atjaunināt mērķus",
"noGoals": "Nav mērķu",
"goalProgress": "Mērķu progress",
"close": "Aizvērt"
```

**Per-task validation:**
- JSON is valid
- `pnpm --filter @vtv/web type-check` passes

---

### Task 4: Extend CalendarEvent Type
**File:** `cms/apps/web/src/types/dashboard.ts` (modify)
**Action:** UPDATE

Add `goals` field to the `CalendarEvent` interface. Import `EventGoals` type from the event module.

Add at the top of the file:
```typescript
import type { EventGoals } from "./event";
```

Update the `CalendarEvent` interface — add after the `description` field:
```typescript
export interface CalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  priority: EventPriority;
  category: EventCategory;
  description?: string;
  goals?: EventGoals | null;  // ADD — goal tracking data from backend
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 5: Update useCalendarEvents Hook to Map Goals
**File:** `cms/apps/web/src/hooks/use-calendar-events.ts` (modify)
**Action:** UPDATE

Update the `toCalendarEvent` function to include `goals` from the API response:

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
    goals: event.goals ?? undefined,  // ADD — pass through goals data
  };
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: Create GoalProgressBadge Component
**File:** `cms/apps/web/src/components/dashboard/goal-progress-badge.tsx` (create)
**Action:** CREATE

Create a reusable compact progress indicator component. This is used in month view mini cards, week view event cards, and the goal panel.

**Component interface:**
```typescript
interface GoalProgressBadgeProps {
  goals: EventGoals;
  /** "compact" = fraction text only, "bar" = fraction + mini progress bar */
  variant?: "compact" | "bar";
}
```

**Imports:**
```typescript
"use client";

import { cn } from "@/lib/utils";
import type { EventGoals } from "@/types/event";
```

**Helper functions (at module scope):**

```typescript
type GoalStatus = "not-started" | "in-progress" | "completed";

function getGoalStatus(goals: EventGoals): GoalStatus {
  const total = goals.items.length;
  if (total === 0) return "not-started";
  const done = goals.items.filter((item) => item.completed).length;
  if (done === 0) return "not-started";
  if (done === total) return "completed";
  return "in-progress";
}

function getCompletionCounts(goals: EventGoals): { done: number; total: number } {
  const total = goals.items.length;
  const done = goals.items.filter((item) => item.completed).length;
  return { done, total };
}

const statusStyles: Record<GoalStatus, string> = {
  "not-started": "text-foreground-muted bg-foreground/10",
  "in-progress": "text-status-delayed bg-status-delayed/15",
  completed: "text-status-ontime bg-status-ontime/15",
};

const barColors: Record<GoalStatus, string> = {
  "not-started": "bg-foreground/20",
  "in-progress": "bg-status-delayed",
  completed: "bg-status-ontime",
};
```

**Component body:**

For `variant="compact"` (default): render just the fraction text (`2/5`) in a small rounded badge with status-colored background.

For `variant="bar"`: render fraction text + a tiny progress bar below it.

```tsx
export function GoalProgressBadge({ goals, variant = "compact" }: GoalProgressBadgeProps) {
  const status = getGoalStatus(goals);
  const { done, total } = getCompletionCounts(goals);

  if (total === 0) return null;

  const pct = Math.round((done / total) * 100);

  if (variant === "compact") {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium",
          statusStyles[status],
        )}
      >
        {done}/{total}
      </span>
    );
  }

  return (
    <div className="flex flex-col gap-0.5">
      <span
        className={cn(
          "inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium",
          statusStyles[status],
        )}
      >
        {done}/{total}
      </span>
      <div className="h-1 w-full overflow-hidden rounded-full bg-foreground/10">
        <div
          className={cn("h-full rounded-full transition-all duration-200", barColors[status])}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
```

**Also export the helper functions** — `getGoalStatus` and `getCompletionCounts` are reused by other components (month-view for dot colors, event-goal-panel):
```typescript
export { getGoalStatus, getCompletionCounts };
export type { GoalStatus };
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 7: Create EventGoalPanel Component
**File:** `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` (create)
**Action:** CREATE

Create a dialog for viewing event details and toggling goal completion checkboxes.

**Component interface:**
```typescript
interface EventGoalPanelProps {
  event: CalendarEvent | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onGoalsUpdated: () => void;
}
```

**Imports:**
```typescript
"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";
import type { EventGoals, GoalItem } from "@/types/event";
import { updateEvent } from "@/lib/events-sdk";
import { getGoalStatus, getCompletionCounts } from "./goal-progress-badge";
import type { GoalStatus } from "./goal-progress-badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
```

**State:**
```typescript
const [goalItems, setGoalItems] = useState<GoalItem[]>([]);
const [isSaving, setIsSaving] = useState(false);
```

**CRITICAL: Use `key` prop on the dialog content** to reset state when a different event is selected. The parent renders:
```tsx
<EventGoalPanel key={event?.id ?? "closed"} event={event} ... />
```
This avoids using `setState` in `useEffect` when the event changes (React 19 anti-pattern).

The component initializes `goalItems` from `event.goals.items` in the `useState` initializer (not in an effect):
```typescript
const [goalItems, setGoalItems] = useState<GoalItem[]>(
  event?.goals?.items ?? [],
);
```

**Toggle handler (at component scope):**
```typescript
const handleToggle = useCallback((index: number) => {
  setGoalItems((prev) =>
    prev.map((item, i) =>
      i === index ? { ...item, completed: !item.completed } : item,
    ),
  );
}, []);
```

**Save handler:**
```typescript
const handleSave = useCallback(async () => {
  if (!event?.goals) return;
  setIsSaving(true);
  try {
    const updatedGoals: EventGoals = {
      ...event.goals,
      items: goalItems,
    };
    await updateEvent(Number(event.id), { goals: updatedGoals });
    toast.success(t("updateSuccess"));
    onGoalsUpdated();
    onOpenChange(false);
  } catch {
    toast.error(t("updateError"));
  } finally {
    setIsSaving(false);
  }
}, [event, goalItems, t, onGoalsUpdated, onOpenChange]);
```

**GoalItemRow sub-component (defined at MODULE SCOPE, not inside EventGoalPanel):**
```typescript
function GoalItemRow({
  item,
  index,
  onToggle,
}: {
  item: GoalItem;
  index: number;
  onToggle: (index: number) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-(--spacing-inline) py-(--spacing-tight)">
      <Checkbox
        checked={item.completed}
        onCheckedChange={() => onToggle(index)}
      />
      <span
        className={cn(
          "text-sm",
          item.completed ? "text-foreground-muted line-through" : "text-foreground",
        )}
      >
        {item.text}
      </span>
    </label>
  );
}
```

**JSX Layout:**

```tsx
return (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="sm:max-w-[32rem]">
      <DialogHeader>
        <DialogTitle>{t("eventDetail")}</DialogTitle>
        <DialogDescription className="sr-only">
          {event?.title ?? ""}
        </DialogDescription>
      </DialogHeader>

      {event && (
        <div className="flex flex-col gap-(--spacing-grid)">
          {/* Event info */}
          <div>
            <p className="text-sm font-medium text-foreground">{event.title}</p>
            <p className="text-xs text-foreground-muted">
              {event.start.toLocaleDateString()} · {formatTime(event.start)} – {formatTime(event.end)}
            </p>
            {event.description && (
              <p className="mt-(--spacing-tight) text-xs text-foreground-muted">
                {event.description}
              </p>
            )}
          </div>

          {/* Goal progress summary */}
          {hasGoals && (
            <>
              <Separator />
              <div>
                <div className="mb-(--spacing-tight) flex items-center justify-between">
                  <p className="text-sm font-medium text-foreground">
                    {t("goalProgress")}
                  </p>
                  <span className={cn("text-xs font-medium", statusTextClass)}>
                    {t("progress", { done, total })}
                  </span>
                </div>

                {/* Progress bar */}
                <div className="h-2 w-full overflow-hidden rounded-full bg-foreground/10">
                  <div
                    className={cn("h-full rounded-full transition-all duration-200", barColorClass)}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>

              {/* Goal checklist */}
              <div className="flex flex-col">
                {goalItems.map((item, index) => (
                  <GoalItemRow
                    key={`goal-${String(index)}`}
                    item={item}
                    index={index}
                    onToggle={handleToggle}
                  />
                ))}
              </div>

              {/* Transport/route info if present */}
              {(event.goals?.transport_type || event.goals?.vehicle_id || event.goals?.route_id) && (
                <div className="flex flex-wrap gap-(--spacing-tight) text-xs text-foreground-muted">
                  {event.goals.transport_type && (
                    <span className="rounded-full bg-foreground/10 px-2 py-0.5">
                      {event.goals.transport_type}
                    </span>
                  )}
                  {event.goals.vehicle_id && (
                    <span className="rounded-full bg-foreground/10 px-2 py-0.5">
                      {event.goals.vehicle_id}
                    </span>
                  )}
                </div>
              )}
            </>
          )}

          {/* No goals fallback */}
          {!hasGoals && (
            <p className="py-4 text-center text-sm text-foreground-muted">
              {t("noGoals")}
            </p>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-(--spacing-inline)">
            {hasGoals ? (
              <Button
                size="sm"
                onClick={handleSave}
                disabled={isSaving}
                className="cursor-pointer"
              >
                {isSaving ? t("saving") : t("save")}
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onOpenChange(false)}
                className="cursor-pointer"
              >
                {t("close")}
              </Button>
            )}
          </div>
        </div>
      )}
    </DialogContent>
  </Dialog>
);
```

**Computed values (between hooks and return):**
```typescript
const hasGoals = Boolean(event?.goals && event.goals.items.length > 0);
const { done, total } = event?.goals
  ? getCompletionCounts(event.goals)
  : { done: 0, total: 0 };
// Use goalItems (local state) for live progress, not event.goals
const localDone = goalItems.filter((item) => item.completed).length;
const localTotal = goalItems.length;
const pct = localTotal > 0 ? Math.round((localDone / localTotal) * 100) : 0;
const status: GoalStatus = localTotal === 0 ? "not-started" : localDone === 0 ? "not-started" : localDone === localTotal ? "completed" : "in-progress";
```

NOTE: For the progress bar and summary, use `localDone`/`localTotal` from `goalItems` (local state) so the UI updates immediately when checkboxes are toggled (optimistic feel without full optimistic API).

**Define `formatTime` at module scope:**
```typescript
function formatTime(date: Date): string {
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
}
```

**Status style maps (at module scope):**
```typescript
const statusTextStyles: Record<GoalStatus, string> = {
  "not-started": "text-foreground-muted",
  "in-progress": "text-status-delayed",
  completed: "text-status-ontime",
};

const barColorStyles: Record<GoalStatus, string> = {
  "not-started": "bg-foreground/20",
  "in-progress": "bg-status-delayed",
  completed: "bg-status-ontime",
};
```

Then: `const statusTextClass = statusTextStyles[status];` and `const barColorClass = barColorStyles[status];`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 8: Update CalendarEventCard with Goal Indicator + onClick
**File:** `cms/apps/web/src/components/dashboard/calendar-event.tsx` (modify)
**Action:** UPDATE

Add `onClick` prop and goal progress indicator to CalendarEventCard.

**Update interface:**
```typescript
interface CalendarEventCardProps {
  event: CalendarEventType;
  onClick?: () => void;  // ADD
}
```

**Add import:**
```typescript
import { GoalProgressBadge } from "./goal-progress-badge";
```

**Update component signature:**
```typescript
export function CalendarEventCard({ event, onClick }: CalendarEventCardProps) {
```

**Update root div** — add `onClick`, `role="button"`, `tabIndex`, and `onKeyDown` for accessibility:
```tsx
<div
  className={cn(
    "h-full cursor-pointer overflow-hidden rounded-md p-(--spacing-cell) text-xs transition-colors duration-200 hover:opacity-80",
    categoryStyles[event.category]
  )}
  onClick={onClick}
  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onClick?.(); }}
  role={onClick ? "button" : undefined}
  tabIndex={onClick ? 0 : undefined}
>
```

**Add goal progress badge** — after the priority badge, conditionally show goal progress:
```tsx
{event.goals && event.goals.items.length > 0 && (
  <GoalProgressBadge goals={event.goals} variant="compact" />
)}
```

Place this inside the card, after the existing priority `<span>`. On the same line or below it.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 9: Add onEventClick to CalendarGrid
**File:** `cms/apps/web/src/components/dashboard/calendar-grid.tsx` (modify)
**Action:** UPDATE

**Update CalendarGridProps:**
```typescript
interface CalendarGridProps {
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
  onEventClick?: (event: CalendarEvent) => void;  // ADD
}
```

**Update component destructuring:**
```typescript
export function CalendarGrid({ events, onDayDrop, onEventClick }: CalendarGridProps) {
```

**Pass `onEventClick` to all view components:**
```tsx
{view === "week" && (
  <WeekView currentDate={currentDate} events={events} onDayDrop={onDayDrop} onEventClick={onEventClick} />
)}
{view === "month" && (
  <MonthView currentDate={currentDate} events={events} onDayDrop={onDayDrop} onEventClick={onEventClick} />
)}
{view === "3month" && (
  <ThreeMonthView currentDate={currentDate} events={events} onDayDrop={onDayDrop} onEventClick={onEventClick} />
)}
```

YearView does NOT get `onEventClick` (too zoomed out, no individual events shown).

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Update MonthView with Goal Mini Cards + Event Click
**File:** `cms/apps/web/src/components/dashboard/month-view.tsx` (modify)
**Action:** UPDATE

**Update MonthViewProps:**
```typescript
interface MonthViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
  onEventClick?: (event: CalendarEvent) => void;  // ADD
}
```

**Add imports:**
```typescript
import { GoalProgressBadge } from "./goal-progress-badge";
import { getGoalStatus } from "./goal-progress-badge";
```

**Update component destructuring:**
```typescript
export function MonthView({ currentDate, events, onDayDrop, onEventClick }: MonthViewProps) {
```

**Update the event rendering inside each day cell.** Replace the current event `<div>` block with logic that differentiates events with goals from those without:

For events WITHOUT goals — keep the existing dot + title rendering.

For events WITH goals — show a mini card:
```tsx
{visibleEvents.map((event) => {
  const hasGoals = event.goals && event.goals.items.length > 0;
  return hasGoals ? (
    <button
      key={event.id}
      type="button"
      onClick={(e) => { e.stopPropagation(); onEventClick?.(event); }}
      className="flex w-full items-center justify-between gap-(--spacing-tight) rounded bg-surface-raised px-1 py-0.5 text-left transition-colors duration-200 hover:bg-interactive/10 cursor-pointer"
    >
      <span className="truncate text-[10px] font-medium text-foreground">
        {event.title}
      </span>
      <GoalProgressBadge goals={event.goals!} variant="compact" />
    </button>
  ) : (
    <button
      key={event.id}
      type="button"
      onClick={(e) => { e.stopPropagation(); onEventClick?.(event); }}
      className="flex w-full items-center gap-(--spacing-tight) text-left cursor-pointer"
    >
      <div
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          categoryDotColors[event.category]
        )}
      />
      <span className="truncate text-[10px] text-foreground-muted">
        {event.title}
      </span>
    </button>
  );
})}
```

**IMPORTANT:** Remove the `t()` wrapping on `event.title`. Real events from the API have plain text titles (e.g., "J. Bērziņš - Morning (05:00-13:00)"), not i18n keys. The mock events used i18n keys, but since Session 1-3, all events come from the real API. Change `{t(event.title)}` to just `{event.title}` in both the goal card and the non-goal dot+title. This prevents next-intl from trying to look up dynamic strings as translation keys.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 11: Update WeekView with Event Click Passthrough
**File:** `cms/apps/web/src/components/dashboard/week-view.tsx` (modify)
**Action:** UPDATE

**Update WeekViewProps:**
```typescript
interface WeekViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
  onEventClick?: (event: CalendarEvent) => void;  // ADD
}
```

**Update component destructuring:**
```typescript
export function WeekView({ currentDate, events, onDayDrop, onEventClick }: WeekViewProps) {
```

**Update the CalendarEventCard rendering** in the events overlay section. Add `onClick` to each card:

```tsx
{eventsByDay.get(dayIdx)?.map((event) => {
  // ... existing positioning logic (startMin, endMin, topPx, heightPx) ...
  return (
    <div
      key={event.id}
      className="absolute inset-x-0 overflow-hidden bg-background"
      style={{
        top: `${topPx}px`,
        height: `${heightPx}px`,
      }}
    >
      <CalendarEventCard
        event={event}
        onClick={onEventClick ? () => onEventClick(event) : undefined}
      />
    </div>
  );
})}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 12: Update ThreeMonthView with Goal Status Dots + Event Click
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx` (modify)
**Action:** UPDATE

**Update ThreeMonthViewProps:**
```typescript
interface ThreeMonthViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onDayDrop?: (date: Date, driverJson: string) => void;
  onEventClick?: (event: CalendarEvent) => void;  // ADD
}
```

**Add import:**
```typescript
import { getGoalStatus } from "./goal-progress-badge";
```

**Update MiniMonth function signature** — add `onEventClick` param:
```typescript
function MiniMonth({
  year,
  month,
  events,
  today,
  onDayDrop,
  onEventClick,
}: {
  year: number;
  month: number;
  events: CalendarEvent[];
  today: Date;
  onDayDrop?: (date: Date, driverJson: string) => void;
  onEventClick?: (event: CalendarEvent) => void;
}) {
```

**Update the event dot rendering inside day cells.** For events with goals, use goal-status-colored dots instead of category dots. For the three-month view (tiny cells), clicking an event with goals opens the panel:

```tsx
{visibleEvents.map((event) => {
  const hasGoals = event.goals && event.goals.items.length > 0;
  const goalStatus = hasGoals ? getGoalStatus(event.goals!) : null;
  const dotClass = hasGoals
    ? goalStatus === "completed"
      ? "bg-status-ontime"
      : goalStatus === "in-progress"
        ? "bg-status-delayed"
        : "bg-foreground/30"
    : categoryDotColors[event.category];

  return (
    <button
      key={event.id}
      type="button"
      onClick={(e) => { e.stopPropagation(); onEventClick?.(event); }}
      className="flex items-center gap-0.5 cursor-pointer"
    >
      <div
        className={cn("size-1 shrink-0 rounded-full", dotClass)}
      />
      <span className="truncate text-[8px] leading-tight text-foreground-muted">
        {event.title}
      </span>
    </button>
  );
})}
```

**Remove `t()` wrapping** on `event.title` — same as MonthView, use `{event.title}` directly.

**Update ThreeMonthView component** to pass `onEventClick` to MiniMonth:
```tsx
export function ThreeMonthView({ currentDate, events, onDayDrop, onEventClick }: ThreeMonthViewProps) {
  // ... existing logic ...
  return (
    <div className="...">
      {months.map(({ year, month }) => (
        <MiniMonth
          key={`${year}-${month}`}
          year={year}
          month={month}
          events={events}
          today={today}
          onDayDrop={onDayDrop}
          onEventClick={onEventClick}
        />
      ))}
    </div>
  );
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 13: Update CalendarPanel to Forward onEventClick
**File:** `cms/apps/web/src/components/dashboard/calendar-panel.tsx` (modify)
**Action:** UPDATE

**Update CalendarPanelProps:**
```typescript
interface CalendarPanelProps {
  onDayDrop?: (date: Date, driverJson: string) => void;
  refetchRef?: RefObject<(() => Promise<void>) | null>;
  onEventClick?: (event: CalendarEvent) => void;  // ADD
}
```

**Add import:**
```typescript
import type { CalendarEvent } from "@/types/dashboard";
```

**Update component:**
```typescript
export function CalendarPanel({ onDayDrop, refetchRef, onEventClick }: CalendarPanelProps) {
```

**Pass to CalendarGrid:**
```tsx
return <CalendarGrid events={events} onDayDrop={onDayDrop} onEventClick={onEventClick} />;
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 14: Update DashboardContent to Host EventGoalPanel
**File:** `cms/apps/web/src/components/dashboard/dashboard-content.tsx` (modify)
**Action:** UPDATE

Wire up the event click flow: calendar event click → open EventGoalPanel → save goals → refetch calendar.

**Add imports:**
```typescript
import { EventGoalPanel } from "./event-goal-panel";
import type { CalendarEvent } from "@/types/dashboard";
```

**Add state for the selected event and goal panel:**
```typescript
const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
const [goalPanelOpen, setGoalPanelOpen] = useState(false);
```

**Add event click handler:**
```typescript
const handleEventClick = useCallback((event: CalendarEvent) => {
  setSelectedEvent(event);
  setGoalPanelOpen(true);
}, []);
```

**Add goals updated handler** — closes the panel and refetches calendar events:
```typescript
const handleGoalsUpdated = useCallback(() => {
  void calendarRefetchRef.current?.();
}, []);
```

**Pass `onEventClick` to CalendarPanel** — in both mobile and desktop layouts:

Desktop:
```tsx
<CalendarPanel
  onDayDrop={canSchedule ? handleDayDrop : undefined}
  refetchRef={calendarRefetchRef}
  onEventClick={handleEventClick}
/>
```

Mobile:
```tsx
<CalendarPanel
  onDayDrop={canSchedule ? handleDayDrop : undefined}
  refetchRef={calendarRefetchRef}
  onEventClick={handleEventClick}
/>
```

**Add EventGoalPanel component** — below the existing DriverDropDialog:
```tsx
{/* Event goal panel */}
<EventGoalPanel
  key={selectedEvent?.id ?? "closed"}
  event={selectedEvent}
  open={goalPanelOpen}
  onOpenChange={setGoalPanelOpen}
  onGoalsUpdated={handleGoalsUpdated}
/>
```

**CRITICAL: The `key` prop** on EventGoalPanel ensures the component remounts with fresh state when a different event is selected. This follows the React 19 anti-pattern #1 (no setState in useEffect).

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 15: Final Validation (3-Level Pyramid)

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

- [ ] Events WITHOUT goals render exactly as before (backward compat)
- [ ] Month view shows mini cards for events with goals (title + progress badge)
- [ ] Week view CalendarEventCard shows GoalProgressBadge for goal events
- [ ] Three-month view uses status-colored dots for goal events
- [ ] Clicking any event opens the EventGoalPanel dialog
- [ ] EventGoalPanel shows event title, time, description
- [ ] EventGoalPanel shows goal checklist with toggleable checkboxes
- [ ] Toggling checkboxes updates progress bar immediately (optimistic)
- [ ] "Save" calls PATCH /api/v1/events/{id} with updated goals
- [ ] Success toast shown after save, calendar refetches
- [ ] Error toast shown on save failure
- [ ] Events without goals show "No goals set" in the panel
- [ ] i18n keys present in both lv.json and en.json
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] Accessibility: checkboxes have proper labels, dialog has title
- [ ] No `t()` wrapping on event titles (real events have plain text, not i18n keys)
- [ ] Dialog uses `sm:max-w-[32rem]` (not named container size)

## Acceptance Criteria

This feature is complete when:
- [ ] Goal progress visible on all calendar views (month, week, three-month)
- [ ] Click-to-complete flow works (click event → toggle goals → save)
- [ ] Events without goals continue to render normally
- [ ] Both languages have complete translations
- [ ] Design system rules followed (MASTER.md, semantic tokens only)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing dashboard functionality (drag-and-drop, metrics, roster)
- [ ] Ready for `/commit`

## Security Checklist
- [x] No cookies modified (Auth.js handles auth cookies)
- [x] No redirects (dialog component, no navigation)
- [x] No hardcoded credentials
- [x] No file uploads
- [x] Auth tokens via httpOnly cookies (Auth.js, unchanged)
- [x] No `dangerouslySetInnerHTML`
- [x] External links use `rel="noopener noreferrer"` (no external links added)
- [x] User input displayed via React JSX (auto-escaped)

## Known Pitfalls

1. **CalendarEvent.id is a string, API expects number** — Use `Number(event.id)` when calling `updateEvent`. The ID was originally a number from `OperationalEvent.id` and converted via `String()` in `toCalendarEvent`.
2. **Don't create components inside EventGoalPanel** — GoalItemRow must be defined at module scope. React 19 forbids component definitions inside render.
3. **Use `key` prop on EventGoalPanel** — To reset local state when different events are selected. Do NOT use setState in useEffect.
4. **event.title is plain text, not an i18n key** — Real events from the API have plain text titles. Do NOT wrap in `t()`. The existing `t(event.title)` in calendar views was from mock data era and should be changed to just `{event.title}`.
5. **GoalProgressBadge returns null for zero items** — When `goals.items.length === 0`, the badge renders nothing. This is intentional — empty goal lists show no indicator.
6. **DialogContent className must not use named sizes** — Use `sm:max-w-[32rem]` not `sm:max-w-md`. Named sizes are broken in this project's Tailwind v4 setup.
7. **Checkbox onCheckedChange** — Radix Checkbox passes `boolean | "indeterminate"`. Our handler ignores the value and toggles based on current state, so the type mismatch is handled.
8. **stopPropagation on event clicks** — In month/three-month views, events are inside drag-and-drop zones. Use `e.stopPropagation()` to prevent click from bubbling to the drop zone.

## Deferred to V2

The following deliverables from the original stub are deferred to future sessions:
- **Today's Goals Dashboard Widget** — needs design exploration for dashboard layout integration
- **Driver Profile Goal History** — requires backend API enhancement (event filtering by driver_id not currently supported)
