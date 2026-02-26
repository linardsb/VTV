# Plan Stub: Goal Dialog UX + Two-Step Flow (Session 3 of 4)

**Status:** STUB — flesh out with `/fe-planning` before executing
**Depends on:** Session 2 (backend goals model) completed + SDK regenerated
**Command to flesh out:** `/fe-planning redesign DriverDropDialog with two-step flow: pick action then add goals with route assignment, transport type, and driver data pre-fill`

## Scope

Redesign the `DriverDropDialog` to support a two-step flow: first pick an action (assign shift, training), then add goals (route assignment, transport type, performance notes) before saving. Pre-fill from driver data. Only shifts and training support goals.

## Decisions Made (from Q&A)

| Question | Answer |
|----------|--------|
| UX flow | A) Two-step: pick action → add goals before saving |
| Which actions get goals | Shifts and training only (not leave, sick, custom) |
| Route list source | B) Filtered to driver's `qualified_route_ids` |
| Transport assignment | C) Pick type + optional vehicle number |
| Checklist items | C) Pre-filled templates + custom items |
| Driver data sync | C) Both — pre-fill dialog AND enhance roster sidebar |
| Who can schedule | Admin, editor, dispatcher |

## Deliverables

### 1. Two-Step DriverDropDialog Redesign
**File:** `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx`

Current flow: Pick action → immediately create event
New flow:
1. **Step 1 — Action Picker** (existing 5 cards): Pick action type
2. **Step 2 — Goals Form** (NEW, only for shift + training):
   - Route assignment dropdown (filtered to `qualified_route_ids`)
   - Transport type selector (bus/trolleybus/tram)
   - Optional vehicle number input
   - Performance notes textarea
   - Goal checklist builder (add/remove items)
   - Pre-filled shift time from driver's `default_shift`
3. **Save** — creates event with goals JSON

For leave, sick, custom: keep existing behavior (no step 2).

### 2. Route Assignment Component
**File:** `cms/apps/web/src/components/dashboard/route-assignment-select.tsx` (new)

- Fetch routes from `/api/v1/schedules/routes`
- Filter to driver's `qualified_route_ids` (parse comma-separated string)
- Show route short_name + long_name in dropdown
- Uses existing `Select` shadcn component

### 3. Driver Roster Enhancements
**File:** `cms/apps/web/src/components/dashboard/driver-roster.tsx`

Add to each driver card:
- Qualified routes count or list (from `qualified_route_ids`)
- License expiry warning (amber if < 30 days, red if expired)
- Medical cert expiry warning

### 4. i18n Keys (new)
Both `lv.json` and `en.json` need keys for:
- `dashboard.goals.title` — "Sesijas mērķi" / "Session Goals"
- `dashboard.goals.route` — "Maršruts" / "Route"
- `dashboard.goals.transportType` — "Transporta veids" / "Transport Type"
- `dashboard.goals.vehicle` — "Transportlīdzeklis" / "Vehicle"
- `dashboard.goals.notes` — "Piezīmes" / "Notes"
- `dashboard.goals.addItem` — "Pievienot mērķi" / "Add Goal"
- `dashboard.goals.removeItem` — "Noņemt" / "Remove"
- `dashboard.goals.placeholder` — "Ievadiet mērķi..." / "Enter a goal..."
- `dashboard.goals.back` — "Atpakaļ" / "Back"
- `dashboard.goals.notesPlaceholder` — "Veiktspējas piezīmes..." / "Performance notes..."
- `dashboard.roster.qualifiedRoutes` — "Kvalificētie maršruti" / "Qualified Routes"
- `dashboard.roster.licenseWarning` — "Licence drīz beigsies" / "License expiring soon"
- `dashboard.roster.licenseExpired` — "Licence beigusies" / "License expired"
- Transport type labels for bus, trolleybus, tram

### 5. Type Updates
**File:** `cms/apps/web/src/types/event.ts`

Add `GoalItem` and `EventGoals` TypeScript types matching the backend schema:
```ts
interface GoalItem {
  text: string;
  completed: boolean;
  type: "route" | "training" | "note" | "checklist";
}

interface EventGoals {
  items: GoalItem[];
  route_id?: number | null;
  transport_type?: string | null;
  vehicle_id?: string | null;
}
```

Update `EventCreate` to include `goals?: EventGoals | null`.

## Files Likely Modified

```
cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx  — Two-step flow redesign
cms/apps/web/src/components/dashboard/driver-roster.tsx        — Roster enhancements
cms/apps/web/src/components/dashboard/route-assignment-select.tsx — NEW component
cms/apps/web/src/types/event.ts                                — Add goals types
cms/apps/web/messages/lv.json                                  — New i18n keys
cms/apps/web/messages/en.json                                  — New i18n keys
```

## Dependencies

- Session 2 must be complete (backend `goals` field exists)
- SDK must be regenerated (`pnpm --filter @vtv/sdk refresh`)
- Routes API must be available for the route dropdown

## Validation

```bash
cd cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint && pnpm --filter @vtv/web build
```

## Notes for `/fe-planning` Agent

- Read the completed Session 2 backend schemas to match types exactly
- Follow Dialog convention: `sm:max-w-[32rem]` for forms (may need `sm:max-w-[36rem]` for the goals step)
- Use semantic tokens only — no hardcoded colors
- Pre-filled checklist templates: define 2-3 default items per action type (shift gets "Pre-trip inspection", "Route completion report"; training gets "Complete training module", "Pass assessment")
- The route dropdown needs to fetch routes — use `authFetch` in a `useEffect` or a small SWR hook
- `qualified_route_ids` is stored as a comma-separated string in the driver model — parse it to filter the route list
