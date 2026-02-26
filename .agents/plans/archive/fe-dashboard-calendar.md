# Plan: Dashboard Calendar Page

## Feature Metadata
**Feature Type**: Enhancement (replaces placeholder dashboard)
**Estimated Complexity**: High
**Route**: `/[locale]/(dashboard)` (existing route, enhanced)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer (all authenticated users)

## Feature Description

Replace the current placeholder dashboard (`cms/apps/web/src/app/[locale]/(dashboard)/page.tsx`) with a full-featured operations dashboard inspired by the dark screenshot reference at `cms/design-system/vtv/pages/1.jpg`. The dashboard consists of two major sections:

**Top Section — Overview Cards:** Four KPI metric cards showing Active Vehicles, On-Time Performance, Delayed Routes, and Fleet Utilization. Each card displays a large metric value, a comparison delta badge (e.g., "+5" or "-8%"), and a subtitle showing last month's comparison. Cards sit in a horizontal 4-column grid.

**Bottom Section — Operations Calendar:** A multi-view calendar (Year, 3-Month, Month, Week) displaying transit operations events (scheduled maintenance, route changes, driver shifts, service alerts). The Week view is the default, showing a 7-day grid with hourly time slots (06:00–22:00) and event cards positioned at their scheduled times. A **live red timeline** (horizontal line) moves in real-time across the calendar to indicate the current time position. The timeline updates every 60 seconds. View switching via segmented button group (Year / 3 Mo / Month / Week).

This is a client component (`'use client'`) because it requires real-time state (live timeline interval, view mode toggle, current date navigation).

## Design System

### Master Rules (from MASTER.md)
- **Typography:** Lexend for headings (`font-heading`), Source Sans 3 for body (`font-body`)
- **Spacing:** Use `--spacing-*` tokens (xs=4px, sm=8px, md=16px, lg=24px, xl=32px)
- **Colors:** High contrast navy + blue. No hardcoded hex values — use semantic tokens only
- **Radius:** `--radius-md` (8px) for cards, `--radius-sm` (4px) for badges
- **Shadows:** `--shadow-md` for cards, `--shadow-sm` for subtle lift
- **Transitions:** 150-300ms for all hover/state changes
- **Accessibility:** 4.5:1 contrast ratio, focus rings (3px), ARIA labels, keyboard nav
- **Anti-patterns:** No emojis as icons, no low contrast, no motion effects, no AI gradients

### Page Override
- None exists — the executing agent should NOT generate one (this is an enhancement of an existing page, not a new page)

### Tokens Used (from `cms/packages/ui/src/tokens.css`)
- **Surfaces:** `bg-surface`, `bg-surface-raised`, `bg-background`
- **Text:** `text-foreground`, `text-foreground-muted`
- **Borders:** `border-border`, `border-border-subtle`
- **Brand:** `bg-brand`, `bg-brand-muted`
- **Interactive:** `bg-interactive`, `bg-interactive-hover`
- **Status:** `text-status-ontime` (emerald), `text-status-delayed` (amber), `text-status-critical` (red)
- **Focus:** `ring-focus-ring`
- **Spacing:** `spacing-xs`, `spacing-sm`, `spacing-md`, `spacing-lg`, `spacing-xl`
- **Radius:** `rounded-md` (8px), `rounded-sm` (4px), `rounded-lg` (12px)
- **Fonts:** `font-heading`, `font-body`

## Components Needed

### Existing (shadcn/ui — already installed)
- `Button` — View mode toggles, "Today" button, navigation arrows
- `Badge` — Status badges on metric delta values and calendar event priorities
- `Skeleton` — Loading states for metric cards and calendar grid
- `Tooltip` — Hover info on calendar events and metric details
- `Separator` — Visual dividers between dashboard sections

### New shadcn/ui to Install
- `Card` — `npx shadcn@latest add card` — Metric overview cards and calendar event cards
- `Select` — `npx shadcn@latest add select` — Month/year picker in calendar header
- `Toggle Group` — `npx shadcn@latest add toggle-group` — Year/3Mo/Month/Week view switcher

### Custom Components to Create

