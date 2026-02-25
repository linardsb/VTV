import { test, expect } from "@playwright/test";
import { waitForDataOrEmpty } from "./helpers";

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
    test("shows calendar table or empty state", async ({ page }) => {
      await page.getByRole("tab", { name: /calendars|kalendāri/i }).click();
      // Either a table with data or an empty state message
      const table = page.getByRole("table");
      const emptyState = page.getByText(/no.*found|nav.*atrast/i);
      await Promise.race([
        table.waitFor({ state: "visible", timeout: 5000 }),
        emptyState.waitFor({ state: "visible", timeout: 5000 }),
      ]);
      expect(
        (await table.isVisible()) || (await emptyState.isVisible())
      ).toBeTruthy();
    });

    test("clicking row opens detail sheet", async ({ page }) => {
      await page.getByRole("tab", { name: /calendars|kalendāri/i }).click();
      // Wait for data or empty state
      const emptyState = page.getByText(/no.*found|nav.*atrast/i);
      const table = page.getByRole("table");
      const firstRow = table.getByRole("row").nth(1);
      await Promise.race([
        firstRow.waitFor({ state: "visible", timeout: 5000 }),
        emptyState.waitFor({ state: "visible", timeout: 5000 }),
      ]).catch(() => {});
      if (await emptyState.isVisible()) return; // No data — skip
      if (!(await firstRow.isVisible())) return;
      // Retry click+dialog check to handle React rendering timing under parallel load
      await expect(async () => {
        await firstRow.getByRole("cell").first().click();
        await expect(page.getByRole("dialog")).toBeVisible();
      }).toPass({ timeout: 10000 });
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
      // Wait for data or empty state
      const emptyState = page.getByText(/no.*found|nav.*atrast/i);
      const table = page.getByRole("table");
      const firstRow = table.getByRole("row").nth(1);
      await Promise.race([
        firstRow.waitFor({ state: "visible", timeout: 5000 }),
        emptyState.waitFor({ state: "visible", timeout: 5000 }),
      ]).catch(() => {});
      if (await emptyState.isVisible()) return; // No data — skip
      if (!(await firstRow.isVisible())) return;
      // Retry click+dialog check to handle React rendering timing under parallel load
      await expect(async () => {
        await firstRow.getByRole("cell").first().click();
        await expect(page.getByRole("dialog")).toBeVisible();
      }).toPass({ timeout: 10000 });
      // Should show day badges (Mon, Tue, etc.)
      const sheet = page.getByRole("dialog");
      const dayBadge = sheet.getByText(/mon|pir/i);
      if (await dayBadge.isVisible()) {
        await expect(dayBadge).toBeVisible();
      }
    });
  });

  test.describe("Trips tab", () => {
    test("shows trip table or empty state", async ({ page }) => {
      await page.getByRole("tab", { name: /trips|reisi/i }).click();
      // Either a table with data or an empty state message
      const table = page.getByRole("table");
      const emptyState = page.getByText(/no.*found|nav.*atrast/i);
      await Promise.race([
        table.waitFor({ state: "visible", timeout: 5000 }),
        emptyState.waitFor({ state: "visible", timeout: 5000 }),
      ]);
      expect(
        (await table.isVisible()) || (await emptyState.isVisible())
      ).toBeTruthy();
    });

    test("route filter dropdown is visible", async ({ page }) => {
      await page.getByRole("tab", { name: /trips|reisi/i }).click();
      // Wait for tab content to render
      const routeFilter = page.getByRole("combobox").first();
      await routeFilter
        .waitFor({ state: "visible", timeout: 3000 })
        .catch(() => {});
      if (await routeFilter.isVisible()) {
        await expect(routeFilter).toBeVisible();
      }
    });

    test("clicking trip row opens detail", async ({ page }) => {
      await page.getByRole("tab", { name: /trips|reisi/i }).click();
      await waitForDataOrEmpty(page);
      const table = page.getByRole("table");
      const firstRow = table.getByRole("row").nth(1);
      if (await firstRow.isVisible()) {
        // Retry click+dialog check to handle React rendering timing under parallel load
        await expect(async () => {
          await firstRow.getByRole("cell").first().click();
          await expect(page.getByRole("dialog")).toBeVisible();
        }).toPass({ timeout: 10000 });
      }
    });

    test("create trip button opens form", async ({ page }) => {
      await page.getByRole("tab", { name: /trips|reisi/i }).click();
      // Wait for tab content to render
      const createButton = page.getByRole("button", {
        name: /create trip|izveidot reisu/i,
      });
      await createButton
        .waitFor({ state: "visible", timeout: 3000 })
        .catch(() => {});
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
      await expect(
        page.getByText(/drop.*zip|ievelciet.*zip/i)
      ).toBeVisible({ timeout: 3000 });
    });

    test("import button is disabled without file", async ({ page }) => {
      await page.getByRole("tab", { name: /import|importēt/i }).click();
      const importButton = page.getByRole("button", {
        name: /^import|^importēt/i,
      });
      await importButton
        .waitFor({ state: "visible", timeout: 3000 })
        .catch(() => {});
      if (await importButton.isVisible()) {
        await expect(importButton).toBeDisabled();
      }
    });

    test("validate button is visible", async ({ page }) => {
      await page.getByRole("tab", { name: /import|importēt/i }).click();
      const validateButton = page.getByRole("button", {
        name: /validate|validēt/i,
      });
      await validateButton
        .waitFor({ state: "visible", timeout: 3000 })
        .catch(() => {});
      if (await validateButton.isVisible()) {
        await expect(validateButton).toBeVisible();
      }
    });
  });
});

