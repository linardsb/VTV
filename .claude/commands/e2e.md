Run Playwright end-to-end tests for the VTV frontend.

## Context

Load test infrastructure context:
- @cms/apps/web/playwright.config.ts (Playwright configuration)
- @cms/apps/web/e2e/ (test files)
- @cms/apps/web/CLAUDE.md (frontend conventions)

## Prerequisites

Before running tests, verify the required services:
1. **Database**: `make db` — PostgreSQL + Redis must be running
2. **Backend**: Backend API must be running on port 8123 (for auth and API calls)
3. **Frontend**: The Playwright config has `webServer` that auto-starts `pnpm dev` if not already running

Check with:
```bash
curl -s http://localhost:8123/health | head -c 100   # Backend health
curl -s http://localhost:3000 -o /dev/null -w "%{http_code}"  # Frontend
```

If either service is down, start them with `make dev` (runs both) or start individually.

## Running Tests

Use the Bash tool to run Playwright tests. Do NOT use the Playwright MCP tools — use the CLI directly.

### Run all tests
```bash
cd /Users/Berzins/Desktop/VTV/cms/apps/web && npx playwright test
```

### Run specific test file
```bash
cd /Users/Berzins/Desktop/VTV/cms/apps/web && npx playwright test e2e/smoke.spec.ts
```

### Run tests matching a pattern
```bash
cd /Users/Berzins/Desktop/VTV/cms/apps/web && npx playwright test -g "dashboard loads"
```

### Run in headed mode (visible browser)
```bash
cd /Users/Berzins/Desktop/VTV/cms/apps/web && npx playwright test --headed
```

### Run with UI mode (interactive)
```bash
cd /Users/Berzins/Desktop/VTV/cms/apps/web && npx playwright test --ui
```

### Debug a failing test
```bash
cd /Users/Berzins/Desktop/VTV/cms/apps/web && npx playwright test --debug e2e/smoke.spec.ts
```

### View last test report
```bash
cd /Users/Berzins/Desktop/VTV/cms/apps/web && npx playwright show-report
```

## Visual Debugging with Browser Skill

When a test fails and you need to visually inspect the page state, use the `/Browser` skill:
1. Open the failing URL in the browser
2. Take screenshots at key interaction points
3. Check console errors and network requests
4. Compare against expected behavior

## Test Structure

```
e2e/
├── .auth/              # Saved auth state (gitignored)
│   └── user.json       # Authenticated session cookies
├── auth.setup.ts       # Login flow — runs before authenticated tests
├── smoke.spec.ts       # Authenticated smoke tests (page loads, navigation)
├── login.noauth.spec.ts # Unauthenticated tests (login form, redirects)
└── {feature}.spec.ts   # Feature-specific tests
```

### Test Projects (in playwright.config.ts)

- **setup**: Runs `auth.setup.ts` to authenticate and save session state
- **chromium**: Authenticated tests — uses saved session from setup
- **no-auth**: Unauthenticated tests — matches `*.noauth.spec.ts` files, no stored session

### Writing New Tests

**Authenticated test** (most common — user is logged in):
```typescript
// e2e/routes.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Routes page", () => {
  test("displays route table", async ({ page }) => {
    await page.goto("/lv/routes");
    await expect(page.getByRole("table")).toBeVisible();
  });
});
```

**Unauthenticated test** (login page, redirects):
```typescript
// e2e/auth-flow.noauth.spec.ts — note the .noauth.spec.ts suffix
import { test, expect } from "@playwright/test";

test("redirects to login when not authenticated", async ({ page }) => {
  await page.goto("/lv/routes");
  await expect(page).toHaveURL(/\/login/);
});
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:3000` | Frontend URL |
| `TEST_USER_EMAIL` | `admin@vtv.lv` | Login email for auth setup |
| `TEST_USER_PASSWORD` | `admin` | Login password for auth setup |

## Execution Steps

1. Check that backend (port 8123) and frontend (port 3000) are reachable
2. If $ARGUMENTS is provided, run that specific test file or pattern:
   ```bash
   cd /Users/Berzins/Desktop/VTV/cms/apps/web && npx playwright test e2e/$ARGUMENTS.spec.ts
   ```
3. If NO arguments, auto-detect changed features and run only those tests:
   ```bash
   cd /Users/Berzins/Desktop/VTV/cms/apps/web && TESTS=$(./e2e/detect-changed.sh) && echo "Detected: $TESTS"
   ```
   - If detection returns test files → run only those: `npx playwright test $TESTS`
   - If detection returns empty (no frontend changes) → run full suite: `npx playwright test`
4. Report results — pass/fail count, any failures with error messages
5. If tests fail, read the failing test file and suggest fixes
6. For visual debugging, use the Browser skill to inspect page state

## Auto-Detection Mapping

The `e2e/detect-changed.sh` script maps git-changed files to test files:

| Changed path | Runs |
|---|---|
| `components/routes/*`, `app/*/routes/*` | `routes.spec.ts` |
| `components/stops/*`, `app/*/stops/*` | `stops.spec.ts` |
| `components/schedules/*`, `app/*/schedules/*` | `schedules.spec.ts` |
| `components/documents/*`, `app/*/documents/*` | `documents.spec.ts` |
| `components/dashboard/*`, dashboard `page.tsx` | `dashboard.spec.ts` |
| `app-sidebar*`, `middleware.ts`, `layout.tsx` | `navigation.spec.ts` |
| `auth.ts`, `login/*` | `login.noauth.spec.ts` |
| `components/ui/*`, `lib/*`, `hooks/*`, `types/*`, `messages/*` | ALL tests |

## Make Targets

```bash
make e2e        # Auto-detect changed features → run only those tests
make e2e-all    # Run ALL tests regardless of changes
make e2e-ui     # Interactive UI mode
make e2e-headed # Visible browser
```