1. **`MetricCard`** at `cms/apps/web/src/components/dashboard/metric-card.tsx`
   - Displays a KPI: icon, title, large value, delta badge, subtitle
   - Props: `icon: LucideIcon, title: string, value: string, delta: string, deltaType: 'positive' | 'negative' | 'neutral', subtitle: string`
   - Uses `Card` from shadcn, `Badge` for delta

2. **`CalendarGrid`** at `cms/apps/web/src/components/dashboard/calendar-grid.tsx`
   - The main calendar component with view mode switching
   - Props: `view: 'year' | '3month' | 'month' | 'week', currentDate: Date, events: CalendarEvent[]`
   - Contains view-switching logic and renders the appropriate view

3. **`WeekView`** at `cms/apps/web/src/components/dashboard/week-view.tsx`
   - 7-day grid with hourly time slots (06:00–22:00)
   - Renders event cards positioned by time
   - Renders the live red timeline indicator

4. **`MonthView`** at `cms/apps/web/src/components/dashboard/month-view.tsx`
   - Traditional month grid (rows of weeks, 7 columns)
   - Day cells with event dots/indicators
   - Live timeline: highlighted "today" cell with pulsing border

5. **`ThreeMonthView`** at `cms/apps/web/src/components/dashboard/three-month-view.tsx`
   - Side-by-side 3 mini month grids
   - Compact day cells with event count indicators

6. **`YearView`** at `cms/apps/web/src/components/dashboard/year-view.tsx`
   - 12 mini month grids in a 4x3 grid layout
   - Day cells as small colored squares (heat map style based on event density)

7. **`LiveTimeline`** at `cms/apps/web/src/components/dashboard/live-timeline.tsx`
   - Horizontal red line with a small circle indicator on the left
   - Absolutely positioned within the week view based on current time
   - Updates position every 60 seconds via `setInterval`
   - Uses `--color-status-critical` (red) for the line color

8. **`CalendarEvent`** at `cms/apps/web/src/components/dashboard/calendar-event.tsx`
   - Single event card within the week view
   - Shows title, time range, priority badge
   - Uses `Badge` for priority indicator (High/Medium/Low)

9. **`CalendarHeader`** at `cms/apps/web/src/components/dashboard/calendar-header.tsx`
   - Navigation: Previous/Next arrows, "Today" button, current date display
   - View mode toggle group: Year | 3 Mo | Month | Week
   - Uses `Button`, `ToggleGroup` from shadcn

## Types

Create `cms/apps/web/src/types/dashboard.ts`:

```typescript
export type CalendarViewMode = "year" | "3month" | "month" | "week";

export type EventPriority = "high" | "medium" | "low";

export type EventCategory = "maintenance" | "route-change" | "driver-shift" | "service-alert";

export interface CalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  priority: EventPriority;
  category: EventCategory;
  description?: string;
}

export interface MetricData {
  title: string;
  value: string;
  delta: string;
  deltaType: "positive" | "negative" | "neutral";
  subtitle: string;
}
```

## i18n Keys

### Latvian (`lv.json`)
```json
{
  "dashboard": {
    "title": "Darbagalds",
    "activeRoutes": "{count, plural, zero {Nav aktivu marsrutu} one {{count} aktivs marsruts} other {{count} aktivi marsruti}}",
    "delayedRoutes": "{count, plural, zero {Neviens nekavejas} one {{count} marsruts kavejas} other {{count} marsruti kavejas}}",
    "metrics": {
      "activeVehicles": "Aktivi transportlidzekli",
      "onTimePerformance": "Savlaicigums",
      "delayedRoutes": "Kaveti marsruti",
      "fleetUtilization": "Parka izmantojums",
      "comparedToLastMonth": "Salidzinot ar iepriekseji menesi"
    },
    "calendar": {
      "title": "Operacijas",
      "today": "Sodien",
      "week": "Nedela",
      "month": "Menesis",
      "threeMonth": "3 menesi",
      "year": "Gads",
      "noEvents": "Nav notikumu",
      "allDay": "Visa diena"
    },
    "events": {
      "maintenance": "Apkope",
      "routeChange": "Marsruta izmaina",
      "driverShift": "Vaditaja maina",
      "serviceAlert": "Servisa bridinajums"
    },
    "priority": {
      "high": "Augsta",
      "medium": "Videja",
      "low": "Zema"
    },
    "weekdays": {
      "mon": "Pr",
      "tue": "Ot",
      "wed": "Tr",
      "thu": "Ce",
      "fri": "Pk",
      "sat": "Se",
      "sun": "Sv"
    },
    "months": {
      "jan": "Janvaris",
      "feb": "Februaris",
      "mar": "Marts",
      "apr": "Aprilis",
      "may": "Maijs",
      "jun": "Junijs",
      "jul": "Julijs",
      "aug": "Augusts",
      "sep": "Septembris",
      "oct": "Oktobris",
      "nov": "Novembris",
      "dec": "Decembris"
    }
  }
}
```

