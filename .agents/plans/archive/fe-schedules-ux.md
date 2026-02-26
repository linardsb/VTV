# Plan: Schedules Page UX & Calendar Management Improvements

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: High
**Route**: `/[locale]/(dashboard)/schedules`
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer (viewer = read-only)

## Feature Description

The Schedules page (`/schedules`) is a feature-complete CRUD interface with three tabs (Calendars, Trips, Import & Validate) but the calendar management workflow has several usability gaps that slow down transit schedulers.

**Current workflow problems identified:**

1. **No visual calendar view** — Calendars are shown as flat table rows with tiny check/cross icons for days. A transit scheduler cannot quickly see which dates a service covers. They must mentally calculate "Monday–Friday from Jan 1 to Jun 30" with no visual confirmation.

2. **No status awareness** — The table shows no indication of whether a calendar is currently active, expired, or upcoming. Schedulers must compare date ranges against today's date manually.

3. **No search or filtering** — With 50+ calendars after GTFS import, finding a specific service requires paginating through the table. There's no text search or "active today" quick filter.

4. **Raw ISO dates** — The calendar table displays `2026-01-01 — 2026-06-30` instead of locale-formatted dates like "1. janvāris 2026 — 30. jūnijs 2026".

5. **Tedious day-of-week selection** — Creating a new calendar requires toggling 7 individual switches. No preset buttons for common patterns (Weekdays, Weekends, Daily).

6. **No form validation feedback** — End date before start date is silently accepted by the form (backend rejects it, but the user gets only a generic error toast).

7. **Calendar exceptions never load** — The CalendarDetail sheet always shows "No exceptions" because there's no `GET /calendars/{id}/exceptions` endpoint. (The backend repository has `list_calendar_dates()` but it's not exposed via a route.)

8. **Tab state lost on refresh** — Navigating to the Trips tab and refreshing returns to the Calendars tab. No URL persistence for active tab.

9. **Trip search missing** — Trips can be filtered by route/calendar/direction but not searched by trip ID or headsign text.

10. **Fake import progress** — The progress bar jumps 20% → 50% → 100% without tracking actual upload progress.

**This plan addresses items 1–6 and 8–10 purely on the frontend.** Item 7 (exceptions loading) requires a backend route addition — noted as a future prerequisite.

## Design System

### Master Rules (from MASTER.md)
- Typography: Lexend headings, Source Sans 3 body, JetBrains Mono for IDs/codes
- Spacing: Use semantic spacing tokens via `gap-(--spacing-grid)`, `p-(--spacing-card)` etc.
- Buttons: 8px radius, 200ms transitions, cursor-pointer required
- Accessibility: 4.5:1 contrast, visible focus rings, 44x44px touch targets, keyboard nav
- Anti-patterns: No emojis as icons, no layout-shifting hovers, no primitive Tailwind colors

### Page Override
None exists — no file at `cms/design-system/vtv/pages/schedules.md`.

### Tokens Used
- **Surface**: `bg-surface`, `bg-surface-raised`, `bg-muted`, `bg-background`
- **Text**: `text-foreground`, `text-foreground-muted`, `text-foreground-subtle`, `text-label-text`
- **Interactive**: `bg-interactive`, `text-interactive`, `text-interactive-foreground`
- **Status**: `bg-status-ontime/10`, `text-status-ontime`, `text-status-delayed`, `text-status-critical`, `border-status-ontime/30`
- **Border**: `border-border`
- **Spacing**: `--spacing-card` (12px), `--spacing-grid` (12px), `--spacing-tight` (4px), `--spacing-inline` (6px), `--spacing-page` (16px)

## Components Needed

### Existing (shadcn/ui)
- `Button` — filter buttons, presets, actions
- `Input` — search input, date inputs
- `Badge` — status badges, day indicators
- `Table` — calendar/trip tables (existing)
- `Select` — filters (existing)
- `Sheet` — detail/form panels (existing)
- `Tabs` — tab container (existing)
- `Tooltip` — hover info on calendar grid cells
- `Switch` — day toggles in form (existing)
- `Skeleton` — loading states (existing)
- `Progress` — import progress (existing)
- `ToggleGroup` — day preset selector in form

### New shadcn/ui to Install
None — all needed components are already installed.