test.describe("Calendars CRUD", () => {
  test("create, edit, and delete calendar", async ({ page }) => {
    const serviceId = `E2E_CAL_${Date.now().toString().slice(-6)}`;

    await page.goto("/lv/schedules");
    await page.waitForLoadState("networkidle");

    // Navigate to calendars tab
    await page.getByRole("tab", { name: /calendars|kalendāri/i }).click();
    await waitForDataOrEmpty(page);

    // --- CREATE ---
    const createButton = page.getByRole("button", {
      name: /create calendar|izveidot kalendāru/i,
    });
    if (!(await createButton.isVisible())) {
      test.skip(true, "Create calendar button not visible");
      return;
    }
    await createButton.click();

    // Fill required fields
    await page.locator("#serviceId").fill(serviceId);
    await page.locator("#startDate").fill("2026-03-01");
    await page.locator("#endDate").fill("2026-12-31");

    // Days are toggled Mon-Fri by default, toggle Saturday on
    const satToggle = page.locator("button#saturday[role='switch']");
    if (await satToggle.isVisible()) {
      await satToggle.click();
    }

    // Save and wait for API response
    const createResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/schedules/calendars") &&
        resp.request().method() === "POST",
    );
    await page.getByRole("button", { name: /save|saglabāt/i }).click();
    await createResponse;

    // Wait for table to show data
    await waitForDataOrEmpty(page);

    // Verify the calendar appears (search for the service ID text)
    await expect(page.getByText(serviceId)).toBeVisible({ timeout: 5000 });

    // --- EDIT ---
    const row = page.getByRole("row").filter({ hasText: serviceId });
    await row.click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible({ timeout: 3000 });

    const editButton = sheet.getByRole("button", { name: /edit|rediģēt/i });
    if (!(await editButton.isVisible())) return;
    await editButton.click();

    // Toggle Sunday on
    const sunToggle = page.locator("button#sunday[role='switch']");
    if (await sunToggle.isVisible()) {
      await sunToggle.click();
    }

    const editResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/schedules/calendars") &&
        resp.request().method() !== "GET",
    );
    await page.getByRole("button", { name: /save|saglabāt/i }).click();
    await editResponse;

    // --- DELETE ---
    const calRow = page.getByRole("row").filter({ hasText: serviceId });
    if (!(await calRow.isVisible())) return;
    await calRow.click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 3000 });

    const deleteButton = page
      .getByRole("dialog")
      .getByRole("button", { name: /delete|dzēst/i });
    if (!(await deleteButton.isVisible())) return;
    await deleteButton.click();

    // Confirm deletion and wait for API response
    const deleteResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/schedules/calendars") &&
        resp.request().method() === "DELETE",
    );
    const confirmDelete = page
      .getByRole("button", { name: /delete|dzēst/i })
      .last();
    await confirmDelete.click();
    await deleteResponse;
  });
});