### English (`en.json`)
```json
{
  "dashboard": {
    "title": "Operations Dashboard",
    "activeRoutes": "{count, plural, one {{count} active route} other {{count} active routes}}",
    "delayedRoutes": "{count, plural, one {{count} route delayed} other {{count} routes delayed}}",
    "metrics": {
      "activeVehicles": "Active Vehicles",
      "onTimePerformance": "On-Time Performance",
      "delayedRoutes": "Delayed Routes",
      "fleetUtilization": "Fleet Utilization",
      "comparedToLastMonth": "Compared to last month"
    },
    "calendar": {
      "title": "Operations",
      "today": "Today",
      "week": "Week",
      "month": "Month",
      "threeMonth": "3 Months",
      "year": "Year",
      "noEvents": "No events",
      "allDay": "All day"
    },
    "events": {
      "maintenance": "Maintenance",
      "routeChange": "Route Change",
      "driverShift": "Driver Shift",
      "serviceAlert": "Service Alert"
    },
    "priority": {
      "high": "High",
      "medium": "Medium",
      "low": "Low"
    },
    "weekdays": {
      "mon": "Mon",
      "tue": "Tue",
      "wed": "Wed",
      "thu": "Thu",
      "fri": "Fri",
      "sat": "Sat",
      "sun": "Sun"
    },
    "months": {
      "jan": "January",
      "feb": "February",
      "mar": "March",
      "apr": "April",
      "may": "May",
      "jun": "June",
      "jul": "July",
      "aug": "August",
      "sep": "September",
      "oct": "October",
      "nov": "November",
      "dec": "December"
    }
  }
}
```

## Data Fetching

- **API endpoints**: None yet — use mock/static data for now. Metrics and events are hardcoded as sample data in a `cms/apps/web/src/lib/mock-dashboard-data.ts` file.
- **Server vs Client**: The page component is `'use client'` because of the live timeline interval and view toggle state. Metric data is passed as static props initially.
- **Loading states**: Use `Skeleton` component for metric cards (4 skeleton rectangles) and calendar grid (shimmer placeholder).

## RBAC Integration

- **No middleware changes needed.** The dashboard route `/[locale]/` is already accessible to all authenticated users. It is NOT in the middleware matcher pattern (matcher only covers specific sub-routes like routes, stops, etc.). The dashboard is the default landing page after auth.

## Sidebar Navigation

- **No sidebar changes needed.** The "Dashboard" nav item already exists and is enabled in the sidebar at `cms/apps/web/src/app/[locale]/layout.tsx` (navItems[0]).

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Current dashboard (will be replaced)
- `cms/apps/web/src/app/[locale]/login/page.tsx` — Client component with `'use client'`, `useState` pattern
- `cms/apps/web/src/app/[locale]/layout.tsx` — Sidebar nav structure (no changes needed)
- `cms/apps/web/src/components/ui/button.tsx` — CVA variant pattern with `cn()` utility
- `cms/apps/web/src/components/ui/badge.tsx` — Badge variant pattern

### Design Reference
- `cms/design-system/vtv/pages/1.jpg` — Dark screenshot with calendar dashboard layout (PRIMARY reference)
- `cms/design-system/vtv/pages/2.jpg` — Light shipments dashboard with metric cards (secondary reference for card layout)

### Token Reference
- `cms/packages/ui/src/tokens.css` — All available design tokens (primitive + semantic)

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add Latvian translations for dashboard enhancement
- `cms/apps/web/messages/en.json` — Add English translations for dashboard enhancement
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Replace with full dashboard

