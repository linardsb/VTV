# Plan: Compact Stops Pagination

## Feature Metadata
**Feature Type**: Enhancement (Bug Fix)
**Estimated Complexity**: Low
**Route**: `/[locale]/(dashboard)/stops` (existing)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer

## Feature Description

The stops page pagination currently renders ALL page number buttons (e.g., 84 buttons for 1664 stops at 20/page). Because the table lives inside a resizable panel that shares horizontal space with the Leaflet map, the pagination overflows behind the map — the last page buttons and the "Next" arrow are unreachable.

The fix replaces the naive all-pages rendering with a compact windowed pagination that shows at most 7 items: first page, last page, current page with ±1 neighbors, and ellipsis gaps. The "Previous"/"Next" text labels are also removed (chevron-only) since the panel is space-constrained.

This same fix is applied to ALL table components that use pagination for consistency, since they all share the same bug pattern (route-table already caps at 5 but doesn't window around the current page).

## Design System

### Master Rules (from MASTER.md)
- 44×44px minimum touch targets for interactive elements
- Transitions 150-300ms for state changes
- Semantic tokens only — no primitive Tailwind color classes

### Page Override
- None — this is a component-level fix, not a page design

### Tokens Used
- `text-foreground-muted` — "Showing X-Y of Z" text
- `border-border` — pagination container top border
- `--spacing-card` — pagination container horizontal padding
- `--spacing-tight` — pagination container vertical padding

## Components Needed

### Existing (shadcn/ui)
- `Pagination`, `PaginationContent`, `PaginationItem`, `PaginationLink` — existing wrapper
- `PaginationPrevious`, `PaginationNext` — prev/next with chevrons
- `PaginationEllipsis` — already exported from `ui/pagination.tsx` but never used

### New shadcn/ui to Install
- None

### Custom Components to Create
- None — the fix is a helper function `getPageRange()` added at module scope in `stop-table.tsx`

## i18n Keys

### Latvian (`lv.json`)
No new keys needed. The existing `stops.table.showing` key with `{from}`, `{to}`, `{total}` interpolation handles the count display. The `pagination.previous` and `pagination.next` keys exist but are hardcoded in the shadcn/ui component — we override with chevron-only buttons.

### English (`en.json`)
No new keys needed.

## Data Fetching

No changes — pagination is purely a UI concern. The `fetchStops()` call already uses server-side pagination with `page` and `page_size` parameters.

## RBAC Integration

No changes needed.

## Sidebar Navigation

No changes needed.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/ui/pagination.tsx` — Available pagination primitives including `PaginationEllipsis`
- `cms/apps/web/src/components/routes/route-table.tsx:250-296` — Route table pagination (reference for consistent pattern)

### Files to Modify
- `cms/apps/web/src/components/stops/stop-table.tsx` — Main target: fix pagination overflow
- `cms/apps/web/src/components/routes/route-table.tsx` — Apply same windowed pattern for consistency
- `cms/apps/web/src/components/drivers/driver-table.tsx` — Apply same windowed pattern for consistency
- `cms/apps/web/src/components/users/user-table.tsx` — Apply same windowed pattern for consistency
- `cms/apps/web/src/components/documents/document-table.tsx` — Apply same windowed pattern for consistency
- `cms/apps/web/src/components/schedules/calendar-table.tsx` — Apply same windowed pattern for consistency
- `cms/apps/web/src/components/schedules/trip-table.tsx` — Apply same windowed pattern for consistency

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping table and forbidden class list are loaded via `@_shared/tailwind-token-map.md`. Key rules:
- Use the mapping table for all color decisions
- Check `cms/packages/ui/src/tokens.css` for available tokens
- Exception: Inline HTML strings (Leaflet) may use hex colors. GTFS route color data values are acceptable.

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first in the component body. TypeScript enforces block-scoped variable ordering (TS2448/TS2454). Plan tasks must respect declaration order.
- **Shared type changes require ripple-effect tasks** — When adding a field to a shared interface (e.g., `BusPosition`), the plan MUST include tasks to update ALL files that construct objects of that type (mock data files, test factories, etc.). Search for all usages with `Grep` before finalizing the plan.

See `cms/apps/web/CLAUDE.md` → "React 19 Anti-Patterns" for full examples.

## TypeScript Security Rules

- **Never use `as` casts on JWT token claims without runtime validation** — JWT payloads are untrusted input. `token.role as VTVRole` is unsafe — a malformed JWT could inject any string. Plan must specify `Array.includes()` validation with a safe fallback (e.g., default to `"viewer"`). Example: `validRoles.includes(token.role as string) ? (token.role as VTVRole) : "viewer"`. This applies to ALL external data: API responses, URL params, localStorage, cookies.
- **Clear `.next` cache when module resolution errors persist after fixing imports** — Turbopack caches module resolution aggressively. If you fix an import path but the dev server still shows the old "Module not found" error, the plan should note: `rm -rf cms/apps/web/.next` and restart the dev server.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

---

### Task 1: Fix stops pagination — replace all-pages with compact windowed range
**File:** `cms/apps/web/src/components/stops/stop-table.tsx` (modify)
**Action:** UPDATE

This is the primary fix. The current pagination at lines 314-343 renders ALL page buttons using `Array.from({ length: totalPages })`. With 84 pages this overflows the resizable panel.

#### 1a. Add `PaginationEllipsis` to the import

Update the import from `@/components/ui/pagination` (lines 24-30) to include `PaginationEllipsis`:

```tsx
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
```

#### 1b. Add `getPageRange` helper function at module scope

Add this BEFORE the `StopTable` component (after `CopyCoordinatesButton`, before the `StopTableProps` interface). This is a pure function, NOT a React component — define at module scope.

```tsx
/**
 * Returns an array of page numbers and ellipsis markers for compact pagination.
 * Always shows first page, last page, current page ± 1 neighbor, and ellipsis gaps.
 * Maximum 7 items rendered (e.g., [1, "…", 4, 5, 6, "…", 84]).
 */
function getPageRange(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 5) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | "ellipsis")[] = [];
  const showLeftEllipsis = current > 3;
  const showRightEllipsis = current < total - 2;

  // Always show first page
  pages.push(1);

  if (showLeftEllipsis) {
    pages.push("ellipsis");
  } else {
    // Show pages 2, 3 when near the start
    for (let i = 2; i < Math.min(current, 4); i++) {
      pages.push(i);
    }
  }

  // Current page and neighbors (ensure within bounds and not duplicating first/last)
  const rangeStart = Math.max(2, current - 1);
  const rangeEnd = Math.min(total - 1, current + 1);
  for (let i = rangeStart; i <= rangeEnd; i++) {
    if (!pages.includes(i)) {
      pages.push(i);
    }
  }

  if (showRightEllipsis) {
    pages.push("ellipsis");
  } else {
    // Show pages near the end
    for (let i = Math.max(total - 2, current + 1); i < total; i++) {
      if (!pages.includes(i)) {
        pages.push(i);
      }
    }
  }

  // Always show last page
  if (!pages.includes(total)) {
    pages.push(total);
  }

  return pages;
}
```

#### 1c. Replace the pagination rendering block

Replace lines 314-343 (the entire pagination `<div>`) with:

```tsx
{/* Pagination */}
<div className="flex items-center justify-between border-t border-border px-(--spacing-card) py-(--spacing-tight)">
  <p className="hidden sm:block text-xs text-foreground-muted whitespace-nowrap">
    {t("table.showing", { from, to, total })}
  </p>
  {totalPages > 1 && (
    <Pagination className="mx-0 w-auto justify-end">
      <PaginationContent className="gap-0.5">
        <PaginationItem>
          <PaginationPrevious
            onClick={() => onPageChange(Math.max(1, page - 1))}
            aria-disabled={page === 1}
            className={cn(
              "h-8 w-8 p-0 [&>svg]:size-4 [&>span]:hidden",
              page === 1 && "pointer-events-none opacity-50",
            )}
          />
        </PaginationItem>
        {getPageRange(page, totalPages).map((item, idx) =>
          item === "ellipsis" ? (
            <PaginationItem key={`ellipsis-${idx}`} className="hidden sm:inline-flex">
              <PaginationEllipsis className="size-8" />
            </PaginationItem>
          ) : (
            <PaginationItem key={item} className="hidden sm:inline-flex">
              <PaginationLink
                isActive={item === page}
                onClick={() => onPageChange(item)}
                className="h-8 w-8 text-xs"
              >
                {item}
              </PaginationLink>
            </PaginationItem>
          ),
        )}
        <PaginationItem>
          <PaginationNext
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            aria-disabled={page === totalPages}
            className={cn(
              "h-8 w-8 p-0 [&>svg]:size-4 [&>span]:hidden",
              page === totalPages && "pointer-events-none opacity-50",
            )}
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  )}
</div>
```

Key changes:
1. **`getPageRange()`** replaces `Array.from({ length: totalPages })` — shows max ~7 items instead of 84
2. **`PaginationEllipsis`** shown between gaps
3. **Previous/Next**: `[&>span]:hidden` hides the "Previous"/"Next" text labels, keeping only chevron arrows. `h-8 w-8 p-0` makes them compact square buttons.
4. **Page number buttons**: `h-8 w-8 text-xs` makes them smaller
5. **`Pagination` wrapper**: `className="mx-0 w-auto justify-end"` removes the default `mx-auto w-full justify-center` so the pagination right-aligns and doesn't take full width
6. **`PaginationContent`**: `gap-0.5` tightens the gap between buttons
7. **`whitespace-nowrap`** on the "Showing" text prevents it from wrapping

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

---

### Task 2: Apply same compact pagination to route-table
**File:** `cms/apps/web/src/components/routes/route-table.tsx` (modify)
**Action:** UPDATE

Read the full file first. The route table currently uses `Array.from({ length: Math.min(totalPages, 5) })` which caps at 5 pages but always shows pages 1-5 (doesn't window around current page).

Apply the same fix pattern as Task 1:

1. Add `PaginationEllipsis` to the pagination import
2. Add the same `getPageRange` helper at module scope (before the component)
3. Replace the pagination block with the identical compact pattern from Task 1

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

---

### Task 3: Apply same compact pagination to driver-table
**File:** `cms/apps/web/src/components/drivers/driver-table.tsx` (modify)
**Action:** UPDATE

Read the full file first. Apply the same fix pattern as Task 1:

1. Add `PaginationEllipsis` to the pagination import
2. Add the same `getPageRange` helper at module scope
3. Replace the pagination block with the identical compact pattern

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

---

### Task 4: Apply same compact pagination to user-table
**File:** `cms/apps/web/src/components/users/user-table.tsx` (modify)
**Action:** UPDATE

Read the full file first. Apply the same fix pattern as Task 1:

1. Add `PaginationEllipsis` to the pagination import
2. Add the same `getPageRange` helper at module scope
3. Replace the pagination block with the identical compact pattern

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

---

### Task 5: Apply same compact pagination to document-table
**File:** `cms/apps/web/src/components/documents/document-table.tsx` (modify)
**Action:** UPDATE

Read the full file first. Apply the same fix pattern as Task 1:

1. Add `PaginationEllipsis` to the pagination import
2. Add the same `getPageRange` helper at module scope
3. Replace the pagination block with the identical compact pattern

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

---

### Task 6: Apply same compact pagination to calendar-table
**File:** `cms/apps/web/src/components/schedules/calendar-table.tsx` (modify)
**Action:** UPDATE

Read the full file first. Apply the same fix pattern as Task 1:

1. Add `PaginationEllipsis` to the pagination import
2. Add the same `getPageRange` helper at module scope
3. Replace the pagination block with the identical compact pattern

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

---

### Task 7: Apply same compact pagination to trip-table
**File:** `cms/apps/web/src/components/schedules/trip-table.tsx` (modify)
**Action:** UPDATE

Read the full file first. Apply the same fix pattern as Task 1:

1. Add `PaginationEllipsis` to the pagination import
2. Add the same `getPageRange` helper at module scope
3. Replace the pagination block with the identical compact pattern

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
```

