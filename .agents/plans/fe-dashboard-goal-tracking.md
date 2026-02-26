# Plan Stub: Calendar Indicators + Goal Tracking (Session 4 of 4 — V2)

**Status:** STUB — flesh out with `/fe-planning` before executing
**Depends on:** Session 3 (goal dialog) completed
**Priority:** Nice-to-have / V2
**Command to flesh out:** `/fe-planning add calendar goal indicators with mini cards showing driver name route and completion percentage plus goal completion UI on calendar click and driver page`

## Scope

Add visual goal tracking to the dashboard calendar — mini cards on day cells showing assigned drivers with completion status, click-to-complete goal items, and goal status on the drivers page. This is the "polish" session that makes goals visible and actionable across the entire UI.

## Decisions Made (from Q&A)

| Question | Answer |
|----------|--------|
| Calendar indicator style | C) Mini card: driver name + route + completion % + color status |
| Color coding | Green (all done), amber (in progress), gray (not started) |
| Multiple drivers per day | Yes — stack mini cards vertically |
| Where to mark goals done | D) All — calendar click, dashboard panel, driver page |
| Goal trackable/completable | Yes — each item has completed boolean |

## Deliverables

### 1. Calendar Day Cell Mini Cards
**Files:** `month-view.tsx`, `week-view.tsx`, `three-month-view.tsx`

For events that have `goals` data, render a mini card instead of (or alongside) the current dot+title:
- Driver name (from event title — already contains "{name} - {shift}")
- Route number (from `goals.route_id` — resolve to route short_name)
- Completion: `{completed}/{total}` or small progress bar
- Status dot: green/amber/gray based on completion ratio

For three-month view (tiny cells): just show a colored dot (green/amber/gray) instead of full card.

### 2. Event Detail / Goal Completion Panel
**File:** `cms/apps/web/src/components/dashboard/event-goal-panel.tsx` (NEW)

Click an event on the calendar → opens a panel/dialog showing:
- Event title and time
- Driver info (name, employee number, shift)
- Assigned route and transport type
- Goal checklist with checkboxes (click to toggle completion)
- Performance notes (editable)
- Save button to update via `PATCH /api/v1/events/{id}`

### 3. "Today's Goals" Dashboard Widget (optional)
**File:** `cms/apps/web/src/components/dashboard/todays-goals.tsx` (NEW)

Compact panel showing all today's driver assignments with goal progress:
- List of drivers scheduled today
- Per-driver: route, shift, goals progress bar
- Quick-toggle checkboxes for common goals
- Could live in the metrics area or as a collapsible section

### 4. Driver Profile Goal History
**Files:** `cms/apps/web/src/components/drivers/driver-detail.tsx`

Add a "Recent Goals" section to the driver detail dialog:
- Last 10 events with goals for this driver
- Per-event: date, route, goal completion status
- Link to full event detail

### 5. i18n Keys (new)
Both `lv.json` and `en.json` need keys for:
- `dashboard.goals.completed` — "Pabeigts" / "Completed"
- `dashboard.goals.inProgress` — "Procesā" / "In Progress"
- `dashboard.goals.notStarted` — "Nav sākts" / "Not Started"
- `dashboard.goals.progress` — "{done} no {total}" / "{done} of {total}"
- `dashboard.goals.todayTitle` — "Šodienas mērķi" / "Today's Goals"
- `dashboard.goals.noGoals` — "Nav mērķu" / "No goals set"
- `dashboard.goals.markDone` — "Atzīmēt kā izpildītu" / "Mark as done"
- `dashboard.goals.recentHistory` — "Nesenie mērķi" / "Recent Goals"
- `dashboard.goals.eventDetail` — "Notikuma detaļas" / "Event Details"
- `dashboard.goals.updateSuccess` — "Mērķi atjaunināti" / "Goals updated"
- `dashboard.goals.updateError` — "Neizdevās atjaunināt" / "Failed to update"

### 6. CalendarEvent Type Extension
**File:** `cms/apps/web/src/types/dashboard.ts`

Extend `CalendarEvent` to include goals:
```ts
export interface CalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  priority: EventPriority;
  category: EventCategory;
  description?: string;
  goals?: EventGoals | null;  // NEW — from Session 2/3 types
}
```

Update `useCalendarEvents` hook to map goals from API response.

## Files Likely Modified

```
# Calendar views — add mini cards
cms/apps/web/src/components/dashboard/month-view.tsx
cms/apps/web/src/components/dashboard/week-view.tsx
cms/apps/web/src/components/dashboard/three-month-view.tsx

# New components
cms/apps/web/src/components/dashboard/event-goal-panel.tsx      — NEW: click-to-complete
cms/apps/web/src/components/dashboard/todays-goals.tsx          — NEW: dashboard widget
cms/apps/web/src/components/dashboard/goal-progress-badge.tsx   — NEW: reusable progress indicator

# Existing component updates
cms/apps/web/src/components/dashboard/calendar-event.tsx        — Render goals indicator
cms/apps/web/src/components/dashboard/calendar-grid.tsx         — Handle event click → goal panel
cms/apps/web/src/components/drivers/driver-detail.tsx           — Add recent goals section

# Types and data
cms/apps/web/src/types/dashboard.ts                            — Extend CalendarEvent
cms/apps/web/src/hooks/use-calendar-events.ts                  — Map goals from API

# i18n
cms/apps/web/messages/lv.json
cms/apps/web/messages/en.json
```

## Dependencies

- Session 3 must be complete (goals are being created with events)
- Backend `goals` field exists and is returned in event responses
- SDK types include `EventGoals`

## Design Considerations

### Goal Status Colors (semantic tokens)
- **Not started** (0%): `text-foreground-muted` + `bg-foreground/10`
- **In progress** (1-99%): `text-status-delayed` + `bg-status-delayed/15`
- **Completed** (100%): `text-status-ontime` + `bg-status-ontime/15`

### Mini Card Layout (month/week view)
```
┌──────────────────────────┐
│ J. Bērziņš  Route 22  2/5│
│ ████████░░░░  amber      │
└──────────────────────────┘
```

### Three-Month View (compact)
Just a colored dot next to the day number — green/amber/gray.

## Validation

```bash
cd cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint && pnpm --filter @vtv/web build
```

## Notes for `/fe-planning` Agent

- This is the largest session — consider splitting into sub-tasks if needed
- Calendar mini cards must not break existing event rendering — layer goals on top
- The "Today's Goals" widget is optional if dashboard space is tight
- Use `Checkbox` from shadcn for goal completion toggles
- Progress badge could be a shared component used in calendar + driver detail + today's goals
- Test with events that have NO goals (backward compat) — they should render exactly as before
- Performance: goal completion updates should use optimistic UI (update local state immediately, revert on API error)