### Custom Components to Create
- `CalendarMonthGrid` at `cms/apps/web/src/components/schedules/calendar-month-grid.tsx` — Visual month grid showing which days a calendar service operates
- `CalendarStatusBadge` at `cms/apps/web/src/components/schedules/calendar-status-badge.tsx` — Active/Expired/Upcoming status badge
- `CalendarSearch` at `cms/apps/web/src/components/schedules/calendar-search.tsx` — Search bar with "active today" toggle
- `TripSearch` at `cms/apps/web/src/components/schedules/trip-search.tsx` — Trip ID / headsign text search

## i18n Keys

### Latvian (`lv.json`) — ADD to `schedules.calendars`
```json
{
  "search": "Meklēt kalendārus...",
  "activeToday": "Aktīvi šodien",
  "statusActive": "Aktīvs",
  "statusExpired": "Beidzies",
  "statusUpcoming": "Gaidāms",
  "presetWeekdays": "Darba dienas",
  "presetWeekend": "Brīvdienas",
  "presetDaily": "Katru dienu",
  "presetClear": "Notīrīt",
  "dateValidation": "Beigu datumam jābūt pēc sākuma datuma",
  "monthGrid": "Mēneša skats",
  "today": "Šodien",
  "prevMonth": "Iepriekšējais mēnesis",
  "nextMonth": "Nākamais mēnesis",
  "gridActive": "Aktīva diena",
  "gridInactive": "Neaktīva diena"
}
```

### English (`en.json`) — ADD to `schedules.calendars`
```json
{
  "search": "Search calendars...",
  "activeToday": "Active today",
  "statusActive": "Active",
  "statusExpired": "Expired",
  "statusUpcoming": "Upcoming",
  "presetWeekdays": "Weekdays",
  "presetWeekend": "Weekend",
  "presetDaily": "Daily",
  "presetClear": "Clear",
  "dateValidation": "End date must be after start date",
  "monthGrid": "Month view",
  "today": "Today",
  "prevMonth": "Previous month",
  "nextMonth": "Next month",
  "gridActive": "Active day",
  "gridInactive": "Inactive day"
}
```

### Latvian (`lv.json`) — ADD to `schedules.trips`
```json
{
  "search": "Meklēt reisus...",
  "searchPlaceholder": "Reisa ID vai galapunkts..."
}
```

### English (`en.json`) — ADD to `schedules.trips`
```json
{
  "search": "Search trips...",
  "searchPlaceholder": "Trip ID or headsign..."
}
```

## Data Fetching

- **API endpoints used**: All existing endpoints in `schedules-client.ts` — no new backend endpoints required
- **Calendar "active today" filter**: Uses existing `fetchCalendars({ active_on: "YYYY-MM-DD" })` backend parameter
- **Calendar search**: Client-side filtering on `gtfs_service_id` text match (already loaded for lookup)
- **Trip search**: Add `search` query parameter to `fetchTrips()` — **check if backend supports it**; if not, do client-side filtering on loaded trips
- **Server vs Client**: All data loads client-side (existing pattern, session-gated)
- **Loading states**: Existing skeleton pattern maintained

**CRITICAL — Server/client boundary:**
- `authFetch` handles dual-context (server/client) automatically — no changes needed
- All schedule components are already `"use client"` — no SSR boundary issues

## RBAC Integration
No changes — existing middleware matcher and `IS_READ_ONLY` gating remain as-is.

