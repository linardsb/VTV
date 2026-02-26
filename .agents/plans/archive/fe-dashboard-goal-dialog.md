# Plan: Dashboard Goal Dialog — Two-Step Driver Scheduling Flow (Session 3 of 4)

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: High
**Route**: `/[locale]/` (dashboard — existing page)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor (scheduling); viewer (read-only, no drag-and-drop)
**Session**: 3 of 4 (depends on Session 2 backend goals model — completed)

## Feature Description

Redesign the `DriverDropDialog` to support a two-step flow when scheduling driver shifts or training sessions. Currently, clicking an action card immediately creates a calendar event. The new flow adds a second step for shift and training actions where dispatchers can attach structured goals: route assignment, transport type, vehicle number, performance notes, and a checklist of goal items.

The two-step flow applies only to "Assign Shift" and "Schedule Training" actions. Leave, sick, and custom events retain their existing single-step behavior. Pre-filled checklist templates provide default goals per action type (shift gets "Pre-trip inspection" + "Route completion report"; training gets "Complete training module" + "Pass assessment"). Routes are filtered to the driver's `qualified_route_ids` for the assignment dropdown.

Additionally, the driver roster sidebar cards are enhanced to display qualified route counts and license/medical certificate expiry warnings, giving dispatchers at-a-glance information about driver readiness before scheduling.

## Design System

### Master Rules (from MASTER.md)
- **Typography**: Lexend for headings, Source Sans 3 for body
- **Spacing**: Use compact dashboard-density tokens (`--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight`)
- **Buttons**: cursor:pointer on all clickable elements, 200ms transitions
- **Cards**: 12px radius, shadow-md, surface background
- **Focus**: 3px focus rings for accessibility
- **Anti-patterns**: No emojis as icons, no hardcoded colors, no layout-shifting hovers

### Page Override
- None — no override exists in `cms/design-system/vtv/pages/`. The dashboard follows MASTER.md rules directly.

### Tokens Used
- Surface: `bg-surface`, `bg-surface-raised`, `bg-card-bg`
- Borders: `border-border`, `border-border-subtle`, `border-card-border`
- Text: `text-foreground`, `text-foreground-muted`
- Interactive: `bg-interactive`, `text-interactive`, `bg-interactive/10`
- Status: `text-status-ontime`, `text-status-delayed`, `text-status-critical`, `bg-status-*/15`
- Transport: `bg-transport-bus`, `bg-transport-trolleybus`, `bg-transport-tram` (+ text- variants)
- Category: `bg-category-driver-shift`
- Spacing: `--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight`

## Components Needed

### Existing (shadcn/ui — already installed)
- `Dialog` / `DialogContent` / `DialogHeader` / `DialogTitle` / `DialogDescription` — two-step dialog container
- `Button` — back, save, add goal buttons
- `Input` — vehicle number, custom goal text input
- `Label` — form field labels
- `Select` / `SelectTrigger` / `SelectContent` / `SelectItem` / `SelectValue` — route assignment dropdown
- `ToggleGroup` / `ToggleGroupItem` — transport type selector (bus/trolleybus/tram)
- `Textarea` — performance notes
- `Badge` — roster card status badges, license warnings
- `ScrollArea` — roster scroll container (existing)
- `Skeleton` — loading states (existing)

### New shadcn/ui to Install
- None — all required components already installed

### Custom Components to Create
- `GoalsForm` at `cms/apps/web/src/components/dashboard/goals-form.tsx` — Step 2 goals form (route select, transport type, vehicle, checklist builder, notes)

## i18n Keys

