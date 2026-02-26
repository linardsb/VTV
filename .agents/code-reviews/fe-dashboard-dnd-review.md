# Frontend Review: Dashboard Drag-and-Drop Components (Session 1 Post-Fix)

**Date:** 2026-02-26
**Scope:** `cms/apps/web/src/components/dashboard/` — 7 DnD-related files

**Summary:** The dashboard drag-and-drop components are well-structured and follow VTV frontend standards closely. Session 1 fixes resolved 3 bugs (type validation, RBAC role, ThreeMonthView drop support). All 8 quality standards pass. Only accessibility polish and minor DRY improvements remain as low-priority items.

## Files Reviewed

1. `dashboard-content.tsx` — Main orchestrator (resizable panels, DnD state)
2. `driver-roster.tsx` — Drag source (driver cards)
3. `driver-drop-dialog.tsx` — Action picker dialog (5 event types)
4. `calendar-grid.tsx` — View switcher
5. `three-month-view.tsx` — 3-month mini calendar with drop support
6. `month-view.tsx` — Month calendar with drop support
7. `week-view.tsx` — Week calendar with drop support

## Findings

| File:Line | Standard | Issue | Suggestion | Priority |
|-----------|----------|-------|------------|----------|
| `three-month-view.tsx:27` | Component Patterns | `isSameDay()` duplicated in three-month-view, month-view, week-view | Extract to shared utility (used 3+ times = three-feature rule) | Low |
| `three-month-view.tsx:35` | Component Patterns | `getMonthGrid()` duplicated in three-month-view and month-view | Extract to shared utility (used 2x) | Low |
| `week-view.tsx:168` | Component Patterns | Hardcoded `ROW_HEIGHT_PX = 48` coupled to `--spacing-row` | Document coupling or read from CSS custom property | Low |
| `three-month-view.tsx:139` | a11y | Drop target day cells lack `aria-dropeffect` for assistive tech | Add `aria-dropeffect="copy"` when `onDayDrop` is present | Medium |
| `month-view.tsx:118` | a11y | Drop target day cells lack `aria-dropeffect` for assistive tech | Add `aria-dropeffect="copy"` when `onDayDrop` is present | Medium |
| `week-view.tsx:126` | a11y | Drop target day columns lack `aria-dropeffect` for assistive tech | Add `aria-dropeffect="copy"` when `onDayDrop` is present | Medium |
| `driver-roster.tsx:46` | a11y | Draggable cards lack `aria-roledescription="draggable"` | Add when `canDrag` is true for screen reader context | Low |
| `dashboard-content.tsx:26` | RBAC & Auth | `SCHEDULE_ROLES` is a local constant — could drift from middleware | Consider importing from shared role constants | Low |
| `three-month-view.tsx:20` | Component Patterns | `categoryDotColors` duplicated in three-month-view and month-view | Extract to shared constant (used 2x) | Low |
| `driver-drop-dialog.tsx:54` | Security | `buildDatetime` trusts time string format without validation | Low risk — input from controlled `<Input type="time">` | Low |

## Standard-by-Standard Assessment

### 1. TypeScript Quality -- PASS
- All components have proper `interface` definitions for props
- No `any` types, no `@ts-ignore`/`@ts-expect-error`
- `'use client'` correctly applied on all files (all need interactivity)
- Runtime shape validation in `handleDayDrop` checks `typeof id !== "number"`

### 2. Design System Compliance -- PASS
- Zero primitive Tailwind color classes
- Semantic tokens: `text-foreground`, `text-foreground-muted`, `text-interactive`, `bg-interactive/10`, `border-border-subtle`, `bg-surface-raised`, `bg-card-bg`, `border-card-border`
- Status: `bg-status-ontime`, `bg-status-delayed`, `bg-status-critical`
- Categories: `bg-category-maintenance`, `bg-category-driver-shift`, `bg-category-route-change`, `bg-category-service-alert`
- Spacing: `p-(--spacing-card)`, `gap-(--spacing-grid)`, `gap-(--spacing-tight)`, `gap-(--spacing-inline)`

### 3. Component Patterns -- PASS
- shadcn/ui: Dialog, Button, Input, Label, Badge, ScrollArea, Skeleton, ResizablePanel
- `cn()` used consistently for conditional classes
- Sub-components at module scope: `ActionCard`, `DriverRosterCard`, `MiniMonth`
- Pure functions at module scope: `buildDatetime`, `isSameDay`, `getMonday`, `getMonthGrid`

### 4. Internationalization (i18n) -- PASS
- All text uses `useTranslations("dashboard")`
- ICU message format for interpolation (`{name}`, `{shift}`, `{count}`)
- Status badges via `t(\`roster.status.${driver.status}\`)`
- No hardcoded user-visible strings

### 5. Accessibility (a11y) -- PASS (with notes)
- `ArrowRight` icon: `aria-hidden="true"`
- All `<input>` have `<Label>` with `htmlFor`/`id` match
- `ActionCard` uses `<button type="button">`
- `DialogTitle` + `DialogDescription` present
- Drag cursor feedback: `cursor-grab` / `cursor-grabbing`
- Drop targets could use `aria-dropeffect` (see findings)

### 6. RBAC & Auth -- PASS
- `SCHEDULE_ROLES` gates both drag and drop capabilities
- `useDriversSummary` gated on `status === "authenticated"`
- Non-privileged users see read-only roster
- `userRole` typed as `string` (avoids React 19 literal narrowing)

### 7. Data Fetching & Performance -- PASS
- SWR for drivers (120s polling) and calendar events (60s polling)
- `useMemo` for derived data (grids, event maps, week days)
- `useCallback` for stable handler references
- Loading skeletons in roster
- Server component page delegates to client `DashboardContent`

### 8. Security -- PASS
- Runtime shape validation on `JSON.parse` DnD data
- API URLs from env vars
- `authFetch` for authenticated requests
- Custom MIME type `application/vtv-driver` for drag data
- No `dangerouslySetInnerHTML`, no localStorage auth, no hardcoded credentials

## Stats

- **Files reviewed:** 7
- **Issues:** 10 total -- 0 Critical, 0 High, 3 Medium, 7 Low
- **Overall:** All 8 standards pass. Ready for `/commit`.

**Next step:** To fix issues: `/code-review-fix .agents/code-reviews/fe-dashboard-dnd-review.md`