## Sidebar Navigation
No changes — existing "Schedules" nav link remains as-is.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/schedules/page.tsx` — Current page (MODIFY)
- `cms/apps/web/src/components/schedules/calendar-table.tsx` — Current table (MODIFY)
- `cms/apps/web/src/components/schedules/calendar-detail.tsx` — Current detail (MODIFY)
- `cms/apps/web/src/components/schedules/calendar-form.tsx` — Current form (MODIFY)
- `cms/apps/web/src/components/schedules/trip-filters.tsx` — Filter pattern reference
- `cms/apps/web/src/components/dashboard/calendar-grid.tsx` — Month grid pattern reference (if exists)

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add Latvian translations
- `cms/apps/web/messages/en.json` — Add English translations
- `cms/apps/web/src/app/[locale]/(dashboard)/schedules/page.tsx` — Add tab URL sync, search state, pass new props
- `cms/apps/web/src/components/schedules/calendar-table.tsx` — Add status badge, locale dates
- `cms/apps/web/src/components/schedules/calendar-detail.tsx` — Add CalendarMonthGrid
- `cms/apps/web/src/components/schedules/calendar-form.tsx` — Add day presets, date validation
- `cms/apps/web/src/components/schedules/gtfs-import.tsx` — Fix fake progress
- `cms/apps/web/src/components/schedules/trip-table.tsx` — Minor: pass search prop

### Files to Create
- `cms/apps/web/src/components/schedules/calendar-month-grid.tsx` — NEW
- `cms/apps/web/src/components/schedules/calendar-status-badge.tsx` — NEW
- `cms/apps/web/src/components/schedules/calendar-search.tsx` — NEW
- `cms/apps/web/src/components/schedules/trip-search.tsx` — NEW

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Common violations and their fixes:

| Forbidden Class | Use Instead |
|----------------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400`, `text-slate-400` | `text-foreground-subtle` |
| `text-white` (on colored bg) | `text-interactive-foreground` / `text-primary-foreground` |
| `text-blue-*`, `text-red-*`, `text-green-*` | `text-primary`, `text-error`, `text-success` |
| `bg-blue-600`, `bg-blue-500` | `bg-primary` or `bg-interactive` |
| `bg-red-500`, `bg-red-600` | `bg-destructive` |
| `bg-green-500`, `bg-emerald-500` | `bg-success` or `bg-status-ontime` |
| `bg-amber-400`, `bg-amber-500` | `bg-status-delayed` |
| `bg-gray-100`, `bg-slate-100` | `bg-surface` / `bg-muted` |
| `border-gray-200` | `border-border` |

## React 19 Coding Rules

- **No `setState` in `useEffect`** — use `key` prop on component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies**
- **Const placeholders for runtime values** — annotate as `string` to avoid TS2367

## TypeScript Security Rules

- **Never use `as` casts on external data without runtime validation**
- **Clear `.next` cache when module resolution errors persist after fixing imports**

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Add i18n Keys (Latvian)
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add the following keys inside `schedules.calendars`:
```json
"search": "Meklēt kalendārus...",
"activeToday": "Aktīvi šodien",
"statusActive": "Aktīvs",
"statusExpired": "Beidzies",
"statusUpcoming": "Gaidāms",
"presetWeekdays": "Darba dienas",
"presetWeekend": "Brīvdienas",
"presetDaily": "Katru dienu",
"presetClear": "Notīrīt",
"dateValidation": "Beigu datumam jābūt pēc sākuma datuma",
"monthGrid": "Mēneša skats",
"today": "Šodien",
"prevMonth": "Iepriekšējais mēnesis",
"nextMonth": "Nākamais mēnesis",
"gridActive": "Aktīva diena",
"gridInactive": "Neaktīva diena"
```

Add the following keys inside `schedules.trips`:
```json
"search": "Meklēt reisus...",
"searchPlaceholder": "Reisa ID vai galapunkts..."
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: Add i18n Keys (English)
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add matching keys inside `schedules.calendars`:
```json
"search": "Search calendars...",
"activeToday": "Active today",
"statusActive": "Active",
"statusExpired": "Expired",
"statusUpcoming": "Upcoming",
"presetWeekdays": "Weekdays",
"presetWeekend": "Weekend",
"presetDaily": "Daily",
"presetClear": "Clear",
"dateValidation": "End date must be after start date",
"monthGrid": "Month view",
"today": "Today",
"prevMonth": "Previous month",
"nextMonth": "Next month",
"gridActive": "Active day",
"gridInactive": "Inactive day"
```

Add matching keys inside `schedules.trips`:
```json
"search": "Search trips...",
"searchPlaceholder": "Trip ID or headsign..."
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Create CalendarStatusBadge Component
**File:** `cms/apps/web/src/components/schedules/calendar-status-badge.tsx` (create)
**Action:** CREATE

Create a small component that determines calendar status from `start_date` and `end_date`:

