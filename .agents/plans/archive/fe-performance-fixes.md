# Plan: Frontend Performance Fixes

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Low
**Route**: N/A (cross-cutting performance fixes, not a new page)
**Auth Required**: N/A
**Allowed Roles**: N/A

## Feature Description

The VTV CMS frontend has several performance bottlenecks despite being a relatively simple Next.js 16 application. This plan addresses 5 independent fixes that collectively eliminate render-blocking requests, reduce client-side JavaScript, optimize build output, and add caching hints.

The biggest issue is a render-blocking Google Fonts `@import` in `globals.css` that fires an external HTTP request on every page load. The dashboard page is unnecessarily marked `'use client'` despite having zero interactive state (all interactivity lives in child components). The `next.config.ts` is completely empty with no build optimizations. The `shadcn` CLI tool is in production `dependencies` instead of `devDependencies`.

These are low-risk, high-impact changes that improve load time with zero added complexity. No new dependencies, no architectural changes, no breaking changes.

## Design System

### Master Rules (from MASTER.md)
- **Heading Font:** Lexend — defined as `--font-heading` in `tokens.css`
- **Body Font:** Source Sans 3 — defined as `--font-body` in `tokens.css`
- **Mono Font:** JetBrains Mono — defined as `--font-mono` in `tokens.css`
- Typography tokens: `--font-heading`, `--font-body`, `--font-mono`
- Currently loaded via CSS `@import url(...)` which is render-blocking

### Page Override
- None — these are infrastructure-level changes, not page-specific

### Tokens Used
- `--font-heading` at `cms/packages/ui/src/tokens.css:52` — currently `"Lexend", system-ui, sans-serif`
- `--font-body` at `cms/packages/ui/src/tokens.css:53` — currently `"Source Sans 3", system-ui, sans-serif`
- `--font-mono` at `cms/packages/ui/src/tokens.css:54` — unchanged (JetBrains Mono not loaded via Google Fonts)

## Components Needed

### Existing (no changes)
- All existing components remain unchanged
- `MetricCard` — `'use client'` component at `cms/apps/web/src/components/dashboard/metric-card.tsx`
- `CalendarGrid` — `'use client'` component at `cms/apps/web/src/components/dashboard/calendar-grid.tsx`
- `ResizablePanelGroup/Panel/Handle` — `'use client'` at `cms/apps/web/src/components/ui/resizable.tsx`
- `Button` — from `cms/apps/web/src/components/ui/button.tsx`

### New shadcn/ui to Install
- None

### Custom Components to Create
- None

## i18n Keys

No i18n changes needed. All existing translation keys remain unchanged.

## Data Fetching

No data fetching changes. The dashboard currently uses static mock data (`MOCK_METRICS`, `MOCK_EVENTS` from `@/lib/mock-dashboard-data`). Converting the page to a server component does not change data flow — mock data imports work identically in server components.

## RBAC Integration

No RBAC changes needed.

## Sidebar Navigation

