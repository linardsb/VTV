# Plan: Fix Calendar Mixed-Language Bug

## Feature Metadata
**Feature Type**: Bug Fix
**Estimated Complexity**: Low-Medium
**Route**: N/A (existing dashboard page)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer

## Problem Statement

The calendar views display a mix of two languages: the UI chrome (weekday headers, month names, view toggle buttons, "Šodien" button) is correctly translated to the active locale via `useTranslations()`, but all **event titles** are hardcoded English strings from mock data in `mock-dashboard-data.ts`.

**Screenshot evidence:** The calendar shows Latvian headers ("Pr", "Ot", "Tr", "Ce", "Pk", "Se", "Sv") alongside English event names ("Bus Fleet Inspection", "Morning Shift Handover", "Service Alert: Ice Warning", etc.).

**Root cause:** The `MOCK_EVENTS` array in `mock-dashboard-data.ts` stores English strings directly in the `title` field. Components render `event.title` as raw text without passing through the translation system.

**Secondary issue:** `year-view.tsx` line 83 uses `date.toLocaleDateString()` without a locale parameter, causing the tooltip date format to depend on the browser's default locale rather than the app's active locale.

## Affected Files

### Files with bugs (will be modified)
1. `cms/apps/web/src/lib/mock-dashboard-data.ts` — Event titles and descriptions are hardcoded English
2. `cms/apps/web/src/components/dashboard/month-view.tsx` — Line 141 renders `event.title` without translation
3. `cms/apps/web/src/components/dashboard/three-month-view.tsx` — Line 165 renders `event.title` without translation
4. `cms/apps/web/src/components/dashboard/calendar-event.tsx` — Line 38 renders `event.title` without translation
5. `cms/apps/web/src/components/dashboard/year-view.tsx` — Line 83 uses `toLocaleDateString()` without locale
6. `cms/apps/web/messages/lv.json` — Missing event title translation keys
7. `cms/apps/web/messages/en.json` — Missing event title translation keys

### Files that are NOT affected (already correct)
- `calendar-header.tsx` — All text uses `t()` correctly
- `week-view.tsx` — Weekday headers use `t()` correctly (but renders `CalendarEventCard` which needs fixing)
- `live-timeline.tsx` — No user-visible text

## Fix Strategy

**Approach:** Change mock data `title` values to be i18n key paths (e.g., `"eventTitles.busFleetInspection"`), then use `t(event.title)` in rendering components to resolve through the translation system.

**Why this approach:** When real API data eventually replaces mock data, event titles will come pre-translated from the server. At that point, the `t()` call can be removed. For mock data, using translation keys is the correct pattern that lets both locales work.

**For descriptions:** The `description` field in mock data is also English but is currently NOT rendered in any calendar view (no component displays it). We will still add translation keys for descriptions and update mock data to use them, for completeness and to prevent future bugs if descriptions get rendered.

## Design System

### Master Rules (from MASTER.md)
- No hardcoded text — all user-visible strings via `useTranslations()`
- High contrast, accessible text
- Existing compact spacing tokens preserved

### Tokens Used
- No new tokens needed — this is a data/translation fix, not a styling change

## i18n Keys

### Event Titles — Latvian (`lv.json`)
Add under `dashboard.eventTitles`:
```json
{
  "eventTitles": {
    "busFleetInspection": "Autobusu parka pārbaude",
    "route15Detour": "15. maršruta apvedceļš",
    "morningShiftHandover": "Rīta maiņas nodošana",
    "trolleybusLineMaintenance": "Trolejbusu līnijas apkope",
    "serviceAlertIceWarning": "Servisa brīdinājums: Apledojums",
    "route22ScheduleChange": "22. maršruta grafika izmaiņa",
    "eveningShiftCoverage": "Vakara maiņas nodrošināšana",
    "depotAMaintenanceWindow": "A depo apkopes logs",
    "weekendScheduleActivation": "Brīvdienu grafika aktivizēšana",
    "emergencyDrill": "Ārkārtas situāciju mācības"
  }
}
```