```tsx
"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";

interface CalendarStatusBadgeProps {
  startDate: string;
  endDate: string;
}

export function CalendarStatusBadge({ startDate, endDate }: CalendarStatusBadgeProps) {
  const t = useTranslations("schedules.calendars");
  const today = new Date().toISOString().split("T")[0];

  // Compare as ISO strings (YYYY-MM-DD) — lexicographic comparison works
  const isActive = startDate <= today && today <= endDate;
  const isExpired = endDate < today;
  // Otherwise it's upcoming

  if (isActive) {
    return (
      <Badge variant="outline" className="border-status-ontime/30 bg-status-ontime/10 text-status-ontime text-xs">
        {t("statusActive")}
      </Badge>
    );
  }

  if (isExpired) {
    return (
      <Badge variant="outline" className="border-border text-foreground-subtle text-xs">
        {t("statusExpired")}
      </Badge>
    );
  }

  return (
    <Badge variant="outline" className="border-status-delayed/30 bg-status-delayed/10 text-status-delayed text-xs">
      {t("statusUpcoming")}
    </Badge>
  );
}
```

Key decisions:
- Uses ISO string comparison (lexicographic YYYY-MM-DD works correctly)
- `today` computed from `new Date()` outside render — not inside useMemo (simple enough)
- Status logic: `start ≤ today ≤ end` = Active, `end < today` = Expired, else = Upcoming
- Uses existing status semantic tokens (ontime=active, delayed=upcoming, subtle=expired)

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 4: Create CalendarSearch Component
**File:** `cms/apps/web/src/components/schedules/calendar-search.tsx` (create)
**Action:** CREATE

Create a search bar with "Active today" toggle filter:

```tsx
"use client";

import { useTranslations } from "next-intl";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CalendarSearchProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  activeTodayFilter: boolean;
  onActiveTodayChange: (active: boolean) => void;
}

export function CalendarSearch({
  searchQuery,
  onSearchChange,
  activeTodayFilter,
  onActiveTodayChange,
}: CalendarSearchProps) {
  const t = useTranslations("schedules.calendars");

  return (
    <div className="flex items-center gap-(--spacing-inline)">
      <div className="relative w-56">
        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-foreground-muted" aria-hidden="true" />
        <Input
          placeholder={t("search")}
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9 h-9"
        />
      </div>
      <Button
        variant="outline"
        size="sm"
        className={cn(
          "cursor-pointer text-xs",
          activeTodayFilter && "bg-interactive text-interactive-foreground hover:bg-interactive/90"
        )}
        onClick={() => onActiveTodayChange(!activeTodayFilter)}
      >
        {t("activeToday")}
      </Button>
    </div>
  );
}
```

Key decisions:
- Search icon inside input (consistent with route search pattern)
- "Active today" is a toggle button that changes appearance when active
- Props-based: state managed by parent page component

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 5: Create CalendarMonthGrid Component
**File:** `cms/apps/web/src/components/schedules/calendar-month-grid.tsx` (create)
**Action:** CREATE

This is the centerpiece UX improvement — a visual month grid showing which days a calendar service operates.

Create a month-view calendar grid component:

