import type { Page } from "@playwright/test";
import { expect, test, visualsSettled } from "./support.ts";

const filters = (page: Page) => page.locator("pulse-report-controls");

test.describe("report page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("./");
    await visualsSettled(page);
  });

  test("renders the latest edition with every visual drawn", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Atlas-3 arrives/);
    const states = await page
      .locator("pulse-vega-chart, pulse-mermaid")
      .evaluateAll((elements) => elements.map((element) => (element as HTMLElement).dataset.state));
    expect(states.length).toBeGreaterThan(5);
    expect(states.every((state) => state === "rendered")).toBe(true);
    const sections = await page
      .locator("section.report-section")
      .evaluateAll((elements) => elements.map((e) => e.id));
    expect(sections).toEqual([
      "section-models",
      "section-tooling",
      "section-research",
      "section-oss",
    ]);
  });

  test("opens the item a permalink names", async ({ page }) => {
    await page.goto("./#verify-then-expand");
    await expect(page.locator("details#verify-then-expand")).toHaveAttribute("open", "");
  });

  test("expands and collapses every item", async ({ page }) => {
    await page.getByRole("button", { name: "Expand all" }).click();
    await expect(page.locator("details[data-item]:not([open])")).toHaveCount(0);
    await page.getByRole("button", { name: "Collapse all" }).click();
    await expect(page.locator("details[data-item][open]")).toHaveCount(0);
  });

  test("filters items and hides empty sections", async ({ page }) => {
    await filters(page).getByLabel("Section", { exact: true }).selectOption("oss");
    await expect(page.locator("details[data-item]:visible")).toHaveCount(2);
    await expect(page.locator("#section-models")).toBeHidden();
    await expect(filters(page).getByRole("status")).toHaveText("2 of 14 items shown");
    await filters(page).getByLabel("Section", { exact: true }).selectOption("all");
    await filters(page).getByLabel("New or update", { exact: true }).selectOption("updates");
    await expect(page.locator("details[data-item]:visible")).toHaveCount(1);
    await filters(page).getByLabel("Impact", { exact: true }).selectOption("5");
    await filters(page).getByLabel("New or update", { exact: true }).selectOption("all");
    await expect(page.locator("details[data-item]:visible")).toHaveCount(3);
    await page.getByRole("button", { name: "Reset" }).click();
    await expect(page.locator("details[data-item]:visible")).toHaveCount(14);
  });

  test("keeps a section that holds only notes until a filter is set", async ({ page }) => {
    await page.evaluate(() => {
      const section = document.createElement("section");
      section.id = "section-notes-only";
      section.dataset.filterGroup = "";
      section.innerHTML = `<h2>Notes only</h2><aside><p>A section with only a note.</p></aside>`;
      document.querySelector("main")?.append(section);
    });
    const section = page.locator("#section-notes-only");
    await filters(page).getByLabel("Section", { exact: true }).selectOption("oss");
    await expect(section).toBeHidden();
    await page.getByRole("button", { name: "Reset" }).click();
    await expect(section).toBeVisible();
  });

  test("says so when no item matches", async ({ page }) => {
    await filters(page).getByLabel("Section", { exact: true }).selectOption("oss");
    await filters(page).getByLabel("New or update", { exact: true }).selectOption("updates");
    await expect(filters(page).getByRole("status")).toHaveText("No items match these filters.");
  });

  test("a broken chart keeps its table and does not stop other charts", async ({ page }) => {
    await page.evaluate(() => {
      const figure = document.createElement("figure");
      figure.id = "visual-broken";
      figure.innerHTML = `<pulse-vega-chart><script type="application/json">{"mark":"nope","data":{"values":[{"a":1}]}}</script><div data-chart hidden></div></pulse-vega-chart><details data-chart-table open><summary>data</summary></details>`;
      document.querySelector("main")?.append(figure);
    });
    const broken = page.locator("#visual-broken pulse-vega-chart");
    await expect(broken).toHaveAttribute("data-state", "error");
    await expect(page.locator("#visual-broken details[data-chart-table]")).toHaveAttribute(
      "open",
      "",
    );
    await expect(page.locator("pulse-vega-chart[data-state=rendered]").first()).toBeVisible();
  });

  test("a chart spec cannot reach the network", async ({ page }) => {
    const requested: string[] = [];
    page.on("request", (request) => requested.push(request.url()));
    await page.evaluate(() => {
      const spec = {
        data: { url: "https://beacon.example.invalid/data.json" },
        mark: "image",
        encoding: { url: { value: "https://beacon.example.invalid/image.png" } },
        usermeta: { embedOptions: { patch: "https://beacon.example.invalid/patch.json" } },
      };
      const figure = document.createElement("figure");
      figure.id = "visual-remote";
      figure.innerHTML = `<pulse-vega-chart><script type="application/json">${JSON.stringify(spec)}</script><div data-chart hidden></div></pulse-vega-chart><details data-chart-table open><summary>data</summary></details>`;
      document.querySelector("main")?.append(figure);
    });
    await expect(page.locator("#visual-remote pulse-vega-chart")).toHaveAttribute("data-state");
    expect(requested.filter((url) => url.includes("beacon.example.invalid"))).toEqual([]);
  });

  test("a broken diagram keeps its alt text and source", async ({ page }) => {
    await page.evaluate(() => {
      const figure = document.createElement("figure");
      figure.id = "visual-broken-diagram";
      figure.innerHTML = `<pulse-mermaid><div data-diagram hidden></div><p data-diagram-fallback>alt text</p></pulse-mermaid><details data-diagram-source><summary>source</summary><pre><code>flowchart LR\n  A --></code></pre></details>`;
      document.querySelector("main")?.append(figure);
    });
    await expect(page.locator("#visual-broken-diagram pulse-mermaid")).toHaveAttribute(
      "data-state",
      "error",
    );
    await expect(page.getByText("alt text")).toBeVisible();
  });

  test("a diagram label cannot inject markup", async ({ page }) => {
    await page.evaluate(() => {
      const figure = document.createElement("figure");
      figure.id = "visual-markup-diagram";
      figure.innerHTML = `<pulse-mermaid><div data-diagram hidden></div><p data-diagram-fallback>alt text</p></pulse-mermaid><details data-diagram-source><summary>source</summary><pre><code></code></pre></details>`;
      const code = figure.querySelector("code");
      if (code !== null) {
        code.textContent = 'flowchart LR\n  A["<img src=x onerror=alert(1)><b>bold</b>"] --> B';
      }
      document.querySelector("main")?.append(figure);
    });
    const diagram = page.locator("#visual-markup-diagram pulse-mermaid");
    await expect(diagram).toHaveAttribute("data-state", "rendered");
    await expect(page.locator("#visual-markup-diagram [onerror]")).toHaveCount(0);
    await expect(page.locator("#visual-markup-diagram script")).toHaveCount(0);
  });

  test("a broken diagram leaves no error graphic behind, even after a theme switch", async ({
    page,
  }) => {
    await page.evaluate(() => {
      const figure = document.createElement("figure");
      figure.id = "visual-broken-diagram";
      figure.innerHTML = `<pulse-mermaid><div data-diagram hidden></div><p data-diagram-fallback>alt text</p></pulse-mermaid><details data-diagram-source><summary>source</summary><pre><code>flowchart LR\n  A --></code></pre></details>`;
      document.querySelector("main")?.append(figure);
    });
    const broken = page.locator("#visual-broken-diagram pulse-mermaid");
    await expect(broken).toHaveAttribute("data-state", "error");
    await broken.evaluate((element) => element.removeAttribute("data-state"));
    await page.getByRole("radio", { name: "Dark" }).check();
    await expect(broken).toHaveAttribute("data-state", "error");
    // Mermaid draws into a temporary `d<id>` element on <body>; nothing of it may stay.
    await expect(page.locator("[id^='dpulse-mermaid-']")).toHaveCount(0);
    await expect(page.getByText("Syntax error in text")).toHaveCount(0);
  });
});

