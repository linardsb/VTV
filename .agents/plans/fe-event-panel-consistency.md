# Plan: Event Panel Quick Actions Consistency Fix

## Feature Metadata
**Feature Type**: Enhancement / Bug Fix
**Estimated Complexity**: Low
**Route**: N/A — affects existing dashboard calendar panel component
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor (canEdit roles)

## Problem Description

The EventGoalPanel component shows inconsistent UI for driver events in the dashboard calendar. When clicking a driver event:

- **Correct behavior** (e.g., Uldis Grinbergs D-012): Shows full panel with event details, goals section with progress bar/checklist, add-goal input, Quick Actions section ("Ātrās darbības") with 4 action cards (assign shift, mark leave, mark sick, schedule training), and Edit/Delete buttons.

- **Incorrect behavior** (e.g., Artūrs Feldmanis D-011): Shows event details and goals section, but **missing Quick Actions section entirely**, even though the event has category "Vadītāja maiņa" (driver-shift).

### Root Cause

The Quick Actions section renders conditionally based on `isDriverEvent`:

```tsx
// Line 260 of event-goal-panel.tsx
const isDriverEvent = Boolean(event?.driver_id);

// Line 649
{isDriverEvent && canEdit && (
  // ... Quick Actions ...
)}
```

This condition only checks `driver_id` field. Some driver-shift events were created without a `driver_id` foreign key, so they fail this check even though they are clearly driver events by category.

Additionally, all 4 quick action handlers early-return when `driver_id` is null:
```tsx
const handleAssignShift = useCallback(() => {
    if (!event?.driver_id) return;  // silently exits
    // ...
}, [event, tDrop, handleQuickAction]);
```

### Fix Strategy (Frontend + Backend Note)

**Frontend (this plan):**
1. Broaden `isDriverEvent` to: `Boolean(event?.driver_id) || event?.category === "driver-shift"`
2. Update 4 quick action handlers to work without `driver_id` — create events with `driver_id` when available, omit it when not (field is optional in `EventCreate`)
3. Extract driver name from title pattern `"DriverName - EventType"` regardless of `driver_id` presence

**Backend (follow-up, not in this plan):**
- Ensure all driver-shift category events have `driver_id` set going forward
- Consider a data migration to backfill `driver_id` on existing driver-shift events

## Design System

### Master Rules (from MASTER.md)
- All interactive elements: `transition: all 200ms ease`, `cursor: pointer`
- Spacing via semantic tokens: `--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight`
- No hardcoded colors — semantic tokens only

### Tokens Used
- No new tokens needed — this fix only changes conditional logic, not styling

## Components Needed

### Existing (no changes)
- `ActionCard` — module-scope sub-component already defined in event-goal-panel.tsx
- All existing UI components (Dialog, Button, Badge, etc.) remain unchanged

### New Components
- None

### shadcn/ui to Install
- None

## i18n Keys

No new i18n keys needed. All existing translation keys are already in place:
- `dashboard.dropAction.assignShift` / `assignShiftDesc`
- `dashboard.dropAction.markLeave` / `markLeaveDesc`
- `dashboard.dropAction.markSick` / `markSickDesc`
- `dashboard.dropAction.scheduleTraining` / `scheduleTrainingDesc`
- `dashboard.eventPanel.quickActions`

## Data Fetching

No changes to data fetching. The `useCalendarEvents` hook already maps `driver_id` from the API response into `CalendarEvent`.

## Relevant Files

The executing agent MUST read these files before starting implementation:

### Files to Modify
- `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` — Main fix: broaden isDriverEvent, update handlers

### Context Files (read-only reference)
- `cms/apps/web/src/types/dashboard.ts` — CalendarEvent type definition (has `driver_id?: number | null`)
- `cms/apps/web/src/types/event.ts` — EventCreate type (confirms `driver_id` is optional)

## Design System Color Rules

No color changes in this fix. The executor MUST NOT introduce any primitive Tailwind color classes. All existing semantic classes remain unchanged.

## React 19 Coding Rules

The executor MUST follow these rules:
- **No component definitions inside components** — ActionCard and GoalItemRow are already at module scope (correct)
- **No `setState` in `useEffect`** — no effects are being added
- All `useCallback` hooks must have complete dependency arrays

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Broaden isDriverEvent condition
**File:** `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` (modify)
**Action:** UPDATE

Find line 260:
```tsx
const isDriverEvent = Boolean(event?.driver_id);
```

Replace with:
```tsx
const isDriverEvent = Boolean(event?.driver_id) || event?.category === "driver-shift";
```

This ensures Quick Actions render for:
- Events with `driver_id` set (any category)
- Events with category `"driver-shift"` (even if `driver_id` is null)

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 2: Update handleAssignShift to work without driver_id
**File:** `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` (modify)
**Action:** UPDATE

Find the `handleAssignShift` callback (around line 398):
```tsx
const handleAssignShift = useCallback(() => {
    if (!event?.driver_id) return;
    const driverName = event.title.split(" - ")[0];
    const times = SHIFT_TIMES.morning;
    void handleQuickAction({
      title: `${driverName} - ${tDrop("shiftMorning")}`,
      start_datetime: buildDatetime(event.start, times.start, false),
      end_datetime: buildDatetime(event.start, times.end, times.nextDay),
      priority: "medium",
      category: "driver-shift",
      driver_id: event.driver_id,
    });
  }, [event, tDrop, handleQuickAction]);
```

