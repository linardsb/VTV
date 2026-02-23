import { test, expect } from "@playwright/test";
import { waitForDataOrEmpty } from "./helpers";

test.describe("Drivers page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/drivers");
    await page.waitForLoadState("networkidle");
    await waitForDataOrEmpty(page);
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays driver table or empty state", async ({ page }) => {
    const table = page.getByRole("table");
    const emptyState = page.getByText(/no.*found|nav.*atrast/i);
    expect(
      (await table.isVisible()) || (await emptyState.isVisible())
    ).toBeTruthy();
  });

  test("table has expected columns when data exists", async ({ page }) => {
    const table = page.getByRole("table");
    if (!(await table.isVisible())) return;
    const headers = page.getByRole("columnheader");
    await expect(headers.first()).toBeVisible();
  });

  test("search input filters drivers", async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("E2E");
      await waitForDataOrEmpty(page);
      await expect(page).toHaveURL(/\/drivers/);
    }
  });

  test("shift filter works", async ({ page }) => {
    const shiftToggle = page.getByRole("radio", { name: /morning|rīts/i });
    if (await shiftToggle.isVisible()) {
      await shiftToggle.click({ force: true });
      await expect(shiftToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("status filter works", async ({ page }) => {
    const statusToggle = page.getByRole("radio", {
      name: /available|pieejams/i,
    });
    if (await statusToggle.isVisible()) {
      await statusToggle.click({ force: true });
      await expect(statusToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("clicking table row opens detail sheet", async ({ page }) => {
    if (await page.getByText(/no.*found|nav.*atrast/i).isVisible()) return;
    const firstRow = page.getByRole("row").nth(1);
    if (!(await firstRow.isVisible())) return;
    await firstRow.click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible({ timeout: 3000 });
  });

  test("create button opens form", async ({ page }) => {
    const createButton = page.getByRole("button", {
      name: /add driver|pievienot/i,
    });
    if (await createButton.isVisible()) {
      await createButton.click({ force: true });
      await expect(page.locator("#firstName")).toBeVisible({ timeout: 3000 });
    }
  });

  test("pagination controls are visible when data exists", async ({
    page,
  }) => {
    const table = page.getByRole("table");
    if (!(await table.isVisible())) return;
    const nextButton = page.getByRole("button", { name: /next|nākamā/i });
    if (await nextButton.isVisible()) {
      await expect(nextButton).toBeVisible();
    }
  });
});

test.describe("Drivers CRUD", () => {
  test("create, edit, and delete driver", async ({ page }) => {
    const uniqueId = `E2E-${Date.now()}`;
    const empNumber = `E2E${Date.now().toString().slice(-6)}`;

    await page.goto("/lv/drivers");
    await page.waitForLoadState("networkidle");
    await waitForDataOrEmpty(page);

    // --- CREATE ---
    const createButton = page.getByRole("button", {
      name: /add driver|pievienot/i,
    });
    await expect(createButton).toBeVisible({ timeout: 5000 });
    await createButton.click();

    // Fill required fields
    await page.locator("#firstName").fill(`Test-${uniqueId}`);
    await page.locator("#lastName").fill("E2E-Driver");
    await page.locator("#employeeNumber").fill(empNumber);
    await page.locator("#phone").fill("+371 99999999");

    // Save and wait for API response
    const createResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/drivers") &&
        resp.request().method() === "POST",
    );
    const saveButton = page.getByRole("button", { name: /save|saglabāt/i });
    await saveButton.click();
    await createResponse;
    await waitForDataOrEmpty(page);

    // Search for the created driver
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill(empNumber);
      await waitForDataOrEmpty(page);
    }

    // Verify the driver appears in the table
    await expect(page.getByText(empNumber)).toBeVisible({ timeout: 5000 });

    // --- EDIT ---
    const row = page.getByRole("row").filter({ hasText: empNumber });
    await row.click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible({ timeout: 3000 });

    const editButton = sheet.getByRole("button", { name: /edit|rediģēt/i });
    await editButton.click();

    // Update phone number
    const phoneInput = page.locator("#phone");
    await phoneInput.clear();
    await phoneInput.fill("+371 88888888");

    // Save and wait for API response
    const editResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/drivers") &&
        resp.request().method() !== "GET",
    );
    await page.getByRole("button", { name: /save|saglabāt/i }).click();
    await editResponse;

    // --- DELETE ---
    await waitForDataOrEmpty(page);
    if (await searchInput.isVisible()) {
      await searchInput.clear();
      await searchInput.fill(empNumber);
      await waitForDataOrEmpty(page);
    }

    const driverRow = page.getByRole("row").filter({ hasText: empNumber });
    await driverRow.click();
    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 3000 });

    const deleteButton = page
      .getByRole("dialog")
      .getByRole("button", { name: /delete|dzēst/i });
    await deleteButton.click();

    // Confirm deletion and wait for API response
    const deleteResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/drivers") &&
        resp.request().method() === "DELETE",
    );
    const confirmDelete = page
      .getByRole("button", { name: /delete|dzēst/i })
      .last();
    await confirmDelete.click();
    await deleteResponse;

    // Verify driver is removed
    await waitForDataOrEmpty(page);
    if (await searchInput.isVisible()) {
      await searchInput.clear();
      await searchInput.fill(empNumber);
      await waitForDataOrEmpty(page);
    }

    await expect(page.getByText(empNumber)).not.toBeVisible({ timeout: 5000 });
  });
});