```tsx
"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { Calendar } from "@/types/schedule";

interface CalendarMonthGridProps {
  calendar: Calendar;
}

const DAY_KEYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"] as const;

export function CalendarMonthGrid({ calendar }: CalendarMonthGridProps) {
  const t = useTranslations("schedules.calendars");
  const tDays = useTranslations("schedules.days");

  // Initialize to the calendar's start month, clamped to today if active
  const today = new Date();
  const startDate = new Date(calendar.start_date + "T00:00:00");
  const endDate = new Date(calendar.end_date + "T00:00:00");
  const initialDate = today >= startDate && today <= endDate ? today : startDate;

  const [viewYear, setViewYear] = useState(initialDate.getFullYear());
  const [viewMonth, setViewMonth] = useState(initialDate.getMonth());

  const daysInMonth = useMemo(() => {
    const firstDay = new Date(viewYear, viewMonth, 1);
    const lastDay = new Date(viewYear, viewMonth + 1, 0);
    const startPad = firstDay.getDay(); // 0=Sun

    const days: Array<{ date: Date; inMonth: boolean; isActive: boolean; isToday: boolean }> = [];

    // Padding days from previous month
    for (let i = 0; i < startPad; i++) {
      const d = new Date(viewYear, viewMonth, -startPad + i + 1);
      days.push({ date: d, inMonth: false, isActive: false, isToday: false });
    }

    // Days in current month
    for (let d = 1; d <= lastDay.getDate(); d++) {
      const date = new Date(viewYear, viewMonth, d);
      const dayOfWeek = date.getDay(); // 0=Sun, 1=Mon, ...
      const dayKey = DAY_KEYS[dayOfWeek];
      const inRange = date >= startDate && date <= endDate;
      const dayEnabled = calendar[dayKey as keyof Calendar] as boolean;
      const isActive = inRange && dayEnabled;
      const isToday = date.toDateString() === today.toDateString();
      days.push({ date, inMonth: true, isActive, isToday });
    }

    // Padding days to complete the last week
    const remaining = 7 - (days.length % 7);
    if (remaining < 7) {
      for (let i = 1; i <= remaining; i++) {
        const d = new Date(viewYear, viewMonth + 1, i);
        days.push({ date: d, inMonth: false, isActive: false, isToday: false });
      }
    }

    return days;
  }, [viewYear, viewMonth, calendar, startDate, endDate, today]);

  const monthLabel = new Intl.DateTimeFormat(undefined, { year: "numeric", month: "long" }).format(
    new Date(viewYear, viewMonth)
  );

  function prevMonth() {
    if (viewMonth === 0) { setViewYear((y) => y - 1); setViewMonth(11); }
    else { setViewMonth((m) => m - 1); }
  }

  function nextMonth() {
    if (viewMonth === 11) { setViewYear((y) => y + 1); setViewMonth(0); }
    else { setViewMonth((m) => m + 1); }
  }

  // Week header: Sun Mon Tue Wed Thu Fri Sat (short labels)
  const weekHeaders = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

  return (
    <div className="space-y-(--spacing-tight)">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-label-text uppercase tracking-wide">
          {t("monthGrid")}
        </p>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" className="size-7 p-0 cursor-pointer" onClick={prevMonth} aria-label={t("prevMonth")}>
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-xs font-medium text-foreground min-w-[120px] text-center">{monthLabel}</span>
          <Button variant="ghost" size="sm" className="size-7 p-0 cursor-pointer" onClick={nextMonth} aria-label={t("nextMonth")}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-px rounded-md border border-border overflow-hidden bg-border">
        {/* Week day headers */}
        {weekHeaders.map((day) => (
          <div key={day} className="bg-surface py-1 text-center text-[10px] font-medium text-foreground-muted uppercase">
            {tDays(day)}
          </div>
        ))}
        {/* Day cells */}
        <TooltipProvider delayDuration={200}>
          {daysInMonth.map((day, i) => (
            <Tooltip key={i}>
              <TooltipTrigger asChild>
                <div
                  className={cn(
                    "flex items-center justify-center py-1.5 text-xs transition-colors",
                    !day.inMonth && "bg-surface text-foreground-subtle",
                    day.inMonth && !day.isActive && "bg-background text-foreground-muted",
                    day.inMonth && day.isActive && "bg-status-ontime/15 text-status-ontime font-medium",
                    day.isToday && "ring-1 ring-inset ring-interactive"
                  )}
                >
                  {day.date.getDate()}
                </div>
              </TooltipTrigger>
              <TooltipContent side="top" className="text-xs">
                {day.isActive ? t("gridActive") : t("gridInactive")}
              </TooltipContent>
            </Tooltip>
          ))}
        </TooltipProvider>
      </div>

      {/* Today indicator */}
      <div className="flex items-center gap-1.5 text-[10px] text-foreground-muted">
        <span className="inline-block size-2.5 rounded-sm ring-1 ring-interactive" />
        <span>{t("today")}</span>
        <span className="ml-2 inline-block size-2.5 rounded-sm bg-status-ontime/15" />
        <span>{t("gridActive")}</span>
      </div>
    </div>
  );
}
```

Key decisions:
- Grid starts on Sunday (standard calendar layout, `getDay()` returns 0=Sun)
- Active day = in date range AND matching day-of-week boolean
- Today highlighted with ring (blue interactive border)
- Active days get green tint (status-ontime/15)
- Inactive days are plain background
- Month navigation with arrow buttons
- Tooltip on each cell for accessibility
- Legend at bottom showing what colors mean
- Initializes to current month if calendar is active, otherwise to calendar start month

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: Create TripSearch Component
**File:** `cms/apps/web/src/components/schedules/trip-search.tsx` (create)
**Action:** CREATE

Create a search input for trips (ID or headsign):

