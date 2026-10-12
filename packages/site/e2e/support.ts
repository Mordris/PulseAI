import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test as base, expect, type Page } from "@playwright/test";

const IMAGE = readFileSync(fileURLToPath(new URL("./fixtures/image.svg", import.meta.url)));

/**
 * Every test runs offline: requests to other hosts are refused, except images, which get a local
 * fixture so screenshots never depend on a third-party server. Page errors fail the test.
 */
export const test = base.extend<{ pageErrors: string[] }>({
  pageErrors: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.route(
        (url) => url.hostname !== "127.0.0.1" && url.hostname !== "localhost",
        (route) =>
          route.request().resourceType() === "image"
            ? route.fulfill({ status: 200, contentType: "image/svg+xml", body: IMAGE })
            : route.abort(),
      );
      await use(errors);
      expect(errors, "uncaught page errors").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };

/** Wait until every chart and diagram on the page has rendered or given up. */
export async function visualsSettled(page: Page): Promise<void> {
  await page.waitForFunction(() =>
    [...document.querySelectorAll<HTMLElement>("pulse-vega-chart, pulse-mermaid")].every(
      (element) => element.dataset.state !== undefined,
    ),
  );
}

/** A hex color as getComputedStyle reports it. */
export function hexToRgb(hex: string): string {
  const value = Number.parseInt(hex.slice(1), 16);
  return `rgb(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255})`;
}

const INSTANCE = resolve(
  fileURLToPath(new URL("..", import.meta.url)),
  process.env.PULSE_E2E_INSTANCE ?? "../../examples",
);

/** A token's resolved value in the instance build under test. */
export function tokenValue(mode: "light" | "dark", path: string): string {
  const resolved = JSON.parse(
    readFileSync(join(INSTANCE, ".pulse", "tokens", `${mode}.json`), "utf8"),
  );
  return String(resolved.tokens[path].value);
}
