# Plan: Fix Latvian Diacritics, Hardcoded Strings & Add Language Toggle

## Feature Metadata
**Feature Type**: Enhancement (i18n quality + new component)
**Estimated Complexity**: Medium
**Route**: N/A — cross-cutting i18n fix + layout component addition
**Auth Required**: N/A — inherits existing auth
**Allowed Roles**: All (language toggle visible to all authenticated users)

## Feature Description

This plan addresses three interconnected i18n issues in the VTV frontend:

1. **Missing Latvian diacritics** — All translations in `lv.json` are missing proper Latvian characters (ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž). For example "Marsruti" should be "Maršruti", "Sodien" should be "Šodien", "Menesis" should be "Mēnesis". The entire `lv.json` file must be corrected with proper diacritical marks.

2. **Hardcoded English strings** — Several components contain hardcoded English text that isn't going through the `useTranslations()` i18n system, causing a mixed language experience. Specifically:
   - `login/page.tsx`: "Email" and "Password" labels are hardcoded English
   - `calendar-header.tsx`: `aria-label="Previous"` and `aria-label="Next"` are hardcoded
   - `month-view.tsx`: `+{overflow} more` is hardcoded English
   - `year-view.tsx`: `${count} events` tooltip is hardcoded English
   - `layout.tsx` (root): `"Pāriet uz saturu"` skip-link is hardcoded Latvian (won't translate to English)
   - `layout.tsx` (root): `<html lang="lv">` is hardcoded (should be dynamic)
   - `mock-dashboard-data.ts`: subtitle strings ("Compared to X last month") are hardcoded English

3. **Language toggle** — There's no UI for switching between Latvian and English. A compact LV/EN toggle should be added to the sidebar navigation, allowing users to switch language. The toggle sets a cookie and navigates to the equivalent path under the new locale prefix.

## Design System

### Master Rules (from MASTER.md)
- Spacing tokens: `--spacing-card`, `--spacing-inline`, `--spacing-tight`
- Typography: `--font-body` for body text
- Colors: semantic tokens only — `text-foreground`, `text-foreground-muted`, `bg-surface-raised`
- Transitions: 150-300ms on interactive elements
- Cursor pointer on all clickable elements

### Page Override
- None — cross-cutting enhancement

### Tokens Used
- `text-foreground-muted` — inactive locale label
- `text-foreground` — active locale label
- `bg-surface-raised` — toggle hover state
- `--spacing-inline` — gap between LV/EN labels
- `--spacing-tight` — micro gaps
- `border-border` — subtle separator

## Components Needed

### Existing (shadcn/ui)
- `Button` — used in calendar-header (already imported, just fixing aria-labels)

### New shadcn/ui to Install
- None

### Custom Components to Create
- `LocaleToggle` at `cms/apps/web/src/components/locale-toggle.tsx` — compact LV | EN switcher for the sidebar

## i18n Keys

### Latvian (`lv.json`) — COMPLETE REPLACEMENT
The entire file needs diacritic corrections. All new keys are also added.

```json
{
  "common": {
    "appName": "VTV — Rīgas Satiksme",
    "login": "Pieteikties",
    "logout": "Iziet",
    "unauthorized": "Nav piekļuves",
    "loading": "Ielāde...",
    "email": "E-pasts",
    "password": "Parole",
    "skipToContent": "Pāriet uz saturu"
  },
  "nav": {
    "dashboard": "Panelis",
    "routes": "Maršruti",
    "stops": "Pieturas",
    "schedules": "Grafiki",
    "gtfs": "GTFS",
    "users": "Lietotāji",
    "chat": "AI palīgs"
  },
  "dashboard": {
    "title": "Darbagalds",
    "activeRoutes": "{count, plural, zero {Nav aktīvu maršrutu} one {{count} aktīvs maršruts} other {{count} aktīvi maršruti}}",
    "delayedRoutes": "{count, plural, zero {Neviens nekavējas} one {{count} maršruts kavējas} other {{count} maršruti kavējas}}",
    "metrics": {
      "activeVehicles": "Aktīvi transportlīdzekļi",
      "onTimePerformance": "Savlaicīgums",
      "delayedRoutes": "Kavēti maršruti",
      "fleetUtilization": "Parka izmantojums",
      "comparedToLastMonth": "Salīdzinot ar iepriekšējo mēnesi"
    },
    "calendar": {
      "title": "Operācijas",
      "today": "Šodien",
      "week": "Nedēļa",
      "month": "Mēnesis",
      "threeMonth": "3 mēneši",
      "year": "Gads",
      "noEvents": "Nav notikumu",
      "allDay": "Visa diena",
      "previous": "Iepriekšējais",
      "next": "Nākamais",
      "moreEvents": "+{count} vēl",
      "eventsCount": "{count, plural, zero {nav notikumu} one {{count} notikums} other {{count} notikumi}}"
    },
    "events": {
      "maintenance": "Apkope",
      "routeChange": "Maršruta izmaiņa",
      "driverShift": "Vadītāja maiņa",
      "serviceAlert": "Servisa brīdinājums"
    },
    "priority": {
      "high": "Augsta",
      "medium": "Vidēja",
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
      "jan": "Janvāris",
      "feb": "Februāris",
      "mar": "Marts",
      "apr": "Aprīlis",
      "may": "Maijs",
      "jun": "Jūnijs",
      "jul": "Jūlijs",
      "aug": "Augusts",
      "sep": "Septembris",
      "oct": "Oktobris",
      "nov": "Novembris",
      "dec": "Decembris"
    }
  }
}
```

### English (`en.json`) — ADD NEW KEYS
Add these new keys (existing keys unchanged):

```json
{
  "common": {
    "email": "Email",
    "password": "Password",
    "skipToContent": "Skip to content"
  },
  "dashboard": {
    "calendar": {
      "previous": "Previous",
      "next": "Next",
      "moreEvents": "+{count} more",
      "eventsCount": "{count, plural, one {{count} event} other {{count} events}}"
    }
  }
}
```

## Data Fetching
- No API changes. Mock data subtitles will be moved to i18n keys.

## RBAC Integration
- No middleware changes needed.

## Sidebar Navigation
- No new nav items. The `LocaleToggle` is added at the bottom of the existing sidebar.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/layout.tsx` — Sidebar structure (where LocaleToggle goes)
- `cms/apps/web/src/i18n/request.ts` — How locale is determined (cookie-based)

### Files to Modify
- `cms/apps/web/messages/lv.json` — Fix all diacritics, add new keys
- `cms/apps/web/messages/en.json` — Add new keys
- `cms/apps/web/src/app/layout.tsx` — Dynamic `lang` attribute, i18n skip-link
- `cms/apps/web/src/app/[locale]/layout.tsx` — Add LocaleToggle to sidebar
- `cms/apps/web/src/app/[locale]/login/page.tsx` — Fix hardcoded "Email"/"Password"
- `cms/apps/web/src/components/dashboard/calendar-header.tsx` — Fix hardcoded aria-labels
- `cms/apps/web/src/components/dashboard/month-view.tsx` — Fix hardcoded "+N more"
- `cms/apps/web/src/components/dashboard/year-view.tsx` — Fix hardcoded "events" tooltip
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Fix mock subtitle to use i18n

### Files to Create
- `cms/apps/web/src/components/locale-toggle.tsx` — Language switcher component

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

---

### Task 1: Fix Latvian Diacritics in lv.json
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE — Replace entire file content

Replace the entire `lv.json` file with properly diacriticized Latvian. Every string must use correct Latvian characters. This is the complete corrected file:

```json
{
  "common": {
    "appName": "VTV — Rīgas Satiksme",
    "login": "Pieteikties",
    "logout": "Iziet",
    "unauthorized": "Nav piekļuves",
    "loading": "Ielāde...",
    "email": "E-pasts",
    "password": "Parole",
    "skipToContent": "Pāriet uz saturu"
  },
  "nav": {
    "dashboard": "Panelis",
    "routes": "Maršruti",
    "stops": "Pieturas",
    "schedules": "Grafiki",
    "gtfs": "GTFS",
    "users": "Lietotāji",
    "chat": "AI palīgs"
  },
  "dashboard": {
    "title": "Darbagalds",
    "activeRoutes": "{count, plural, zero {Nav aktīvu maršrutu} one {{count} aktīvs maršruts} other {{count} aktīvi maršruti}}",
    "delayedRoutes": "{count, plural, zero {Neviens nekavējas} one {{count} maršruts kavējas} other {{count} maršruti kavējas}}",
    "metrics": {
      "activeVehicles": "Aktīvi transportlīdzekļi",
      "onTimePerformance": "Savlaicīgums",
      "delayedRoutes": "Kavēti maršruti",
      "fleetUtilization": "Parka izmantojums",
      "comparedToLastMonth": "Salīdzinot ar iepriekšējo mēnesi"
    },
    "calendar": {
      "title": "Operācijas",
      "today": "Šodien",
      "week": "Nedēļa",
      "month": "Mēnesis",
      "threeMonth": "3 mēneši",
      "year": "Gads",
      "noEvents": "Nav notikumu",
      "allDay": "Visa diena",
      "previous": "Iepriekšējais",
      "next": "Nākamais",
      "moreEvents": "+{count} vēl",
      "eventsCount": "{count, plural, zero {nav notikumu} one {{count} notikums} other {{count} notikumi}}"
    },
    "events": {
      "maintenance": "Apkope",
      "routeChange": "Maršruta izmaiņa",
      "driverShift": "Vadītāja maiņa",
      "serviceAlert": "Servisa brīdinājums"
    },
    "priority": {
      "high": "Augsta",
      "medium": "Vidēja",
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
      "jan": "Janvāris",
      "feb": "Februāris",
      "mar": "Marts",
      "apr": "Aprīlis",
      "may": "Maijs",
      "jun": "Jūnijs",
      "jul": "Jūlijs",
      "aug": "Augusts",
      "sep": "Septembris",
      "oct": "Oktobris",
      "nov": "Novembris",
      "dec": "Decembris"
    }
  }
}
```

**Diacritic changes made:**
- `Rigas` → `Rīgas` (ī)
- `piekluves` → `piekļuves` (ļ)
- `Ielade` → `Ielāde` (ā)
- `Panele` → `Panelis`
- `Marsruti` → `Maršruti` (š)
- `Lietotaji` → `Lietotāji` (ā)
- `paligs` → `palīgs` (ī)
- `aktivu marsrutu` → `aktīvu maršrutu` (ī, š)
- `nekavejas` → `nekavējas` (ē)
- `kavejas` → `kavējas` (ē)
- `transportlidzekli` → `transportlīdzekļi` (ī, ļ)
- `Savlaicigums` → `Savlaicīgums` (ī)
- `Kaveti` → `Kavēti` (ē)
- `iepriekseji menesi` → `iepriekšējo mēnesi` (š, ē, ē)
- `Operacijas` → `Operācijas` (ā)
- `Sodien` → `Šodien` (Š)
- `Nedela` → `Nedēļa` (ē, ļ)
- `Menesis` → `Mēnesis` (ē)
- `menesi` → `mēneši` (ē, š)
- `izmaina` → `izmaiņa` (ņ)
- `Vaditaja maina` → `Vadītāja maiņa` (ī, ā, ņ)
- `bridinajums` → `brīdinājums` (ī, ā)
- `Videja` → `Vidēja` (ē)
- `Janvaris` → `Janvāris` (ā)
- `Februaris` → `Februāris` (ā)
- `Aprilis` → `Aprīlis` (ī)
- `Junijs` → `Jūnijs` (ū)
- `Julijs` → `Jūlijs` (ū)

**New keys added:**
- `common.email` — "E-pasts"
- `common.password` — "Parole"
- `common.skipToContent` — "Pāriet uz saturu"
- `dashboard.calendar.previous` — "Iepriekšējais"
- `dashboard.calendar.next` — "Nākamais"
- `dashboard.calendar.moreEvents` — "+{count} vēl"
- `dashboard.calendar.eventsCount` — plural form for event count

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: Add New Keys to en.json
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add new keys to match `lv.json`. Keep all existing English strings unchanged. Add these new keys:

In the `"common"` section, add after `"loading"`:
```json
"email": "Email",
"password": "Password",
"skipToContent": "Skip to content"
```

In the `"dashboard" > "calendar"` section, add after `"allDay"`:
```json
"previous": "Previous",
"next": "Next",
"moreEvents": "+{count} more",
"eventsCount": "{count, plural, one {{count} event} other {{count} events}}"
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Create LocaleToggle Component
**File:** `cms/apps/web/src/components/locale-toggle.tsx` (create)
**Action:** CREATE

Create a compact LV | EN toggle component. This is a `"use client"` component that:
- Shows two locale labels side by side: "LV" and "EN"
- Highlights the active locale with `text-foreground font-semibold`
- Dims the inactive locale with `text-foreground-muted`
- On click: sets a `locale` cookie and navigates to the equivalent path under the new locale prefix
- Uses `usePathname` from `next/navigation` to get current path
- Uses `useLocale` from `next-intl` to get current locale

```typescript
"use client";

import { usePathname, useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { cn } from "@/lib/utils";

const locales = ["lv", "en"] as const;

export function LocaleToggle() {
  const pathname = usePathname();
  const router = useRouter();
  const currentLocale = useLocale();

  function switchLocale(newLocale: string) {
    if (newLocale === currentLocale) return;

    // Set cookie for next-intl server-side resolution
    document.cookie = `locale=${newLocale};path=/;max-age=31536000`;

    // Replace locale prefix in current path: /lv/dashboard → /en/dashboard
    const segments = pathname.split("/");
    segments[1] = newLocale;
    const newPath = segments.join("/");

    router.push(newPath);
  }

  return (
    <div className="flex items-center gap-(--spacing-tight)" role="radiogroup" aria-label="Language">
      {locales.map((locale, i) => (
        <span key={locale} className="flex items-center gap-(--spacing-tight)">
          {i > 0 && (
            <span className="text-xs text-foreground-muted" aria-hidden="true">|</span>
          )}
          <button
            type="button"
            role="radio"
            aria-checked={locale === currentLocale}
            onClick={() => switchLocale(locale)}
            className={cn(
              "cursor-pointer text-xs font-medium uppercase transition-colors duration-200",
              locale === currentLocale
                ? "text-foreground font-semibold"
                : "text-foreground-muted hover:text-foreground"
            )}
          >
            {locale.toUpperCase()}
          </button>
        </span>
      ))}
    </div>
  );
}
```

**Design notes:**
- `role="radiogroup"` + `role="radio"` + `aria-checked` for accessibility
- `aria-label="Language"` on the group
- `cursor-pointer` on all clickable elements (MASTER.md requirement)
- `transition-colors duration-200` for smooth state change
- Cookie `max-age=31536000` = 1 year persistence
- No hardcoded colors — uses semantic tokens only

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 4: Add LocaleToggle to Sidebar
**File:** `cms/apps/web/src/app/[locale]/layout.tsx` (modify)
**Action:** UPDATE

Add the `LocaleToggle` component to the sidebar. Place it at the bottom of the sidebar, after the nav list, using flex layout to push it down.

1. Add import at top of file:
```typescript
import { LocaleToggle } from "@/components/locale-toggle";
```

2. Modify the `Sidebar` component to use flex layout and add the toggle at the bottom. The `<aside>` should become a flex column, and the `LocaleToggle` should be placed after the nav with `mt-auto` to push it to the bottom:

Change the Sidebar's `<aside>` structure from:
```tsx
<aside className="w-60 border-r border-border bg-surface p-4">
  <nav aria-label="Main navigation">
    <p className="text-sm font-semibold text-foreground-muted mb-(--spacing-card)">
      VTV
    </p>
    <ul className="space-y-1">
      {/* ... nav items ... */}
    </ul>
  </nav>
</aside>
```

To:
```tsx
<aside className="flex w-60 flex-col border-r border-border bg-surface p-4">
  <nav aria-label="Main navigation">
    <p className="text-sm font-semibold text-foreground-muted mb-(--spacing-card)">
      VTV
    </p>
    <ul className="space-y-1">
      {/* ... nav items ... (unchanged) */}
    </ul>
  </nav>
  <div className="mt-auto pt-(--spacing-card)">
    <LocaleToggle />
  </div>
</aside>
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 5: Fix Root Layout — Dynamic lang and i18n Skip Link
**File:** `cms/apps/web/src/app/layout.tsx` (modify)
**Action:** UPDATE

The root layout has two issues:
1. `<html lang="lv">` is hardcoded — should be dynamic based on locale
2. `"Pāriet uz saturu"` skip-link is hardcoded Latvian

Since `layout.tsx` is a server component at the root level (above `[locale]`), it doesn't have access to `useTranslations`. The locale must be read from the cookie or determined differently.

**Approach:** Read the locale from the cookie in the root layout (same mechanism as `request.ts`), and use it for the `lang` attribute. For the skip-link text, use a simple locale-to-text map since this is a static server component.

Replace the entire root layout file with:

```typescript
import type { Metadata } from "next";
import { cookies } from "next/headers";
import "./globals.css";

export const metadata: Metadata = {
  title: "VTV — Rīgas Satiksme",
  description: "Transit operations management for Riga municipal bus system",
};

const skipLinkText: Record<string, string> = {
  lv: "Pāriet uz saturu",
  en: "Skip to content",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const store = await cookies();
  const locale = store.get("locale")?.value ?? "lv";

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className="min-h-screen font-body antialiased">
        <a href="#main-content" className="skip-link">
          {skipLinkText[locale] ?? skipLinkText.lv}
        </a>
        {children}
      </body>
    </html>
  );
}
```

**Changes:**
- `lang="lv"` → `lang={locale}` (dynamic)
- Hardcoded skip-link → locale-aware lookup
- Added `cookies` import from `next/headers`
- Made function `async` to await cookies
- Fixed diacritic in metadata title: `Rigas` → `Rīgas`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: Fix Login Page Hardcoded Labels
**File:** `cms/apps/web/src/app/[locale]/login/page.tsx` (modify)
**Action:** UPDATE

Replace the hardcoded "Email" and "Password" labels with i18n translations. Also fix the hardcoded `/lv` callbackUrl to use the current locale.

1. The login page already uses `const t = useTranslations("common");`

2. Replace `Email` label (around line 30):
```tsx
// FROM:
<label htmlFor="email" className="text-sm font-medium">
  Email
