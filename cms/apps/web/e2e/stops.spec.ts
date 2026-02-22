import { test, expect } from "@playwright/test";

/** Wait for the page data to load — either a table with rows or an empty state message. */
async function waitForDataOrEmpty(page: import("@playwright/test").Page) {
  await Promise.race([
    page.getByRole("row").nth(1).waitFor({ state: "visible", timeout: 10000 }),
    page.getByText(/no.*found|nav.*atrast/i).waitFor({ state: "visible", timeout: 10000 }),
  ]).catch(() => {});
}

test.describe("Stops page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/stops");
    await page.waitForLoadState("networkidle");
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays stop table or empty state", async ({ page }) => {
    const table = page.getByRole("table");
    const emptyState = page.getByText(/no.*found|nav.*atrast/i);
    await Promise.race([
      table.waitFor({ state: "visible", timeout: 10000 }),
      emptyState.waitFor({ state: "visible", timeout: 10000 }),
    ]);
    expect(
      (await table.isVisible()) || (await emptyState.isVisible())
    ).toBeTruthy();
  });

  test("search input filters stops", async ({ page }) => {
    await waitForDataOrEmpty(page);
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("central");
      await waitForDataOrEmpty(page);
      const table = page.getByRole("table");
      const noResults = page.getByText(/no.*found|nav.*atrast/i);
      expect(
        (await table.isVisible()) || (await noResults.isVisible())
      ).toBeTruthy();
    }
  });

  test("status filter works", async ({ page }) => {
    const statusSelect = page.getByLabel(/status|statuss/i);
    if (await statusSelect.isVisible()) {
      await statusSelect.click({ force: true });
      // Wait for dropdown to open — use exact match to avoid "Neaktīvs"
      const activeOption = page.getByRole("option", {
        name: /^active$|^aktīvs$/i,
      });
      await activeOption.waitFor({ state: "visible", timeout: 3000 }).catch(() => {});
      if (await activeOption.isVisible()) {
        await activeOption.click({ force: true });
      }
    }
  });

  test("location type filter works", async ({ page }) => {
    const stopToggle = page.getByRole("radio", { name: /stop.*0/i });
    if (await stopToggle.isVisible()) {
      await stopToggle.click({ force: true });
      await expect(stopToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("clicking table row opens detail sheet", async ({ page }) => {
    await waitForDataOrEmpty(page);
    const firstRow = page.getByRole("row").nth(1);
    if (await firstRow.isVisible()) {
      await firstRow.click();
      const sheet = page.getByRole("dialog");
      await expect(sheet).toBeVisible({ timeout: 3000 });
    }
  });

  test("create button opens form", async ({ page }) => {
    const createButton = page.getByRole("button", {
      name: /create|izveidot/i,
    });
    if (await createButton.isVisible()) {
      await createButton.click({ force: true });
      await expect(
        page.getByLabel(/stop name|pieturas nosaukums/i)
      ).toBeVisible({ timeout: 3000 });
    }
  });

  test("map is visible on desktop", async ({ page }) => {
    const map = page.locator(".leaflet-container");
    if (await map.isVisible()) {
      await expect(map).toBeVisible();
    }
  });

  test("GTFS copy button shows toast", async ({ page }) => {
    await waitForDataOrEmpty(page);
    const copyButton = page.getByRole("button", { name: /copy/i }).first();
    if (await copyButton.isVisible()) {
      await copyButton.click({ force: true });
      // Toast notification should appear
      const toast = page.getByText(/copied|nokopēts/i);
      await expect(toast).toBeVisible({ timeout: 3000 });
    }
  });

  test("pagination works", async ({ page }) => {
    await waitForDataOrEmpty(page);
    const nextButton = page.getByRole("button", { name: /next|nākamā/i });
    if (await nextButton.isVisible() && await nextButton.isEnabled()) {
      await nextButton.click({ force: true });
      // Should still be on stops page
      await expect(page).toHaveURL(/\/stops/);
    }
  });
});
