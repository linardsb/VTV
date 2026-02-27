# Plan: Calendar Event Hover Card

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Route**: N/A (enhances existing dashboard page)
**Auth Required**: Yes (inherits dashboard auth)
**Allowed Roles**: all authenticated

## Feature Description

Add a hover popup (HoverCard) to calendar event entries across the Week, Month, and Three-Month views on the dashboard. Currently, event cards truncate titles and only show minimal info (time range, priority badge, goal count). Users must click to open a full dialog to see details.

The hover card appears when the user hovers over any event entry and shows all key information at a glance: full untruncated title, time range, category label, priority badge, description (if available), and individual goal items with completion checkmarks. This eliminates the need to click into the full event dialog for quick reference.

The Year view (heatmap) is excluded — it only shows event density, not individual events.

## Design System

### Master Rules (from MASTER.md)
- Spacing: `--spacing-card` (12px) for card padding, `--spacing-inline` (6px) for icon-text gaps, `--spacing-tight` (4px) for micro gaps
- Typography: Source Sans 3 body, 16px+ for accessibility
- Shadows: `--shadow-lg` for dropdowns/popovers
- Transitions: 150-300ms ease
- Focus: 3px ring using `--color-focus-ring`
- Border radius: `--radius-md` (8px)

### Page Override
- None — uses MASTER.md rules

### Tokens Used
- `--color-surface-raised` — popover background
- `--color-foreground` — primary text
- `--color-foreground-muted` — secondary text (times, labels)
- `--color-border` — separator lines
- `--color-border-subtle` — card border
- `--shadow-lg` — popover elevation
- `--spacing-card`, `--spacing-inline`, `--spacing-tight`
- `--color-status-ontime`, `--color-status-delayed`, `--color-foreground` (goal status)
- Category/event tokens from `event-styles.ts` for colored dots

## Components Needed

### Existing (shadcn/ui)
- `Tooltip` — already installed, but semantically wrong for rich content
- `Badge` — for priority/category display

### New shadcn/ui to Install
- `HoverCard` — `npx shadcn@latest add hover-card` — purpose-built for hover-triggered rich content popups with Radix primitives (open delay, close delay, positioning, portal)

### Custom Components to Create
- `EventHoverCard` at `cms/apps/web/src/components/dashboard/event-hover-card.tsx` — wraps Radix HoverCard with event-specific content layout. Accepts a `CalendarEvent` and renders children as the trigger.

## i18n Keys

### Latvian (`lv.json`)
Add under `dashboard.hover`:
```json
{
  "dashboard": {
    "hover": {
      "category": "Kategorija",
      "priority": "Prioritāte",
      "description": "Apraksts",
      "noDescription": "Nav apraksta",
      "goals": "Mērķi",
      "noGoals": "Nav mērķu",
      "time": "Laiks",
      "allDay": "Visa diena"
    }
  }
}
```

### English (`en.json`)
Add under `dashboard.hover`:
```json
{
  "dashboard": {
    "hover": {
      "category": "Category",
      "priority": "Priority",
      "description": "Description",
      "noDescription": "No description",
      "goals": "Goals",
      "noGoals": "No goals",
      "time": "Time",
      "allDay": "All day"
    }
  }
}
```

## Data Fetching

- **No new API calls** — all data already available on the `CalendarEvent` object passed to each view
- **Fields used**: `title`, `start`, `end`, `priority`, `category`, `description`, `goals` (with `items[]`, each having `text` and `completed`)
- **Server/client boundary**: All calendar views are already client components (`'use client'`). HoverCard is a client-only interaction — no SSR concerns.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules
- `cms/apps/web/CLAUDE.md` — Frontend-specific conventions, React 19 anti-patterns

### Pattern Files (Read for context)
- `cms/apps/web/src/components/dashboard/calendar-event.tsx` — Current event card renderer (week view). Shows how title is parsed for driver name, how priority badges are rendered, how goal badges work. **Read this first** to understand the event data shape and rendering patterns.
- `cms/apps/web/src/components/dashboard/event-styles.ts` — Event color mapping (subtype detection from title keywords, category-to-color mapping). The hover card should reuse these color utilities.
- `cms/apps/web/src/components/dashboard/goal-progress-badge.tsx` — Goal progress display. The hover card will show individual goal items instead of the compact badge.
- `cms/apps/web/src/components/ui/tooltip.tsx` — Existing tooltip component for reference on Radix patterns and styling conventions.

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add Latvian translations for hover card labels
- `cms/apps/web/messages/en.json` — Add English translations for hover card labels
- `cms/apps/web/src/components/dashboard/week-view.tsx` — Wrap event cards with `EventHoverCard`
- `cms/apps/web/src/components/dashboard/month-view.tsx` — Wrap event buttons with `EventHoverCard`
- `cms/apps/web/src/components/dashboard/three-month-view.tsx` — Wrap mini event buttons with `EventHoverCard`

