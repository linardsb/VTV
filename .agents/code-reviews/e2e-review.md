# Review: `/e2e`

**Summary:** The E2E test suite is well-structured with consistent patterns (bilingual selectors, graceful degradation for empty states, unique IDs for CRUD tests). Main issues are duplicated helper functions across 4 files, `waitForTimeout` anti-patterns in CRUD tests, and some flaky assertions in the drivers CRUD cleanup.

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `drivers.spec.ts:4` | `waitForDataOrEmpty` helper duplicated identically in 4 files (drivers, routes, stops, documents) | Extract to `e2e/helpers.ts` and import — avoids maintenance drift across copies | Medium |
| `routes.spec.ts:12` | `hasDataTable` helper only exists in routes but could benefit other specs | Include in shared helpers file if extracting `waitForDataOrEmpty` | Low |
| `drivers.spec.ts:120` | `waitForTimeout(1000)` used as implicit wait after form submit — fragile, may flake on slow CI | Replace with `waitForResponse` on the API endpoint or `waitFor` on the expected DOM change: `await page.waitForResponse(r => r.url().includes('/api/v1/drivers') && r.status() === 201)` | High |
| `routes.spec.ts:149` | Same `waitForTimeout(1000)` pattern after create/edit/delete | Replace with `waitForResponse` or `waitFor` on expected state | High |
| `stops.spec.ts:143` | Same `waitForTimeout(1000)` pattern after create/edit/delete | Replace with `waitForResponse` or `waitFor` on expected state | High |
| `schedules.spec.ts:206` | Same `waitForTimeout(1000)` pattern after create/edit/delete | Replace with `waitForResponse` or `waitFor` on expected state | High |
| `schedules.spec.ts:108` | `waitForTimeout(500)` used after tab click — fragile timing | Use `waitFor` on the expected content becoming visible instead | Medium |
| `documents.spec.ts:163` | `waitForTimeout(3000)` after upload — 3 seconds is arbitrary, may be too short for large uploads or too long for small files | Replace with `waitForResponse` on upload endpoint | High |
| `documents.spec.ts:187` | `waitForTimeout(1000)` after delete | Replace with `waitForResponse` or `waitForSelector` | High |
| `drivers.spec.ts:186-194` | Flaky delete verification: uses `.or()` then `.catch(() => {})` then re-checks with `isVisible()` — complex and unreliable. If `noResults` and `driverText` are both invisible the `catch` swallows the failure | Simplify: after delete + `waitForDataOrEmpty`, assert `await expect(page.getByText(empNumber)).not.toBeVisible()` or check for empty state directly | High |
| `drivers.spec.ts:94` | `const uniqueId = \`E2E-${Date.now()}\`` at module scope — `Date.now()` runs at module parse time, not at test execution time. If test runner delays, the ID is stale (not a correctness issue but misleading) | Move unique ID generation into the test body for clarity | Low |
| `routes.spec.ts:113` | Same `Date.now()` at module scope | Move into test body | Low |
| `stops.spec.ts:122` | Same `Date.now()` at module scope | Move into test body | Low |
| `schedules.spec.ts:176` | Same `Date.now()` at module scope | Move into test body | Low |
| `auth.setup.ts:5` | Default password is `"admin"` — matches the hardcoded fallback. CI uses `DEMO_USER_PASSWORD` env var but this fallback suggests weak local default | Add comment clarifying this is for local dev only where demo seed creates this user, or use a stronger default | Low |
| `login.noauth.spec.ts:27` | `test.skip` for unauthenticated redirect — this test is permanently skipped with a comment about Turbopack limitation | Add `// TODO: Re-enable when Next.js middleware works under Turbopack dev server` to track future fix, or remove if it's covered by the production build test | Low |
| `detect-changed.sh:53` | Dashboard mapping missing: `*components/dashboard/*` maps to `dashboard.spec.ts` but `*app/*/\\(dashboard\\)/page.tsx` requires shell escaping of parentheses — verify this pattern works | Test with: `echo "cms/apps/web/src/app/lv/(dashboard)/page.tsx" \| grep 'app/.*\\(dashboard\\)/page.tsx'` to confirm | Medium |
| `detect-changed.sh:66-73` | Events-related paths not mapped — `*components/dashboard/calendar-panel*` and `*hooks/use-calendar-events*` would trigger all tests instead of just `dashboard.spec.ts` | Add explicit mapping: `*hooks/use-calendar-events*\|*lib/events-client*) add_test "dashboard.spec.ts" ;;` | Medium |
| `playwright.config.ts:15` | `timeout: 30_000` for tests but CRUD tests with multiple `waitForTimeout(1000)` calls can accumulate. 30s is tight for a full create→edit→delete cycle on slow CI | Consider 45s or 60s for CI, or keep 30s and remove the `waitForTimeout` calls | Medium |
| `ci.yml:158` | `timeout 180 bash -c 'until curl -sf http://localhost:80/health; do sleep 5; done'` — 3-minute timeout for backend health but no separate check for database migration completion | The migration service runs independently and may not be done. Add a migration check or increase timeout to 240s | Low |
| `ci.yml:76` | `uv run pytest -x -q` runs all tests but doesn't split by feature — acceptable now but may need sharding as test count grows | No action needed now. Add a comment noting future sharding consideration at 1000+ tests | Low |
| `smoke.spec.ts:31-41` | Smoke test for sidebar nav duplicates logic from `navigation.spec.ts:12-17` | Remove the sidebar test from smoke.spec.ts — it's already covered by the dedicated navigation file | Low |
| `stops.spec.ts:202` | Delete verification uses `.catch(() => {})` on the `expect` — swallows assertion failures | Use `try/catch` that re-throws if the element IS visible, or wait for `not.toBeVisible` pattern | Medium |
| `routes.spec.ts:160` | After edit, searches for `uniqueId.slice(-4)` which is only 4 chars — could match unrelated routes if data exists | Use the full `gtfsRouteId` which is unique per test run | Medium |
| `schedules.spec.ts:263-273` | Trip CRUD early-returns without test feedback when no create button visible — test passes silently without testing anything | Add `test.skip()` annotation or `console.warn("Skipping: no create button")` so CI logs show it was skipped vs passed | Medium |