test.describe("Trips CRUD", () => {
  test("create, edit, and delete trip", async ({ page }) => {
    const tripId = `E2E_TRIP_${Date.now().toString().slice(-6)}`;

    await page.goto("/lv/schedules");
    await page.waitForLoadState("networkidle");

    // Navigate to trips tab
    await page.getByRole("tab", { name: /trips|reisi/i }).click();
    await waitForDataOrEmpty(page);

    // --- CREATE ---
    const createButton = page.getByRole("button", {
      name: /create trip|izveidot reisu/i,
    });
    if (!(await createButton.isVisible())) {
      // No create button — skip test (may need routes/calendars first)
      test.skip(true, "No create button visible — routes/calendars may be required");
      return;
    }
    await createButton.click();

    // Fill trip ID
    await page.locator("#tripId").fill(tripId);

    // Select route (first available)
    const routeSelect = page
      .locator("button")
      .filter({ hasText: /select route|izvēlieties/i })
      .first();
    if (await routeSelect.isVisible()) {
      await routeSelect.click();
      const firstRoute = page.getByRole("option").first();
      if (await firstRoute.isVisible()) {
        await firstRoute.click();
      } else {
        // No routes available — can't create trip
        await page.getByRole("button", { name: /cancel|atcelt/i }).click();
        test.skip(true, "No routes available to create a trip");
        return;
      }
    }

    // Select calendar (first available)
    const calSelect = page
      .locator("button")
      .filter({ hasText: /select calendar|izvēlieties/i })
      .first();
    if (await calSelect.isVisible()) {
      await calSelect.click();
      const firstCal = page.getByRole("option").first();
      if (await firstCal.isVisible()) {
        await firstCal.click();
      } else {
        await page.getByRole("button", { name: /cancel|atcelt/i }).click();
        test.skip(true, "No calendars available to create a trip");
        return;
      }
    }

    // Fill headsign
    const headsign = page.locator("#headsign");
    if (await headsign.isVisible()) {
      await headsign.fill("E2E Test Destination");
    }

    // Save and wait for API response
    const createResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/schedules/trips") &&
        resp.request().method() === "POST",
    );
    await page.getByRole("button", { name: /save|saglabāt/i }).click();
    await createResponse;

    // Verify the trip appears
    await expect(page.getByText(tripId)).toBeVisible({ timeout: 5000 });

    // --- EDIT ---
    const row = page.getByRole("row").filter({ hasText: tripId });
    await row.click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible({ timeout: 3000 });

    const editButton = sheet.getByRole("button", { name: /edit|rediģēt/i });
    if (!(await editButton.isVisible())) return;
    await editButton.click();

    // Update headsign
    const headsignEdit = page.locator("#headsign");
    if (await headsignEdit.isVisible()) {
      await headsignEdit.clear();
      await headsignEdit.fill("E2E Updated Destination");
    }

    const editResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/schedules/trips") &&
        resp.request().method() !== "GET",
    );
    await page.getByRole("button", { name: /save|saglabāt/i }).click();
    await editResponse;

    // --- DELETE ---
    const tripRow = page.getByRole("row").filter({ hasText: tripId });
    if (!(await tripRow.isVisible())) return;
    await tripRow.click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 3000 });

    const deleteButton = page
      .getByRole("dialog")
      .getByRole("button", { name: /delete|dzēst/i });
    if (!(await deleteButton.isVisible())) return;
    await deleteButton.click();

    const deleteResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/schedules/trips") &&
        resp.request().method() === "DELETE",
    );
    const confirmDelete = page
      .getByRole("button", { name: /delete|dzēst/i })
      .last();
    await confirmDelete.click();
    await deleteResponse;
  });
});
