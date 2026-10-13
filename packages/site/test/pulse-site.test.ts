import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import { fontImports, main } from "../scripts/pulse-site.ts";

const SITE_DIR = fileURLToPath(new URL("..", import.meta.url));

describe("pulse-site", () => {
  it("exits 2 with usage for a missing command or instance", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(await main([])).toBe(2);
    expect(await main(["build"])).toBe(2);
    expect(await main(["deploy", "--instance", "."])).toBe(2);
    expect(await main(["build", "--nope"])).toBe(2);
    expect(error.mock.calls.flat().join("\n")).toContain("usage: node scripts/pulse-site.ts");
    error.mockRestore();
  });

  it("exits 1 when the instance has no context yet", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const instance = mkdtempSync(join(tmpdir(), "pulse-instance-"));
    expect(await main(["build", "--instance", instance])).toBe(1);
    expect(error.mock.calls.flat().join("\n")).toContain(
      'run "pulse site context --instance <dir>"',
    );
    error.mockRestore();
  });

  it("imports fonts relative to the generated file", () => {
    const css = fontImports(
      ["@fontsource-variable/inter"],
      join(SITE_DIR, ".pulse", "tokens", "fonts.css"),
      [SITE_DIR],
    );
    expect(css).toMatch(/@import "\.\.\/\.\.\/.*@fontsource-variable\/inter\/index\.css";/);
  });

  it("names a font package that is not installed", () => {
    expect(() =>
      fontImports(["@fontsource-variable/nope"], join(SITE_DIR, "fonts.css"), [SITE_DIR]),
    ).toThrow('font package "@fontsource-variable/nope" is not installed');
  });
});