### Files to Create
- `cms/apps/web/src/types/dashboard.ts` — Type definitions
- `cms/apps/web/src/lib/mock-dashboard-data.ts` — Sample data for metrics and events
- `cms/apps/web/src/components/dashboard/metric-card.tsx` — KPI metric card
- `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — Main calendar container
- `cms/apps/web/src/components/dashboard/calendar-header.tsx` — Nav + view toggle
- `cms/apps/web/src/components/dashboard/week-view.tsx` — Weekly calendar with time slots
- `cms/apps/web/src/components/dashboard/month-view.tsx` — Monthly calendar grid
- `cms/apps/web/src/components/dashboard/three-month-view.tsx` — 3-month overview
- `cms/apps/web/src/components/dashboard/year-view.tsx` — Annual heat map
- `cms/apps/web/src/components/dashboard/live-timeline.tsx` — Real-time red line
- `cms/apps/web/src/components/dashboard/calendar-event.tsx` — Event card

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD, INSTALL

---

### Task 1: Install shadcn/ui Dependencies
**Action:** INSTALL

Run the following commands from the `cms/` directory:

```bash
cd /Users/Berzins/Desktop/AI/VTV/cms && npx shadcn@latest add card --yes
cd /Users/Berzins/Desktop/AI/VTV/cms && npx shadcn@latest add select --yes
cd /Users/Berzins/Desktop/AI/VTV/cms && npx shadcn@latest add toggle-group --yes
```

After each install, verify the component file was created in `cms/apps/web/src/components/ui/`.

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- Verify files exist: `card.tsx`, `select.tsx`, `toggle-group.tsx` in `components/ui/`

---

### Task 2: Update Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Replace the entire `"dashboard"` key with the expanded version from the **i18n Keys** section above. Keep the existing `"common"` and `"nav"` keys unchanged. The new `"dashboard"` object must include all nested keys: `title`, `activeRoutes`, `delayedRoutes`, `metrics`, `calendar`, `events`, `priority`, `weekdays`, `months`.

**Per-task validation:**
- JSON is valid (no trailing commas, proper nesting)
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes

---

### Task 3: Update English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Replace the entire `"dashboard"` key with the expanded English version from the **i18n Keys** section above. Keep existing `"common"` and `"nav"` keys unchanged.

**Per-task validation:**
- JSON is valid
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes

---

### Task 4: Create Type Definitions
**File:** `cms/apps/web/src/types/dashboard.ts` (create)
**Action:** CREATE

Create the file with exact contents from the **Types** section above. Export all types and interfaces.

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes

---

### Task 5: Create Mock Dashboard Data
**File:** `cms/apps/web/src/lib/mock-dashboard-data.ts` (create)
**Action:** CREATE

Create mock data file exporting:

1. `MOCK_METRICS: MetricData[]` — 4 items:
   - Active Vehicles: value "342", delta "+12", deltaType "positive", subtitle "Compared to 330 last month"
   - On-Time Performance: value "94.2%", delta "+2.1%", deltaType "positive", subtitle "Compared to 92.1% last month"
   - Delayed Routes: value "3", delta "+1", deltaType "negative", subtitle "Compared to 2 last month"
   - Fleet Utilization: value "87%", delta "+5%", deltaType "positive", subtitle "Compared to 82% last month"

2. `MOCK_EVENTS: CalendarEvent[]` — 8-10 sample events spread across the current week:
   - Mix of all 4 categories (maintenance, route-change, driver-shift, service-alert)
   - Mix of priorities (high, medium, low)
   - Times between 06:00 and 20:00
   - Use `new Date()` with relative day offsets so events always appear in current week
   - Each event 1-3 hours duration

Import types from `@/types/dashboard`.

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes

---

### Task 6: Create MetricCard Component
**File:** `cms/apps/web/src/components/dashboard/metric-card.tsx` (create)
**Action:** CREATE

```
'use client'
```

Create a reusable metric card component:
- Import `Card, CardContent` from `@/components/ui/card`
- Import `Badge` from `@/components/ui/badge`
- Import `cn` from `@/lib/utils`
- Import `type LucideIcon` from `lucide-react`

Props interface `MetricCardProps`:
- `icon: LucideIcon`
- `title: string`
- `value: string`
- `delta: string`
- `deltaType: 'positive' | 'negative' | 'neutral'`
- `subtitle: string`

Layout (matching screenshot 2.jpg card pattern):
- Card with `bg-surface-raised border-border rounded-lg p-4` (use semantic tokens)
- Top row: Icon (24px, `text-foreground-muted`) + Title (`text-sm text-foreground-muted`) + Delta Badge (right-aligned)
- Value: Large text `text-3xl font-heading font-semibold text-foreground`
- Subtitle: `text-xs text-foreground-muted mt-1`

Delta Badge colors:
- positive: `bg-status-ontime/10 text-status-ontime` (greenish)
- negative: `bg-status-critical/10 text-status-critical` (reddish)
- neutral: `bg-border text-foreground-muted`

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint` passes