</label>

// TO:
<label htmlFor="email" className="text-sm font-medium">
  {t("email")}
</label>
```

3. Replace `Password` label (around line 43):
```tsx
// FROM:
<label htmlFor="password" className="text-sm font-medium">
  Password
</label>

// TO:
<label htmlFor="password" className="text-sm font-medium">
  {t("password")}
</label>
```

4. Fix the hardcoded `/lv` callbackUrl. Add `useLocale` import and use it:

Add import:
```typescript
import { useLocale } from "next-intl";
```

Add inside component:
```typescript
const locale = useLocale();
```

Change callbackUrl:
```tsx
// FROM:
callbackUrl: "/lv",

// TO:
callbackUrl: `/${locale}`,
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: Fix Calendar Header Hardcoded Aria Labels
**File:** `cms/apps/web/src/components/dashboard/calendar-header.tsx` (modify)
**Action:** UPDATE

The component already has `const t = useTranslations("dashboard");` — just replace the hardcoded strings.

1. Replace `aria-label="Previous"` (line 95):
```tsx
// FROM:
aria-label="Previous"

// TO:
aria-label={t("calendar.previous")}
```

2. Replace `aria-label="Next"` (line 116):
```tsx
// FROM:
aria-label="Next"

// TO:
aria-label={t("calendar.next")}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 8: Fix Month View Hardcoded Overflow Text
**File:** `cms/apps/web/src/components/dashboard/month-view.tsx` (modify)
**Action:** UPDATE

The component already has `const t = useTranslations("dashboard");`

Replace the hardcoded `+{overflow} more` string (around line 146-148):

```tsx
// FROM:
{overflow > 0 && (
  <span className="text-[10px] text-foreground-muted">
    +{overflow} more
  </span>
)}

