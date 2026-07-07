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

/**
 * Wait for a data table to finish loading, then report whether it has real data rows.
 *
 * While loading, the tables render skeleton placeholders inside `<TableRow>`s, which
 * expose `role="row"` just like real rows. Row-based waits therefore race the skeletons
 * and can treat a placeholder as data — then, once loading resolves to the empty state,
 * that row vanishes and any "click the row" assertion times out on a detached element.
 * Waiting for the skeletons to detach first removes the race, so the caller sees a
 * settled table: either real data rows or the empty state.
 *
 * @returns true when real data rows are present, false when the table is empty.
 */
export async function waitForTableSettled(page: Page): Promise<boolean> {
  // Let the loading skeletons detach (resolves immediately if none are shown).
  await page
    .locator('table [data-slot="skeleton"]')
    .last()
    .waitFor({ state: "detached", timeout: 10000 })
    .catch(() => {});

  const emptyState = page.getByText(/no.*found|nav.*atrast/i);
  const firstRow = page.getByRole("table").getByRole("row").nth(1);
  await Promise.race([
    firstRow.waitFor({ state: "visible", timeout: 5000 }),
    emptyState.waitFor({ state: "visible", timeout: 5000 }),
  ]).catch(() => {});

  return (await firstRow.isVisible()) && !(await emptyState.isVisible());
}