```tsx
"use client";

import { useTranslations } from "next-intl";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";

interface TripSearchProps {
  value: string;
  onChange: (value: string) => void;
}

export function TripSearch({ value, onChange }: TripSearchProps) {
  const t = useTranslations("schedules.trips");

  return (
    <div className="relative w-56">
      <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-foreground-muted" aria-hidden="true" />
      <Input
        placeholder={t("searchPlaceholder")}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="pl-9 h-9"
      />
    </div>
  );
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: Update CalendarTable — Add Status Badge & Locale Dates
**File:** `cms/apps/web/src/components/schedules/calendar-table.tsx` (modify)
**Action:** UPDATE

1. **Import** `CalendarStatusBadge` from `./calendar-status-badge`
2. **Import** `useLocale` from `next-intl`
3. **Add a "Status" column** after the date range column:
   - Header: `{t("status")}` (add `"status": "Statuss"` / `"Status"` to i18n if not already present — BUT note this key doesn't exist yet. Use a column-level key or add it)
   - Cell: `<CalendarStatusBadge startDate={cal.start_date} endDate={cal.end_date} />`
   - Hide on mobile: `hidden lg:table-cell`
4. **Format date range with locale**: Replace raw `{cal.start_date} — {cal.end_date}` with:
   ```tsx
   const locale = useLocale();
   const dateFormatter = new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric" });
   // In the cell:
   {dateFormatter.format(new Date(cal.start_date))} — {dateFormatter.format(new Date(cal.end_date))}
   ```
   NOTE: `dateFormatter` must be created inside the component body (not in a useMemo per-row). Create it once with `useMemo` depending on `locale`.

Also add i18n key `"status": "Statuss"` to `lv.json` and `"status": "Status"` to `en.json` inside `schedules.calendars`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 8: Update CalendarDetail — Add Month Grid
**File:** `cms/apps/web/src/components/schedules/calendar-detail.tsx` (modify)
**Action:** UPDATE

1. **Import** `CalendarMonthGrid` from `./calendar-month-grid`
2. **Add** `<CalendarMonthGrid calendar={calendar} />` between the "Operating days" section and the Exceptions section (after the existing `<Separator />`, before the exceptions heading).
3. **Add** a `<Separator />` after the grid.

The placement should be:
```
- Operating days badges
- Date range
- <Separator />
- <CalendarMonthGrid calendar={calendar} />    ← NEW
- <Separator />                                 ← NEW
- Exceptions section
- Actions
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 9: Update CalendarForm — Add Day Presets & Date Validation
**File:** `cms/apps/web/src/components/schedules/calendar-form.tsx` (modify)
**Action:** UPDATE

**Day presets** — Add preset buttons above the day toggles:

1. Import `ToggleGroup`, `ToggleGroupItem` from `@/components/ui/toggle-group` (already installed)
2. Add a row of 4 small buttons above the day switches:
   - **Weekdays** — sets Mon-Fri true, Sat-Sun false
   - **Weekend** — sets Mon-Fri false, Sat-Sun true
   - **Daily** — sets all true
   - **Clear** — sets all false
3. Implementation:
   ```tsx
   function applyPreset(preset: "weekdays" | "weekend" | "daily" | "clear") {
     const presets = {
       weekdays: { monday: true, tuesday: true, wednesday: true, thursday: true, friday: true, saturday: false, sunday: false },
       weekend: { monday: false, tuesday: false, wednesday: false, thursday: false, friday: false, saturday: true, sunday: true },
       daily: { monday: true, tuesday: true, wednesday: true, thursday: true, friday: true, saturday: true, sunday: true },
       clear: { monday: false, tuesday: false, wednesday: false, thursday: false, friday: false, saturday: false, sunday: false },
     };
     setForm((prev) => ({ ...prev, ...presets[preset] }));
   }
   ```
4. Render as small outline buttons in a flex row below the "Operating Days" label, above the switches.

**Date validation** — Add client-side validation:

1. In `handleSubmit`, before calling `onSubmit`, check:
   ```tsx
   if (form.end_date < form.start_date) {
     toast.error(t("dateValidation"));
     return;
   }
   ```
