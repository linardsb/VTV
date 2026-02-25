# Execution Report: Sheet-to-Dialog Conversion

**Date:** 2026-02-25
**Plan:** `.agents/plans/fe-sheet-to-dialog-conversion.md`
**Status:** Complete

## Summary

Converted all right-side sliding Sheet modals to centered Dialog modals across the entire CMS frontend. This unifies the modal UX pattern — all detail views, create/edit forms, and upload panels now use Radix Dialog centered overlays instead of side-sliding Sheets.

## Files Modified

### Components converted (Sheet → Dialog):
- `cms/apps/web/src/components/routes/route-detail.tsx`
- `cms/apps/web/src/components/routes/route-form.tsx`
- `cms/apps/web/src/components/stops/stop-detail.tsx`
- `cms/apps/web/src/components/stops/stop-form.tsx` (preserves inline mode for desktop)
- `cms/apps/web/src/components/schedules/trip-detail.tsx`
- `cms/apps/web/src/components/schedules/trip-form.tsx`
- `cms/apps/web/src/components/drivers/driver-detail.tsx`
- `cms/apps/web/src/components/drivers/driver-form.tsx`
- `cms/apps/web/src/components/documents/document-detail.tsx`
- `cms/apps/web/src/components/documents/document-upload-form.tsx`

### Other changes:
- `cms/apps/web/src/components/ui/dialog.tsx` — Fixed default width from `sm:max-w-lg` to `sm:max-w-[32rem]`
- `cms/apps/web/src/components/schedules/calendar-detail.tsx` — Deleted (dead code, not imported anywhere)

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| All dialogs render as ~50px wide strips | Tailwind v4's `sm:max-w-lg` generates `max-width: var(--container-lg)`. The project's `@theme inline` in `globals.css` does NOT define `--container-lg` (only `--container-3xl` is defined from shadcn). The undefined CSS variable resolves to nothing, causing collapse. | Replaced all named container sizes with explicit rem values: `sm:max-w-md` → `sm:max-w-[28rem]`, `sm:max-w-lg` → `sm:max-w-[32rem]`, `sm:max-w-xl` → `sm:max-w-[36rem]` |

## Validation Results

- TypeScript: PASS (0 errors)
- Lint: PASS (0 issues)
- Build: PASS (12 routes)
- Design system: PASS (0 violations)
- i18n: PASS (769 keys, lv/en in sync)
- Accessibility: PASS (0 issues)
