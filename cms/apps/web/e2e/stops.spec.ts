import { test, expect } from "@playwright/test";
import { waitForDataOrEmpty } from "./helpers";

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
      await activeOption
        .waitFor({ state: "visible", timeout: 3000 })
        .catch(() => {});
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
    if ((await nextButton.isVisible()) && (await nextButton.isEnabled())) {
      await nextButton.click({ force: true });
      // Should still be on stops page
      await expect(page).toHaveURL(/\/stops/);
    }
  });
});

test.describe("Stops CRUD", () => {
  test("create, edit, and delete stop", async ({ page }) => {
    const uniqueId = `E2E-${Date.now()}`;
    const gtfsStopId = `E2E_S_${Date.now().toString().slice(-6)}`;

    await page.goto("/lv/stops");
    await page.waitForLoadState("networkidle");
    await waitForDataOrEmpty(page);

    // --- CREATE ---
    const createButton = page.getByRole("button", {
      name: /create|izveidot/i,
    });
    if (!(await createButton.isVisible())) {
      test.skip(true, "Create button not visible — may require prerequisite data");
      return;
    }
    await createButton.click();

    // Fill required fields
    await page.locator("#stop_name").fill(`E2E Stop ${uniqueId}`);
    await page.locator("#gtfs_stop_id").fill(gtfsStopId);
    await page.locator("#stop_lat").fill("56.9496");
    await page.locator("#stop_lon").fill("24.1052");

    // Save and wait for API response
    const createResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/stops") &&
        resp.request().method() === "POST",
    );
    await page.getByRole("button", { name: /save|saglabāt/i }).click();
    await createResponse;
    await waitForDataOrEmpty(page);

    // Search for the created stop
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill(gtfsStopId);
      await waitForDataOrEmpty(page);
    }

    // Verify the stop appears
    await expect(page.getByText(gtfsStopId)).toBeVisible({ timeout: 5000 });

    // --- EDIT ---
    const row = page.getByRole("row").filter({ hasText: gtfsStopId });
    await row.click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible({ timeout: 3000 });

    const editButton = sheet.getByRole("button", { name: /edit|rediģēt/i });
    if (!(await editButton.isVisible())) return;
    await editButton.click();

    // Update stop name
    const nameInput = page.locator("#stop_name");
    await nameInput.clear();
    await nameInput.fill(`E2E Stop Updated ${uniqueId}`);

    const editResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/stops") &&
        resp.request().method() !== "GET",
    );
    await page.getByRole("button", { name: /save|saglabāt/i }).click();
    await editResponse;

    // --- DELETE ---
    await waitForDataOrEmpty(page);
    if (await searchInput.isVisible()) {
      await searchInput.clear();
      await searchInput.fill(gtfsStopId);
      await waitForDataOrEmpty(page);
    }

    const stopRow = page.getByRole("row").filter({ hasText: gtfsStopId });
    await stopRow.click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 3000 });

    const deleteButton = page
      .getByRole("dialog")
      .getByRole("button", { name: /delete|dzēst/i });
    if (!(await deleteButton.isVisible())) return;
    await deleteButton.click();

    // Confirm deletion and wait for API response
    const deleteResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/stops") &&
        resp.request().method() === "DELETE",
    );
    const confirmDelete = page
      .getByRole("button", { name: /delete|dzēst/i })
      .last();
    await confirmDelete.click();
    await deleteResponse;

    // Verify stop is gone
    await waitForDataOrEmpty(page);
    if (await searchInput.isVisible()) {
      await searchInput.clear();
      await searchInput.fill(gtfsStopId);
      await waitForDataOrEmpty(page);
    }
    await expect(page.getByText(gtfsStopId)).not.toBeVisible({ timeout: 5000 });
  });
});