### English (`en.json`)
Add under `dashboard.goals`:
```json
{
  "dashboard": {
    "goals": {
      "title": "Session Goals",
      "subtitle": "Set goals for {name} on {date}",
      "route": "Route Assignment",
      "routePlaceholder": "Select a route...",
      "routeNoQualified": "No qualified routes",
      "routeLoading": "Loading routes...",
      "transportType": "Transport Type",
      "vehicle": "Vehicle Number",
      "vehiclePlaceholder": "e.g. RS-1047",
      "notes": "Notes",
      "notesPlaceholder": "Performance notes...",
      "items": "Shift Goals",
      "itemsTraining": "Training Goals",
      "addItem": "Add Goal",
      "addItemPlaceholder": "Enter a goal...",
      "removeItem": "Remove",
      "back": "Back",
      "save": "Save",
      "saving": "Saving...",
      "bus": "Bus",
      "trolleybus": "Trolleybus",
      "tram": "Tram"
    },
    "roster": {
      "qualifiedRoutes": "{count, plural, one {{count} route} other {{count} routes}}",
      "licenseExpiring": "License expires {date}",
      "licenseExpired": "License expired",
      "medicalExpiring": "Medical cert expires {date}",
      "medicalExpired": "Medical cert expired"
    }
  }
}
```

### Latvian (`lv.json`)
Add under `dashboard.goals`:
```json
{
  "dashboard": {
    "goals": {
      "title": "Sesijas merki",
      "subtitle": "Iestatiet merkus {name} uz {date}",
      "route": "Marsruta pieskirsana",
      "routePlaceholder": "Izvelieties marsrutu...",
      "routeNoQualified": "Nav kvalificetu marsrutu",
      "routeLoading": "Ielade marsrutus...",
      "transportType": "Transporta veids",
      "vehicle": "Transportlidzekla numurs",
      "vehiclePlaceholder": "piem. RS-1047",
      "notes": "Piezimes",
      "notesPlaceholder": "Veiktspecjas piezimes...",
      "items": "Mainas merki",
      "itemsTraining": "Apmacibas merki",
      "addItem": "Pievienot merki",
      "addItemPlaceholder": "Ievadiet merki...",
      "removeItem": "Nonemt",
      "back": "Atpakal",
      "save": "Saglabat",
      "saving": "Saglaba...",
      "bus": "Autobuss",
      "trolleybus": "Trolejbuss",
      "tram": "Tramvajs"
    },
    "roster": {
      "qualifiedRoutes": "{count, plural, one {{count} marsruts} other {{count} marsruti}}",
      "licenseExpiring": "Licence beidzas {date}",
      "licenseExpired": "Licence beigusies",
      "medicalExpiring": "Mediciniskais sertifikats beidzas {date}",
      "medicalExpired": "Mediciniskais sertifikats beidzies"
    }
  }
}
```

**IMPORTANT for executor:** The i18n keys above use ASCII-safe transliterations. The executor MUST use proper Latvian diacritics when writing the actual values:
- `merki` → `mērķi`, `merkus` → `mērķus`
- `Marsruta` → `Maršruta`, `marsrutu` → `maršrutu`, `marsrutus` → `maršrutus`, `marsruts` → `maršruts`, `marsruti` → `maršruti`
- `pieskirsana` → `piešķiršana`
- `Izvelieties` → `Izvēlieties`
- `kvalificetu` → `kvalificētu`
- `Ielade` → `Ielādē`
- `Transportlidzekla` → `Transportlīdzekļa`
- `Piezimes` → `Piezīmes`, `piezimes` → `piezīmes`
- `Veiktspecjas` → `Veiktspējas`
- `Mainas` → `Maiņas`
- `Apmacibas` → `Apmācības`
- `Ievadiet` → `Ievadiet` (correct as-is)
- `Nonemt` → `Noņemt`
- `Atpakal` → `Atpakaļ`
- `Saglabat` → `Saglabāt`
- `Saglaba` → `Saglabā`
- `beidzas` → `beidzas` (correct as-is)
- `beigusies` → `beigusies` (correct as-is)
- `Mediciniskais sertifikats` → `Medicīniskais sertifikāts`
- `beidzies` → `beidzies` (correct as-is)
- `Sesijas` → `Sesijas` (correct as-is)
- `Iestatiet` → `Iestatiet` (correct as-is)

## Data Fetching

- **API endpoints used**:
  - `POST /api/v1/events/` — create event with goals (existing, now accepts `goals` field)
  - `GET /api/v1/schedules/routes?page_size=500` — fetch routes for dropdown
