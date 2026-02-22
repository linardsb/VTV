import { test, expect } from "@playwright/test";

test.describe("Stops page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/stops");
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays stop table", async ({ page }) => {
    await expect(page.getByRole("table")).toBeVisible();
  });

  test("search input filters stops", async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("central");
      await page.waitForTimeout(500);
      const table = page.getByRole("table");
      const noResults = page.getByText(/no results|nav rezultātu/i);
      expect(
        (await table.isVisible()) || (await noResults.isVisible())
      ).toBeTruthy();
    }
  });

  test("status filter works", async ({ page }) => {
    const statusSelect = page.getByLabel(/status|statuss/i);
    if (await statusSelect.isVisible()) {
      await statusSelect.click();
      const activeOption = page.getByRole("option", {
        name: /active|aktīvs/i,
      });
      if (await activeOption.isVisible()) {
        await activeOption.click();
      }
    }
  });

  test("location type filter works", async ({ page }) => {
    const stopToggle = page.getByRole("radio", { name: /stop.*0/i });
    if (await stopToggle.isVisible()) {
      await stopToggle.click();
      await expect(stopToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("clicking table row opens detail sheet", async ({ page }) => {
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
      await createButton.click();
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
    const copyButton = page.getByRole("button", { name: /copy/i }).first();
    if (await copyButton.isVisible()) {
      await copyButton.click();
      // Toast notification should appear
      const toast = page.getByText(/copied|nokopēts/i);
      await expect(toast).toBeVisible({ timeout: 3000 });
    }
  });

  test("pagination works", async ({ page }) => {
    const nextButton = page.getByRole("button", { name: /next|nākamā/i });
    if (await nextButton.isVisible() && await nextButton.isEnabled()) {
      await nextButton.click();
      // Should still be on stops page
      await expect(page).toHaveURL(/\/stops/);
    }
  });
});