---

### Task 7: Create LiveTimeline Component
**File:** `cms/apps/web/src/components/dashboard/live-timeline.tsx` (create)
**Action:** CREATE

```
'use client'
```

- Import `{ useEffect, useState }` from `react`
- Import `cn` from `@/lib/utils`

Logic:
- State: `currentMinuteOfDay` (number, default: calculated from `new Date()`)
- `useEffect` with `setInterval` every 60000ms to update `currentMinuteOfDay`
- Clean up interval on unmount
- Calculate `topPercent` position: `((currentMinuteOfDay - startHour * 60) / ((endHour - startHour) * 60)) * 100`
- Accept props: `startHour: number` (default 6), `endHour: number` (default 22)
- Only render if current time is within startHour–endHour range

Render:
- Absolute positioned `div` at calculated `top` percentage
- Full width horizontal line: `h-[2px] bg-status-critical`
- Left side: small circle `w-2.5 h-2.5 rounded-full bg-status-critical` with subtle pulse animation
- The pulse uses `animate-pulse` (respects `prefers-reduced-motion` via Tailwind defaults)
- z-index: `z-10` to sit above event cards

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint` passes

---

### Task 8: Create CalendarEvent Component
**File:** `cms/apps/web/src/components/dashboard/calendar-event.tsx` (create)
**Action:** CREATE

```
'use client'
```

- Import `Badge` from `@/components/ui/badge`
- Import `cn` from `@/lib/utils`
- Import `type CalendarEvent as CalendarEventType` from `@/types/dashboard`

Props: `{ event: CalendarEventType }`

Layout:
- Container: `rounded-md p-2 text-xs cursor-pointer transition-colors duration-200`
- Background color based on category:
  - maintenance: `bg-blue-400/10 border-l-2 border-l-blue-400`
  - route-change: `bg-amber-400/10 border-l-2 border-l-amber-400`
  - driver-shift: `bg-emerald-500/10 border-l-2 border-l-emerald-500`
  - service-alert: `bg-red-500/10 border-l-2 border-l-red-500`
- Use primitive token colors for the category borders (these are domain-specific, not general UI)
- Title: `font-medium text-foreground truncate`
- Time: `text-foreground-muted` formatted as "HH:MM – HH:MM"
- Priority badge: small inline badge using the priority i18n key

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint` passes

---

### Task 9: Create WeekView Component
**File:** `cms/apps/web/src/components/dashboard/week-view.tsx` (create)
**Action:** CREATE

```
'use client'
```

This is the primary calendar view (default). Reference: screenshot `1.jpg` bottom section.

Props: `{ currentDate: Date, events: CalendarEvent[] }`

Structure:
- **Header row:** 7 columns (Mon–Sun) showing day name + date number. Today's column highlighted with `bg-interactive/10 text-interactive font-semibold`
- **Time column:** Left-most column showing hours from 06:00 to 22:00 (17 rows). `text-xs text-foreground-muted w-16`
- **Grid:** 7 day columns x 17 hour rows. Each cell has `border-b border-border-subtle` horizontal lines
- **Events:** Absolutely positioned within their day column, top calculated from start time, height from duration
- **LiveTimeline:** Render `<LiveTimeline startHour={6} endHour={22} />` inside the grid container with `position: relative`

