import { test, expect } from "@playwright/test";

test.describe("Map Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/map");
    await page.waitForLoadState("networkidle");
  });

  test("displays page with map container", async ({ page }) => {
    const map = page.locator(".leaflet-container");
    await expect(map).toBeVisible({ timeout: 15000 });
  });

  test("shows connection status badge", async ({ page }) => {
    const badge = page.locator("[data-testid='connection-badge']");
    await expect(badge).toBeVisible({ timeout: 10000 });
  });

  test("filter bar is visible", async ({ page }) => {
    const filters = page.locator("[data-testid='map-filters']");
    await expect(filters).toBeVisible({ timeout: 10000 });
  });

  test("can navigate to map from sidebar", async ({ page }) => {
    await page.goto("/lv");
    const mapLink = page.getByRole("link", { name: /karte|map/i });
    if (await mapLink.isVisible()) {
      await mapLink.click();
      await expect(page).toHaveURL(/\/map/);
    }
  });
});
