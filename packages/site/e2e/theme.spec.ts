import { expect, hexToRgb, test, tokenValue, visualsSettled } from "./support.ts";

const background = (page: import("@playwright/test").Page) =>
  page.evaluate(() => getComputedStyle(document.body).backgroundColor);

test.describe("theme", () => {
  test("follows the OS until the reader picks a theme", async ({ page }, testInfo) => {
    const mode = testInfo.project.use.colorScheme === "dark" ? "dark" : "light";
    await page.goto("./");
    expect(await background(page)).toBe(hexToRgb(tokenValue(mode, "color.surface.page")));
    await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
  });

  test("remembers the reader's pick across pages", async ({ page }) => {
    await page.goto("./");
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.goto("archive/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await background(page)).toBe(hexToRgb(tokenValue("dark", "color.surface.page")));
    await page.getByRole("radio", { name: "Auto" }).check();
    await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
  });

  test("honours a valid theme query and ignores an invalid one", async ({ page }) => {
    await page.goto("./?theme=light");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.goto("./?theme=neon");
    await expect(page.locator("html")).toHaveAttribute("data-theme-choice", "auto");
  });

  test("keeps a stored light choice when the OS is dark", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("./");
    await page.getByRole("radio", { name: "Light" }).check();
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    expect(await background(page)).toBe(hexToRgb(tokenValue("light", "color.surface.page")));
  });

  test("survives storage that throws", async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(window, "localStorage", {
        get() {
          throw new DOMException("blocked", "SecurityError");
        },
      });
    });
    await page.goto("./");
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  });

  test("chart tooltips wear the page's tokens", async ({ page }, testInfo) => {
    const mode = testInfo.project.use.colorScheme === "dark" ? "dark" : "light";
    await page.goto("./");
    await visualsSettled(page);
    await page.locator("#visual-research-funnel .role-mark path").first().hover();
    const tooltip = page.locator("#vg-tooltip-element");
    await expect(tooltip).toBeVisible();
    const colors = await tooltip.evaluate((element) => ({
      background: getComputedStyle(element).backgroundColor,
      key: getComputedStyle(element.querySelector("td.key") ?? element).color,
      value: getComputedStyle(element.querySelector("td.value") ?? element).color,
    }));
    expect(colors).toEqual({
      background: hexToRgb(tokenValue(mode, "color.surface.raised")),
      key: hexToRgb(tokenValue(mode, "color.text.secondary")),
      value: hexToRgb(tokenValue(mode, "color.text.primary")),
    });
  });

  test("charts end in the last theme after rapid switching", async ({ page }) => {
    await page.goto("./?theme=light");
    await visualsSettled(page);
    await page.evaluate(() => {
      // Three picks without waiting for any chart to redraw.
      for (const choice of ["Dark", "Light", "Dark"]) {
        const radio = [...document.querySelectorAll<HTMLInputElement>("input[type=radio]")].find(
          (input) => input.labels?.[0]?.textContent?.trim() === choice,
        );
        radio?.click();
      }
    });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    const label = page.locator("#visual-impact-by-section pulse-vega-chart svg text").first();
    await expect(label).toHaveAttribute("fill", tokenValue("dark", "color.chart.label"));
    await page.waitForTimeout(500);
    await expect(label).toHaveAttribute("fill", tokenValue("dark", "color.chart.label"));
  });

  test("re-themes charts when the theme changes", async ({ page }) => {
    await page.goto("./?theme=light");
    await visualsSettled(page);
    const label = page.locator("#visual-impact-by-section pulse-vega-chart svg text").first();
    const light = await label.getAttribute("fill");
    expect(light).toBe(tokenValue("light", "color.chart.label"));
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(label).toHaveAttribute("fill", tokenValue("dark", "color.chart.label"));
  });
});