---

### Task 8: Extract shared `getPageRange` to avoid duplication (three-feature rule)
**File:** `cms/apps/web/src/lib/pagination-utils.ts` (create)
**Action:** CREATE

Since `getPageRange` is now duplicated across 7 table components (exceeding the three-feature rule), extract it to a shared utility:

```tsx
/**
 * Returns an array of page numbers and ellipsis markers for compact pagination.
 * Always shows first page, last page, current page ± 1 neighbor, and ellipsis gaps.
 * Maximum 7 items rendered (e.g., [1, "…", 4, 5, 6, "…", 84]).
 */
export function getPageRange(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 5) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | "ellipsis")[] = [];
  const showLeftEllipsis = current > 3;
  const showRightEllipsis = current < total - 2;

  pages.push(1);

  if (showLeftEllipsis) {
    pages.push("ellipsis");
  } else {
    for (let i = 2; i < Math.min(current, 4); i++) {
      pages.push(i);
    }
  }

  const rangeStart = Math.max(2, current - 1);
  const rangeEnd = Math.min(total - 1, current + 1);
  for (let i = rangeStart; i <= rangeEnd; i++) {
    if (!pages.includes(i)) {
      pages.push(i);
    }
  }

  if (showRightEllipsis) {
    pages.push("ellipsis");
  } else {
    for (let i = Math.max(total - 2, current + 1); i < total; i++) {
      if (!pages.includes(i)) {
        pages.push(i);
      }
    }
  }

  if (!pages.includes(total)) {
    pages.push(total);
  }

  return pages;
}
```

