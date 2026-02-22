import { test, expect } from "@playwright/test";

test.describe("Smoke tests (authenticated)", () => {
  test("dashboard loads", async ({ page }) => {
    await page.goto("/lv");
    await expect(page).toHaveURL(/\/(lv|en)\/?$/);
    // Sidebar should be visible on desktop
    await expect(page.getByRole("navigation")).toBeVisible();
  });

  test("routes page loads", async ({ page }) => {
    await page.goto("/lv/routes");
    await expect(page).toHaveURL(/\/routes/);
  });

  test("stops page loads", async ({ page }) => {
    await page.goto("/lv/stops");
    await expect(page).toHaveURL(/\/stops/);
  });

  test("schedules page loads", async ({ page }) => {
    await page.goto("/lv/schedules");
    await expect(page).toHaveURL(/\/schedules/);
  });

  test("documents page loads", async ({ page }) => {
    await page.goto("/lv/documents");
    await expect(page).toHaveURL(/\/documents/);
  });

  test("sidebar navigation works", async ({ page }) => {
    await page.goto("/lv");
    // Click a nav link and verify navigation
    const routesLink = page.getByRole("link", {
      name: /routes|maršruti/i,
    });
    if (await routesLink.isVisible()) {
      await routesLink.click();
      await expect(page).toHaveURL(/\/routes/);
    }
  });
});
