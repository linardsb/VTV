# Plan: Convert All Side-Panel Sheets to Centered Dialogs

## Feature Metadata
**Feature Type**: Enhancement (UX consistency refactor)
**Estimated Complexity**: Medium
**Auth Required**: N/A (no new routes)
**Allowed Roles**: N/A (no RBAC changes)

## Feature Description

All detail views, create/edit forms, and upload panels across the CMS currently use `Sheet` (right-side sliding panel) while only the calendar dialog and delete confirmations use centered `Dialog` modals. The user wants unified UX: every popup/modal should be a centered Dialog, matching the calendar-dialog pattern visible in the schedules page.

This plan converts 10 components from `Sheet` to `Dialog` and deletes 1 unused component (`calendar-detail.tsx`). No new files are created. No i18n, RBAC, sidebar, or page-level changes are needed since component prop interfaces remain identical — only the internal rendering primitive changes.

**Components to convert (Sheet → Dialog):**

| # | Component | Current | Target Width |
|---|-----------|---------|-------------|
| 1 | `route-detail.tsx` | Sheet 400px | Dialog `sm:max-w-md` |
| 2 | `route-form.tsx` | Sheet 420px | Dialog `sm:max-w-lg` |
| 3 | `stop-detail.tsx` | Sheet 400px | Dialog `sm:max-w-md` |
| 4 | `stop-form.tsx` | Sheet 400px (non-inline) | Dialog `sm:max-w-lg` |
| 5 | `trip-detail.tsx` | Sheet 480px | Dialog `sm:max-w-xl` |
| 6 | `trip-form.tsx` | Sheet 400px | Dialog `sm:max-w-lg` |
| 7 | `driver-detail.tsx` | Sheet 400px | Dialog `sm:max-w-md` |
| 8 | `driver-form.tsx` | Sheet 420px | Dialog `sm:max-w-lg` |
| 9 | `document-detail.tsx` | Sheet 480px | Dialog `sm:max-w-xl` |
| 10 | `document-upload-form.tsx` | Sheet 480px | Dialog `sm:max-w-lg` |

**Already correct (no changes needed):**
- `calendar-dialog.tsx` — already Dialog (this is the reference pattern)
- `calendar-form.tsx` — already Dialog
- All 6 `delete-*-dialog.tsx` components — already Dialog
- Filter components (`*-filters.tsx`) — these use Sheet for mobile filter drawers, which is the correct UX
- `app-sidebar.tsx` — uses Sheet for mobile hamburger menu, which is correct

**Dead code to remove:**
- `calendar-detail.tsx` — not imported anywhere (schedules page uses `calendar-dialog.tsx` directly)

## Design System

### Master Rules (from MASTER.md)
- All interactive elements must have `cursor-pointer`
- Transitions 150-300ms for state changes
- No hardcoded colors — use semantic tokens
- Modals: `border-radius: 16px`, `box-shadow: var(--shadow-xl)`, `max-width: 500px` (MASTER.md default; we use shadcn Dialog which handles this)

### Tokens Used
- `--spacing-card` (0.75rem) — internal section spacing
- `--spacing-grid` (0.75rem) — grid gaps
- `--spacing-inline` (0.375rem) — icon-to-text gaps
- `--spacing-tight` (0.25rem) — micro gaps
- `--color-foreground`, `--color-foreground-muted`, `--color-label-text` — text colors
- `--color-border`, `--color-status-*`, `--color-surface` — accents and borders

## Conversion Pattern

Every task follows the same mechanical transformation. The reference implementation is `calendar-dialog.tsx`.

### Step A: Import Swap

**Remove:**
```tsx
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
```

**Add:**
```tsx
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
```

### Step B: Wrapper Swap

**From:**
```tsx
<Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
  <SheetContent side="right" className="w-full overflow-y-auto sm:w-[Xpx]">
    <SheetHeader>
      <SheetTitle className="font-heading text-heading font-semibold">
        {title}
      </SheetTitle>
    </SheetHeader>
    <div className="px-4 pb-4 space-y-(--spacing-card)">
      {/* content */}
    </div>
  </SheetContent>
</Sheet>
```

**To:**
```tsx
<Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
  <DialogContent className="sm:max-w-[SIZE] max-h-[90vh] overflow-y-auto" showCloseButton>
    <DialogHeader>
      <DialogTitle className="font-heading text-heading font-semibold">
        {title}
      </DialogTitle>
      <DialogDescription className="sr-only">
        {screenReaderDescription}
      </DialogDescription>
    </DialogHeader>
    <div className="space-y-(--spacing-card)">
      {/* content — remove px-4 pb-4, DialogContent has p-6 built in */}
    </div>
  </DialogContent>
</Dialog>
```

### Step C: Width Mapping