Replace with:
```tsx
const handleAssignShift = useCallback(() => {
    if (!event) return;
    const driverName = event.title.split(" - ")[0];
    const times = SHIFT_TIMES.morning;
    void handleQuickAction({
      title: `${driverName} - ${tDrop("shiftMorning")}`,
      start_datetime: buildDatetime(event.start, times.start, false),
      end_datetime: buildDatetime(event.start, times.end, times.nextDay),
      priority: "medium",
      category: "driver-shift",
      ...(event.driver_id ? { driver_id: event.driver_id } : {}),
    });
  }, [event, tDrop, handleQuickAction]);
```

Key changes:
- Guard changed from `if (!event?.driver_id) return` to `if (!event) return`
- `driver_id` is now conditionally spread — included when available, omitted when null
- Driver name extraction from title still works regardless of `driver_id`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 3: Update handleMarkLeave to work without driver_id
**File:** `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` (modify)
**Action:** UPDATE

Find the `handleMarkLeave` callback (around line 412):
```tsx
const handleMarkLeave = useCallback(() => {
    if (!event?.driver_id) return;
    const driverName = event.title.split(" - ")[0];
    void handleQuickAction({
      title: tDrop("eventTitleLeave", { name: driverName }),
      start_datetime: buildDatetime(event.start, "00:00", false),
      end_datetime: buildDatetime(event.start, "23:59", false),
      priority: "low",
      category: "driver-shift",
      driver_id: event.driver_id,
    });
  }, [event, tDrop, handleQuickAction]);
```

Replace with:
```tsx
const handleMarkLeave = useCallback(() => {
    if (!event) return;
    const driverName = event.title.split(" - ")[0];
    void handleQuickAction({
      title: tDrop("eventTitleLeave", { name: driverName }),
      start_datetime: buildDatetime(event.start, "00:00", false),
      end_datetime: buildDatetime(event.start, "23:59", false),
      priority: "low",
      category: "driver-shift",
      ...(event.driver_id ? { driver_id: event.driver_id } : {}),
    });
  }, [event, tDrop, handleQuickAction]);
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 4: Update handleMarkSick to work without driver_id
**File:** `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` (modify)
**Action:** UPDATE

Find the `handleMarkSick` callback (around line 425):
```tsx
const handleMarkSick = useCallback(() => {
    if (!event?.driver_id) return;
    const driverName = event.title.split(" - ")[0];
    void handleQuickAction({
      title: tDrop("eventTitleSick", { name: driverName }),
      start_datetime: buildDatetime(event.start, "00:00", false),
      end_datetime: buildDatetime(event.start, "23:59", false),
      priority: "high",
      category: "driver-shift",
      driver_id: event.driver_id,
    });
  }, [event, tDrop, handleQuickAction]);
```

Replace with:
```tsx
const handleMarkSick = useCallback(() => {
    if (!event) return;
    const driverName = event.title.split(" - ")[0];
    void handleQuickAction({
      title: tDrop("eventTitleSick", { name: driverName }),
      start_datetime: buildDatetime(event.start, "00:00", false),
      end_datetime: buildDatetime(event.start, "23:59", false),
      priority: "high",
      category: "driver-shift",
      ...(event.driver_id ? { driver_id: event.driver_id } : {}),
    });
  }, [event, tDrop, handleQuickAction]);
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 5: Update handleScheduleTraining to work without driver_id
**File:** `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` (modify)
**Action:** UPDATE

Find the `handleScheduleTraining` callback (around line 438):
```tsx
const handleScheduleTraining = useCallback(() => {
    if (!event?.driver_id) return;
    const driverName = event.title.split(" - ")[0];
    void handleQuickAction({
      title: tDrop("eventTitleTraining", { name: driverName }),
      start_datetime: buildDatetime(event.start, "09:00", false),
      end_datetime: buildDatetime(event.start, "11:00", false),
      priority: "medium",
      category: "maintenance",
      driver_id: event.driver_id,
    });
  }, [event, tDrop, handleQuickAction]);
```

Replace with:
```tsx
const handleScheduleTraining = useCallback(() => {
    if (!event) return;
    const driverName = event.title.split(" - ")[0];
    void handleQuickAction({
      title: tDrop("eventTitleTraining", { name: driverName }),
      start_datetime: buildDatetime(event.start, "09:00", false),
      end_datetime: buildDatetime(event.start, "11:00", false),
      priority: "medium",
      category: "maintenance",
      ...(event.driver_id ? { driver_id: event.driver_id } : {}),
    });
  }, [event, tDrop, handleQuickAction]);
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

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

- [ ] Quick Actions section appears for ALL driver-shift category events (with or without driver_id)
- [ ] Quick Actions section appears for events with driver_id (any category)
- [ ] Quick action buttons create events successfully when driver_id is present
- [ ] Quick action buttons create events successfully when driver_id is null (omit driver_id from payload)
- [ ] Events with goals still show progress bar and checklist correctly
- [ ] Events without goals still show "Nav mērķu" fallback correctly
- [ ] Edit and Delete buttons work for all event types
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] No TypeScript errors, no lint warnings

## Acceptance Criteria

This feature is complete when:
- [ ] All driver-shift events show Quick Actions consistently (like Uldis Grinbergs panel)
- [ ] Quick Actions work correctly regardless of driver_id presence
- [ ] All 3 validation levels pass (type-check, lint, build)
- [ ] No regressions in existing event panel functionality
- [ ] Ready for `/commit`

## Backend Follow-Up (Not In This Plan)

After frontend fix is deployed, create a backend task to:
1. Add validation in `EventService.create_event()` — when category is "driver-shift", warn if `driver_id` is null
2. Consider a data migration script to backfill `driver_id` on existing driver-shift events using driver name lookup from event titles
3. Update the driver actions panel (drag-and-drop) to always include `driver_id` when creating events