### Files to Create
- `cms/apps/web/src/components/ui/hover-card.tsx` — shadcn HoverCard component (generated by CLI)
- `cms/apps/web/src/components/dashboard/event-hover-card.tsx` — Custom EventHoverCard wrapper

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping table and forbidden class list are loaded via `@_shared/tailwind-token-map.md`. Key rules:
- Use the mapping table for all color decisions
- Check `cms/packages/ui/src/tokens.css` for available tokens
- Reuse `getEventDotColor()` and `getEventCardStyle()` from `event-styles.ts` for consistent category colors
- Use `text-foreground` for primary text, `text-foreground-muted` for labels
- Use `bg-surface-raised` for popover background
- Use `border-border` for separators
- Exception: Inline HTML strings (Leaflet) may use hex colors

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract `EventHoverCard` to its own file at module scope. Do NOT define it inline inside `WeekView`, `MonthView`, or `ThreeMonthView`.
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies**

See `cms/apps/web/CLAUDE.md` -> "React 19 Anti-Patterns" for full examples.

## TypeScript Security Rules

- No JWT handling in this feature — purely UI enhancement
- No external data beyond what's already validated in `useCalendarEvents` hook
- Clear `.next` cache if module resolution errors persist after adding new component

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Install shadcn HoverCard component
**Action:** RUN

```bash
cd cms && npx shadcn@latest add hover-card --yes
```

This generates `cms/apps/web/src/components/ui/hover-card.tsx` using Radix HoverCard primitives with project-consistent styling.

**Per-task validation:**
- Verify file exists at `cms/apps/web/src/components/ui/hover-card.tsx`
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 2: Add i18n keys — Latvian
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add the following keys inside the existing `"dashboard"` object, as a new `"hover"` sub-object. Place it after the existing `"eventPanel"` key:

```json
"hover": {
  "category": "Kategorija",
  "priority": "Prioritāte",
  "description": "Apraksts",
  "noDescription": "Nav apraksta",
  "goals": "Mērķi",
  "noGoals": "Nav mērķu",
  "time": "Laiks",
  "allDay": "Visa diena"
}
```

**Per-task validation:**
- Verify valid JSON: `node -e "JSON.parse(require('fs').readFileSync('cms/apps/web/messages/lv.json','utf8'))"`

---

### Task 3: Add i18n keys — English
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add the matching keys inside the existing `"dashboard"` object, as a new `"hover"` sub-object. Place it after the existing `"eventPanel"` key:

```json
"hover": {
  "category": "Category",
  "priority": "Priority",
  "description": "Description",
  "noDescription": "No description",
  "goals": "Goals",
  "noGoals": "No goals",
  "time": "Time",
  "allDay": "All day"
}
```

**Per-task validation:**
- Verify valid JSON: `node -e "JSON.parse(require('fs').readFileSync('cms/apps/web/messages/en.json','utf8'))"`
- Verify key parity: both files have `dashboard.hover` with identical key names

---

### Task 4: Create EventHoverCard component
**File:** `cms/apps/web/src/components/dashboard/event-hover-card.tsx` (create)
**Action:** CREATE

Create a client component that wraps children with a Radix HoverCard. This is the core of the feature.

**Component API:**
```typescript
interface EventHoverCardProps {
  event: CalendarEvent;
  children: React.ReactNode;
  locale: string;
}
```

**Implementation details:**

1. Import `HoverCard`, `HoverCardContent`, `HoverCardTrigger` from `@/components/ui/hover-card`
2. Import `useTranslations` from `next-intl`
3. Import `getEventDotColor` from `./event-styles` for category dot color
4. Import `CalendarEvent` type from `@/types/event`

4. **HoverCard configuration:**
   - `openDelay={300}` — 300ms delay before showing (prevents flash on quick mouse movements)
   - `closeDelay={100}` — 100ms delay before hiding (prevents flicker when moving to card)

5. **HoverCardTrigger:**
   - Wrap `children` with `asChild` so the trigger IS the existing event element (no extra DOM wrapper that could break layout)
   - The trigger must be a `<div>` wrapper around `{children}` to ensure HoverCard can attach ref. Use `className="contents"` on the wrapper ONLY if the parent is a flex/grid container and wrapping would break layout. Otherwise use no class.
   - CRITICAL: In week-view, events are absolutely positioned. Wrapping them must NOT change their positioning. Use `<HoverCardTrigger asChild>` so it attaches directly to the child element.

