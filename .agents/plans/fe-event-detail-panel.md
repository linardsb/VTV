# Plan: Enhanced Event Detail Panel

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: N/A (component enhancement on existing dashboard page)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer (view); admin, editor, dispatcher (edit/delete)

## Feature Description

The current `EventGoalPanel` component is a bare dialog that shows only the event title, time,
goal checklist (if goals exist), or "Nav mērķu" (no goals) with a close button. Users cannot
edit event fields, delete events, or add goals when none exist.

This enhancement transforms `EventGoalPanel` into a full-featured event detail panel with:
1. **View mode** (default): Rich event info display with edit/delete actions
2. **Edit mode** (inline toggle): All event fields become editable in-place
3. **Delete flow**: Confirmation step within the same dialog
4. **Goals management**: Add goals to events that don't have them, edit existing goals
5. **Quick actions** (driver events only): Create related events for the same driver/date

This applies to ALL event types (driver-shift, maintenance, route-change, service-alert).

## Design System

### Master Rules (from MASTER.md)
- Spacing: use `--spacing-card` (12px), `--spacing-grid` (12px), `--spacing-tight` (4px), `--spacing-inline` (6px)
- Typography: Lexend headings, Source Sans 3 body, 16px+ base
- Transitions: 200ms ease on all interactive elements
- Focus rings: 3px for WCAG AAA
- Touch targets: 44x44px minimum

### Page Override
- None — dashboard has no page-specific override file

### Tokens Used
- Surface: `bg-surface`, `bg-surface-raised`, `bg-background`
- Text: `text-foreground`, `text-foreground-muted`
- Border: `border-border`, `border-border-subtle`
- Interactive: `bg-interactive`, `text-interactive`, `text-interactive-foreground`
- Status: `text-status-ontime`, `text-status-delayed`, `text-status-critical`
- Error: `bg-destructive`, `text-destructive-foreground`
- Event subtypes: `bg-event-vacation/10`, `bg-event-sick/10`, `bg-event-training/10`, `bg-event-shift/10`
- Spacing: `--spacing-card`, `--spacing-grid`, `--spacing-tight`, `--spacing-inline`, `--spacing-cell`

## Components Needed

### Existing (shadcn/ui)
- `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription` — main container
- `Button` — edit, delete, save, cancel actions
- `Input` — title, time, date fields
- `Textarea` — description field
- `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue` — priority and category
- `Label` — form field labels
- `Separator` — section dividers
- `Checkbox` — goal item toggles
- `Badge` — priority and category display (view mode)

### New shadcn/ui to Install
- None — all needed components already installed

### Custom Components to Create
- None — enhancing existing `EventGoalPanel` component

## i18n Keys

### Latvian (`lv.json`) — add under `dashboard.eventPanel`
```json
{
  "dashboard": {
    "eventPanel": {
      "title": "Notikuma detaļas",
      "edit": "Rediģēt",
      "delete": "Dzēst",
      "save": "Saglabāt",
      "cancel": "Atcelt",
      "saving": "Saglabā...",
      "description": "Apraksts",
      "descriptionPlaceholder": "Notikuma apraksts...",
      "startTime": "Sākuma laiks",
      "endTime": "Beigu laiks",
      "startDate": "Sākuma datums",
      "endDate": "Beigu datums",
      "priority": "Prioritāte",
      "category": "Kategorija",
      "addGoals": "Pievienot mērķus",
      "addGoalPlaceholder": "Ievadiet mērķi...",
      "allDay": "Visa diena",
      "updated": "Notikums atjaunināts",
      "deleted": "Notikums dzēsts",
      "updateError": "Neizdevās atjaunināt notikumu",
      "deleteError": "Neizdevās dzēst notikumu",
      "deleteTitle": "Dzēst notikumu",
      "deleteConfirmation": "Vai tiešām vēlaties dzēst šo notikumu?",
      "deleteWarning": "Šī darbība ir neatgriezeniska. Notikums tiks neatgriezeniski dzēsts.",
      "deleteConfirm": "Dzēst",
      "deleteCancel": "Atcelt",
      "deleting": "Dzēš...",
      "quickActions": "Ātrās darbības",
      "categories": {
        "maintenance": "Apkope",
        "route-change": "Maršruta izmaiņa",
        "driver-shift": "Vadītāja maiņa",
        "service-alert": "Servisa brīdinājums"
      }
    }
  }
}
```