### Event Titles — English (`en.json`)
Add under `dashboard.eventTitles`:
```json
{
  "eventTitles": {
    "busFleetInspection": "Bus Fleet Inspection",
    "route15Detour": "Route 15 Detour",
    "morningShiftHandover": "Morning Shift Handover",
    "trolleybusLineMaintenance": "Trolleybus Line Maintenance",
    "serviceAlertIceWarning": "Service Alert: Ice Warning",
    "route22ScheduleChange": "Route 22 Schedule Change",
    "eveningShiftCoverage": "Evening Shift Coverage",
    "depotAMaintenanceWindow": "Depot A Maintenance Window",
    "weekendScheduleActivation": "Weekend Schedule Activation",
    "emergencyDrill": "Emergency Drill"
  }
}
```

### Event Descriptions — Latvian (`lv.json`)
Add under `dashboard.eventDescriptions`:
```json
{
  "eventDescriptions": {
    "busFleetInspection": "Ceturkšņa pārbaude autobusiem 101-120",
    "route15Detour": "Būvdarbi Brīvības ielā",
    "trolleybusLineMaintenance": "11. līnijas kontakttīkla remonts",
    "serviceAlertIceWarning": "Samazināts ātrums visos maršrutos",
    "depotAMaintenanceWindow": "Plānotā depo tīrīšana un aprīkojuma pārbaude",
    "emergencyDrill": "Pilsētas ārkārtas reaģēšanas mācības"
  }
}
```

