import { expect, test } from "./support.ts";

test.use({ javaScriptEnabled: false });

test.describe("without JavaScript", () => {
  test("every item is reachable and every chart shows its data", async ({ page }) => {
    await page.goto("./");
    await expect(page.locator("details[data-item]")).toHaveCount(14);
    await expect(page.locator("details[data-chart-table][open]").first()).toBeAttached();
    expect(await page.locator("details[data-chart-table]:not([open])").count()).toBe(0);
    await expect(page.locator("pulse-report-controls")).toBeHidden();
    await expect(page.locator("pulse-theme-switch")).toBeHidden();
    await page.locator("details#verify-then-expand > summary").click();
    await expect(page.locator("details#verify-then-expand [data-diagram-fallback]")).toBeVisible();
  });
});

test.describe("print", () => {
  test("expands every item", async ({ page }) => {
    await page.goto("./");
    await page.emulateMedia({ media: "print" });
    const items = page.locator("details[data-item]");
    const count = await items.count();
    expect(count).toBeGreaterThan(1);
    for (let index = 0; index < count; index += 1) {
      await expect(items.nth(index).locator(".item__note--why")).toBeVisible();
    }
    await expect(page.locator("pulse-report-controls")).toBeHidden();
  });
});
