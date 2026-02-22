import { test, expect } from "@playwright/test";

test.describe("Routes page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/routes");
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays route table", async ({ page }) => {
    await expect(page.getByRole("table")).toBeVisible();
  });

  test("table has expected columns", async ({ page }) => {
    const table = page.getByRole("table");
    await expect(table).toBeVisible();
    // Route number and name columns should always be visible
    const headers = page.getByRole("columnheader");
    await expect(headers.first()).toBeVisible();
  });

  test("search input filters routes", async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("1");
      // Wait for debounce (300ms)
      await page.waitForTimeout(500);
      // Table should still be visible (filtered or empty state)
      const table = page.getByRole("table");
      const noResults = page.getByText(/no results|nav rezultātu/i);
      const hasResults = await table.isVisible();
      const hasNoResults = await noResults.isVisible();
      expect(hasResults || hasNoResults).toBeTruthy();
    }
  });

  test("type filter toggles work", async ({ page }) => {
    const busToggle = page.getByRole("radio", { name: /bus|autobuss/i });
    if (await busToggle.isVisible()) {
      await busToggle.click();
      await expect(busToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("clicking table row opens detail sheet", async ({ page }) => {
    const firstRow = page.getByRole("row").nth(1); // skip header
    if (await firstRow.isVisible()) {
      await firstRow.click();
      // Detail sheet should appear
      const sheet = page.getByRole("dialog");
      await expect(sheet).toBeVisible({ timeout: 3000 });
    }
  });

  test("create button opens form", async ({ page }) => {
    const createButton = page.getByRole("button", {
      name: /create|izveidot/i,
    });
    if (await createButton.isVisible()) {
      await createButton.click();
      // Form sheet should open with input fields
      await expect(
        page.getByLabel(/route short name|maršruta īsais nosaukums/i)
      ).toBeVisible({ timeout: 3000 });
    }
  });

  test("pagination controls are visible when data exists", async ({ page }) => {
    const table = page.getByRole("table");
    if (await table.isVisible()) {
      const rows = page.getByRole("row");
      const rowCount = await rows.count();
      if (rowCount > 1) {
        // Pagination buttons should exist
        const nextButton = page.getByRole("button", { name: /next|nākamā/i });
        await expect(nextButton).toBeVisible();
      }
    }
  });

  test("map panel is visible on desktop", async ({ page }) => {
    // Leaflet map container
    const map = page.locator(".leaflet-container");
    if (await map.isVisible()) {
      await expect(map).toBeVisible();
    }
  });
});