Use `useTranslations('dashboard')` for weekday names via `t('weekdays.mon')` etc.

Date calculations:
- Get Monday of current week from `currentDate`
- Generate array of 7 dates (Mon–Sun)
- Filter events to those falling within the week
- Group events by day index (0=Mon to 6=Sun)

Grid implementation:
- Use CSS Grid: `grid-cols-[4rem_repeat(7,1fr)]` for time col + 7 day cols
- Each hour row height: `h-16` (64px) — enough for event text
- Container must be `relative` for absolute positioning of events and timeline

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint` passes

---

### Task 10: Create MonthView Component
**File:** `cms/apps/web/src/components/dashboard/month-view.tsx` (create)
**Action:** CREATE

```
'use client'
```

Props: `{ currentDate: Date, events: CalendarEvent[] }`

Structure:
- Standard month grid: 7 columns (Mon–Sun), 5-6 rows of weeks
- Header: weekday labels (`text-xs text-foreground-muted font-medium`)
- Day cells: `min-h-24 p-1 border border-border-subtle rounded-sm`
  - Day number: `text-sm` top-left
  - Today: highlighted with `bg-interactive/10 border-interactive` and pulsing subtle border
  - Days outside current month: `opacity-40`
  - Event indicators: Small colored dots (max 3 visible) + "+N more" text if overflow
- Events filtered by day, show category-colored dots using same colors as CalendarEvent

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint` passes

---

### Task 11: Create ThreeMonthView Component
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx` (create)
**Action:** CREATE

```
'use client'
```

Props: `{ currentDate: Date, events: CalendarEvent[] }`

Structure:
- 3 mini month grids side-by-side in a `grid grid-cols-3 gap-6` layout
- Shows: previous month, current month, next month
- Each mini month: compact header with month name, 7-col grid of small day cells
- Day cells: `w-8 h-8 text-xs flex items-center justify-center rounded-sm`
- Today: `bg-interactive text-white rounded-full`
- Days with events: small dot indicator below the number
- Month name: `font-heading text-sm font-semibold text-foreground`

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint` passes

---

### Task 12: Create YearView Component
**File:** `cms/apps/web/src/components/dashboard/year-view.tsx` (create)
**Action:** CREATE

```
'use client'
```

Props: `{ currentDate: Date, events: CalendarEvent[] }`

Structure:
- 12 mini month grids in a `grid grid-cols-4 gap-4` layout (4 columns x 3 rows)
- Each mini month: tiny month name header, 7-col grid of tiny day squares
- Day squares: `w-4 h-4 rounded-xs` (heat map style)
  - No events: `bg-border-subtle`
  - 1 event: `bg-interactive/30`
  - 2+ events: `bg-interactive/60`
  - 3+ events: `bg-interactive`
- Today: outlined with `ring-1 ring-status-critical`
- Month label: `text-xs font-medium text-foreground-muted`

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint` passes

---

### Task 13: Create CalendarHeader Component
**File:** `cms/apps/web/src/components/dashboard/calendar-header.tsx` (create)
**Action:** CREATE

```
'use client'
```

Props:
- `currentDate: Date`
- `view: CalendarViewMode`
- `onViewChange: (view: CalendarViewMode) => void`
- `onDateChange: (date: Date) => void`

Layout (reference: screenshot 1.jpg "Projects" header with "Today Week Month Year" toggles):
- Left side: Title `t('calendar.title')` with `font-heading text-xl font-semibold`
- Center: navigation arrows (ChevronLeft, ChevronRight from lucide-react) + "Today" button + current date label
  - "Today" button: `Button variant="outline" size="sm"`
  - Date label: formatted month/year based on view mode
  - Arrow buttons: `Button variant="ghost" size="icon-sm"`
- Right side: View mode toggle using `ToggleGroup` with items: Year, 3 Mo, Month, Week
  - Use `t('calendar.year')`, `t('calendar.threeMonth')`, `t('calendar.month')`, `t('calendar.week')` for labels

Navigation behavior:
- Week view: arrows navigate +-1 week
- Month view: arrows navigate +-1 month
- 3-month view: arrows navigate +-3 months
- Year view: arrows navigate +-1 year
- "Today" always resets to current date

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint` passes