No sidebar changes needed.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/apps/web/CLAUDE.md` — React 19 anti-patterns, zero-warning policy

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Current dashboard (will be modified)
- `cms/apps/web/src/app/layout.tsx` — Root layout (will be modified)

### Files to Modify
- `cms/apps/web/src/app/layout.tsx` — Add next/font declarations, apply CSS vars to `<html>`
- `cms/apps/web/src/app/globals.css` — Remove render-blocking Google Fonts `@import`
- `cms/packages/ui/src/tokens.css` — Update font-family tokens to use next/font CSS vars
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Convert to server component, add revalidation
- `cms/apps/web/next.config.ts` — Add image formats, package import optimizations
- `cms/apps/web/package.json` — Move `shadcn` to devDependencies

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367

See `cms/apps/web/CLAUDE.md` → "React 19 Anti-Patterns" for full examples.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

---

### Task 1: Move shadcn CLI to devDependencies
**File:** `cms/apps/web/package.json` (modify)
**Action:** UPDATE

Move `"shadcn": "^3.8.5"` from the `dependencies` object to the `devDependencies` object. The `shadcn` package is a CLI tool (`npx shadcn@latest add [component]`) used only during development to scaffold shadcn/ui components. It is never imported in application code and should not be in the production bundle.

**Current state (line 25 in dependencies):**
```json
"shadcn": "^3.8.5",
```

**Target state — remove from `dependencies`, add to `devDependencies`:**
```json
"devDependencies": {
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "16.1.6",
    "shadcn": "^3.8.5",
    "tailwindcss": "^4",
    "typescript": "^5"
}
```

After editing, run from the `cms/` directory:
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm install
```

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
```

---

### Task 2: Add next.config.ts build optimizations
**File:** `cms/apps/web/next.config.ts` (modify)
**Action:** UPDATE

Replace the empty config object with performance optimizations. The `optimizePackageImports` setting tells Next.js to tree-shake barrel exports from `lucide-react` (hundreds of icon exports, only ~6 used) and `radix-ui` (unified v1.x package with all primitives, only ~11 used).

**Current state (full file):**
```ts
import createNextIntlPlugin from "next-intl/plugin";
import type { NextConfig } from "next";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {};

export default withNextIntl(nextConfig);
```

**Target state (full file):**
```ts
import createNextIntlPlugin from "next-intl/plugin";
import type { NextConfig } from "next";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  images: {
    formats: ["image/avif", "image/webp"],
  },
  experimental: {
    optimizePackageImports: ["lucide-react", "radix-ui"],
  },
};

export default withNextIntl(nextConfig);
```

**Why these specific settings:**
- `images.formats` — enables AVIF (best compression) and WebP as preferred image formats
- `optimizePackageImports` for `lucide-react` — only bundles the ~6 icons actually imported (`Bus`, `Clock`, `AlertTriangle`, `Gauge`, `ArrowRight`, `GripVerticalIcon`) instead of all 1000+ icons
- `optimizePackageImports` for `radix-ui` — only bundles the ~11 primitives actually used (`Slot`, `Dialog`, `Label`, `Switch`, `Select`, `ToggleGroup`, `Avatar`, `DropdownMenu`, `Tooltip`, `Separator`, `Toggle`) instead of all ~30+ primitives
- NOT adding `output: "standalone"` — the frontend doesn't use Docker yet

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
```

---

### Task 3: Replace Google Fonts @import with next/font
**Files:** 3 files modified in this task
**Action:** UPDATE

This is the highest-impact fix. The current `@import url(...)` in `globals.css` fires a render-blocking external HTTP request to `fonts.googleapis.com` on every page load. `next/font` self-hosts the fonts, generates optimized `@font-face` declarations, and sets CSS custom properties on `<html>`.

#### Step 3a: Update root layout to declare fonts

**File:** `cms/apps/web/src/app/layout.tsx` (modify)

**Current state (full file, 33 lines):**
```tsx
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

**Target state (full file):**
```tsx
import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Lexend, Source_Sans_3 } from "next/font/google";
import "./globals.css";