- **Server vs Client**: All client-side (dialog is a client component)
- **Loading states**: Skeleton for route dropdown while fetching
- **Route fetching**: Use `fetchRoutes` from `schedules-client.ts` inside `useEffect` in the goals form. Fetch when the goals form mounts (dialog enters step 2). Filter fetched routes by driver's `qualified_route_ids` (comma-separated string → array of numbers → filter `route.id`).
- **CRITICAL — Server/client boundary**: The goals form is a `'use client'` component. It uses `authFetch` (via `fetchRoutes` from `schedules-client.ts`) which handles dual-context internally. No server-only imports needed.

## RBAC Integration

- **No changes needed** — the dashboard page already enforces RBAC via middleware. The `canSchedule` check in `DashboardContent` already gates drag-and-drop to admin/editor/dispatcher roles.

## Sidebar Navigation

- **No changes needed** — this is an enhancement to the existing dashboard page, not a new page.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules
- `cms/apps/web/CLAUDE.md` — Frontend conventions, React 19 anti-patterns, SWR patterns

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` — Current dialog (being modified)
- `cms/apps/web/src/components/dashboard/driver-roster.tsx` — Current roster (being modified)
- `cms/apps/web/src/components/dashboard/dashboard-content.tsx` — Parent component (context for props)
- `cms/apps/web/src/lib/events-sdk.ts` — Events API wrapper (being modified)
- `cms/apps/web/src/lib/schedules-client.ts` — Routes API (used for route dropdown, `fetchRoutes` function)
- `cms/apps/web/src/types/event.ts` — Event types (being modified)
- `cms/apps/web/src/types/driver.ts` — Driver type (has `qualified_route_ids`, `license_expiry_date`, `medical_cert_expiry`)
- `cms/apps/web/src/types/route.ts` — Route type (has `id`, `route_short_name`, `route_long_name`)
- `app/events/schemas.py` — Backend schema (reference for type alignment: `GoalItem`, `EventGoals`, `TransportType`, `GoalItemType`)

### Files to Modify
- `cms/apps/web/src/types/event.ts` — Add GoalItem, EventGoals, TransportType, GoalItemType types; update EventCreate and OperationalEvent
- `cms/apps/web/src/lib/events-sdk.ts` — Add goals field to createEvent and updateEvent body mappings
- `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` — Two-step flow redesign
- `cms/apps/web/src/components/dashboard/driver-roster.tsx` — License/route info enhancements
- `cms/apps/web/messages/en.json` — English i18n keys
- `cms/apps/web/messages/lv.json` — Latvian i18n keys

### Files to Create
- `cms/apps/web/src/components/dashboard/goals-form.tsx` — Goals form component (step 2)

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

**Transport type colors** (for the ToggleGroup items):
- Bus: `bg-transport-bus text-interactive-foreground` when active
- Trolleybus: `bg-transport-trolleybus text-interactive-foreground` when active
- Tram: `bg-transport-tram text-interactive-foreground` when active

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first in the component body
- **No named Tailwind container sizes** — Use explicit rem values: `sm:max-w-[32rem]`, `sm:max-w-[36rem]`

## TypeScript Security Rules

- **Never use `as` casts on external data without runtime validation** — Validate route data from API before casting
- **Clear `.next` cache when module resolution errors persist** — `rm -rf cms/apps/web/.next`

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

---

### Task 0: Regenerate TypeScript SDK
**Action:** RUN

The backend Session 2 added the `goals` JSONB field to events. The SDK must be regenerated so the generated API functions accept the `goals` field in request bodies.

**Prerequisites:** Backend must be running on port 8123.

```bash
cd cms && pnpm --filter @vtv/sdk refresh
```

**Per-task validation:**
- Verify `EventGoals` type exists in `cms/packages/sdk/src/client/types.gen.ts`
- Verify `GoalItem` type exists in the generated types
- `pnpm --filter @vtv/web type-check` passes (no regressions from SDK update)

---

### Task 1: Update Event Types
**File:** `cms/apps/web/src/types/event.ts` (modify)
**Action:** UPDATE

Add goal-related types matching the backend `app/events/schemas.py`. Add BEFORE the existing `OperationalEvent` interface:

```typescript
export type TransportType = "bus" | "trolleybus" | "tram";
export type GoalItemType = "route" | "training" | "note" | "checklist";