---

### Task 14: Create CalendarGrid Container
**File:** `cms/apps/web/src/components/dashboard/calendar-grid.tsx` (create)
**Action:** CREATE

```
'use client'
```

This is the orchestrator that renders CalendarHeader + the active view component.

Props: `{ events: CalendarEvent[] }`

State:
- `view: CalendarViewMode` — default `'week'`
- `currentDate: Date` — default `new Date()`

Render:
- `CalendarHeader` with view/date state and handlers
- Conditional render based on `view`:
  - `'week'` → `<WeekView currentDate={currentDate} events={events} />`
  - `'month'` → `<MonthView currentDate={currentDate} events={events} />`
  - `'3month'` → `<ThreeMonthView currentDate={currentDate} events={events} />`
  - `'year'` → `<YearView currentDate={currentDate} events={events} />`
- Wrap view in a container with `border border-border rounded-lg bg-surface-raised overflow-hidden`

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint` passes

---

### Task 15: Replace Dashboard Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` (modify — full replacement)
**Action:** UPDATE

Replace the entire file content with:

```
'use client'
```

Imports:
- `useTranslations` from `next-intl`
- `MetricCard` from `@/components/dashboard/metric-card`
- `CalendarGrid` from `@/components/dashboard/calendar-grid`
- `MOCK_METRICS, MOCK_EVENTS` from `@/lib/mock-dashboard-data`
- Icons from `lucide-react`: `Bus, Clock, AlertTriangle, Gauge`

Layout:
- Container: `space-y-6`
- Header: `<h1 className="font-heading text-2xl font-semibold text-foreground">{t('title')}</h1>`
- Metrics section: `<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">`
  - 4 `MetricCard` components mapping MOCK_METRICS with icons:
    - Active Vehicles → `Bus`
    - On-Time Performance → `Clock`
    - Delayed Routes → `AlertTriangle`
    - Fleet Utilization → `Gauge`
  - Use `t('metrics.activeVehicles')` etc. for titles (not the mock data titles)
- Calendar section: `<CalendarGrid events={MOCK_EVENTS} />`

**Per-task validation:**
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint` passes
- `cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web build` passes

---

## Final Validation (3-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: TypeScript**
```bash
cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web type-check
```

**Level 2: Lint**
```bash
cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web lint
```

**Level 3: Build**
```bash
cd /Users/Berzins/Desktop/AI/VTV/cms && pnpm --filter @vtv/web build
```

**Success definition:** All 3 levels exit code 0, zero errors.

## Post-Implementation Checks

- [ ] Dashboard renders at `/{locale}/` with metric cards and calendar
- [ ] i18n keys present in both lv.json and en.json (check all nested keys)
- [ ] No middleware changes needed (dashboard already accessible)
- [ ] No sidebar changes needed (dashboard link already present)
- [ ] No hardcoded colors — all styling uses semantic tokens from tokens.css
- [ ] Live red timeline visible in Week view, updates position every 60 seconds
- [ ] All 4 view modes work: Year, 3 Month, Month, Week
- [ ] View toggle switches views correctly
- [ ] Navigation arrows move date forward/backward per view mode
- [ ] "Today" button resets to current date
- [ ] Metric cards show delta badges with correct colors (green for positive, red for negative)
- [ ] Calendar events show with category-colored left borders
- [ ] Accessibility: all interactive elements have ARIA labels, buttons have focus rings
- [ ] Week view: events positioned correctly by time, timeline at current hour
- [ ] Month view: today highlighted, event dots visible
- [ ] Responsive: cards stack on mobile (sm:grid-cols-2, lg:grid-cols-4)

## Acceptance Criteria

This feature is complete when:
- [ ] Dashboard page enhanced with metric cards and multi-view calendar
- [ ] Live timeline indicator works in Week view
- [ ] All 4 calendar views render correctly (Year, 3-Month, Month, Week)
- [ ] Both languages have complete translations for all new keys
- [ ] Design system rules followed (MASTER.md tokens, no hardcoded colors)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages (login, unauthorized still work)
- [ ] Ready for `/commit`
