import type { Page } from "@playwright/test";

/** Wait for the page data to load — either a table with rows or an empty state message. */
export async function waitForDataOrEmpty(page: Page) {
  await Promise.race([
    page
      .getByRole("row")
      .nth(1)
      .waitFor({ state: "visible", timeout: 10000 }),
    page
      .getByText(/no.*found|nav.*atrast/i)
      .waitFor({ state: "visible", timeout: 10000 }),
  ]).catch(() => {});
}

/** Check if the page has a visible data table (not just empty state). */
export async function hasDataTable(page: Page) {
  const table = page.getByRole("table");
  return await table.isVisible();
}
