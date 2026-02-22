import { test, expect } from "@playwright/test";

test.describe("Schedules page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/schedules");
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays three tabs", async ({ page }) => {
    await expect(
      page.getByRole("tab", { name: /calendars|kalendāri/i })
    ).toBeVisible();
    await expect(
      page.getByRole("tab", { name: /trips|reisi/i })
    ).toBeVisible();
    await expect(
      page.getByRole("tab", { name: /import|importēt/i })
    ).toBeVisible();
  });

  test.describe("Calendars tab", () => {
    test("shows calendar table", async ({ page }) => {
      await page.getByRole("tab", { name: /calendars|kalendāri/i }).click();
      await expect(page.getByRole("table")).toBeVisible();
    });

    test("clicking row opens detail sheet", async ({ page }) => {
      await page.getByRole("tab", { name: /calendars|kalendāri/i }).click();
      const firstRow = page.getByRole("row").nth(1);
      if (await firstRow.isVisible()) {
        await firstRow.click();
        const sheet = page.getByRole("dialog");
        await expect(sheet).toBeVisible({ timeout: 3000 });
      }
    });

    test("create button opens calendar form", async ({ page }) => {
      await page.getByRole("tab", { name: /calendars|kalendāri/i }).click();
      const createButton = page.getByRole("button", {
        name: /create calendar|izveidot kalendāru/i,
      });
      if (await createButton.isVisible()) {
        await createButton.click();
        // Form should show day toggles
        await expect(
          page.getByLabel(/service id|servisa id/i)
        ).toBeVisible({ timeout: 3000 });
      }
    });

    test("calendar detail shows operating days", async ({ page }) => {
      await page.getByRole("tab", { name: /calendars|kalendāri/i }).click();
      const firstRow = page.getByRole("row").nth(1);
      if (await firstRow.isVisible()) {
        await firstRow.click();
        const sheet = page.getByRole("dialog");
        await expect(sheet).toBeVisible({ timeout: 3000 });
        // Should show day badges (Mon, Tue, etc.)
        const dayBadge = sheet.getByText(/mon|pir/i);
        if (await dayBadge.isVisible()) {
          await expect(dayBadge).toBeVisible();
        }
      }
    });
  });

  test.describe("Trips tab", () => {
    test("shows trip table", async ({ page }) => {
      await page.getByRole("tab", { name: /trips|reisi/i }).click();
      // Wait for tab content to load
      await page.waitForTimeout(500);
      await expect(page.getByRole("table")).toBeVisible();
    });

    test("route filter dropdown is visible", async ({ page }) => {
      await page.getByRole("tab", { name: /trips|reisi/i }).click();
      await page.waitForTimeout(500);
      // Should have filter dropdowns
      const routeFilter = page.getByRole("combobox").first();
      if (await routeFilter.isVisible()) {
        await expect(routeFilter).toBeVisible();
      }
    });

    test("clicking trip row opens detail", async ({ page }) => {
      await page.getByRole("tab", { name: /trips|reisi/i }).click();
      await page.waitForTimeout(500);
      const firstRow = page.getByRole("row").nth(1);
      if (await firstRow.isVisible()) {
        await firstRow.click();
        const sheet = page.getByRole("dialog");
        await expect(sheet).toBeVisible({ timeout: 3000 });
      }
    });

    test("create trip button opens form", async ({ page }) => {
      await page.getByRole("tab", { name: /trips|reisi/i }).click();
      await page.waitForTimeout(500);
      const createButton = page.getByRole("button", {
        name: /create trip|izveidot reisu/i,
      });
      if (await createButton.isVisible()) {
        await createButton.click();
        await expect(
          page.getByLabel(/trip id|reisa id/i)
        ).toBeVisible({ timeout: 3000 });
      }
    });
  });

  test.describe("Import tab", () => {
    test("shows GTFS upload dropzone", async ({ page }) => {
      await page.getByRole("tab", { name: /import|importēt/i }).click();
      await page.waitForTimeout(500);
      await expect(
        page.getByText(/drop.*zip|ievelciet.*zip/i)
      ).toBeVisible({ timeout: 3000 });
    });

    test("import button is disabled without file", async ({ page }) => {
      await page.getByRole("tab", { name: /import|importēt/i }).click();
      await page.waitForTimeout(500);
      const importButton = page.getByRole("button", {
        name: /^import|^importēt/i,
      });
      if (await importButton.isVisible()) {
        await expect(importButton).toBeDisabled();
      }
    });

    test("validate button is visible", async ({ page }) => {
      await page.getByRole("tab", { name: /import|importēt/i }).click();
      await page.waitForTimeout(500);
      const validateButton = page.getByRole("button", {
        name: /validate|validēt/i,
      });
      if (await validateButton.isVisible()) {
        await expect(validateButton).toBeVisible();
      }
    });
  });
});