| Sheet Width | Dialog Max-Width | Notes |
|-------------|-----------------|-------|
| `sm:w-[400px]` (detail views) | `sm:max-w-md` (448px) | Simple info display |
| `sm:w-[420px]` (forms) | `sm:max-w-lg` (512px, Dialog default) | Can omit class |
| `sm:w-[480px]` (content-heavy) | `sm:max-w-xl` (576px) | Trip detail, documents |

### Step D: Padding Adjustment

- DialogContent has `p-6` and `gap-4` built in
- Remove any `px-4 pb-4` wrapper divs that were compensating for SheetContent's narrower default padding
- If content used `mt-6` or `mt-(--spacing-grid)` to offset from SheetHeader, remove that too since DialogHeader already has `gap-4` spacing

### Step E: Accessibility

- **REQUIRED**: Add `<DialogDescription className="sr-only">` inside `<DialogHeader>` — Radix requires this for a11y. Use the component's title translation as fallback text.
- The `showCloseButton` prop is `true` by default on DialogContent, so the X button appears automatically.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Reference Implementation (Pattern to Follow)
- `cms/apps/web/src/components/schedules/calendar-dialog.tsx` — The gold standard centered Dialog with view/edit mode

### UI Primitives (Understand the API)
- `cms/apps/web/src/components/ui/dialog.tsx` — Dialog component API (DialogContent has `p-6`, `gap-4`, `sm:max-w-lg` default, `showCloseButton` prop)
- `cms/apps/web/src/components/ui/sheet.tsx` — Sheet component API (being replaced)

### Files to Modify (10 conversions)
- `cms/apps/web/src/components/routes/route-detail.tsx`
- `cms/apps/web/src/components/routes/route-form.tsx`
- `cms/apps/web/src/components/stops/stop-detail.tsx`
- `cms/apps/web/src/components/stops/stop-form.tsx`
- `cms/apps/web/src/components/schedules/trip-detail.tsx`
- `cms/apps/web/src/components/schedules/trip-form.tsx`
- `cms/apps/web/src/components/drivers/driver-detail.tsx`
- `cms/apps/web/src/components/drivers/driver-form.tsx`
- `cms/apps/web/src/components/documents/document-detail.tsx`
- `cms/apps/web/src/components/documents/document-upload-form.tsx`

### File to Delete (dead code)
- `cms/apps/web/src/components/schedules/calendar-detail.tsx`

## Design System Color Rules

The executor MUST NOT introduce any primitive Tailwind color classes during the conversion. All existing semantic classes must be preserved as-is. No color changes should be needed — this is a structural swap only.

## React 19 Coding Rules

- **No `setState` in `useEffect`** — not relevant to this refactor, but don't introduce any
- **No component definitions inside components** — `DetailRow` helper components in each file are already at module scope; keep them there
- **DialogDescription is required** — Radix Dialog throws a console warning without it; use `className="sr-only"` to hide visually

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Convert route-detail.tsx (Sheet → Dialog)
**File:** `cms/apps/web/src/components/routes/route-detail.tsx` (modify)
**Action:** UPDATE

1. Replace Sheet imports with Dialog imports (Step A pattern above)
2. Replace `<Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>` with `<Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>`
3. Replace `<SheetContent side="right" className="w-full overflow-y-auto sm:w-[400px]">` with `<DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto" showCloseButton>`
4. Replace `<SheetHeader>` with `<DialogHeader>`
5. Replace `<SheetTitle ...>` with `<DialogTitle ...>`
6. Add after DialogTitle: `<DialogDescription className="sr-only">{route.route_short_name} — {route.route_long_name}</DialogDescription>`
7. Add `<RouteTypeBadge>` AFTER `</DialogHeader>` (move it out of header since Dialog header has different layout)
8. Replace `</SheetContent>` with `</DialogContent>`, `</Sheet>` with `</Dialog>`
9. Change `<div className="px-4 pb-4 space-y-(--spacing-card)">` to `<div className="space-y-(--spacing-card)">` (remove px-4 pb-4 — Dialog has p-6)

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 2: Convert route-form.tsx (Sheet → Dialog)
**File:** `cms/apps/web/src/components/routes/route-form.tsx` (modify)
**Action:** UPDATE

1. Replace Sheet imports with Dialog imports (Step A). Also import `DialogDescription`
2. Replace `<Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>` with `<Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>`
3. Replace `<SheetContent side="right" className="w-full overflow-y-auto sm:w-[420px]">` with `<DialogContent className="max-h-[90vh] overflow-y-auto" showCloseButton>` (default `sm:max-w-lg` is fine for forms)
4. Replace `<SheetHeader>` / `<SheetTitle>` with `<DialogHeader>` / `<DialogTitle>`
5. Add after DialogTitle: `<DialogDescription className="sr-only">{mode === "create" ? t("form.createTitle") : t("form.editTitle")}</DialogDescription>`
6. Replace closing tags: `</SheetContent>` → `</DialogContent>`, `</Sheet>` → `</Dialog>`
7. Change `<form onSubmit={handleSubmit} className="mt-6 space-y-5 px-4 pb-4">` to `<form onSubmit={handleSubmit} className="space-y-5">` (remove mt-6, px-4, pb-4)

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 3: Convert stop-detail.tsx (Sheet → Dialog)
**File:** `cms/apps/web/src/components/stops/stop-detail.tsx` (modify)
**Action:** UPDATE

