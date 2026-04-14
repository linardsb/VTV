import { test as setup, expect } from "@playwright/test";

const TEST_USER = {
  email: process.env.TEST_USER_EMAIL ?? "admin@vtv.lv",
  // Prefer DEMO_USER_PASSWORD (same env var the backend uses to seed demo
  // users) so there's a single source of truth. Fall back to legacy
  // TEST_USER_PASSWORD for local dev overrides, then "admin" for default.
  password:
    process.env.DEMO_USER_PASSWORD ?? process.env.TEST_USER_PASSWORD ?? "admin",
};

setup("authenticate", async ({ page }) => {
  await page.goto("/lv/login");
  await page.getByLabel(/email|e-pasts/i).fill(TEST_USER.email);
  await page.getByLabel(/password|parole/i).fill(TEST_USER.password);
  await page.getByRole("button", { name: /login|pieteikties/i }).click();

  // Wait for redirect to dashboard after successful login
  await expect(page).toHaveURL(/\/(lv|en)\/?$/);

  // Save signed-in state for reuse by other test projects
  await page.context().storageState({ path: "e2e/.auth/user.json" });
});
