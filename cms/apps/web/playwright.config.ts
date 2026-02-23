import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;
const baseURL = process.env.BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: isCI ? 1 : undefined,
  reporter: isCI
    ? [["github"], ["html", { open: "never" }]]
    : "html",
  timeout: 30_000,
  expect: { timeout: 5_000 },

  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "on-first-retry",
  },

  projects: [
    // Auth setup — runs first, saves session state for other projects
    { name: "setup", testMatch: /.*\.setup\.ts/ },

    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        storageState: "e2e/.auth/user.json",
      },
      testIgnore: /.*\.noauth\.spec\.ts/,
      dependencies: ["setup"],
    },

    // Unauthenticated tests (login page, unauthorized page)
    {
      name: "no-auth",
      testMatch: /.*\.noauth\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  /* Only start local dev server when NOT in CI (docker-compose handles it in CI) */
  ...(!isCI && {
    webServer: {
      command: "pnpm dev",
      url: baseURL,
      reuseExistingServer: true,
      timeout: 60_000,
    },
  }),
});