This component uses `open` + `onOpenChange` props (not `isOpen` + `onClose`). Dialog supports the same API.

1. Replace Sheet imports with Dialog imports (Step A)
2. Replace `<Sheet open={open} onOpenChange={onOpenChange}>` with `<Dialog open={open} onOpenChange={onOpenChange}>`
3. Replace `<SheetContent side="right" className="w-full overflow-y-auto sm:w-[400px]">` with `<DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto" showCloseButton>`
4. Replace header components: `SheetHeader` → `DialogHeader`, `SheetTitle` → `DialogTitle`
5. Add `<DialogDescription className="sr-only">{stop?.stop_name ?? ""}</DialogDescription>` after DialogTitle
6. Replace closing tags
7. Remove wrapper div's Sheet-specific padding if present (check the actual file for `px-4 pb-4` patterns)

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 4: Convert stop-form.tsx (Sheet → Dialog, preserve inline mode)
**File:** `cms/apps/web/src/components/stops/stop-form.tsx` (modify)
**Action:** UPDATE

This component has TWO rendering modes:
- **`inline` mode** (desktop): Renders raw JSX in a resizable panel — **DO NOT CHANGE THIS**
- **Sheet mode** (mobile/default): Renders in a Sheet — **CONVERT TO DIALOG**

1. Replace Sheet imports with Dialog imports (Step A)
2. Find the Sheet rendering block (around line 382-393):
   ```tsx
   <Sheet open={open} onOpenChange={onOpenChange}>
     <SheetContent side="right" className="w-full overflow-y-auto sm:w-[400px]">
       <SheetHeader>
         <SheetTitle className="font-heading text-heading font-semibold">
           {title}
         </SheetTitle>
       </SheetHeader>
       <div className="mt-(--spacing-grid)">{formBody}</div>
     </SheetContent>
   </Sheet>
   ```
3. Replace with:
   ```tsx
   <Dialog open={open} onOpenChange={onOpenChange}>
     <DialogContent className="max-h-[90vh] overflow-y-auto" showCloseButton>
       <DialogHeader>
         <DialogTitle className="font-heading text-heading font-semibold">
           {title}
         </DialogTitle>
         <DialogDescription className="sr-only">{title}</DialogDescription>
       </DialogHeader>
       {formBody}
     </DialogContent>
   </Dialog>
   ```
4. The `inline` rendering path (line 360-378) stays exactly as-is
5. Remove the `mt-(--spacing-grid)` wrapper since Dialog has built-in gap

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 5: Convert trip-detail.tsx (Sheet → Dialog)
**File:** `cms/apps/web/src/components/schedules/trip-detail.tsx` (modify)
**Action:** UPDATE

This component is wider (480px) because it has a stop times table. Use `sm:max-w-xl`.

1. Replace Sheet imports with Dialog imports (Step A)
2. Replace `<Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>` with `<Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>`
3. Replace `<SheetContent side="right" className="w-full overflow-y-auto sm:w-[480px]">` with `<DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto" showCloseButton>`
4. Replace header components: `SheetHeader` → `DialogHeader`, `SheetTitle` → `DialogTitle`
5. Add `<DialogDescription className="sr-only">{trip?.gtfs_trip_id ?? ""}</DialogDescription>` after DialogTitle
6. Replace closing tags
7. Remove any Sheet-specific padding from content wrapper divs

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 6: Convert trip-form.tsx (Sheet → Dialog)
**File:** `cms/apps/web/src/components/schedules/trip-form.tsx` (modify)
**Action:** UPDATE

1. Replace Sheet imports with Dialog imports (Step A)
2. Replace `<Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>` with `<Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>`
3. Replace `<SheetContent side="right" className="w-full overflow-y-auto sm:w-[400px]">` with `<DialogContent className="max-h-[90vh] overflow-y-auto" showCloseButton>`
4. Replace header components and add DialogDescription (sr-only with form title)
5. Replace closing tags
6. Remove any `mt-*` or `px-4 pb-4` spacers from the form wrapper

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 7: Convert driver-detail.tsx (Sheet → Dialog)
**File:** `cms/apps/web/src/components/drivers/driver-detail.tsx` (modify)
**Action:** UPDATE

This component uses `open` + `onOpenChange` props.