// TO:
{overflow > 0 && (
  <span className="text-[10px] text-foreground-muted">
    {t("calendar.moreEvents", { count: overflow })}
  </span>
)}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 9: Fix Year View Hardcoded Tooltip
**File:** `cms/apps/web/src/components/dashboard/year-view.tsx` (modify)
**Action:** UPDATE

The component already has `const t = useTranslations("dashboard");`

Replace the hardcoded title attribute (around line 83):

```tsx
// FROM:
title={`${date.toLocaleDateString()}: ${count} events`}

// TO:
title={`${date.toLocaleDateString()}: ${t("calendar.eventsCount", { count })}`}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 10: Fix Dashboard Page Mock Subtitles
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` (modify)
**Action:** UPDATE

The `MetricCard` receives `subtitle` from `MOCK_METRICS` which contains hardcoded English like "Compared to 330 last month". Since the dashboard page already has `const t = useTranslations("dashboard");`, replace the hardcoded subtitle with the i18n key.

The `MOCK_METRICS` data contains `subtitle` strings, but the dashboard page passes them through directly. Instead of modifying mock data (which will be replaced by real API data), override the subtitle in the render:

Replace the MetricCard rendering section:

```tsx
// FROM:
{MOCK_METRICS.map((metric, i) => (
  <MetricCard
    key={METRIC_KEYS[i]}
    icon={METRIC_ICONS[i]}
    title={t(`metrics.${METRIC_KEYS[i]}`)}
    value={metric.value}
    delta={metric.delta}
    deltaType={metric.deltaType}
    subtitle={metric.subtitle}
  />
))}

// TO:
{MOCK_METRICS.map((metric, i) => (
  <MetricCard
    key={METRIC_KEYS[i]}
    icon={METRIC_ICONS[i]}
    title={t(`metrics.${METRIC_KEYS[i]}`)}
    value={metric.value}
    delta={metric.delta}
    deltaType={metric.deltaType}
    subtitle={t("metrics.comparedToLastMonth")}
  />
))}
```