6. **HoverCardContent layout:**
   - `className="w-72 p-(--spacing-card)"` — fixed 288px width, card padding
   - `side="top"` with `sideOffset={8}` — appears above the event by default, auto-flips
   - `align="center"`
   - Use `z-50` to appear above calendar grid

7. **Content sections (top to bottom):**

   **a) Title section:**
   - Full event title (untruncated), `text-sm font-semibold text-foreground`
   - Category label on same line or below: use `t(`events.${categoryKey}`)` to get the i18n category name (reuse existing `dashboard.events.*` keys: maintenance, routeChange, driverShift, serviceAlert)
   - Category shown as a small badge or colored dot + text

   **b) Time section:**
   - Label: `t("hover.time")` in `text-xs text-foreground-muted`
   - Value: formatted time range using same `formatTime` helper as week-view, OR "All day" if start is 00:00 and end is 23:59
   - Format: `"HH:MM – HH:MM"` or the i18n `hover.allDay` key

   **c) Priority section:**
   - Label: `t("hover.priority")` in `text-xs text-foreground-muted`
   - Value: Priority badge (reuse exact same badge styling from `calendar-event.tsx` — the colored pill with `t(`priority.${event.priority}`)`)

   **d) Description section** (conditional — only if `event.description` exists and is non-empty):
   - Label: `t("hover.description")` in `text-xs text-foreground-muted`
   - Value: `event.description` in `text-xs text-foreground`, max 3 lines with `line-clamp-3`

   **e) Goals section** (conditional — only if `event.goals?.items.length > 0`):
   - Label: `t("hover.goals")` with count `({completed}/{total})` in `text-xs text-foreground-muted`
   - List of goal items as a `<ul>`:
     - Each item: checkbox icon (filled green check `text-status-ontime` if `completed`, empty circle `text-foreground-muted` if not) + goal text in `text-xs`
     - Max 5 items shown. If more than 5, show "+N more" text
   - Use Lucide icons: `CheckCircle2` for completed, `Circle` for incomplete

   **f) Separators:**
   - Use `<Separator />` (from `@/components/ui/separator`) between sections, styled with `my-(--spacing-tight)` margin

8. **Styling rules:**
   - ALL colors use semantic tokens (no primitives)
   - Use `--spacing-tight` (4px) for gaps between label and value
   - Use `--spacing-inline` (6px) for icon-text gaps
   - Use `--spacing-card` (12px) for overall padding
   - Background: inherits from shadcn HoverCard default (which uses `bg-popover`)
   - Border: inherits from shadcn default (`border`)
   - Shadow: inherits from shadcn default (uses shadow utility)

9. **Category key mapping** — the `event.category` field uses hyphenated values (`"driver-shift"`) but i18n keys use camelCase (`"driverShift"`). Create a simple lookup:
   ```typescript
   const categoryI18nKey: Record<string, string> = {
     "maintenance": "maintenance",
     "route-change": "routeChange",
     "driver-shift": "driverShift",
     "service-alert": "serviceAlert",
   };
   ```

10. **Time formatting** — Create a local helper or import the `formatTime` function. Check `week-view.tsx` for the existing `formatTime` implementation. If it's defined locally in week-view, replicate it in the hover card (it's a simple `toLocaleTimeString` call). Do NOT extract to shared — only 2 usages doesn't meet the three-feature rule.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 5: Integrate EventHoverCard into Week View
**File:** `cms/apps/web/src/components/dashboard/week-view.tsx` (modify)
**Action:** UPDATE

**Pre-read:** Read the full file first. Understand the event rendering logic. Events are rendered inside a mapped loop over `dayEvents`. Each event is a `<div>` with absolute positioning (`style={{ top, height, left, width }}`).

**Changes:**

1. Add import at top:
   ```typescript
   import { EventHoverCard } from "./event-hover-card";
   ```

2. Find where individual events are rendered — look for the event map that creates absolutely positioned `<div>` elements containing the `<CalendarEventCard>` component or inline event rendering.

3. Wrap each event's outermost element with `<EventHoverCard>`:
   ```tsx
   <EventHoverCard event={event} locale={locale}>
     <div
       key={event.id}
       className={/* existing classes */}
       style={/* existing absolute positioning */}
       onClick={/* existing handler */}
     >
       {/* existing event content */}
     </div>
   </EventHoverCard>
   ```