### English (`en.json`) — add under `dashboard.eventPanel`
```json
{
  "dashboard": {
    "eventPanel": {
      "title": "Event Details",
      "edit": "Edit",
      "delete": "Delete",
      "save": "Save",
      "cancel": "Cancel",
      "saving": "Saving...",
      "description": "Description",
      "descriptionPlaceholder": "Event description...",
      "startTime": "Start Time",
      "endTime": "End Time",
      "startDate": "Start Date",
      "endDate": "End Date",
      "priority": "Priority",
      "category": "Category",
      "addGoals": "Add Goals",
      "addGoalPlaceholder": "Enter a goal...",
      "allDay": "All day",
      "updated": "Event updated",
      "deleted": "Event deleted",
      "updateError": "Failed to update event",
      "deleteError": "Failed to delete event",
      "deleteTitle": "Delete Event",
      "deleteConfirmation": "Are you sure you want to delete this event?",
      "deleteWarning": "This action cannot be undone. The event will be permanently deleted.",
      "deleteConfirm": "Delete",
      "deleteCancel": "Cancel",
      "deleting": "Deleting...",
      "quickActions": "Quick Actions",
      "categories": {
        "maintenance": "Maintenance",
        "route-change": "Route Change",
        "driver-shift": "Driver Shift",
        "service-alert": "Service Alert"
      }
    }
  }
}
```

## Data Fetching

- **API endpoints used**:
  - `PATCH /api/v1/events/{event_id}` — update event (via `updateEvent` from `@/lib/events-sdk`)
  - `DELETE /api/v1/events/{event_id}` — delete event (via `deleteEvent` from `@/lib/events-sdk`)
  - `POST /api/v1/events` — create quick action events (via `createEvent` from `@/lib/events-sdk`)
- **All client-side**: The panel is a client component using existing SDK wrappers
- **No new API wrappers needed**: `updateEvent`, `deleteEvent`, `createEvent` already exist in `events-sdk.ts`

## RBAC Integration

- **No middleware changes needed** — this is an enhancement to the existing dashboard page
- **Role-based UI gating**: Edit/Delete buttons only shown for roles in `SCHEDULE_ROLES` (`admin`, `editor`, `dispatcher`). Viewers see read-only event details.

## Sidebar Navigation