**Priority Guide:**
- **Critical**: Type safety violations, security issues, data corruption risks
- **High**: Missing logging, broken patterns, no tests
- **Medium**: Inconsistent naming, missing docstrings, suboptimal patterns
- **Low**: Style nits, minor improvements

**Stats:**
- Files reviewed: 13 (10 .ts + 1 .sh + 1 .yml + 1 playwright.config.ts)
- Issues: 25 total — 0 Critical, 7 High, 8 Medium, 10 Low

**Recommendations by theme:**

### 1. Extract shared helpers (Medium, 1 change)
Create `e2e/helpers.ts` with `waitForDataOrEmpty()` and `hasDataTable()`. Import in all spec files. Prevents copy-paste drift.

### 2. Replace `waitForTimeout` with deterministic waits (High, 6 files)
Every `waitForTimeout(1000)` in CRUD tests should become either:
- `await page.waitForResponse(r => r.url().includes('/api/v1/...') && r.ok())` — waits for API response
- `await expect(element).toBeVisible()` or `not.toBeVisible()` — waits for DOM state

This is the single biggest improvement for CI reliability.

### 3. Fix flaky delete verification in drivers (High, 1 file)
The `.or().catch().isVisible()` chain in `drivers.spec.ts:186-194` should be simplified to:
```typescript
await expect(page.getByText(empNumber)).not.toBeVisible({ timeout: 5000 });
```

### 4. Add events path mapping to detect-changed.sh (Medium, 1 file)
New `calendar-panel.tsx`, `use-calendar-events.ts`, and `events-client.ts` should map to `dashboard.spec.ts`.

---

**Next step:** To fix issues: `/code-review-fix .agents/code-reviews/e2e-review.md`