1. Replace Sheet imports with Dialog imports (Step A)
2. Replace `<Sheet open={open} onOpenChange={onOpenChange}>` with `<Dialog open={open} onOpenChange={onOpenChange}>`
3. Replace `<SheetContent side="right" className="...">` with `<DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto" showCloseButton>`
4. Replace header components: `SheetHeader` → `DialogHeader`, `SheetTitle` → `DialogTitle`
5. Add `<DialogDescription className="sr-only">{driver.first_name} {driver.last_name}</DialogDescription>` after DialogTitle
6. Replace closing tags
7. Remove Sheet-specific padding from content wrapper

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 8: Convert driver-form.tsx (Sheet → Dialog)
**File:** `cms/apps/web/src/components/drivers/driver-form.tsx` (modify)
**Action:** UPDATE

This component uses `open` + `onOpenChange` props. It's a long form (~313 lines).

1. Replace Sheet imports with Dialog imports (Step A)
2. Replace `<Sheet open={open} onOpenChange={onOpenChange}>` with `<Dialog open={open} onOpenChange={onOpenChange}>`
3. Replace `<SheetContent side="right" className="...sm:w-[420px]">` with `<DialogContent className="max-h-[90vh] overflow-y-auto" showCloseButton>`
4. Replace header components and add DialogDescription
5. Replace closing tags
6. Remove Sheet-specific padding from form wrapper

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 9: Convert document-detail.tsx (Sheet → Dialog)
**File:** `cms/apps/web/src/components/documents/document-detail.tsx` (modify)
**Action:** UPDATE

This component uses `ScrollArea` inside Sheet for content preview. After conversion, the Dialog's `max-h-[90vh] overflow-y-auto` handles scrolling, so `ScrollArea` may still be useful for the chunks preview section but the outer scroll is handled by DialogContent.

1. Replace Sheet imports with Dialog imports (Step A)
2. Replace `<Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>` with `<Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>`
3. Replace `<SheetContent side="right" className="... sm:w-[480px]">` with `<DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto" showCloseButton>`
4. Replace header components: `SheetHeader` → `DialogHeader`, `SheetTitle` → `DialogTitle`
5. Add `<DialogDescription className="sr-only">{document?.title ?? document?.file_name ?? ""}</DialogDescription>` after DialogTitle
6. Replace closing tags
7. Remove Sheet-specific padding from content wrapper

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 10: Convert document-upload-form.tsx (Sheet → Dialog)
**File:** `cms/apps/web/src/components/documents/document-upload-form.tsx` (modify)
**Action:** UPDATE

1. Replace Sheet imports with Dialog imports (Step A)
2. Replace `<Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>` with `<Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>`
3. Replace `<SheetContent side="right" className="... sm:w-[480px]">` with `<DialogContent className="max-h-[90vh] overflow-y-auto" showCloseButton>`
4. Replace header components and add DialogDescription (sr-only with upload title)
5. Replace closing tags
6. Remove Sheet-specific padding from content wrapper (check for `px-*` classes)

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes

---

### Task 11: Delete dead calendar-detail.tsx
**File:** `cms/apps/web/src/components/schedules/calendar-detail.tsx` (delete)
**Action:** DELETE

This file is not imported anywhere in the codebase. The schedules page uses `calendar-dialog.tsx` directly for both view and edit modes. Remove the dead code.

Verify before deleting:
```bash
cd cms && grep -r "calendar-detail" apps/web/src/
```
This should return no results.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web build` passes

---

### Task 12: Final Validation
**Action:** VALIDATE

Run the full 3-level validation pyramid:

```bash
cd cms && pnpm --filter @vtv/web type-check
cd cms && pnpm --filter @vtv/web lint
cd cms && pnpm --filter @vtv/web build
```

All three must exit 0 with no errors.

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

- [ ] All detail views open as centered modals (not side panels)
- [ ] All create/edit forms open as centered modals (not side panels)
- [ ] Delete confirmations still work (already Dialog, unchanged)
- [ ] Stop form inline mode still works on desktop (embedded in resizable panel)
- [ ] Mobile filter drawers still work as Sheet (unchanged)
- [ ] Sidebar hamburger still works as Sheet (unchanged)
- [ ] No hardcoded colors introduced
- [ ] All DialogContent has `showCloseButton` (X button in corner)
- [ ] All DialogHeader has `DialogDescription` (even if sr-only) for a11y
- [ ] Scrollable content works in all modals (max-h-[90vh] + overflow-y-auto)

## Acceptance Criteria

This feature is complete when:
- [ ] All 10 components converted from Sheet to Dialog
- [ ] Dead `calendar-detail.tsx` deleted
- [ ] Stop form inline mode preserved (no regression)
- [ ] Filter sheets preserved (no regression)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] Visual check: all popups appear centered on screen
- [ ] Ready for `/commit`
