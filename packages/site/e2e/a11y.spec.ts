import AxeBuilder from "@axe-core/playwright";
import { expect, test, visualsSettled } from "./support.ts";

const IMPACTS = new Set(["serious", "critical"]);

for (const path of ["./", "archive/", "2026/10/09/"]) {
  test(`no serious accessibility problems on ${path}`, async ({ page }) => {
    await page.goto(path);
    await visualsSettled(page);
    // Audit the expanded deep dives too, not only the summaries.
    await page.evaluate(() => {
      for (const details of document.querySelectorAll("details")) details.open = true;
    });
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    const problems = results.violations
      .filter(
        (violation) =>
          violation.impact !== undefined &&
          violation.impact !== null &&
          IMPACTS.has(violation.impact),
      )
      .map(
        (violation) =>
          `${violation.id}: ${violation.nodes.map((node) => node.target.join(" ")).join(", ")}`,
      );
    expect(problems).toEqual([]);
  });
}
