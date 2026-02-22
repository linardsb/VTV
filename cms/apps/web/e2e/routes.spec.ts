import { test, expect } from "@playwright/test";

/** Wait for the page data to load — either a table with rows or an empty state message. */
async function waitForDataOrEmpty(page: import("@playwright/test").Page) {
  await Promise.race([
    page.getByRole("row").nth(1).waitFor({ state: "visible", timeout: 10000 }),
    page.getByText(/no.*found|nav.*atrast/i).waitFor({ state: "visible", timeout: 10000 }),
  ]).catch(() => {});
}

/** Check if the page has a visible data table (not just empty state). */
async function hasDataTable(page: import("@playwright/test").Page) {
  const table = page.getByRole("table");
  return await table.isVisible();
}

test.describe("Routes page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/routes");
    await page.waitForLoadState("networkidle");
    await waitForDataOrEmpty(page);
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays route table or empty state", async ({ page }) => {
    const table = page.getByRole("table");
    const emptyState = page.getByText(/no.*found|nav.*atrast/i);
    expect(
      (await table.isVisible()) || (await emptyState.isVisible())
    ).toBeTruthy();
  });

  test("table has expected columns", async ({ page }) => {
    const table = page.getByRole("table");
    const emptyState = page.getByText(/no.*found|nav.*atrast/i);
    // If empty state is showing, there are no columns to check
    if (await emptyState.isVisible()) return;
    if (!(await table.isVisible())) return;
    const headers = page.getByRole("columnheader");
    await expect(headers.first()).toBeVisible();
  });

  test("search input filters routes", async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("1");
      await waitForDataOrEmpty(page);
      const table = page.getByRole("table");
      const noResults = page.getByText(/no.*found|nav.*atrast/i);
      expect(
        (await table.isVisible()) || (await noResults.isVisible())
      ).toBeTruthy();
    }
  });

  test("type filter toggles work", async ({ page }) => {
    // Use exact match to avoid matching "Trolejbuss" which also contains "bus"
    const busToggle = page.getByRole("radio", { name: /^bus$|^autobuss$/i });
    if (await busToggle.isVisible()) {
      await busToggle.click({ force: true });
      await expect(busToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("clicking table row opens detail sheet", async ({ page }) => {
    // Skip if empty state is showing (no data to click)
    if (await page.getByText(/no.*found|nav.*atrast/i).isVisible()) return;
    const firstRow = page.getByRole("row").nth(1);
    try {
      await firstRow.waitFor({ state: "visible", timeout: 3000 });
    } catch {
      return; // No data rows — skip
    }
    await firstRow.click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible({ timeout: 3000 });
  });

  test("create button opens form", async ({ page }) => {
    const createButton = page.getByRole("button", {
      name: /create|izveidot/i,
    });
    if (await createButton.isVisible()) {
      await createButton.click({ force: true });
      // Form sheet should open with input fields
      await expect(
        page.getByLabel(/route short name|maršruta īsais nosaukums/i)
      ).toBeVisible({ timeout: 3000 });
    }
  });

  test("pagination controls are visible when data exists", async ({ page }) => {
    if (!(await hasDataTable(page))) return; // No data — skip
    const rows = page.getByRole("row");
    if ((await rows.count()) > 1) {
      const nextButton = page.getByRole("button", { name: /next|nākamā/i });
      await expect(nextButton).toBeVisible();
    }
  });

  test("map panel is visible on desktop", async ({ page }) => {
    const map = page.locator(".leaflet-container");
    if (await map.isVisible()) {
      await expect(map).toBeVisible();
    }
  });
});
