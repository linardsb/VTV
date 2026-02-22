import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv");
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays 4 metric cards", async ({ page }) => {
    // Metric cards: Active Vehicles, On-Time Performance, Delayed Routes, Fleet Utilization
    const cards = page.locator("[class*='border-card-border']");
    await expect(cards).toHaveCount(4);
  });

  test("manage routes link navigates to routes page", async ({ page }) => {
    const link = page.getByRole("link", { name: /manage routes|pārvaldīt maršrutus/i });
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/routes/);
    }
  });

  test("calendar view toggle works", async ({ page }) => {
    // Click Month view
    const monthToggle = page.getByRole("radio", { name: /month|mēnesis/i });
    if (await monthToggle.isVisible()) {
      await monthToggle.click();
      await expect(monthToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("calendar today button is visible", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /today|šodien/i })
    ).toBeVisible();
  });

  test("calendar navigation arrows work", async ({ page }) => {
    const nextButton = page.getByRole("button", { name: /next|nākamais/i });
    if (await nextButton.isVisible()) {
      await nextButton.click();
      // Should still be on dashboard
      await expect(page).toHaveURL(/\/(lv|en)\/?$/);
    }
  });
});