Then update ALL 7 table files to:
1. Remove the local `getPageRange` function
2. Add `import { getPageRange } from "@/lib/pagination-utils";`

Files to update (remove local, add import):
- `cms/apps/web/src/components/stops/stop-table.tsx`
- `cms/apps/web/src/components/routes/route-table.tsx`
- `cms/apps/web/src/components/drivers/driver-table.tsx`
- `cms/apps/web/src/components/users/user-table.tsx`
- `cms/apps/web/src/components/documents/document-table.tsx`
- `cms/apps/web/src/components/schedules/calendar-table.tsx`
- `cms/apps/web/src/components/schedules/trip-table.tsx`

**Per-task validation:**
```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
cd cms && pnpm --filter @vtv/web build
```

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

- [ ] Stops pagination shows max ~7 page items (first, ellipsis, neighbors, current, ellipsis, last)
- [ ] Previous/Next buttons show chevrons only (no text labels)
- [ ] Pagination fits within the resizable panel without overflowing behind the map
- [ ] Clicking page numbers navigates correctly
- [ ] Clicking prev/next navigates correctly
- [ ] First/last page disables prev/next respectively
- [ ] Ellipsis appears when current page is far from first/last
- [ ] With ≤5 total pages, all page numbers show without ellipsis
- [ ] All 7 table components use the shared `getPageRange` from `pagination-utils.ts`
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] No regressions in existing table functionality

## Acceptance Criteria

This feature is complete when:
- [ ] Pagination on stops page fits within the resizable panel
- [ ] All 7 table components have consistent compact pagination
- [ ] `getPageRange` is extracted to shared utility (three-feature rule)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`

## getPageRange Algorithm Examples

For reference, here's what `getPageRange` produces for various inputs:

| Current | Total | Output |
|---------|-------|--------|
| 1 | 3 | `[1, 2, 3]` |
| 1 | 5 | `[1, 2, 3, 4, 5]` |
| 1 | 84 | `[1, 2, 3, …, 84]` |
| 2 | 84 | `[1, 2, 3, …, 84]` |
| 5 | 84 | `[1, …, 4, 5, 6, …, 84]` |
| 42 | 84 | `[1, …, 41, 42, 43, …, 84]` |
| 83 | 84 | `[1, …, 82, 83, 84]` |
| 84 | 84 | `[1, …, 82, 83, 84]` |

Maximum rendered items: 7 (first + ellipsis + 3 neighbors + ellipsis + last).
