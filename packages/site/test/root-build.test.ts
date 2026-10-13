import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { main } from "../scripts/pulse-site.ts";
import { sitePaths } from "../src/lib/setup.ts";
import { EXAMPLES, engineContext } from "./fixtures.ts";

// A full build with the engine defaults, where config.site.url is null.
describe("a site without a URL", () => {
  it("builds with root-relative links and no feed or sitemap", { timeout: 180_000 }, async () => {
    const context = engineContext();
    expect(context.config.site.url).toBeNull();
    const instance = mkdtempSync(join(tmpdir(), "pulse-root-site-"));
    const paths = sitePaths(instance);
    mkdirSync(paths.workDir, { recursive: true });
    writeFileSync(paths.contextFile, JSON.stringify(context));
    cpSync(join(EXAMPLES, "reports"), paths.reportsDir, { recursive: true });

    expect(await main(["build", "--instance", instance])).toBe(0);

    expect(existsSync(join(paths.outDir, "rss.xml"))).toBe(false);
    expect(existsSync(join(paths.outDir, "sitemap-index.xml"))).toBe(false);
    const archive = readFileSync(join(paths.outDir, "archive", "index.html"), "utf8");
    expect(archive).toContain('href="/2026/10/11/"');
    expect(archive).not.toContain("/PulseAI/");
    expect(archive).not.toMatch(/(href|src)="https?:/);
  });
});