const lexend = Lexend({
  subsets: ["latin", "latin-ext"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
  variable: "--font-lexend",
});

const sourceSans3 = Source_Sans_3({
  subsets: ["latin", "latin-ext"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
  variable: "--font-source-sans-3",
});

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
    <html
      lang={locale}
      suppressHydrationWarning
      className={`${lexend.variable} ${sourceSans3.variable}`}
    >
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

**Key changes:**
1. Import `Lexend` and `Source_Sans_3` from `next/font/google` (line 3)
2. Declare font instances with `variable` option to create CSS custom properties (lines 6-18)
3. Apply `className={...}` to `<html>` so CSS vars `--font-lexend` and `--font-source-sans-3` are available globally
4. `subsets: ["latin", "latin-ext"]` — includes Latvian diacritics (ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž)
5. `display: "swap"` — shows fallback font immediately, swaps when loaded (no FOIT)

#### Step 3b: Remove Google Fonts @import from globals.css

**File:** `cms/apps/web/src/app/globals.css` (modify)

Delete line 4 entirely:
```css
@import url("https://fonts.googleapis.com/css2?family=Lexend:wght@300;400;500;600;700&family=Source+Sans+3:wght@300;400;500;600;700&display=swap");
```

The file should start with:
```css
/* VTV Transit CMS — Global Styles
 * Uses Tailwind v4 @theme for CSS-native token system
 */
@import "tailwindcss";
@import "@vtv/ui/tokens.css";
```

(Line 4 was the `@import url(...)`, line 5 `@import "tailwindcss"` becomes the new line 4.)

#### Step 3c: Update design token font-family references

**File:** `cms/packages/ui/src/tokens.css` (modify)

Update lines 52-53 in the `@theme` block to reference the CSS variables set by `next/font` instead of hardcoded font family names:

**Current (lines 52-53):**
```css
  --font-heading: "Lexend", system-ui, sans-serif;
  --font-body: "Source Sans 3", system-ui, sans-serif;
```

**Target (lines 52-53):**
```css
  --font-heading: var(--font-lexend), system-ui, sans-serif;
  --font-body: var(--font-source-sans-3), system-ui, sans-serif;
```

**How the chain works:**
1. `next/font` generates `@font-face` with an internal name like `__Lexend_a1b2c3`
2. `next/font` sets `--font-lexend: '__Lexend_a1b2c3'` on `<html>` via `className`
3. `tokens.css` defines `--font-heading: var(--font-lexend), system-ui, sans-serif`
4. Tailwind's `@theme` makes `--font-heading` available as the `font-heading` utility class
5. Components using `font-heading` class or `font-family: var(--font-heading)` get the self-hosted font
6. The `system-ui, sans-serif` fallbacks work if `--font-lexend` is not yet defined

**Leave `--font-mono` unchanged** — JetBrains Mono is not loaded from Google Fonts (it's a system/installed font reference).

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web lint
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web build
```

The build step is critical here — it validates that:
- `next/font` can resolve the Google Font families
- The CSS variable chain resolves correctly at build time
- No SSR errors from the font declarations

---

### Task 4: Convert dashboard page to server component
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` (modify)
**Action:** UPDATE

The dashboard page is currently `'use client'` but has zero interactive state. All interactivity lives in child components:
- `MetricCard` — `'use client'` (static display, hover effects only)
- `CalendarGrid` — `'use client'` (has `useState` for view mode, date navigation)
- `ResizablePanelGroup/Panel/Handle` — `'use client'` (resize interaction)

The page only uses `useTranslations()` and `useLocale()` — both have server-side equivalents. Converting to a server component eliminates the page's JavaScript from the client bundle while child components continue hydrating normally (server components can render client component children — this is standard RSC composition).

**Current state (full file, 71 lines):**
```tsx
"use client";

import { useTranslations, useLocale } from "next-intl";
import Link from "next/link";
import { Bus, Clock, AlertTriangle, Gauge, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MetricCard } from "@/components/dashboard/metric-card";
import { CalendarGrid } from "@/components/dashboard/calendar-grid";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { MOCK_METRICS, MOCK_EVENTS } from "@/lib/mock-dashboard-data";

const METRIC_ICONS = [Bus, Clock, AlertTriangle, Gauge] as const;
const METRIC_KEYS = [
  "activeVehicles",
  "onTimePerformance",
  "delayedRoutes",
  "fleetUtilization",
] as const;

export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const locale = useLocale();

  return (
    <div className="space-y-(--spacing-section)">
      {/* ... JSX ... */}
    </div>
  );
}
```

**Target state (full file):**
```tsx
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { Bus, Clock, AlertTriangle, Gauge, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MetricCard } from "@/components/dashboard/metric-card";
import { CalendarGrid } from "@/components/dashboard/calendar-grid";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { MOCK_METRICS, MOCK_EVENTS } from "@/lib/mock-dashboard-data";

const METRIC_ICONS = [Bus, Clock, AlertTriangle, Gauge] as const;
const METRIC_KEYS = [
  "activeVehicles",
  "onTimePerformance",
  "delayedRoutes",
  "fleetUtilization",
] as const;

export const revalidate = 3600;

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations("dashboard");

  return (
    <div className="space-y-(--spacing-section)">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-heading font-semibold text-foreground">
          {t("title")}
        </h1>
        <Button asChild variant="outline" className="cursor-pointer">
          <Link href={`/${locale}/routes`}>
            {t("manageRoutes")}
            <ArrowRight className="ml-2 size-4" aria-hidden="true" />
          </Link>
        </Button>
      </div>

      <ResizablePanelGroup orientation="vertical" className="min-h-[calc(100vh-6rem)]">
        {/* Metrics panel */}
        <ResizablePanel defaultSize={20} minSize={10}>
          <div className="grid grid-cols-1 gap-(--spacing-grid) sm:grid-cols-2 lg:grid-cols-4">
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
          </div>
        </ResizablePanel>

        <ResizableHandle withHandle />

        {/* Calendar panel */}
        <ResizablePanel defaultSize={80} minSize={30}>
          <div className="h-full pt-(--spacing-grid)">
            <CalendarGrid events={MOCK_EVENTS} />
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
```

**Key changes (4 total):**
1. **Remove `"use client";`** — line 1 deleted entirely
2. **Replace imports** — `useTranslations, useLocale` from `"next-intl"` becomes `getTranslations` from `"next-intl/server"`
3. **Make async with params** — `function DashboardPage()` becomes `async function DashboardPage({ params })` with `params: Promise<{ locale: string }>` (Next.js 16 App Router pattern — params is a Promise)
4. **Await translations** — `const t = useTranslations("dashboard")` becomes `const t = await getTranslations("dashboard")`
5. **Add revalidation** — `export const revalidate = 3600` (1 hour cache since data is mock/static)

**What stays the same:**
- ALL JSX markup is identical
- ALL `t()` calls work identically (`getTranslations` returns the same API as `useTranslations`)
- ALL child component rendering is unchanged (client components render normally inside server components)
- The `Link href={`/${locale}/routes`}` pattern is unchanged (locale comes from `params` instead of `useLocale()`)

**Per-task validation:**
```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web type-check
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web lint
cd /Users/Berzins/Desktop/VTV/cms && pnpm --filter @vtv/web build
```

The build step is critical — it validates the server/client component boundary. If any import chain pulls in a client-only API (like `useState`) into the server component, the build will fail with a clear error.

---

### Task 5: Run pnpm install and final validation
**Action:** VERIFY

After all 4 tasks are complete, run the full validation suite:

```bash
cd /Users/Berzins/Desktop/VTV/cms && pnpm install
```

This is required because Task 1 modified `package.json` (moved `shadcn` to devDependencies).

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

- [ ] No request to `fonts.googleapis.com` in browser Network tab
- [ ] Fonts render correctly (Lexend headings, Source Sans 3 body text)
- [ ] Latvian diacritics display correctly (ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž)
- [ ] Dashboard page loads and displays metrics + calendar
- [ ] Dashboard page serves less client JS (no page-level `'use client'`)
- [ ] Routes page still works (no regressions)
- [ ] Login page still works (no regressions)
- [ ] Build output shows no warnings about font loading

## Acceptance Criteria

This feature is complete when:
- [ ] Google Fonts `@import` removed from `globals.css`
- [ ] `next/font/google` self-hosts Lexend and Source Sans 3 via root layout
- [ ] `tokens.css` font tokens reference `next/font` CSS variables
- [ ] Dashboard page is a server component (no `'use client'`)
- [ ] `next.config.ts` has image format and package import optimizations
- [ ] `shadcn` CLI is in `devDependencies`, not `dependencies`
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`