2. Import `toast` from `sonner`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Update Page — Tab URL Sync, Search State, Wiring
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/schedules/page.tsx` (modify)
**Action:** UPDATE

This is the most complex task — wire everything together in the page component.

**10a. Tab state from URL search params:**

1. Import `useSearchParams` and `useRouter` from `next/navigation`
2. Read initial tab from URL: `const searchParams = useSearchParams(); const initialTab = searchParams.get("tab") ?? "calendars";`
3. Add state: `const [activeTab, setActiveTab] = useState(initialTab);`
4. Update URL when tab changes:
   ```tsx
   const router = useRouter();
   const pathname = usePathname(); // from next/navigation
   function handleTabChange(tab: string) {
     setActiveTab(tab);
     const params = new URLSearchParams(searchParams.toString());
     if (tab === "calendars") { params.delete("tab"); } else { params.set("tab", tab); }
     const qs = params.toString();
     router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
   }
   ```
5. Change `<Tabs defaultValue="calendars">` to `<Tabs value={activeTab} onValueChange={handleTabChange}>`

**10b. Calendar search & "active today" filter state:**

1. Add state: `const [calendarSearch, setCalendarSearch] = useState("");`
2. Add state: `const [activeTodayFilter, setActiveTodayFilter] = useState(false);`
3. Modify `loadCalendars` to pass `active_on` when filter is active:
   ```tsx
   const loadCalendars = useCallback(async () => {
     setIsCalendarLoading(true);
     try {
       const result = await fetchCalendars({
         page: calendarPage,
         page_size: PAGE_SIZE,
         active_on: activeTodayFilter ? new Date().toISOString().split("T")[0] : undefined,
       });
       setCalendars(result.items);
       setCalendarTotal(result.total);
     } catch (e) {
       console.warn("[schedules] Failed to load calendars:", e);
       setCalendars([]);
       setCalendarTotal(0);
     } finally {
       setIsCalendarLoading(false);
     }
   }, [calendarPage, activeTodayFilter]);
   ```
4. Add `useMemo` for client-side search filtering:
   ```tsx
   const filteredCalendars = useMemo(() => {
     if (!calendarSearch.trim()) return calendars;
     const q = calendarSearch.toLowerCase();
     return calendars.filter((c) => c.gtfs_service_id.toLowerCase().includes(q));
   }, [calendars, calendarSearch]);
   ```
5. Pass `filteredCalendars` to `<CalendarTable>` instead of `calendars`
6. Reset `calendarPage` to 1 when `activeTodayFilter` changes (add `useEffect` or handle in the toggle callback)
7. Handle "active today" toggle:
   ```tsx
   function handleActiveTodayChange(active: boolean) {
     setActiveTodayFilter(active);
     setCalendarPage(1);
   }
   ```

**10c. Trip search state:**

1. Add state: `const [tripSearch, setTripSearch] = useState("");`
2. Add `useMemo` for client-side search filtering:
   ```tsx
   const filteredTrips = useMemo(() => {
     if (!tripSearch.trim()) return trips;
     const q = tripSearch.toLowerCase();
     return trips.filter((t) =>
       t.gtfs_trip_id.toLowerCase().includes(q) ||
       (t.trip_headsign?.toLowerCase().includes(q) ?? false)
     );
   }, [trips, tripSearch]);
   ```
3. Pass `filteredTrips` to `<TripTable>` instead of `trips`

**10d. Wire CalendarSearch into calendar tab header:**

1. Import `CalendarSearch` from `@/components/schedules/calendar-search`
2. In the Calendars tab content, replace the existing toolbar div with:
   ```tsx
   <div className="flex items-center justify-between border-b border-border px-(--spacing-card) py-(--spacing-tight)">
     <CalendarSearch
       searchQuery={calendarSearch}
       onSearchChange={setCalendarSearch}
       activeTodayFilter={activeTodayFilter}
       onActiveTodayChange={handleActiveTodayChange}
     />
     {!IS_READ_ONLY && (
       <Button size="sm" className="cursor-pointer" onClick={handleCalendarCreate}>
         <Plus className="mr-1 size-4" aria-hidden="true" />
         {t("calendars.create")}
       </Button>
     )}
   </div>
   ```
   NOTE: Currently the toolbar only shows the "New Calendar" button (conditionally). Now it ALWAYS shows the search bar + conditionally the create button. Adjust the layout so the toolbar row always renders.

**10e. Wire TripSearch into trip tab header:**

1. Import `TripSearch` from `@/components/schedules/trip-search`
2. In the Trips tab content, add `<TripSearch value={tripSearch} onChange={setTripSearch} />` in the filter bar alongside `TripFilters`:
   ```tsx
   <div className="flex items-center justify-between border-b border-border px-(--spacing-card) py-(--spacing-tight)">
     <div className="flex items-center gap-(--spacing-inline) flex-wrap">
       <TripSearch value={tripSearch} onChange={setTripSearch} />
       <TripFilters ... />
     </div>
     {!IS_READ_ONLY && ( ... )}
   </div>
   ```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 11: Fix Import Progress Bar
**File:** `cms/apps/web/src/components/schedules/gtfs-import.tsx` (modify)
**Action:** UPDATE

The current progress bar fakes progress (20% → 50% → 100%). Replace with an indeterminate state during upload:

1. Remove `uploadProgress` state and `setUploadProgress` calls
2. During upload, show the `<Progress>` component with indeterminate animation:
   - Set `value={undefined}` or use a CSS animation approach
   - Actually, shadcn `<Progress>` doesn't support indeterminate natively. Instead, use a pulsing animation:
   ```tsx
   {isUploading && (
     <div className="space-y-(--spacing-tight)">
       <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
         <div className="h-full w-1/3 animate-pulse rounded-full bg-interactive" />
       </div>
       <p className="text-xs text-foreground-muted text-center">{t("importing")}</p>
     </div>
   )}
   ```
3. Remove `uploadProgress` state variable entirely.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 12: Add Missing Status i18n Key
**File:** `cms/apps/web/messages/lv.json` and `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

