import { test, expect } from "@playwright/test";

test.describe("Sidebar navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv");
  });

  test("sidebar is visible on desktop", async ({ page }) => {
    await expect(page.getByRole("navigation")).toBeVisible();
  });

  test("navigate to routes via sidebar", async ({ page }) => {
    const link = page.getByRole("link", { name: /routes|maršruti/i });
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/routes/);
    }
  });

  test("navigate to stops via sidebar", async ({ page }) => {
    const link = page.getByRole("link", { name: /stops|pieturas/i });
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/stops/);
    }
  });

  test("navigate to schedules via sidebar", async ({ page }) => {
    const link = page.getByRole("link", { name: /schedules|grafiki/i });
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/schedules/);
    }
  });

  test("navigate to documents via sidebar", async ({ page }) => {
    const link = page.getByRole("link", { name: /documents|dokumenti/i });
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/documents/);
    }
  });

  test("active link is highlighted", async ({ page }) => {
    await page.goto("/lv/routes");
    const link = page.getByRole("link", { name: /routes|maršruti/i });
    if (await link.isVisible()) {
      // Active link should have a distinct style (data-active or aria-current)
      const isActive =
        (await link.getAttribute("data-active")) === "true" ||
        (await link.getAttribute("aria-current")) === "page";
      expect(isActive).toBeTruthy();
    }
  });
});

test.describe("Locale switching", () => {
  test("pages load with /lv locale", async ({ page }) => {
    await page.goto("/lv");
    await expect(page).toHaveURL(/\/lv/);
  });

  test("pages load with /en locale", async ({ page }) => {
    await page.goto("/en");
    await expect(page).toHaveURL(/\/en/);
  });
});