### Event Descriptions — English (`en.json`)
Add under `dashboard.eventDescriptions`:
```json
{
  "eventDescriptions": {
    "busFleetInspection": "Quarterly inspection of buses 101-120",
    "route15Detour": "Construction on Brivibas iela",
    "trolleybusLineMaintenance": "Overhead wire repair on line 11",
    "serviceAlertIceWarning": "Reduced speed on all routes",
    "depotAMaintenanceWindow": "Scheduled depot cleaning and equipment check",
    "emergencyDrill": "City-wide emergency response drill"
  }
}
```

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/dashboard/calendar-header.tsx` — Correct i18n pattern: `t("calendar.today")`
- `cms/apps/web/src/components/dashboard/week-view.tsx` — Correct i18n pattern: `t(\`weekdays.${WEEKDAY_KEYS[i]}\`)`

### Files to Modify
1. `cms/apps/web/messages/lv.json` — Add event title + description translation keys
2. `cms/apps/web/messages/en.json` — Add event title + description translation keys
3. `cms/apps/web/src/lib/mock-dashboard-data.ts` — Replace English strings with i18n key paths
4. `cms/apps/web/src/components/dashboard/month-view.tsx` — Use `t(event.title)` instead of `event.title`
5. `cms/apps/web/src/components/dashboard/three-month-view.tsx` — Use `t(event.title)` instead of `event.title`
6. `cms/apps/web/src/components/dashboard/calendar-event.tsx` — Use `t(event.title)` instead of `event.title`
7. `cms/apps/web/src/components/dashboard/year-view.tsx` — Fix `toLocaleDateString()` locale parameter

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Add Latvian event translation keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Inside the `"dashboard"` object, add two new sibling objects next to the existing `"events"`, `"priority"`, etc. keys:

Add `"eventTitles"` object with these keys:
- `"busFleetInspection"`: `"Autobusu parka pārbaude"`
- `"route15Detour"`: `"15. maršruta apvedceļš"`
- `"morningShiftHandover"`: `"Rīta maiņas nodošana"`
- `"trolleybusLineMaintenance"`: `"Trolejbusu līnijas apkope"`
- `"serviceAlertIceWarning"`: `"Servisa brīdinājums: Apledojums"`
- `"route22ScheduleChange"`: `"22. maršruta grafika izmaiņa"`
- `"eveningShiftCoverage"`: `"Vakara maiņas nodrošināšana"`
- `"depotAMaintenanceWindow"`: `"A depo apkopes logs"`
- `"weekendScheduleActivation"`: `"Brīvdienu grafika aktivizēšana"`
- `"emergencyDrill"`: `"Ārkārtas situāciju mācības"`

Add `"eventDescriptions"` object with these keys:
- `"busFleetInspection"`: `"Ceturkšņa pārbaude autobusiem 101-120"`
- `"route15Detour"`: `"Būvdarbi Brīvības ielā"`
- `"trolleybusLineMaintenance"`: `"11. līnijas kontakttīkla remonts"`
- `"serviceAlertIceWarning"`: `"Samazināts ātrums visos maršrutos"`
- `"depotAMaintenanceWindow"`: `"Plānotā depo tīrīšana un aprīkojuma pārbaude"`
- `"emergencyDrill"`: `"Pilsētas ārkārtas reaģēšanas mācības"`

**Per-task validation:**
- Verify JSON is valid (no trailing commas, matching braces)
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: Add English event translation keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add the same structure as Task 1 but with English values:

Add `"eventTitles"` object:
- `"busFleetInspection"`: `"Bus Fleet Inspection"`
- `"route15Detour"`: `"Route 15 Detour"`
- `"morningShiftHandover"`: `"Morning Shift Handover"`
- `"trolleybusLineMaintenance"`: `"Trolleybus Line Maintenance"`
- `"serviceAlertIceWarning"`: `"Service Alert: Ice Warning"`
- `"route22ScheduleChange"`: `"Route 22 Schedule Change"`
- `"eveningShiftCoverage"`: `"Evening Shift Coverage"`
- `"depotAMaintenanceWindow"`: `"Depot A Maintenance Window"`
- `"weekendScheduleActivation"`: `"Weekend Schedule Activation"`
- `"emergencyDrill"`: `"Emergency Drill"`

Add `"eventDescriptions"` object:
- `"busFleetInspection"`: `"Quarterly inspection of buses 101-120"`
- `"route15Detour"`: `"Construction on Brivibas iela"`
- `"trolleybusLineMaintenance"`: `"Overhead wire repair on line 11"`
- `"serviceAlertIceWarning"`: `"Reduced speed on all routes"`
- `"depotAMaintenanceWindow"`: `"Scheduled depot cleaning and equipment check"`
- `"emergencyDrill"`: `"City-wide emergency response drill"`

**Per-task validation:**
- Verify JSON is valid
- Verify key parity: every key in lv.json `eventTitles`/`eventDescriptions` exists in en.json and vice versa
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Update mock data to use translation keys
**File:** `cms/apps/web/src/lib/mock-dashboard-data.ts` (modify)
**Action:** UPDATE

Replace each event's `title` with a translation key path (relative to the `dashboard` namespace). Replace each event's `description` with a translation key path. Events without descriptions remain unchanged.

**Exact replacements:**

| Event ID | Old `title` | New `title` |
|----------|------------|-------------|
| evt-1 | `"Bus Fleet Inspection"` | `"eventTitles.busFleetInspection"` |
| evt-2 | `"Route 15 Detour"` | `"eventTitles.route15Detour"` |
| evt-3 | `"Morning Shift Handover"` | `"eventTitles.morningShiftHandover"` |
| evt-4 | `"Trolleybus Line Maintenance"` | `"eventTitles.trolleybusLineMaintenance"` |
| evt-5 | `"Service Alert: Ice Warning"` | `"eventTitles.serviceAlertIceWarning"` |
| evt-6 | `"Route 22 Schedule Change"` | `"eventTitles.route22ScheduleChange"` |
| evt-7 | `"Evening Shift Coverage"` | `"eventTitles.eveningShiftCoverage"` |
| evt-8 | `"Depot A Maintenance Window"` | `"eventTitles.depotAMaintenanceWindow"` |
| evt-9 | `"Weekend Schedule Activation"` | `"eventTitles.weekendScheduleActivation"` |
| evt-10 | `"Emergency Drill"` | `"eventTitles.emergencyDrill"` |

| Event ID | Old `description` | New `description` |
|----------|------------------|-------------------|
| evt-1 | `"Quarterly inspection of buses 101-120"` | `"eventDescriptions.busFleetInspection"` |
| evt-2 | `"Construction on Brivibas iela"` | `"eventDescriptions.route15Detour"` |
| evt-4 | `"Overhead wire repair on line 11"` | `"eventDescriptions.trolleybusLineMaintenance"` |
| evt-5 | `"Reduced speed on all routes"` | `"eventDescriptions.serviceAlertIceWarning"` |
| evt-8 | `"Scheduled depot cleaning and equipment check"` | `"eventDescriptions.depotAMaintenanceWindow"` |
| evt-10 | `"City-wide emergency response drill"` | `"eventDescriptions.emergencyDrill"` |

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 4: Fix month-view.tsx — translate event titles
**File:** `cms/apps/web/src/components/dashboard/month-view.tsx` (modify)
**Action:** UPDATE

**Line 141** — Change:
```tsx
{event.title}
```
To:
```tsx
{t(event.title)}
```

This uses the existing `t` function (already imported via `useTranslations("dashboard")` on line 64) to resolve the translation key stored in `event.title`.

No other changes needed in this file.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 5: Fix three-month-view.tsx — translate event titles
**File:** `cms/apps/web/src/components/dashboard/three-month-view.tsx` (modify)
**Action:** UPDATE

**Line 165** (inside `MiniMonth` component) — Change:
```tsx
{event.title}
```
To:
```tsx
{t(event.title)}
```

The `t` function is already available via `useTranslations("dashboard")` on line 75.

No other changes needed in this file.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: Fix calendar-event.tsx — translate event titles
**File:** `cms/apps/web/src/components/dashboard/calendar-event.tsx` (modify)
**Action:** UPDATE

**Line 38** — Change:
```tsx
<p className="truncate font-medium text-foreground">{event.title}</p>
```
To:
```tsx
<p className="truncate font-medium text-foreground">{t(event.title)}</p>
```

The `t` function is already available via `useTranslations("dashboard")` on line 29.

No other changes needed in this file.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: Fix year-view.tsx — locale-aware date formatting
**File:** `cms/apps/web/src/components/dashboard/year-view.tsx` (modify)
**Action:** UPDATE

**Step 7a:** Add `useLocale` import. Change line 3:
```tsx
import { useTranslations } from "next-intl";
```
To:
```tsx
import { useLocale, useTranslations } from "next-intl";
```

**Step 7b:** Add locale variable inside the `YearView` component, after `const t = useTranslations("dashboard");` (line 44). Add:
```tsx
const locale = useLocale();
```

**Step 7c:** Fix the tooltip on **line 83**. Change:
```tsx
title={`${date.toLocaleDateString()}: ${t("calendar.eventsCount", { count })}`}
```
To:
```tsx
title={`${date.toLocaleDateString(locale)}: ${t("calendar.eventsCount", { count })}`}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 8: Fix calendar-event.tsx — locale-aware time formatting
**File:** `cms/apps/web/src/components/dashboard/calendar-event.tsx` (modify)
**Action:** UPDATE

This is a secondary fix. The `formatTime` function (line 24) uses `toLocaleTimeString([])` which falls back to browser locale. While the output is usually the same (24hr `HH:MM` format), it should be explicit.

**Step 8a:** Add `useLocale` import. Change line 3:
```tsx
import { useTranslations } from "next-intl";
```
To:
```tsx
import { useLocale, useTranslations } from "next-intl";
```

**Step 8b:** Add locale variable inside the `CalendarEventCard` component, after `const t = useTranslations("dashboard");` (line 29). Add:
```tsx
const locale = useLocale();
```

**Step 8c:** Change `formatTime` from a standalone function to use locale. Since `formatTime` is defined outside the component (line 24), it needs the locale passed in. Change the function signature and call sites:

Change the `formatTime` function (lines 24-26):
```tsx
function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}
```
To:
```tsx
function formatTime(date: Date, locale: string): string {
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", hour12: false });
}
```

Change line 40 (time display):
```tsx
{formatTime(event.start)} – {formatTime(event.end)}
```
To:
```tsx
{formatTime(event.start, locale)} – {formatTime(event.end, locale)}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

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

**Success definition:** All 3 levels exit code 0, zero errors, zero warnings.

## Post-Implementation Checks

- [ ] Month view: event titles display in Latvian when locale is `lv`
- [ ] Month view: event titles display in English when locale is `en`
- [ ] Three-month view: event titles display in correct locale
- [ ] Week view: event cards display titles in correct locale
- [ ] Year view: tooltip date format matches app locale (not browser locale)
- [ ] No hardcoded English strings visible when browsing in Latvian locale
- [ ] i18n key parity: every key in `lv.json` exists in `en.json` and vice versa
- [ ] Zero lint warnings
- [ ] Production build succeeds

## Acceptance Criteria

This fix is complete when:
- [ ] All calendar views show event titles in the active locale language only
- [ ] No mixed English/Latvian text appears anywhere in the calendar
- [ ] Year view tooltip uses locale-aware date formatting
- [ ] All 3 validation levels pass (type-check, lint, build) with 0 errors and 0 warnings
- [ ] Translation key parity maintained between lv.json and en.json
- [ ] Ready for `/commit`
