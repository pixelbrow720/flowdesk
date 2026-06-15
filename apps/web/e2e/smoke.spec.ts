import { expect, test } from "@playwright/test";

/**
 * Canary: the assembled dashboard preview at /preview/dashboard must mount.
 *
 * Why these assertions prove the shell rendered (and not a blank/500 page):
 *   1. Response status must be < 400 — catches server-side render errors.
 *   2. The "FlowDesk" wordmark span (apps/web/components/topbar/topbar.tsx:29-31)
 *      only renders when <Topbar/> mounts, which only happens when the page
 *      component executes without throwing. A blank page or error boundary
 *      will not contain it.
 *   3. The Instrument SegmentedControl (aria-label="Instrument", topbar.tsx:33)
 *      is unique to the dashboard topbar; it confirms interactive shell chrome
 *      mounted, not just static text. If either of these is missing, the
 *      dashboard is broken — this canary will fail loudly.
 */
test("dashboard preview loads and renders the heatmap shell", async ({ page }) => {
  const response = await page.goto("/preview/dashboard");
  expect(response, "navigation must produce a response").not.toBeNull();
  expect(response!.ok(), `expected 2xx/3xx, got ${response!.status()}`).toBe(true);

  // Wordmark — proves <Topbar/> mounted.
  await expect(page.getByText("FlowDesk", { exact: true })).toBeVisible();

  // Instrument switcher — proves interactive topbar chrome rendered.
  // SegmentedControl renders role="radiogroup" with aria-label="Instrument"
  // (apps/web/components/ui/segmented-control.tsx:32-33).
  await expect(page.getByRole("radiogroup", { name: "Instrument" })).toBeVisible();
});
