import type { Page } from "@playwright/test";
import { expect, test, visualsSettled } from "./support.ts";

/** A page ready for a screenshot: fonts loaded, every chart and diagram drawn. */
async function settle(page: Page): Promise<void> {
  await visualsSettled(page);
  await page.evaluate(() => document.fonts.ready);
}

test.describe("screenshots @visual", () => {
  test("latest edition", async ({ page }) => {
    await page.goto("./");
    await settle(page);
    await expect(page).toHaveScreenshot("latest.png", { fullPage: true });
  });

  test("deep dives", async ({ page }) => {
    for (const id of ["northwind-atlas-3", "verify-then-expand", "pyfetchkit-path-traversal"]) {
      await page.goto(`./#${id}`);
      await settle(page);
      await expect(page.locator(`details#${id}`)).toHaveScreenshot(`item-${id}.png`);
    }
  });

  test("long title brief", async ({ page }) => {
    await page.goto("./#quillmark-1-8-4");
    await settle(page);
    await expect(page.locator("details#quillmark-1-8-4")).toHaveScreenshot("item-long-title.png");
  });

  test("archive", async ({ page }) => {
    await page.goto("archive/");
    await settle(page);
    await expect(page).toHaveScreenshot("archive.png", { fullPage: true });
  });
});
