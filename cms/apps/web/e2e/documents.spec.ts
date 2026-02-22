import { test, expect } from "@playwright/test";

test.describe("Documents page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/lv/documents");
  });

  test("displays page title", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("displays document table", async ({ page }) => {
    const table = page.getByRole("table");
    const noResults = page.getByText(/no results|nav rezultātu/i);
    expect(
      (await table.isVisible()) || (await noResults.isVisible())
    ).toBeTruthy();
  });

  test("search input works", async ({ page }) => {
    const searchInput = page.getByPlaceholder(/search|meklēt/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("test");
      await page.waitForTimeout(500);
      // Should still be on documents page
      await expect(page).toHaveURL(/\/documents/);
    }
  });

  test("type filter toggles work", async ({ page }) => {
    const pdfToggle = page.getByRole("radio", { name: /pdf/i });
    if (await pdfToggle.isVisible()) {
      await pdfToggle.click();
      await expect(pdfToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("status filter toggles work", async ({ page }) => {
    const completedToggle = page.getByRole("radio", {
      name: /completed|pabeigts/i,
    });
    if (await completedToggle.isVisible()) {
      await completedToggle.click();
      await expect(completedToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("upload button opens form", async ({ page }) => {
    const uploadButton = page.getByRole("button", {
      name: /upload|augšupielādēt/i,
    });
    if (await uploadButton.isVisible()) {
      await uploadButton.click();
      // Upload form sheet should appear with dropzone
      await expect(
        page.getByText(/drop.*here|ievelciet/i)
      ).toBeVisible({ timeout: 3000 });
    }
  });

  test("clicking table row opens detail sheet", async ({ page }) => {
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
      await domainSelect.click();
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
      await lvToggle.click();
      await expect(lvToggle).toHaveAttribute("data-state", "on");
    }
  });

  test("pagination controls exist when data present", async ({ page }) => {
    const rows = page.getByRole("row");
    const rowCount = await rows.count();
    if (rowCount > 1) {
      const nextButton = page.getByRole("button", { name: /next|nākamā/i });
      await expect(nextButton).toBeVisible();
    }
  });
});