export interface GoalItem {
  text: string;
  completed: boolean;
  item_type: GoalItemType;
}

export interface EventGoals {
  items: GoalItem[];
  route_id: number | null;
  transport_type: TransportType | null;
  vehicle_id: string | null;
}
```

Update `OperationalEvent` to include goals:
```typescript
export interface OperationalEvent {
  // ... existing fields ...
  goals: EventGoals | null;  // ADD after category
}
```

Update `EventCreate` to include goals:
```typescript
export interface EventCreate {
  // ... existing fields ...
  goals?: EventGoals | null;  // ADD after category
}
```

Update `EventUpdate` to include goals:
```typescript
export interface EventUpdate {
  // ... existing fields ...
  goals?: EventGoals | null;  // ADD after category
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: Update Events SDK Wrapper
**File:** `cms/apps/web/src/lib/events-sdk.ts` (modify)
**Action:** UPDATE

The `createEvent` function passes `eventData` directly as `body` — this already works since our `EventCreate` type now includes `goals` and the SDK body type also includes it after regeneration. No change needed for `createEvent`.

Update the `updateEvent` function to include `goals` in the explicit body mapping. Currently it maps each field individually. Add the goals field:

```typescript
export async function updateEvent(
  id: number,
  eventData: EventUpdate,
): Promise<OperationalEvent> {
  const { data, error, response } = await updateEventApiV1EventsEventIdPatch({
    path: { event_id: id },
    body: {
      title: eventData.title ?? null,
      description: eventData.description ?? null,
      start_datetime: eventData.start_datetime ?? null,
      end_datetime: eventData.end_datetime ?? null,
      priority: eventData.priority ?? null,
      category: eventData.category ?? null,
      goals: eventData.goals ?? null,  // ADD THIS LINE
    },
  });
  // ... rest unchanged
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 3: Add English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add `goals` key inside the existing `dashboard` object, after the `dropAction` block (after line ~156). Also add new keys to the existing `roster` block.

Add to `dashboard.goals`:
```json
"goals": {
  "title": "Session Goals",
  "subtitle": "Set goals for {name} on {date}",
  "route": "Route Assignment",
  "routePlaceholder": "Select a route...",
  "routeNoQualified": "No qualified routes",
  "routeLoading": "Loading routes...",
  "transportType": "Transport Type",
  "vehicle": "Vehicle Number",
  "vehiclePlaceholder": "e.g. RS-1047",
  "notes": "Notes",
  "notesPlaceholder": "Performance notes...",
  "items": "Shift Goals",
  "itemsTraining": "Training Goals",
  "addItem": "Add Goal",
  "addItemPlaceholder": "Enter a goal...",
  "removeItem": "Remove",
  "back": "Back",
  "save": "Save",
  "saving": "Saving...",
  "bus": "Bus",
  "trolleybus": "Trolleybus",
  "tram": "Tram"
}
```

Add to existing `dashboard.roster` (merge into existing object):
```json
"qualifiedRoutes": "{count, plural, one {{count} route} other {{count} routes}}",
"licenseExpiring": "License expires {date}",
"licenseExpired": "License expired",
"medicalExpiring": "Medical cert expires {date}",
"medicalExpired": "Medical cert expired"
```

**Per-task validation:**
- JSON is valid (no trailing commas, proper nesting)
- `pnpm --filter @vtv/web type-check` passes

---

### Task 4: Add Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Mirror the English keys with proper Latvian translations including diacritics.

Add to `dashboard.goals`:
```json
"goals": {
  "title": "Sesijas mērķi",
  "subtitle": "Iestatiet mērķus priekš {name} uz {date}",
  "route": "Maršruta piešķiršana",
  "routePlaceholder": "Izvēlieties maršrutu...",
  "routeNoQualified": "Nav kvalificētu maršrutu",
  "routeLoading": "Ielādē maršrutus...",
  "transportType": "Transporta veids",
  "vehicle": "Transportlīdzekļa numurs",
  "vehiclePlaceholder": "piem. RS-1047",
  "notes": "Piezīmes",
  "notesPlaceholder": "Veiktspējas piezīmes...",
  "items": "Maiņas mērķi",
  "itemsTraining": "Apmācības mērķi",
  "addItem": "Pievienot mērķi",
  "addItemPlaceholder": "Ievadiet mērķi...",
  "removeItem": "Noņemt",
  "back": "Atpakaļ",
  "save": "Saglabāt",
  "saving": "Saglabā...",
  "bus": "Autobuss",
  "trolleybus": "Trolejbuss",
  "tram": "Tramvajs"
}
```

Add to existing `dashboard.roster`:
```json
"qualifiedRoutes": "{count, plural, one {{count} maršruts} other {{count} maršruti}}",
"licenseExpiring": "Licence beidzas {date}",
"licenseExpired": "Licence beigusies",
"medicalExpiring": "Medicīniskais sertifikāts beidzas {date}",
"medicalExpired": "Medicīniskais sertifikāts beidzies"
```

**Per-task validation:**
- JSON is valid
- `pnpm --filter @vtv/web type-check` passes

---

### Task 5: Create Goals Form Component
**File:** `cms/apps/web/src/components/dashboard/goals-form.tsx` (create)
**Action:** CREATE

Create a new `'use client'` component that renders the Step 2 goals form. This component receives the driver, target date, action type, and callbacks as props.

**Component interface:**
```typescript
interface GoalsFormProps {
  driver: Driver;
  targetDate: Date;
  actionType: "shift" | "training";
  isSaving: boolean;
  onBack: () => void;
  onSave: (goals: EventGoals) => void;
}
```

**Imports needed:**
```typescript
"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import { X, Plus, Bus, Zap, TrainFront } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Driver } from "@/types/driver";
import type { EventGoals, GoalItem, TransportType } from "@/types/event";
import type { Route } from "@/types/route";
import { fetchRoutes } from "@/lib/schedules-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
```

**State management:**
```typescript
const [routeId, setRouteId] = useState<number | null>(null);
const [transportType, setTransportType] = useState<TransportType | null>(null);
const [vehicleId, setVehicleId] = useState("");
const [notes, setNotes] = useState("");
const [goalItems, setGoalItems] = useState<GoalItem[]>(getDefaultGoals(actionType));
const [newGoalText, setNewGoalText] = useState("");
const [routes, setRoutes] = useState<Route[]>([]);
const [routesLoading, setRoutesLoading] = useState(true);
```

**Default goals function** (defined at module scope, NOT inside the component):
```typescript
function getDefaultGoals(actionType: "shift" | "training"): GoalItem[] {
  if (actionType === "shift") {
    return [
      { text: "Pre-trip inspection", completed: false, item_type: "checklist" },
      { text: "Route completion report", completed: false, item_type: "checklist" },
    ];
  }
  return [
    { text: "Complete training module", completed: false, item_type: "checklist" },
    { text: "Pass assessment", completed: false, item_type: "checklist" },
  ];
}
```

**NOTE for executor:** The default goal text strings above are English. They are NOT i18n-ized because they become data stored in the backend `goals.items[].text` field. They are user-editable content, not UI labels.

**Route fetching** (inside component):
```typescript
useEffect(() => {
  let cancelled = false;
  async function loadRoutes() {
    try {
      const result = await fetchRoutes({ page_size: 500 });
      if (!cancelled) {
        // Parse driver's qualified route IDs
        const qualifiedIds = driver.qualified_route_ids
          ? driver.qualified_route_ids.split(",").map(Number).filter(Boolean)
          : [];
        // Filter routes to only qualified ones (show all if no qualification data)
        const filtered = qualifiedIds.length > 0
          ? result.items.filter((r) => qualifiedIds.includes(r.id))
          : result.items;
        setRoutes(filtered);
      }
    } catch {
      // Silently handle — route select will show empty state
    } finally {
      if (!cancelled) setRoutesLoading(false);
    }
  }
  void loadRoutes();
  return () => { cancelled = true; };
}, [driver.qualified_route_ids]);
```

**Goal item management:**
```typescript
const handleAddGoal = useCallback(() => {
  if (!newGoalText.trim()) return;
  setGoalItems((prev) => [
    ...prev,
    { text: newGoalText.trim(), completed: false, item_type: "checklist" },
  ]);
  setNewGoalText("");
}, [newGoalText]);

const handleRemoveGoal = useCallback((index: number) => {
  setGoalItems((prev) => prev.filter((_, i) => i !== index));
}, []);
```

**Save handler:**
```typescript
function handleSave() {
  const goals: EventGoals = {
    items: goalItems,
    route_id: routeId,
    transport_type: transportType,
    vehicle_id: vehicleId.trim() || null,
  };
  onSave(goals);
}
```

**UI Layout:**

1. **Route Assignment** — `Select` dropdown showing `route_short_name - route_long_name`. When no qualified routes, show `routeNoQualified` message. When loading, show `routeLoading`.

2. **Transport Type** — `ToggleGroup type="single"` with three items (Bus, Trolleybus, Tram). Each item shows a Lucide icon + translated label. Use semantic transport colors for active state.

3. **Vehicle Number** — `Input` with placeholder. Optional field.

4. **Goal Checklist** — List of goal items with remove (X) button each. Below the list: `Input` + "Add" `Button` to add custom goals.

5. **Performance Notes** — `Textarea` with placeholder. Optional field.

6. **Actions** — "Back" button (outline variant) + "Save" button. Save disabled when `isSaving`.

**Dialog width:** The parent `DialogContent` should use `sm:max-w-[36rem]` when showing the goals form (step 2) to accommodate the wider form layout. The executor must update the `DialogContent` className in `driver-drop-dialog.tsx` to be conditional on the current step.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 6: Redesign DriverDropDialog with Two-Step Flow
**File:** `cms/apps/web/src/components/dashboard/driver-drop-dialog.tsx` (modify)
**Action:** UPDATE

**New state:**
Add a `step` state to track the current dialog step. Add `selectedAction` to track which action was picked in step 1.

```typescript
type DialogStep = "action" | "goals";
type GoalAction = "shift" | "training";

const [step, setStep] = useState<DialogStep>("action");
const [selectedAction, setSelectedAction] = useState<GoalAction | null>(null);
```

**New imports:**
```typescript
import { GoalsForm } from "./goals-form";
import type { EventGoals } from "@/types/event";
```

**Modified action handlers:**

For "Assign Shift": Instead of immediately creating the event, transition to step 2.
```typescript
function handleAssignShift() {
  setSelectedAction("shift");
  setStep("goals");
}
```

For "Schedule Training": Same — transition to step 2.
```typescript
function handleScheduleTraining() {
  setSelectedAction("training");
  setStep("goals");
}
```

Leave, sick, custom: Keep existing behavior (no step 2).

**New handler for goals save:**
```typescript
const handleGoalsSave = useCallback(
  (goals: EventGoals) => {
    if (!driver || !targetDate || !selectedAction) return;

    if (selectedAction === "shift") {
      const shift = driver.default_shift;
      const times = SHIFT_TIMES[shift] ?? SHIFT_TIMES.morning;
      const shiftLabelKey = SHIFT_LABEL_KEYS[shift] ?? "shiftMorning";

      void handleCreate({
        title: t("dropAction.eventTitleShift", {
          name: driverName,
          shift: t(`dropAction.${shiftLabelKey}`),
        }),
        description: t("dropAction.eventDesc", { number: driver.employee_number }),
        start_datetime: buildDatetime(targetDate, times.start, false),
        end_datetime: buildDatetime(targetDate, times.end, times.nextDay),
        priority: "medium",
        category: "driver-shift",
        goals,
      });
    } else {
      void handleCreate({
        title: t("dropAction.eventTitleTraining", { name: driverName }),
        description: t("dropAction.eventDesc", { number: driver.employee_number }),
        start_datetime: buildDatetime(targetDate, "09:00", false),
        end_datetime: buildDatetime(targetDate, "11:00", false),
        priority: "medium",
        category: "maintenance",
        goals,
      });
    }
  },
  [driver, targetDate, selectedAction, handleCreate, t, driverName],
);
```

**Updated handleOpenChange:**
Reset `step` and `selectedAction` when dialog closes:
```typescript
function handleOpenChange(nextOpen: boolean) {
  if (!nextOpen) {
    setStep("action");
    setSelectedAction(null);
    setShowCustomForm(false);
    setCustomTitle("");
    setCustomStart("09:00");
    setCustomEnd("17:00");
  }
  onOpenChange(nextOpen);
}
```

**Updated back handler for goals form:**
```typescript
const handleGoalsBack = useCallback(() => {
  setStep("action");
  setSelectedAction(null);
}, []);
```

**Updated JSX structure:**

The `DialogContent` receives a conditional className for width:
```tsx
<DialogContent className={cn(step === "goals" && "sm:max-w-[36rem]")}>
```

The body renders three possible states:
1. `step === "action" && !showCustomForm` → Action cards (existing)
2. `step === "action" && showCustomForm` → Custom event form (existing)
3. `step === "goals"` → GoalsForm component

```tsx
{step === "goals" && selectedAction && driver && targetDate ? (
  <GoalsForm
    key={`goals-${selectedAction}`}
    driver={driver}
    targetDate={targetDate}
    actionType={selectedAction}
    isSaving={isSaving}
    onBack={handleGoalsBack}
    onSave={handleGoalsSave}
  />
) : !showCustomForm ? (
  /* existing action cards */
) : (
  /* existing custom form */
)}
```

**CRITICAL: Use `key` prop on GoalsForm** — The `key={`goals-${selectedAction}`}` ensures the form remounts with fresh state when switching between shift and training. This follows the React 19 pattern of avoiding `setState` in `useEffect`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 7: Enhance Driver Roster Cards
**File:** `cms/apps/web/src/components/dashboard/driver-roster.tsx` (modify)
**Action:** UPDATE

Enhance the `DriverRosterCard` component to show:
1. Qualified routes count (from `qualified_route_ids`)
2. License expiry warning (amber < 30 days, red if expired)
3. Medical cert expiry warning (amber < 30 days, red if expired)

**Helper function** (at module scope):
```typescript
type ExpiryStatus = "ok" | "expiring" | "expired";

function getExpiryStatus(dateStr: string | null): ExpiryStatus {
  if (!dateStr) return "ok";
  const expiry = new Date(dateStr);
  const now = new Date();
  if (expiry < now) return "expired";
  const thirtyDays = 30 * 24 * 60 * 60 * 1000;
  if (expiry.getTime() - now.getTime() < thirtyDays) return "expiring";
  return "ok";
}

function getQualifiedRouteCount(routeIds: string | null): number {
  if (!routeIds) return 0;
  return routeIds.split(",").filter(Boolean).length;
}
```

**Updated DriverRosterCard JSX:**

After the existing employee number line, add a new row:
```tsx
{/* Qualification and expiry indicators */}
<div className="flex flex-wrap items-center gap-(--spacing-tight) mt-(--spacing-tight)">
  {qualifiedCount > 0 && (
    <span className="text-[10px] text-foreground-muted">
      {t("roster.qualifiedRoutes", { count: qualifiedCount })}
    </span>
  )}
  {licenseStatus === "expired" && (
    <Badge variant="secondary" className="bg-status-critical/15 text-status-critical text-[10px]">
      {t("roster.licenseExpired")}
    </Badge>
  )}
  {licenseStatus === "expiring" && (
    <Badge variant="secondary" className="bg-status-delayed/15 text-status-delayed text-[10px]">
      {t("roster.licenseExpiring", {
        date: new Date(driver.license_expiry_date!).toLocaleDateString(),
      })}
    </Badge>
  )}
  {medicalStatus === "expired" && (
    <Badge variant="secondary" className="bg-status-critical/15 text-status-critical text-[10px]">
      {t("roster.medicalExpired")}
    </Badge>
  )}
  {medicalStatus === "expiring" && (
    <Badge variant="secondary" className="bg-status-delayed/15 text-status-delayed text-[10px]">
      {t("roster.medicalExpiring", {
        date: new Date(driver.medical_cert_expiry!).toLocaleDateString(),
      })}
    </Badge>
  )}
</div>
```

Compute status values inside the component (before the return):
```typescript
const qualifiedCount = getQualifiedRouteCount(driver.qualified_route_ids);
const licenseStatus = getExpiryStatus(driver.license_expiry_date);
const medicalStatus = getExpiryStatus(driver.medical_cert_expiry);
```

Only render the qualification/expiry row if there's something to show:
```tsx
{(qualifiedCount > 0 || licenseStatus !== "ok" || medicalStatus !== "ok") && (
  <div className="...">...</div>
)}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 8: Final Validation (3-Level Pyramid)

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

- [ ] Step 1 (action cards) renders correctly — all 5 cards clickable
- [ ] Clicking "Assign Shift" transitions to Step 2 (goals form)
- [ ] Clicking "Schedule Training" transitions to Step 2 (goals form)
- [ ] Clicking "Mark Leave", "Mark Sick" creates event immediately (no step 2)
- [ ] "Custom Event" still shows the custom form (no step 2)
- [ ] Goals form shows route dropdown filtered to driver's qualified routes
- [ ] Goals form shows transport type ToggleGroup (bus/trolleybus/tram)
- [ ] Goals form shows pre-filled checklist items (varies by action type)
- [ ] Custom goal items can be added and removed
- [ ] "Back" button returns to Step 1 (action cards)
- [ ] "Save" creates event with goals JSON attached
- [ ] Dialog resets to Step 1 when closed and reopened
- [ ] Driver roster cards show qualified route count
- [ ] Driver roster cards show license/medical expiry warnings
- [ ] i18n keys present in both lv.json and en.json
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] Accessibility: all interactive elements have labels, form inputs have associated labels
- [ ] Dialog width expands to `sm:max-w-[36rem]` during step 2

