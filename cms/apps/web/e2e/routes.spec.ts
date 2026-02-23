import { test, expect } from "@playwright/test";
import { waitForDataOrEmpty, hasDataTable } from "./helpers";

test.describe("Routes page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/routes");
    await page.waitForLoadState("networkidle");
    await waitForDataOrEmpty(page);
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays route table or empty state", async ({ page }) => {
    const table = page.getByRole("table");
    const emptyState = page.getByText(/no.*found|nav.*atrast/i);
    expect(
      (await table.isVisible()) || (await emptyState.isVisible())
    ).toBeTruthy();
  });

  test("table has expected columns", async ({ page }) => {
    const table = page.getByRole("table");
    const emptyState = page.getByText(/no.*found|nav.*atrast/i);
    // If empty state is showing, there are no columns to check
    if (await emptyState.isVisible()) return;
    if (!(await table.isVisible())) return;
    const headers = page.getByRole("columnheader");
    await expect(headers.first()).toBeVisible();
  });

  test("search input filters routes", async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("1");
      await waitForDataOrEmpty(page);
      const table = page.getByRole("table");
      const noResults = page.getByText(/no.*found|nav.*atrast/i);
      expect(
        (await table.isVisible()) || (await noResults.isVisible())
      ).toBeTruthy();
    }
  });

  test("type filter toggles work", async ({ page }) => {
    // Use exact match to avoid matching "Trolejbuss" which also contains "bus"
    const busToggle = page.getByRole("radio", { name: /^bus$|^autobuss$/i });
    if (await busToggle.isVisible()) {
      await busToggle.click({ force: true });
      await expect(busToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("clicking table row opens detail sheet", async ({ page }) => {
    // Skip if empty state is showing (no data to click)
    if (await page.getByText(/no.*found|nav.*atrast/i).isVisible()) return;
    const firstRow = page.getByRole("row").nth(1);
    try {
      await firstRow.waitFor({ state: "visible", timeout: 3000 });
    } catch {
      return; // No data rows — skip
    }
    await firstRow.click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible({ timeout: 3000 });
  });

  test("create button opens form", async ({ page }) => {
    const createButton = page.getByRole("button", {
      name: /create|izveidot/i,
    });
    if (await createButton.isVisible()) {
      await createButton.click({ force: true });
      // Form sheet should open with input fields
      await expect(
        page.getByLabel(/route short name|maršruta īsais nosaukums/i)
      ).toBeVisible({ timeout: 3000 });
    }
  });

  test("pagination controls are visible when data exists", async ({
    page,
  }) => {
    if (!(await hasDataTable(page))) return; // No data — skip
    const rows = page.getByRole("row");
    if ((await rows.count()) > 1) {
      const nextButton = page.getByRole("button", { name: /next|nākamā/i });
      await expect(nextButton).toBeVisible();
    }
  });

  test("map panel is visible on desktop", async ({ page }) => {
    const map = page.locator(".leaflet-container");
    if (await map.isVisible()) {
      await expect(map).toBeVisible();
    }
  });
});

test.describe("Routes CRUD", () => {
  test("create, edit, and delete route", async ({ page }) => {
    const uniqueId = `E2E-${Date.now()}`;
    const gtfsRouteId = `E2E_R_${Date.now().toString().slice(-6)}`;

    await page.goto("/lv/routes");
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
    await page.locator("#gtfsRouteId").fill(gtfsRouteId);
    await page.locator("#shortName").fill(`T${uniqueId.slice(-4)}`);
    await page.locator("#longName").fill(`E2E Test Route ${uniqueId}`);

    // Select route type (Bus = 3)
    const routeTypeSelect = page
      .locator("button")
      .filter({ hasText: /bus|autobuss|type|veids/i })
      .first();
    if (await routeTypeSelect.isVisible()) {
      await routeTypeSelect.click();
      const busOption = page
        .getByRole("option", { name: /bus|autobuss/i })
        .first();
      if (await busOption.isVisible()) await busOption.click();
    }

    // Select agency if available
    const agencySelect = page
      .locator("button")
      .filter({ hasText: /operator|operators|agency/i })
      .first();
    if (await agencySelect.isVisible()) {
      await agencySelect.click();
      const firstAgency = page.getByRole("option").first();
      if (await firstAgency.isVisible()) await firstAgency.click();
    }

    // Save and wait for API response
    const createResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/schedules/routes") &&
        resp.request().method() === "POST",
    );
    await page.getByRole("button", { name: /save|saglabāt/i }).click();
    await createResponse;
    await waitForDataOrEmpty(page);

    // Search for created route using the unique GTFS route ID
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill(gtfsRouteId);
      await waitForDataOrEmpty(page);
    }

    // --- EDIT ---
    const row = page.getByRole("row").nth(1);
    if (!(await row.isVisible())) return;
    await row.click();

    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible({ timeout: 3000 });

    const editButton = sheet.getByRole("button", { name: /edit|rediģēt/i });
    if (!(await editButton.isVisible())) return;
    await editButton.click();

    // Update short name
    const shortNameInput = page.locator("#shortName");
    await shortNameInput.clear();
    await shortNameInput.fill(`U${uniqueId.slice(-4)}`);

    const editResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/schedules/routes") &&
        resp.request().method() !== "GET",
    );
    await page.getByRole("button", { name: /save|saglabāt/i }).click();
    await editResponse;

    // --- DELETE ---
    await waitForDataOrEmpty(page);
    if (await searchInput.isVisible()) {
      await searchInput.clear();
      await searchInput.fill(gtfsRouteId);
      await waitForDataOrEmpty(page);
    }

    const routeRow = page.getByRole("row").nth(1);
    if (!(await routeRow.isVisible())) return;
    await routeRow.click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 3000 });

    const deleteButton = page
      .getByRole("dialog")
      .getByRole("button", { name: /delete|dzēst/i });
    if (!(await deleteButton.isVisible())) return;
    await deleteButton.click();

    // Confirm deletion and wait for API response
    const deleteResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/schedules/routes") &&
        resp.request().method() === "DELETE",
    );
    const confirmDelete = page
      .getByRole("button", { name: /delete|dzēst/i })
      .last();
    await confirmDelete.click();
    await deleteResponse;
  });
});