- **No changes needed** — existing dashboard nav entry covers this

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/apps/web/CLAUDE.md` — Frontend-specific conventions, React 19 anti-patterns
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Files to Read (understand existing patterns)
- `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` — **THE FILE BEING REWRITTEN** (current 258 lines)
- `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — Parent orchestrator (wires event click → panel)
- `cms/apps/web/src/components/dashboard/driver-actions-panel.tsx` — Pattern for quick actions + event cards
- `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` — Pattern for multi-step dialog with action cards
- `cms/apps/web/src/components/dashboard/calendar-event.tsx` — CalendarEventCard (click source)
- `cms/apps/web/src/components/dashboard/goals-form.tsx` — Goals editing form (for reference)
- `cms/apps/web/src/components/dashboard/goal-progress-badge.tsx` — GoalProgressBadge component
- `cms/apps/web/src/components/dashboard/event-styles.ts` — `getEventCardStyle()` function
- `cms/apps/web/src/lib/events-sdk.ts` — `updateEvent()`, `deleteEvent()`, `createEvent()` functions
- `cms/apps/web/src/types/event.ts` — `EventUpdate`, `EventCreate`, `EventGoals`, `GoalItem` types
- `cms/apps/web/src/types/dashboard.ts` — `CalendarEvent` type
- `cms/apps/web/messages/lv.json` — Current Latvian translations
- `cms/apps/web/messages/en.json` — Current English translations

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add `dashboard.eventPanel` keys
- `cms/apps/web/messages/en.json` — Add `dashboard.eventPanel` keys
- `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` — Complete rewrite
- `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — Add `onEventDeleted` callback

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping:
- `text-gray-*` → `text-foreground-muted`
- `bg-blue-*` → `bg-interactive`
- `bg-red-*` → `bg-destructive`
- `text-white` on colored bg → `text-interactive-foreground` or `text-destructive-foreground`
- `border-gray-*` → `border-border`
- `bg-gray-*` → `bg-surface`
Check `cms/packages/ui/src/tokens.css` for available tokens.

## React 19 Coding Rules

- **No `setState` in `useEffect`** — use `key` prop to remount with new state
- **No component definitions inside components** — extract ALL sub-components to module scope
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Hook ordering**: `useMemo`/`useCallback` MUST come AFTER their dependencies from `useState`

## TypeScript Security Rules

- **Role gating**: Use `SCHEDULE_ROLES.includes(userRole)` pattern from existing code
- **Event ID**: Already a string on CalendarEvent, convert with `Number(event.id)` for API calls

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Add Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add the `eventPanel` object inside the existing `dashboard` object. Insert it AFTER the `driverActions` block (before the closing `}` of `dashboard`). Exact keys and values are specified in the i18n section above.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 2: Add English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add the matching `eventPanel` object inside the existing `dashboard` object, same position as Task 1. Exact keys and values are in the i18n section above. Ensure key structure matches lv.json exactly.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 3: Rewrite EventGoalPanel Component
**File:** `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` (modify)
**Action:** UPDATE — complete rewrite of the component

This is the main task. Rewrite the component with these capabilities:

#### 3a. Props interface change

Update the props interface:
```typescript
interface EventGoalPanelProps {
  event: CalendarEvent | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEventUpdated: () => void;    // renamed from onGoalsUpdated
  onEventDeleted: () => void;    // NEW — called after successful delete
}
```

#### 3b. Internal state

The component uses a `step` state to manage dialog content:
```typescript
type PanelStep = "view" | "edit" | "delete-confirm";
```

State variables:
- `step` — current dialog step (`"view"` default)
- `isSaving` — loading state for save/delete operations
- `goalItems` — local copy of goal items for checkbox toggling (existing pattern)
- `editTitle` — edited title string
- `editDescription` — edited description string
- `editStartDate` — edited start date string (YYYY-MM-DD format)
- `editStartTime` — edited start time string (HH:MM format)
- `editEndDate` — edited end date string
- `editEndTime` — edited end time string
- `editPriority` — edited priority value
- `editCategory` — edited category value
- `newGoalText` — text for adding new goal items

When `step` transitions to `"edit"`, initialize edit fields from the current event. Use a `useCallback` for this initialization so it can be called explicitly (NOT in a useEffect — React 19 anti-pattern).

IMPORTANT: When the dialog opens with a new event (tracked by `key` prop from parent), reset step to `"view"`.

#### 3c. Role-based access

Import `useSession` and check role:
```typescript
const { data: session } = useSession();
const userRole: string = (session?.user?.role as string) ?? "";
const canEdit = ["admin", "editor", "dispatcher"].includes(userRole);
```

Only show Edit/Delete buttons when `canEdit` is true.

#### 3d. View mode layout

```
┌─────────────────────────────────────────┐
│ Dialog Header: "Notikuma detaļas"       │
│ DialogDescription: event.title (sr-only)│
├─────────────────────────────────────────┤
│ Event title (bold, with subtype color)  │
│ Date · Start time – End time            │
│ Description (if present, muted text)    │
│ Priority badge + Category badge         │
├─ Separator ─────────────────────────────┤
│ GOAL SECTION (if goals exist):          │
│   "Mērķu progress" header + fraction   │
│   Progress bar                          │
│   Checkbox list (toggleable)            │
│   [+ Add goal input] (if canEdit)       │
│   Transport/vehicle badges              │
│                                         │
│ NO GOALS SECTION (if no goals):         │
│   "Nav mērķu" text                     │
│   [Pievienot mērķus] button (if canEdit)│
├─ Separator ─────────────────────────────┤
│ QUICK ACTIONS (only if driver event     │
│ AND canEdit):                           │
│   "Ātrās darbības" header              │
│   Assign Shift, Mark Leave,            │
│   Mark Sick, Schedule Training cards    │
├─────────────────────────────────────────┤
│ Footer:                                 │
│   [Rediģēt] [Dzēst]  (if canEdit)     │
│   [Aizvērt]           (if !canEdit)     │
│   [Saglabāt] (if goals modified)        │
└─────────────────────────────────────────┘
```

For the goal checklist in view mode: reuse the existing `GoalItemRow` pattern (module-scope component with `Checkbox`). When a goal is toggled, track changes locally. Show a "Save" button when goal state differs from original.

For the "Add Goal" input: show an inline `Input` + `Button` row (same pattern as `GoalsForm` component). When a goal is added, append to local `goalItems` state and mark the goals as dirty (show save button).

For "Add Goals" (when no goals): clicking the button sets `goalItems` to an empty array and reveals the add-goal input field. This allows adding the first goal without switching to edit mode.

#### 3e. Edit mode layout

When user clicks "Edit", transition to `step = "edit"` and initialize edit fields:

```
┌─────────────────────────────────────────┐
│ Dialog Header: "Notikuma detaļas"       │
├─────────────────────────────────────────┤
│ Title: [Input field]                    │
│ Description: [Textarea]                 │
│ Start: [date input] [time input]        │
│ End:   [date input] [time input]        │
│ Priority: [Select: high/medium/low]     │
│ Category: [Select: 4 categories]        │
├─────────────────────────────────────────┤
│ Footer: [Atcelt] [Saglabāt]           │
└─────────────────────────────────────────┘
```

Field initialization from `CalendarEvent`:
- `editTitle` = `event.title`
- `editDescription` = `event.description ?? ""`
- `editStartDate` = format `event.start` as `YYYY-MM-DD`
- `editStartTime` = format `event.start` as `HH:MM`
- `editEndDate` = format `event.end` as `YYYY-MM-DD`
- `editEndTime` = format `event.end` as `HH:MM`
- `editPriority` = `event.priority`
- `editCategory` = `event.category`

Save handler: build `EventUpdate` object, call `updateEvent(Number(event.id), update)`, toast success/error, call `onEventUpdated()`, return to view mode.

Priority select values: `high`, `medium`, `low` with labels from `dashboard.priority.high/medium/low`.
Category select values: `maintenance`, `route-change`, `driver-shift`, `service-alert` with labels from `dashboard.eventPanel.categories.*`.

Cancel button: return to `step = "view"`.

#### 3f. Delete confirmation layout

When user clicks "Delete", transition to `step = "delete-confirm"`:

```
┌─────────────────────────────────────────┐
│ Dialog Header: "Dzēst notikumu"         │
├─────────────────────────────────────────┤
│ Event title (bold)                      │
│ Date and time                           │
│                                         │
│ "Vai tiešām vēlaties dzēst?"           │
│ "Šī darbība ir neatgriezeniska."       │
├─────────────────────────────────────────┤
│ Footer: [Atcelt] [Dzēst (destructive)] │
└─────────────────────────────────────────┘
```

Delete handler: call `deleteEvent(Number(event.id))`, toast success/error, call `onEventDeleted()`, close the dialog.

The delete confirm button uses `variant="destructive"` and shows "Dzēš..." while loading.
Cancel returns to `step = "view"`.

#### 3g. Quick actions section (driver events only)

Show quick actions section when `event.driver_id` is present AND `canEdit` is true.

Reuse the `ActionCard` pattern from `driver-actions-panel.tsx` (extract it to module scope or just define it in this file — it's already at module scope in `driver-actions-panel.tsx`).

Quick actions:
1. **Assign Shift** — Create a morning shift event for the driver on the same date
2. **Mark Leave** — Create an all-day leave event
3. **Mark Sick** — Create an all-day sick event
4. **Schedule Training** — Create a 2-hour training event

Each action calls `createEvent()` with the same pattern used in `driver-actions-panel.tsx`:
- Extract driver name from event title: `event.title.split(" - ")[0]`
- Use `event.start` for the target date
- Use `event.driver_id` for the driver_id field
- After creation: toast success, call `onEventUpdated()` to refresh calendar

Import icons: `Clock`, `CalendarOff`, `Thermometer`, `GraduationCap` from `lucide-react`.

Use translations from `dashboard.dropAction.*` for the action card labels (already exist).

#### 3h. Module-scope helper components

Extract ALL sub-components to module scope (React 19 rule). These components should be defined OUTSIDE `EventGoalPanel`:

1. `GoalItemRow` — checkbox + text (already exists in current file, keep it)
2. `ActionCard` — icon + title + description button card (copy pattern from driver-actions-panel.tsx)

#### 3i. Imports needed

```typescript
import { useState, useCallback, useMemo } from "react";
import { useTranslations, useLocale } from "next-intl";
import { useSession } from "next-auth/react";
import { toast } from "sonner";
import { Pencil, Trash2, Plus, Clock, CalendarOff, Thermometer, GraduationCap } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/dashboard";
import type { EventGoals, GoalItem, EventUpdate, EventCategory, EventPriority, EventCreate } from "@/types/event";
import { updateEvent, deleteEvent, createEvent } from "@/lib/events-sdk";
import type { GoalStatus } from "./goal-progress-badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
```

#### 3j. Helper functions needed at module scope

```typescript
function formatTime(date: Date): string {
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
}

