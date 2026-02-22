import { test as setup, expect } from "@playwright/test";

const TEST_USER = {
  email: process.env.TEST_USER_EMAIL ?? "admin@vtv.lv",
  password: process.env.TEST_USER_PASSWORD ?? "admin",
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
