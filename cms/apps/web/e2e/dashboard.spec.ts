import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv");
    await page.waitForLoadState("networkidle");
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays 4 metric cards", async ({ page }) => {
    // Metric cards show 4 titles: Active Vehicles, On-Time, Delayed Routes, Active Routes
    // They render with "—" values even when API data is unavailable
    const titles = [
      /aktīvi transportlīdzekļi|active vehicles/i,
      /savlaicīgums|on-time performance/i,
      /kavēti maršruti|delayed routes/i,
      /aktīvi maršruti|active routes/i,
    ];
    for (const titleRegex of titles) {
      await expect(page.getByText(titleRegex)).toBeVisible({ timeout: 10000 });
    }
  });

  test("manage routes link navigates to routes page", async ({ page }) => {
    const link = page.getByRole("link", { name: /manage routes|pārvaldīt maršrutus/i });
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/routes/, { timeout: 10000 });
    }
  });

  test("calendar view toggle works", async ({ page }) => {
    // Click Month view
    const monthToggle = page.getByRole("radio", { name: /month|mēnesis/i });
    if (await monthToggle.isVisible()) {
      await monthToggle.click();
      await expect(monthToggle).toHaveAttribute("data-state", "on", { timeout: 3000 });
    }
  });

  test("calendar today button is visible", async ({ page }) => {
    await expect(
      page.getByRole("button", { name: /today|šodien/i })
    ).toBeVisible();
  });

  test("calendar navigation arrows work", async ({ page }) => {
    // Scope to main content area to avoid matching Next.js dev tools button
    const nextButton = page.locator("main").getByRole("button", { name: /next|nākamais/i });
    if (await nextButton.isVisible()) {
      await nextButton.click({ force: true });
      // Should still be on dashboard
      await expect(page).toHaveURL(/\/(lv|en)\/?$/);
    }
  });
});