function formatDateISO(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatTimeHHMM(date: Date): string {
  const h = String(date.getHours()).padStart(2, "0");
  const m = String(date.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

function buildISO(dateStr: string, timeStr: string): string {
  const [y, mo, d] = dateStr.split("-").map(Number);
  const [h, mi] = timeStr.split(":").map(Number);
  const dt = new Date(y, mo - 1, d, h, mi, 0, 0);
  return dt.toISOString();
}

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
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 4: Update DashboardContent to Handle Event Deletion
**File:** `cms/apps/web/src/components/dashboard/dashboard-content.tsx` (modify)
**Action:** UPDATE

Changes needed:

1. Add `handleEventDeleted` callback (same as `handleGoalsUpdated` — refetch calendar):
```typescript
const handleEventDeleted = useCallback(() => {
  setGoalPanelOpen(false);
  setSelectedEvent(null);
  void calendarRefetchRef.current?.();
}, []);
```

2. Update `EventGoalPanel` usage to pass the new props:
```tsx
<EventGoalPanel
  key={selectedEvent?.id ?? "closed"}
  event={selectedEvent}
  open={goalPanelOpen}
  onOpenChange={setGoalPanelOpen}
  onEventUpdated={handleGoalsUpdated}
  onEventDeleted={handleEventDeleted}
/>
```

Note: rename the prop from `onGoalsUpdated` to `onEventUpdated` in this file. The existing `handleGoalsUpdated` callback does the right thing (refetches calendar), so reuse it.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 5: Update DriverActionsPanel Event Click Bridge
**File:** `cms/apps/web/src/components/dashboard/driver-actions-panel.tsx` (modify — optional, only if needed)
**Action:** UPDATE

Check if the `onEventClick` callback from DriverActionsPanel still correctly opens the EventGoalPanel. The DriverActionsPanel calls `onEventClick(event)` which in dashboard-content sets `selectedEvent` and opens `goalPanelOpen`. This flow should still work since EventGoalPanel's `event` and `open` props haven't changed. Verify no compile errors.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes

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

- [ ] Clicking an event in week view opens the enhanced detail panel
- [ ] View mode shows: title, date/time, priority badge, category badge, description
- [ ] Goal checklist is toggleable with save button appearing when modified
- [ ] "Add Goals" button appears when no goals exist and user has edit role
- [ ] Edit button transitions to inline edit mode with all fields editable
- [ ] Save in edit mode calls updateEvent API and refreshes calendar
- [ ] Delete button shows confirmation step within the dialog
- [ ] Delete confirmation calls deleteEvent API, closes dialog, refreshes calendar
- [ ] Quick actions appear for driver events (events with driver_id) when user has edit role
- [ ] Quick actions create events and refresh calendar
- [ ] Viewer role sees read-only view (no edit/delete/quick actions)
- [ ] i18n keys present in both lv.json and en.json
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] All interactive elements have cursor-pointer
- [ ] Transitions on hover/state changes (200ms)

## Acceptance Criteria

This feature is complete when:
- [ ] EventGoalPanel shows rich event details in view mode
- [ ] Inline editing works for all event fields (title, times, priority, category, description)
- [ ] Events can be deleted with confirmation
- [ ] Goals can be added to events without goals
- [ ] Goals can be toggled and saved
- [ ] Quick actions work for driver events
- [ ] Role-based access control: viewers see read-only, editors can edit/delete
- [ ] Both lv and en translations complete
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing dashboard functionality
- [ ] Ready for `/commit`
