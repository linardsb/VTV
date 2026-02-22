# RCA: E2E Test Failures — 9 Pre-existing Playwright Failures

## Summary

9 Playwright e2e tests fail across 4 pages (dashboard, documents, routes, stops). Two systemic root causes: (1) Next.js 16 dev overlay (`<nextjs-portal>`) intercepts pointer events on interactive elements like ToggleGroup and Select dropdowns, and (2) tests don't wait for async data fetches to complete before querying DOM elements. A third minor cause is an ambiguous locator (`/next|nakamais/i`) matching both the calendar arrow and Next.js dev tools button.

## Symptoms

- Tests pass auth setup but fail on page interactions
- `<nextjs-portal>` appears in click error logs: "subtree intercepts pointer events"
- `table.isVisible()` and `noResults.isVisible()` both return false (page still loading)
- `getByRole('button', { name: /next|nakamais/i })` resolves to 2 elements (strict mode violation)

## Root Causes

### RC1: Next.js Dev Overlay Interference
**Category:** Environment / test configuration issue
**Affects:** 4 tests (dashboard arrows, documents language filter, routes type filter, stops status filter)

Next.js 16 injects a `<nextjs-portal>` element in dev mode that renders above page content. When Playwright attempts `.click()` on elements positioned below the overlay (e.g., filter ToggleGroup items near page edges), the portal intercepts pointer events and the click never reaches the target element.

### RC2: Missing Async Wait for Data Fetches
**Category:** Test design / timing
**Affects:** 6 tests (all dashboard tests, documents table, routes row click, stops search)

All VTV pages fetch data on mount via `useEffect` -> API call -> `setState`. Tests navigate to pages and immediately assert on DOM state without waiting for the fetch round-trip to complete. Using `waitForTimeout(500)` is insufficient and unreliable.

### RC3: Ambiguous Locator
**Category:** Locator specificity
**Affects:** 1 test (dashboard calendar navigation)

`page.getByRole("button", { name: /next|nakamais/i })` matches both:
1. Calendar "Next" arrow button (`aria-label="Nakamais"`)
2. Next.js dev tools button (`aria-label="Open Next.js Dev Tools"`)

## Evidence

```
# RC1 — Dev overlay intercept (from test output)
Call log:
  - <nextjs-portal></nextjs-portal> from <script data-nextjs-dev-overlay="true">…</script> subtree intercepts pointer events

# RC2 — Both table and noResults invisible (from test output)
expect(received).toBeTruthy()
Received: false
  // (await table.isVisible()) || (await noResults.isVisible())

# RC3 — Strict mode violation (from test output)
Error: strict mode violation: getByRole('button', { name: /next|nakamais/i }) resolved to 2 elements
```

## Proposed Fix

### Changes Required

1. **`cms/apps/web/e2e/auth.setup.ts`** — Already fixed. Updated label regex to match both English and Latvian (`/email|e-pasts/i`, `/password|parole/i`, `/login|pieteikties/i`).

2. **`cms/apps/web/e2e/dashboard.spec.ts`** — Fix all 3 tests:
   - Add `await page.waitForLoadState('networkidle')` after navigation
   - Scope calendar arrow locator to exclude dev tools: use `.locator('main').getByRole('button', ...)` or `page.getByLabel(/nakamais/i).first()`
   - Add `.waitFor()` for metric cards before counting

3. **`cms/apps/web/e2e/documents.spec.ts`** — Fix 2 tests:
   - Replace immediate visibility checks with `Promise.race([table.waitFor(), noResults.waitFor()])`
   - Add `{ force: true }` to language filter toggle click

4. **`cms/apps/web/e2e/routes.spec.ts`** — Fix 2 tests:
   - Add `{ force: true }` to type filter toggle click
   - Wait for table rows before attempting row click: `await page.getByRole('row').nth(1).waitFor()`

5. **`cms/apps/web/e2e/stops.spec.ts`** — Fix 2 tests:
   - Replace `waitForTimeout(500)` with proper `waitFor()` on table/noResults
   - Add `{ force: true }` to status filter select click
   - Wait for dropdown to open before selecting option

### Database Migration
Not required.

### New Tests
No new tests needed — this fixes existing tests.

## Fix Pattern Reference

**Pattern A: Wait for async data** (replaces `waitForTimeout`)
```typescript
// Before
await page.waitForTimeout(500);
const table = page.getByRole("table");

// After
await Promise.race([
  page.getByRole("row").nth(1).waitFor({ state: "visible", timeout: 5000 }),
  page.getByText(/no results|nav/i).waitFor({ state: "visible", timeout: 5000 }),
]).catch(() => {});
```

**Pattern B: Bypass dev overlay** (for ToggleGroup / Select clicks)
```typescript
// Before
await toggle.click();

// After
await toggle.click({ force: true });
```

**Pattern C: Scope ambiguous locators**
```typescript
// Before — matches dev tools button too
page.getByRole("button", { name: /next|nakamais/i });

// After — scoped to main content area
page.locator("main").getByRole("button", { name: /next|nakamais/i });
```

## Validation

After fix, run:
```bash
cd cms/apps/web && npx playwright test e2e/dashboard.spec.ts e2e/documents.spec.ts e2e/routes.spec.ts e2e/stops.spec.ts
```

Expected: all 57 tests pass (including setup).

## Impact

- **Severity:** Medium — tests fail but application functionality is correct
- **Affected users:** Development team (CI/CD pipeline reliability)
- **Related code:** All e2e test files share the same async wait and overlay issues
