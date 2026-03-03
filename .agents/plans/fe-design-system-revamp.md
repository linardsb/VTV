# Plan: Design System Revamp — Merkle-Inspired Colors + Sharp Corners

## Feature Metadata
**Feature Type**: Enhancement (Design System Overhaul)
**Estimated Complexity**: High
**Route**: N/A — affects all pages globally via token system
**Auth Required**: N/A
**Allowed Roles**: N/A

## Feature Description

Complete visual overhaul of the VTV transit CMS design system. Two changes:

1. **Color palette revamp** — Replace the current navy/blue government palette with a Merkle-inspired corporate-modern scheme. Key colors derived from Merkle brand guidelines: deep navy primary (#040E4B), vibrant blue CTA (#0391F2), teal success (#06757E), red alert (#DD3039), and blue-purple tinted neutrals (#60607D, #8888A1). All primitives in oklch for perceptual uniformity.

2. **Remove all rounded corners** — Set every radius token to 0. Replace all hardcoded `rounded-full` classes on badges, progress bars, and icon containers with sharp edges. Keep `rounded-full` ONLY on avatars (circular profile images), switch toggles (inherent pill shape), scrollbar thumbs, and tiny status dots (decorative indicators).

The change is 100% token-driven for color and radius. Components using semantic tokens get the new look automatically. Only components with hardcoded `rounded-full` need individual edits.

## Design System

### Color Palette (Merkle-Inspired)

| Role | Hex | oklch | Usage |
|------|-----|-------|-------|
| Primary | #040E4B | oklch(0.22 0.10 268) | Sidebar, headers, primary buttons |
| CTA Blue | #0391F2 | oklch(0.58 0.20 250) | Interactive elements, links, focus rings |
| Success Teal | #06757E | oklch(0.50 0.08 196) | On-time status, driver-shift events |
| Alert Red | #DD3039 | oklch(0.55 0.22 23) | Errors, critical status, destructive actions |
| Secondary Text | #60607D | oklch(0.47 0.03 275) | Muted foreground text |
| Tertiary Text | #8888A1 | oklch(0.65 0.02 275) | Subtle/disabled text |
| Amber Warning | (retained) | oklch(0.77 0.17 70) | Delayed status, route-change events |

### Radius Strategy
Set `--radius: 0` in globals.css and all `--radius-*` tokens to `0`. This cascades to every shadcn component using `rounded-sm`, `rounded-md`, `rounded-lg`, `rounded-xl`. For `rounded-full` (which is `9999px`, NOT token-based), manually replace on badges, progress bars, and dialog icons.

**Keep `rounded-full` on:**
- `avatar.tsx` — circular profile images (universal UI convention)
- `switch.tsx` — toggle track + thumb (inherent to pattern)
- `scroll-area.tsx` — scrollbar thumb
- Tiny status dots (size <= 3, decorative indicators in route-table, month-view, etc.)

### Tokens Used
All three tiers updated: primitive colors + radius → semantic references → component overrides.

## Components Needed

### Existing (no new installs needed)
All 27 shadcn/ui components already installed. No new dependencies.

### Files to Modify

**Token layer (2 files):**
- `cms/packages/ui/src/tokens.css` — primitives + semantic + component tiers
- `cms/apps/web/src/app/globals.css` — shadcn theme variables + radius

**shadcn/ui components (2 files):**
- `cms/apps/web/src/components/ui/badge.tsx` — `rounded-full` → remove
- `cms/apps/web/src/components/ui/progress.tsx` — `rounded-full` → `rounded-none`

**Custom components (14 files):**
- `cms/apps/web/src/components/dashboard/metric-card.tsx`
- `cms/apps/web/src/components/dashboard/calendar-event.tsx`
- `cms/apps/web/src/components/dashboard/event-hover-card.tsx`
- `cms/apps/web/src/components/dashboard/goal-progress-badge.tsx`
- `cms/apps/web/src/components/dashboard/event-goal-panel.tsx`
- `cms/apps/web/src/components/schedules/gtfs-import.tsx`
- `cms/apps/web/src/components/routes/delete-route-dialog.tsx`
- `cms/apps/web/src/components/schedules/delete-calendar-dialog.tsx`
- `cms/apps/web/src/components/schedules/delete-trip-dialog.tsx`
- `cms/apps/web/src/components/drivers/delete-driver-dialog.tsx`
- `cms/apps/web/src/components/users/delete-user-dialog.tsx`
- `cms/apps/web/src/components/stops/delete-stop-dialog.tsx`
- `cms/apps/web/src/components/documents/delete-document-dialog.tsx`

**Documentation (2 files):**
- `cms/design-system/vtv/MASTER.md` — updated palette + radius rules
- `.claude/commands/_shared/tailwind-token-map.md` — update emerald→teal references

**Total: 20 files modified, 0 files created.**

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules
- `cms/apps/web/CLAUDE.md` — Frontend conventions, React 19 anti-patterns

### Token Files (read first to understand current state)
- `cms/packages/ui/src/tokens.css` — Three-tier token system (the main file to rewrite)
- `cms/apps/web/src/app/globals.css` — shadcn theme variables + dark mode

### Pattern Files
- `cms/apps/web/src/components/ui/badge.tsx` — Badge component with `rounded-full`
- `cms/apps/web/src/components/ui/progress.tsx` — Progress bar with `rounded-full`
- `cms/apps/web/src/components/ui/avatar.tsx` — Avatar (DO NOT change `rounded-full`)
- `cms/apps/web/src/components/ui/switch.tsx` — Switch (DO NOT change `rounded-full`)

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping table in `@_shared/tailwind-token-map.md`. The token map will be updated in Task 9 to reflect emerald→teal renaming.

## React 19 Coding Rules

No new components created — only editing existing files. No React 19 anti-pattern risk.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Update tokens.css — Primitive Tier (Colors + Radius)
**File:** `cms/packages/ui/src/tokens.css` (modify)
**Action:** UPDATE

Replace the entire TIER 1: PRIMITIVE TOKENS `@theme { ... }` block. Changes:

**Navy scale** — shift hue from 260→268, adjust lightness/chroma for Merkle deep navy:
```css
--color-navy-50:  oklch(0.97 0.005 268);
--color-navy-100: oklch(0.93 0.01 268);
--color-navy-200: oklch(0.85 0.02 268);
--color-navy-400: oklch(0.55 0.07 268);
--color-navy-600: oklch(0.35 0.09 268);
--color-navy-800: oklch(0.22 0.10 268);
--color-navy-900: oklch(0.17 0.09 268);
--color-navy-950: oklch(0.12 0.06 268);
```

**Slate scale** — shift hue from 265→275 (blue-purple tint from Merkle #60607D/#8888A1):
```css
--color-slate-50:  oklch(0.98 0.003 275);
--color-slate-100: oklch(0.95 0.005 275);
--color-slate-200: oklch(0.90 0.008 275);
--color-slate-300: oklch(0.82 0.012 275);
--color-slate-400: oklch(0.65 0.02 275);
--color-slate-500: oklch(0.55 0.025 275);
--color-slate-600: oklch(0.47 0.03 275);
--color-slate-700: oklch(0.37 0.025 275);
--color-slate-800: oklch(0.28 0.02 275);
--color-slate-900: oklch(0.20 0.015 275);
```

**Blue scale** — shift hue from 240→250, match Merkle #0391F2:
```css
--color-blue-400: oklch(0.72 0.16 250);
--color-blue-500: oklch(0.65 0.18 250);
--color-blue-600: oklch(0.58 0.20 250);
--color-blue-700: oklch(0.50 0.18 250);
```

**Rename emerald→teal** (Merkle #06757E success color):
```css
/* Teal scale (success — replaces emerald, from Merkle #06757E) */
--color-teal-400: oklch(0.58 0.09 196);
--color-teal-500: oklch(0.50 0.08 196);
--color-teal-600: oklch(0.44 0.08 196);
```

**Red scale** — add missing red-50/red-200 for error backgrounds, adjust to Merkle #DD3039:
```css
--color-red-50:  oklch(0.97 0.01 23);
--color-red-200: oklch(0.88 0.05 23);
--color-red-500: oklch(0.58 0.22 23);
--color-red-600: oklch(0.50 0.22 23);
```

**Amber scale** — retain as-is (no Merkle equivalent, needed for delayed/warning contrast):
```css
--color-amber-400: oklch(0.85 0.17 85);
--color-amber-500: oklch(0.77 0.17 70);
```

**Purple + orange** — adjust for palette harmony, add missing purple-600:
```css
--color-purple-500: oklch(0.55 0.20 300);
--color-purple-600: oklch(0.48 0.18 300);
--color-orange-500: oklch(0.70 0.17 50);
```

**Remove** the standalone `--color-teal-500` entry (now part of teal scale above).
**Remove** the standalone `--color-emerald-500` entry (replaced by teal).

**Radius tokens** — set all to 0:
```css
--radius-sm: 0;
--radius-md: 0;
--radius-lg: 0;
--radius-xl: 0;
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web build` passes (CSS changes only, should succeed)

---

### Task 2: Update tokens.css — Semantic + Component Tiers
**File:** `cms/packages/ui/src/tokens.css` (modify, same file as Task 1)
**Action:** UPDATE

In TIER 2: SEMANTIC TOKENS, update all `var(--color-emerald-*)` references to `var(--color-teal-*)`:

```css
/* Transit status — emerald→teal */
--color-status-ontime: var(--color-teal-500);

/* Calendar event categories — emerald→teal */
--color-category-driver-shift: var(--color-teal-500);

/* Event subtypes — emerald→teal */
--color-event-shift: var(--color-teal-500);

/* Route transport types — emerald→teal */
--color-transport-trolleybus: var(--color-teal-500);

/* Stop location types — emerald→teal */
--color-stop-terminus: var(--color-teal-500);

/* Transport tram — now uses defined purple-600 */
--color-transport-tram: var(--color-purple-600);
```

In TIER 3: COMPONENT TOKENS, update the dark mode `.dark` block — change navy active bg oklch values to match new hue 275:
```css
/* Dark mode component overrides — hue 265→275 */
--color-nav-active-bg: oklch(0.98 0.003 275 / 12%);
--color-selected-bg: oklch(0.98 0.003 275 / 10%);
--color-filter-active-bg: oklch(0.98 0.003 275 / 12%);
```

And in the light mode component tier:
```css
--color-nav-active-bg: oklch(0.2 0.01 275 / 10%);
--color-selected-bg: oklch(0.2 0.01 275 / 8%);
--color-filter-active-bg: oklch(0.2 0.01 275 / 10%);
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web build` passes

---

### Task 3: Update globals.css — shadcn Theme Variables + Radius
**File:** `cms/apps/web/src/app/globals.css` (modify)
**Action:** UPDATE

**3a. Update `@theme inline` radius block** — replace all calc expressions with `0`:
```css
@theme inline {
  --radius-sm: 0;
  --radius-md: 0;
  --radius-lg: 0;
  --radius-xl: 0;
  --radius-2xl: 0;
  --radius-3xl: 0;
  --radius-4xl: 0;
  /* ... keep all color mappings unchanged ... */
}
```

**3b. Update `:root` variables** — set `--radius: 0` and apply Merkle-inspired navy palette:
```css
:root {
  --radius: 0;
  --background: oklch(1 0 0);
  --foreground: oklch(0.17 0.09 268);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.17 0.09 268);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.17 0.09 268);
  --primary: oklch(0.22 0.10 268);
  --primary-foreground: oklch(0.98 0.003 275);
  --secondary: oklch(0.95 0.005 275);
  --secondary-foreground: oklch(0.22 0.10 268);
  --muted: oklch(0.95 0.005 275);
  --muted-foreground: oklch(0.47 0.03 275);
  --accent: oklch(0.95 0.005 275);
  --accent-foreground: oklch(0.22 0.10 268);
  --destructive: oklch(0.55 0.22 23);
  --border: oklch(0.90 0.008 275);
  --input: oklch(0.90 0.008 275);
  --ring: oklch(0.58 0.20 250);
  --chart-1: oklch(0.58 0.20 250);
  --chart-2: oklch(0.50 0.08 196);
  --chart-3: oklch(0.22 0.10 268);
  --chart-4: oklch(0.77 0.17 70);
  --chart-5: oklch(0.55 0.20 300);
  --sidebar: oklch(0.98 0.003 275);
  --sidebar-foreground: oklch(0.17 0.09 268);
  --sidebar-primary: oklch(0.22 0.10 268);
  --sidebar-primary-foreground: oklch(0.98 0.003 275);
  --sidebar-accent: oklch(0.95 0.005 275);
  --sidebar-accent-foreground: oklch(0.22 0.10 268);
  --sidebar-border: oklch(0.90 0.008 275);
  --sidebar-ring: oklch(0.58 0.20 250);
}
```

**3c. Update `.dark` variables:**
```css
.dark {
  --background: oklch(0.17 0.09 268);
  --foreground: oklch(0.98 0.003 275);
  --card: oklch(0.22 0.10 268);
  --card-foreground: oklch(0.98 0.003 275);
  --popover: oklch(0.22 0.10 268);
  --popover-foreground: oklch(0.98 0.003 275);
  --primary: oklch(0.90 0.008 275);
  --primary-foreground: oklch(0.22 0.10 268);
  --secondary: oklch(0.28 0.02 275);
  --secondary-foreground: oklch(0.98 0.003 275);
  --muted: oklch(0.28 0.02 275);
  --muted-foreground: oklch(0.65 0.02 275);
  --accent: oklch(0.28 0.02 275);
  --accent-foreground: oklch(0.98 0.003 275);
  --destructive: oklch(0.63 0.20 23);
  --border: oklch(1 0 0 / 10%);
  --input: oklch(1 0 0 / 15%);
  --ring: oklch(0.65 0.18 250);
  --chart-1: oklch(0.65 0.18 250);
  --chart-2: oklch(0.58 0.09 196);
  --chart-3: oklch(0.77 0.17 70);
  --chart-4: oklch(0.55 0.20 300);
  --chart-5: oklch(0.58 0.22 23);
  --sidebar: oklch(0.22 0.10 268);
  --sidebar-foreground: oklch(0.98 0.003 275);
  --sidebar-primary: oklch(0.65 0.18 250);
  --sidebar-primary-foreground: oklch(0.98 0.003 275);
  --sidebar-accent: oklch(0.28 0.02 275);
  --sidebar-accent-foreground: oklch(0.98 0.003 275);
  --sidebar-border: oklch(1 0 0 / 10%);
  --sidebar-ring: oklch(0.47 0.03 275);
}
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web build` passes
- Visually verify: `cd cms && pnpm --filter @vtv/web dev` → open browser, check light mode + dark mode

---

### Task 4: Update badge.tsx — Remove rounded-full
**File:** `cms/apps/web/src/components/ui/badge.tsx` (modify)
**Action:** UPDATE

In the `badgeVariants` cva base string (line 8), replace `rounded-full` with `rounded-none`:
```
Before: "inline-flex items-center justify-center rounded-full border ..."
After:  "inline-flex items-center justify-center rounded-none border ..."
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 5: Update progress.tsx — Remove rounded-full
**File:** `cms/apps/web/src/components/ui/progress.tsx` (modify)
**Action:** UPDATE

Read the file first. Replace `rounded-full` with `rounded-none` on BOTH the track and the fill indicator elements.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 6: Update dashboard badge/progress components
**File:** Multiple dashboard components (modify)
**Action:** UPDATE

Apply `rounded-full` → `rounded-none` on badge-like and progress-bar elements in these files:

**6a. `cms/apps/web/src/components/dashboard/metric-card.tsx`:**
- Line ~39: change indicator badge `rounded-full` → `rounded-none`

**6b. `cms/apps/web/src/components/dashboard/calendar-event.tsx`:**
- Line ~80: priority badge `rounded-full` → `rounded-none`

**6c. `cms/apps/web/src/components/dashboard/event-hover-card.tsx`:**
- Line ~109: priority badge `rounded-full` → `rounded-none`
- Line ~81: DO NOT CHANGE — this is a tiny category dot (size-2), keep `rounded-full`

**6d. `cms/apps/web/src/components/dashboard/goal-progress-badge.tsx`:**
- Lines ~59, ~72: status badges `rounded-full` → `rounded-none`
- Lines ~78, ~81: progress bar track + fill `rounded-full` → `rounded-none`

**6e. `cms/apps/web/src/components/dashboard/event-goal-panel.tsx`:**
- Lines ~520, ~523: progress bar track + fill `rounded-full` → `rounded-none`
- Lines ~572, ~577: count badges `rounded-full` → `rounded-none`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 7: Update delete dialog icon containers (7 files)
**File:** Multiple delete dialog components (modify)
**Action:** UPDATE

In each of these 7 files, find the warning icon container with `rounded-full bg-status-critical/10` and replace `rounded-full` with `rounded-none`:

1. `cms/apps/web/src/components/routes/delete-route-dialog.tsx` — line ~38
2. `cms/apps/web/src/components/schedules/delete-calendar-dialog.tsx` — line ~38
3. `cms/apps/web/src/components/schedules/delete-trip-dialog.tsx` — line ~38
4. `cms/apps/web/src/components/drivers/delete-driver-dialog.tsx` — line ~40
5. `cms/apps/web/src/components/users/delete-user-dialog.tsx` — line ~38
6. `cms/apps/web/src/components/stops/delete-stop-dialog.tsx` — line ~38
7. `cms/apps/web/src/components/documents/delete-document-dialog.tsx` — line ~38

Pattern in each file:
```
Before: <div className="flex size-10 items-center justify-center rounded-full bg-status-critical/10">
After:  <div className="flex size-10 items-center justify-center rounded-none bg-status-critical/10">
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 8: Update GTFS import progress bar
**File:** `cms/apps/web/src/components/schedules/gtfs-import.tsx` (modify)
**Action:** UPDATE

Lines ~113-114: Replace `rounded-full` with `rounded-none` on the indeterminate loading bar:
```
Before: <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted">
After:  <div className="relative h-2 w-full overflow-hidden rounded-none bg-muted">

Before: <div className="absolute inset-0 h-full w-1/3 animate-pulse rounded-full bg-interactive" />
After:  <div className="absolute inset-0 h-full w-1/3 animate-pulse rounded-none bg-interactive" />
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes

---

### Task 9: Update MASTER.md design documentation
**File:** `cms/design-system/vtv/MASTER.md` (modify)
**Action:** UPDATE

Update the following sections:

**Color Palette table** — replace all hex values with Merkle-inspired palette:
| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#040E4B` | `--color-primary` |
| Secondary | `#60607D` | `--color-secondary` |
| CTA/Accent | `#0391F2` | `--color-cta` |
| Background | `#F8FAFC` | `--color-background` |
| Text | `#040E4B` | `--color-text` |
| Success | `#06757E` | `--color-status-ontime` |
| Error | `#DD3039` | `--color-error` |

**Color Notes:** "Merkle-inspired deep navy + vibrant blue. Blue-purple tinted neutrals."

**Component Specs** — update all `border-radius` values to `0`:
- Buttons: `border-radius: 0;`
- Cards: `border-radius: 0;`
- Inputs: `border-radius: 0;`
- Modals: `border-radius: 0;`

**Anti-Patterns** — add:
- "Rounded corners (any `border-radius > 0`) — Use sharp edges only"

**Pre-Delivery Checklist** — add:
- "No `rounded-*` classes except on avatars, switches, scrollbars, and status dots"

**Per-task validation:**
- Markdown renders correctly (no broken tables)

---

### Task 10: Update tailwind-token-map.md
**File:** `.claude/commands/_shared/tailwind-token-map.md` (modify)
**Action:** UPDATE

Update the mapping table to reflect emerald→teal renaming:

Replace all emerald references:
```
Before: `bg-emerald-500` → `bg-category-driver-shift` or `bg-transport-trolleybus`
After:  `bg-teal-500` → `bg-category-driver-shift` or `bg-transport-trolleybus`

Before: `text-emerald-500` → `text-transport-trolleybus` or `text-status-ontime`
After:  `text-teal-500` → `text-transport-trolleybus` or `text-status-ontime`

Before: `border-emerald-*` → referenced in forbidden list
After:  `border-teal-*` → referenced in forbidden list
```

Add note: "Border radius: ALL components use `border-radius: 0`. Do not add `rounded-*` classes except on avatars, switches, scrollbar thumbs, and status indicator dots."

**Per-task validation:**
- File renders correctly as markdown

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

- [ ] All radius tokens are 0 in tokens.css
- [ ] `--radius: 0` in globals.css :root
- [ ] All `--radius-*` are 0 in globals.css @theme inline
- [ ] No `rounded-full` on badges — verify badge.tsx
- [ ] No `rounded-full` on progress bars — verify progress.tsx
- [ ] Delete dialog icon containers use `rounded-none`
- [ ] Avatars STILL use `rounded-full` (not changed)
- [ ] Switch component STILL uses `rounded-full` (not changed)
- [ ] Status dots (size-1 to size-3) STILL use `rounded-full` (not changed)
- [ ] Scrollbar thumb STILL uses `rounded-full` (not changed)
- [ ] Navy hue = 268 throughout tokens.css primitives
- [ ] Slate hue = 275 throughout tokens.css primitives
- [ ] Blue hue = 250 throughout tokens.css primitives
- [ ] No reference to `--color-emerald-*` anywhere in tokens.css
- [ ] `--color-teal-*` used in semantic tier for ontime/driver-shift/trolleybus/terminus
- [ ] MASTER.md updated with new hex values and zero radius
- [ ] tailwind-token-map.md updated with emerald→teal
- [ ] Dark mode colors updated in globals.css
- [ ] Dark mode colors updated in tokens.css component tier
- [ ] Build passes with zero errors
- [ ] Visual check: sharp corners on cards, buttons, inputs, dialogs, badges, tabs

## Acceptance Criteria

This feature is complete when:
- [ ] All color tokens reflect Merkle-inspired palette
- [ ] All radius tokens are 0 — no rounded corners anywhere except exempted elements
- [ ] Both light and dark mode display correctly
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions — all existing pages render correctly with new theme
- [ ] Design system documentation updated
- [ ] Token map reference updated
- [ ] Ready for `/commit`

## Elements NOT Changed (By Design)

These elements intentionally keep `rounded-full`:
- `avatar.tsx` — Avatar, AvatarFallback, AvatarBadge, AvatarGroupCount (circular profile images)
- `switch.tsx` — track and thumb (pill-shaped toggle is standard UX)
- `scroll-area.tsx` — scrollbar thumb
- `route-table.tsx:192` — color swatch dot (size-3)
- `event-hover-card.tsx:81` — category dot (size-2)
- `three-month-view.tsx:205` — event dot (size-1)
- `month-view.tsx:192` — event dot (size-1.5)
- `route-map.tsx:30` — status dot (size-2)
- `live-timeline.tsx:46` — pulsing status dot (size-2.5)
- `stop-table.tsx:206` — location type dot (size-2)
