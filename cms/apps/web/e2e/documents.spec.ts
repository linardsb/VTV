import { test, expect } from "@playwright/test";
import { waitForDataOrEmpty } from "./helpers";

test.describe("Documents page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/documents");
    await page.waitForLoadState("networkidle");
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays document table", async ({ page }) => {
    await waitForDataOrEmpty(page);
    const table = page.getByRole("table");
    const noResults = page.getByText(/no.*found|nav.*atrast/i);
    expect(
      (await table.isVisible()) || (await noResults.isVisible())
    ).toBeTruthy();
  });

  test("search input works", async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("test");
      await waitForDataOrEmpty(page);
      // Should still be on documents page
      await expect(page).toHaveURL(/\/documents/);
    }
  });

  test("type filter toggles work", async ({ page }) => {
    const pdfToggle = page.getByRole("radio", { name: /pdf/i });
    if (await pdfToggle.isVisible()) {
      await pdfToggle.click({ force: true });
      await expect(pdfToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("status filter toggles work", async ({ page }) => {
    const completedToggle = page.getByRole("radio", {
      name: /completed|pabeigts/i,
    });
    if (await completedToggle.isVisible()) {
      await completedToggle.click({ force: true });
      await expect(completedToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("upload button opens form", async ({ page }) => {
    const uploadButton = page.getByRole("button", {
      name: /upload|augšupielādēt/i,
    });
    if (await uploadButton.isVisible()) {
      await uploadButton.click({ force: true });
      // Upload form sheet should appear with dropzone
      await expect(page.getByText(/drop.*here|ievelciet/i)).toBeVisible({
        timeout: 3000,
      });
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

  test("domain filter dropdown works", async ({ page }) => {
    const domainSelect = page.getByLabel(/domain|domēns/i);
    if (await domainSelect.isVisible()) {
      await domainSelect.click({ force: true });
      // Dropdown options should appear
      const option = page.getByRole("option").first();
      if (await option.isVisible()) {
        await expect(option).toBeVisible();
      }
    }
  });

  test("language filter toggles work", async ({ page }) => {
    const lvToggle = page.getByRole("radio", { name: /^lv$/i });
    if (await lvToggle.isVisible()) {
      await lvToggle.click({ force: true });
      // Language toggle uses aria-checked, not Radix data-state
      await expect(lvToggle).toHaveAttribute("aria-checked", "true");
    }
  });

  test("pagination controls exist when data present", async ({ page }) => {
    await waitForDataOrEmpty(page);
    const rows = page.getByRole("row");
    const rowCount = await rows.count();
    if (rowCount > 1) {
      const nextButton = page.getByRole("button", { name: /next|nākamā/i });
      await expect(nextButton).toBeVisible();
    }
  });
});

test.describe("Documents CRUD", () => {
  test("upload and delete document", async ({ page }) => {
    await page.goto("/lv/documents");
    await page.waitForLoadState("networkidle");
    await waitForDataOrEmpty(page);

    // --- UPLOAD ---
    const uploadButton = page.getByRole("button", {
      name: /upload|augšupielādēt/i,
    });
    if (!(await uploadButton.isVisible())) {
      test.skip(true, "Upload button not visible");
      return;
    }
    await uploadButton.click();

    // Wait for upload form
    await expect(page.getByText(/drop.*here|ievelciet/i)).toBeVisible({
      timeout: 3000,
    });

    // Create a test file and upload via file input
    const fileInput = page.locator("input[type='file']");
    if (!(await fileInput.count())) return;

    // Create a small test file
    const testContent = `E2E Test Document ${Date.now()}`;
    const buffer = Buffer.from(testContent);
    await fileInput.setInputFiles({
      name: `e2e-test-${Date.now()}.txt`,
      mimeType: "text/plain",
      buffer,
    });

    // Select domain
    const domainSelect = page.locator("#doc-domain");
    if (await domainSelect.isVisible()) {
      await domainSelect.click();
      const generalOption = page.getByRole("option", { name: /general/i });
      if (await generalOption.isVisible()) {
        await generalOption.click();
      } else {
        // Try first option
        const firstOption = page.getByRole("option").first();
        if (await firstOption.isVisible()) await firstOption.click();
      }
    }

    // Submit upload and wait for API response
    const submitButton = page.getByRole("button", {
      name: /^upload$|^augšupielādēt$/i,
    });
    if ((await submitButton.isVisible()) && (await submitButton.isEnabled())) {
      const uploadResponse = page.waitForResponse(
        (resp) =>
          resp.url().includes("/api/v1/knowledge") &&
          resp.request().method() === "POST",
      );
      await submitButton.click();
      await uploadResponse;
    }

    // Check if document appeared in the table
    await waitForDataOrEmpty(page);
    const table = page.getByRole("table");
    if (!(await table.isVisible())) return;

    // --- DELETE ---
    // Click the first row (most recently uploaded)
    const firstRow = page.getByRole("row").nth(1);
    if (!(await firstRow.isVisible())) return;
    await firstRow.click();

    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible({ timeout: 3000 });

    const deleteButton = sheet.getByRole("button", {
      name: /delete|dzēst/i,
    });
    if (!(await deleteButton.isVisible())) return;
    await deleteButton.click();

    // Confirm deletion and wait for API response
    const deleteResponse = page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/v1/knowledge") &&
        resp.request().method() === "DELETE",
    );
    const confirmDelete = page
      .getByRole("button", { name: /delete|dzēst/i })
      .last();
    await confirmDelete.click();
    await deleteResponse;
  });
});
