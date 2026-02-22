import { test, expect } from "@playwright/test";

test.describe("Login page", () => {
  test("renders login form", async ({ page }) => {
    await page.goto("/lv/login");
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /login|pieslēgties/i })
    ).toBeVisible();
  });

  test("rejects invalid credentials", async ({ page }) => {
    await page.goto("/lv/login");
    await page.getByLabel(/email/i).fill("bad@example.com");
    await page.getByLabel(/password/i).fill("wrongpassword");
    await page.getByRole("button", { name: /login|pieslēgties/i }).click();

    // Should stay on login page (auth fails, no redirect)
    await expect(page).toHaveURL(/\/login/);
  });

  test("unauthenticated user is redirected to login", async ({ page }) => {
    await page.goto("/lv/routes");
    await expect(page).toHaveURL(/\/login/);
  });
});
