import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the FlowDesk web app E2E suite.
 * Boots `pnpm dev` against http://localhost:3000 and runs the smoke spec(s)
 * in apps/web/e2e against Chromium. Reuses an existing dev server locally so
 * iteration is fast; in CI it always boots a fresh one.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    // Use `corepack pnpm` rather than bare `pnpm` so the dev server launches
    // even on machines (incl. CI/Windows here) where pnpm is provided via
    // corepack and not on PATH. The repo pins pnpm via `packageManager` in
    // the root package.json, so corepack picks the correct version.
    command: "corepack pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