If not already added in Task 1/2, add inside `schedules.calendars`:
- `lv.json`: `"status": "Statuss"`
- `en.json`: `"status": "Status"`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

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

- [ ] Calendar table shows status badges (Active/Expired/Upcoming) on each row
- [ ] Calendar table shows locale-formatted dates (not raw ISO strings)
- [ ] Calendar search filters by service ID text
- [ ] "Active today" toggle filter works (fetches with `active_on` param)
- [ ] CalendarDetail sheet shows visual month grid with active days highlighted
- [ ] Month grid navigation (prev/next) works correctly
- [ ] Today is highlighted with a blue ring in the month grid
- [ ] Calendar form has Weekdays/Weekend/Daily/Clear preset buttons
- [ ] Calendar form validates end date > start date before submit
- [ ] Tab state persists in URL (`?tab=trips`, `?tab=import`)
- [ ] Refreshing the page preserves the active tab
- [ ] Trip search filters by trip ID or headsign text
- [ ] Import progress shows honest indeterminate animation (no fake percentages)
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] All new strings use `useTranslations()` — no hardcoded text
- [ ] Accessibility: all interactive elements have labels, month grid cells have tooltips

## Acceptance Criteria

This feature is complete when:
- [ ] All 12 tasks completed with per-task validation passing
- [ ] All 3 final validation levels pass (type-check, lint, build)
- [ ] Visual month grid renders correctly in CalendarDetail sheet
- [ ] Calendar status badges display correctly for active/expired/upcoming calendars
- [ ] Search and filter functionality works on both Calendars and Trips tabs
- [ ] Tab URL persistence works (deep-link `?tab=trips`)
- [ ] Form presets and date validation improve creation workflow
- [ ] No regressions in existing CRUD operations
- [ ] Both lv and en languages have complete translations
- [ ] Ready for `/commit`

## Future Improvements (Out of Scope)

1. **Calendar exceptions loading** — Requires backend `GET /calendars/{id}/exceptions` endpoint. The repository method `list_calendar_dates(calendar_id)` exists but is not exposed via a route. Once the backend adds this endpoint, add `fetchCalendarExceptions(calendarId)` to `schedules-client.ts` and wire it into CalendarDetail.
2. **Exception visualization in month grid** — Once exceptions load, color exception-added days with `bg-status-delayed/15` and exception-removed days with `bg-status-critical/15`.
3. **Bulk calendar actions** — Multi-select for bulk delete/status change.
4. **Calendar coverage heatmap** — Show all calendars overlaid on a month grid to identify gaps.
5. **Trip search via backend** — Add `search` query parameter to backend `GET /trips` for server-side filtering (currently client-side).

## Security Checklist
- [x] No hardcoded credentials
- [x] No `dangerouslySetInnerHTML`
- [x] External links use `rel="noopener noreferrer"` (none added)
- [x] User input displayed via React JSX (auto-escaped)
- [x] Redirects preserve locale (no new redirects)
- [x] All cookies set with `SameSite=Lax` (no new cookies)
- [x] Auth tokens in httpOnly cookies only (no changes to auth flow)