test.describe("other routes", () => {
  test("serves every edition at its date and lists them in the archive", async ({ page }) => {
    await page.goto("archive/");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Archive");
    await expect(page.locator(".archive-list li")).toHaveCount(3);
    await page.getByRole("link", { name: /Relay CLI 3.0 enters release candidate/ }).click();
    await expect(page).toHaveURL(/\/2026\/10\/10\/$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Relay CLI 3.0 enters/);
  });

  test("points the front page at the edition it repeats", async ({ page }) => {
    await page.goto("./");
    await expect(page.locator("link[rel=canonical]")).toHaveAttribute(
      "href",
      /\/PulseAI\/2026\/10\/11\/$/,
    );
  });

  test("answers unknown pages with the not-found page", async ({ page }) => {
    const response = await page.goto("no-such-page/");
    expect(response?.status()).toBe(404);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Page not found");
  });

  test("publishes a feed with absolute links below the base path", async ({ request }) => {
    const response = await request.get("rss.xml");
    expect(response.ok()).toBe(true);
    const feed = await response.text();
    expect(feed.match(/<item>/g)).toHaveLength(3);
    expect(feed).toContain("<link>https://mordris.github.io/PulseAI/2026/10/11/</link>");
  });

  test("finds editions with search, without duplicating the front page", async ({ page }) => {
    await page.goto("archive/");
    await page.getByRole("combobox").fill("Atlas");
    const results = page.locator("pagefind-searchbox a[href*='/2026/']");
    await expect(results.first()).toBeVisible();
    const links = await page
      .locator("pagefind-searchbox a")
      .evaluateAll((anchors) => anchors.map((anchor) => anchor.getAttribute("href")));
    expect(links).not.toContain("/PulseAI/");
  });
});