4. CRITICAL positioning note: The `<HoverCardTrigger asChild>` pattern means the HoverCard attaches directly to the child `<div>`. This preserves absolute positioning. The EventHoverCard component uses `asChild` on the trigger, so no extra wrapper DOM is added.

5. Pass the `locale` prop. Check how locale is obtained in week-view — it likely uses `useLocale()` from `next-intl`. If not already imported, add the import and call.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 6: Integrate EventHoverCard into Month View
**File:** `cms/apps/web/src/components/dashboard/month-view.tsx` (modify)
**Action:** UPDATE

**Pre-read:** Read the full file first. Events are rendered as `<button>` elements inside day cells. There are two rendering paths: events WITH goals (show GoalProgressBadge) and events WITHOUT goals (show colored dot).

**Changes:**

1. Add import at top:
   ```typescript
   import { EventHoverCard } from "./event-hover-card";
   ```

2. Find where `visibleEvents` are mapped inside day cells. Each event is a `<button>`.

3. Wrap each event `<button>` with `<EventHoverCard>`:
   ```tsx
   <EventHoverCard event={event} locale={locale}>
     <button
       key={event.id}
       className={/* existing classes */}
       onClick={/* existing handler */}
     >
       {/* existing content (dot + title or title + GoalProgressBadge) */}
     </button>
   </EventHoverCard>
   ```

4. IMPORTANT: The `<button>` must remain the direct child of EventHoverCard so `asChild` works. Do NOT add any intermediate wrapper.

5. Pass the `locale` prop. Add `useLocale()` import if not already present.

6. Also consider wrapping the overflow "+N more" button — but do NOT wrap it with hover card, since it's not a single event. Leave overflow as-is.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 7: Integrate EventHoverCard into Three-Month View
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx` (modify)
**Action:** UPDATE

**Pre-read:** Read the full file first. This component renders a `MiniMonth` sub-component (defined at module scope, NOT inline — verify this). Inside MiniMonth, events are tiny `<button>` elements with 8px text and 1px dots.

**Changes:**

1. Add import at top of the file:
   ```typescript
   import { EventHoverCard } from "./event-hover-card";
   ```

2. Find where events are mapped inside `MiniMonth`. Each event is a `<button>` with a dot and truncated title.

3. Wrap each event `<button>` with `<EventHoverCard>`:
   ```tsx
   <EventHoverCard event={event} locale={locale}>
     <button
       key={event.id}
       className={/* existing classes */}
       onClick={/* existing handler */}
     >
       {/* existing dot + title */}
     </button>
   </EventHoverCard>
   ```

4. Pass the `locale` prop. The `MiniMonth` component may need a new `locale` prop added to its interface if it doesn't already receive one. Check the parent component that renders `MiniMonth` — if locale is available there, thread it through.

5. If `MiniMonth` is defined as a separate function at module scope (React 19 compliance), add `locale: string` to its props interface and pass it from the parent.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes
- `cd cms && pnpm --filter @vtv/web build` passes

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

- [ ] Hover card appears on Week view events after ~300ms hover
- [ ] Hover card appears on Month view events after ~300ms hover
- [ ] Hover card appears on Three-Month view mini events after ~300ms hover
- [ ] Hover card does NOT appear on Year view (no changes to year-view.tsx)
- [ ] Full title shown (not truncated) in hover card
- [ ] Time range displayed correctly with locale-appropriate formatting
- [ ] Category label displayed with correct i18n translation
- [ ] Priority badge matches existing style from event cards
- [ ] Description shown when available, hidden when empty
- [ ] Goal items listed with check/circle icons and completion state
- [ ] Hover card auto-positions (flips when near edge of viewport)
- [ ] Hover card does NOT interfere with existing click handlers (clicking still opens event dialog)
- [ ] Hover card does NOT break absolute positioning in week view
- [ ] Hover card does NOT break drag-and-drop functionality
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] i18n keys present in both lv.json and en.json
- [ ] No lint warnings or errors introduced
- [ ] Accessibility: hover card content is accessible (Radix handles aria attributes)

## Acceptance Criteria

This feature is complete when:
- [ ] Hovering over any event in Week/Month/Three-Month views shows a rich info popup
- [ ] Popup shows: full title, time, category, priority, description (if any), goal items (if any)
- [ ] Popup disappears when mouse leaves the event and the popup area
- [ ] Existing click, drag-and-drop, and navigation behaviors are unaffected
- [ ] Both lv and en translations work correctly
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing dashboard functionality
- [ ] Ready for `/commit`