**Note:** This uses a single generic "Compared to last month" string for all metrics. When real API data replaces mock data, the subtitle will come from the backend with proper values and the i18n key can be parameterized (e.g., `t("metrics.comparedTo", { value: "330", period: "last month" })`).

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 11: Full Build Validation
**Action:** VALIDATE

Run the complete validation pyramid:

```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web lint
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web build
```

All three must exit with code 0 and zero errors.

**If type-check fails on LocaleToggle:** Ensure `usePathname` is imported from `next/navigation` (not `next/router`). Ensure `useLocale` is imported from `next-intl`.

**If type-check fails on root layout:** The `cookies()` function returns a `Promise<ReadonlyRequestCookies>` in Next.js 16 — ensure the function is `async` and uses `await`.

**If lint fails:** Check for unused imports after removing hardcoded strings. The `MOCK_METRICS` import in `page.tsx` still needs `subtitle` on the type even though we override it.

**If build fails:** Check SSR compatibility. `LocaleToggle` must be `"use client"` since it uses `usePathname`, `useRouter`, and `useLocale`.

---

## Final Validation (3-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: TypeScript**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
```

**Level 2: Lint**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web lint
```

**Level 3: Build**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web build
```

**Success definition:** All 3 levels exit code 0, zero errors.

## Post-Implementation Checks

- [ ] All Latvian strings use proper diacritics (ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž)
- [ ] No hardcoded English or Latvian strings in component files
- [ ] Login page labels switch language when locale changes
- [ ] Calendar navigation aria-labels are translated
- [ ] Month view overflow text is translated
- [ ] Year view tooltip is translated
- [ ] Skip-link text changes with locale
- [ ] `<html lang>` attribute reflects current locale
- [ ] LV | EN toggle visible at bottom of sidebar
- [ ] Clicking EN navigates to /en/... path and sets cookie
- [ ] Clicking LV navigates to /lv/... path and sets cookie
- [ ] After switching locale, page content fully renders in selected language
- [ ] No mixed language content on any page
- [ ] i18n keys present in both lv.json and en.json with matching structure
- [ ] All validation levels pass (type-check, lint, build)

## Acceptance Criteria

This feature is complete when:
- [ ] All Latvian translations have correct diacritical marks
- [ ] Zero hardcoded user-visible strings in component files (all via `useTranslations`)
- [ ] Language toggle (LV | EN) works in sidebar — switches language without page refresh issues
- [ ] Both `/lv/...` and `/en/...` routes render fully in the selected language
- [ ] All 3 validation levels pass with zero errors
- [ ] No regressions in existing functionality
- [ ] Ready for `/commit`

## Summary of Changes

| Aspect | Files Modified | Files Created |
|--------|---------------|---------------|
| i18n translations | 2 (`lv.json`, `en.json`) | 0 |
| Root layout | 1 (`app/layout.tsx`) | 0 |
| Locale layout | 1 (`app/[locale]/layout.tsx`) | 0 |
| Login page | 1 (`login/page.tsx`) | 0 |
| Dashboard components | 3 (`calendar-header.tsx`, `month-view.tsx`, `year-view.tsx`) | 0 |
| Dashboard page | 1 (`page.tsx`) | 0 |
| Language toggle | 0 | 1 (`locale-toggle.tsx`) |

**Total: 9 files modified, 1 file created.**
