# Execution Report: Fix Schedules Page Sheet Panel

## Summary

**Issue:** Clicking any calendar row (or trip, or opening any detail/form Sheet) on the Schedules page caused the page to "gray out" with no visible panel.

**Root Cause:** Tailwind CSS v4 breaking change. The `sm:max-w-sm` class in the shadcn Sheet component (`sheet.tsx`) resolved to `--spacing-sm` (0.5rem = 8px) instead of the Tailwind v3 container size (24rem = 384px). This capped the Sheet panel width to 8px, making it invisible while the semi-transparent overlay (`bg-black/50`) was fully visible — creating the "graying out" effect.

**Fix:** Replaced `sm:max-w-sm` with `sm:max-w-[24rem]` (explicit value) for both `right` and `left` sheet sides.

## Verification

- `--spacing-sm` = 0.5rem (8px) — defined in tokens.css, incorrectly consumed by `max-w-sm`
- `--container-sm` = empty — no Tailwind v4 container variable defined
- Before fix: Sheet panel computed width = 8px
- After fix: Sheet panel computed width = 384px (correct)

## Blast Radius

This fix restores Sheet panels across **14 components**: all schedule (calendar-detail, calendar-form, trip-detail, trip-form), route (route-detail, route-form, route-filters), stop (stop-form, stop-detail, stop-filters), document (document-detail, document-upload-form, document-filters), and sidebar components.

## Files Modified

- `cms/apps/web/src/components/ui/sheet.tsx` — replaced `sm:max-w-sm` → `sm:max-w-[24rem]`

## Validation

- TypeScript: PASS
- Lint: PASS (zero errors, zero warnings)
- Build: PASS
- Visual verification: Sheet panel renders correctly at proper width
