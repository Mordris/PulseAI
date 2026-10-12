import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";
import { loadSiteContext } from "./src/lib/context.ts";
import { siteLocation, sitePaths } from "./src/lib/setup.ts";

// End-to-end tests run against a built instance (the demo in examples/ unless PULSE_E2E_INSTANCE
// names another), served by `astro preview` at the instance's own base path.
const SITE_DIR = fileURLToPath(new URL(".", import.meta.url));
const INSTANCE = resolve(SITE_DIR, process.env.PULSE_E2E_INSTANCE ?? "../../examples");
const PORT = Number(process.env.PULSE_E2E_PORT ?? 4321);
const { base } = siteLocation(loadSiteContext(sitePaths(INSTANCE).contextFile).config.site.url);
const ORIGIN = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `${ORIGIN}${base}`,
    locale: "en-US",
    timezoneId: "Europe/Istanbul",
    trace: "retain-on-failure",
  },
  expect: {
    toHaveScreenshot: { animations: "disabled", caret: "hide", maxDiffPixelRatio: 0.002 },
  },
  snapshotPathTemplate: "{testDir}/__screenshots__/{projectName}/{arg}{ext}",
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], colorScheme: "light" } },
    { name: "desktop-dark", use: { ...devices["Desktop Chrome"], colorScheme: "dark" } },
    { name: "mobile", use: { ...devices["Pixel 7"], colorScheme: "light" } },
  ],
  webServer: {
    command: `node scripts/pulse-site.ts preview --instance "${INSTANCE}" -- --port ${PORT} --host 127.0.0.1`,
    url: `${ORIGIN}${base}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