## Acceptance Criteria

This feature is complete when:
- [ ] Two-step flow works for shift and training actions
- [ ] Single-step flow preserved for leave, sick, and custom actions
- [ ] Goals form captures route, transport type, vehicle, notes, and checklist items
- [ ] Events created with goals have the `goals` field populated in the backend
- [ ] Driver roster shows qualification and expiry information
- [ ] Both languages have complete translations
- [ ] Design system rules followed (MASTER.md, semantic tokens only)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing dashboard functionality
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

1. **Route IDs are numbers, not strings** — `qualified_route_ids` is a comma-separated STRING ("1,5,22"). Parse with `.split(",").map(Number).filter(Boolean)` to get `number[]`. Then filter routes by `route.id` (also a number). Don't compare strings to numbers.
2. **ToggleGroup value is a string** — Radix ToggleGroup uses string values. Store transport type as `TransportType | null` in state. Use `value={transportType ?? ""}` and handle empty string as null in `onValueChange`.
3. **Route select value must be string** — Radix Select uses string values. Convert route ID to/from string: `value={String(routeId)}` and `onValueChange={(v) => setRouteId(Number(v))}`.
4. **fetchRoutes is async, needs cleanup** — Use the `cancelled` flag pattern in useEffect to prevent state updates after unmount.
5. **Don't create components inside GoalsForm** — Goal item row, transport type toggle, etc. must be defined at module scope or as separate files. React 19 forbids component definitions inside render.
6. **DialogContent className must not use named sizes** — Use `sm:max-w-[36rem]` not `sm:max-w-lg`. Named sizes are broken in this project's Tailwind v4 setup.
7. **i18n pluralization syntax** — next-intl uses ICU format: `{count, plural, one {{count} route} other {{count} routes}}`. Double braces for the interpolation within the plural branch.
8. **Badge text for license dates** — Use `toLocaleDateString()` to format the expiry date. The `{date}` interpolation in the i18n string receives this formatted string.
