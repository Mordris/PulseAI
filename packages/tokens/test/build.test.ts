import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { validator } from "@pulseai/contracts";
import { describe, expect, it } from "vitest";
import {
  buildTokens,
  CSS_FILE,
  ENGINE_TOKENS_DIR,
  MEDIA_FILE,
  MODES,
  mergeTokens,
  readResolved,
  TokenError,
  token,
  writeTokenBuild,
} from "../src/index.ts";

const SECTIONS = [
  { id: "models", color_token: "color.section.models" },
  { id: "tooling", color_token: "color.section.tooling" },
  { id: "research", color_token: "color.section.research" },
  { id: "oss", color_token: "color.section.oss" },
];

function instanceWith(files: Record<string, unknown>): string {
  const dir = mkdtempSync(join(tmpdir(), "pulse-tokens-"));
  for (const [rel, content] of Object.entries(files)) {
    const path = join(dir, "tokens", rel);
    mkdirSync(join(path, ".."), { recursive: true });
    writeFileSync(path, JSON.stringify(content));
  }
  return dir;
}

describe("mergeTokens", () => {
  it("merges objects and lets later trees replace values and arrays", () => {
    const merged = mergeTokens(
      { a: { $value: 1, $type: "number" }, f: { $value: ["A", "B"] } },
      { a: { $value: 2 }, f: { $value: ["C"] } },
    );
    expect(merged).toEqual({ a: { $value: 2, $type: "number" }, f: { $value: ["C"] } });
  });
});

describe("buildTokens", () => {
  it("resolves both modes of the default preset", async () => {
    const build = await buildTokens({ preset: "pulse", sections: SECTIONS });
    expect(MODES).toEqual(["light", "dark"]);
    expect(token(build.resolved.light, "color.surface.page").value).toBe("#f9f9f7");
    expect(token(build.resolved.dark, "color.surface.page").value).toBe("#0d0d0d");
    expect(token(build.resolved.light, "color.section.models").value).toBe("#2a78d6");
    expect(token(build.resolved.light, "space.4")).toMatchObject({
      value: "1rem",
      name: "--pulse-space-4",
    });
    expect(
      token(build.resolved.light, "color.text.primary").extensions?.contrast_against,
    ).toContain("color.surface.page");
  });

  it("writes shared values once and dark values for both the toggle and the OS setting", async () => {
    const { css } = await buildTokens({ preset: "pulse", sections: SECTIONS });
    const [root, light, dark, media] = css.split("\n\n").slice(1);
    expect(root).toContain("--pulse-space-4: 1rem;");
    expect(light).toMatch(/^:root,\n:root\[data-theme="light"\] \{/);
    expect(light).toContain("--pulse-color-surface-page: #f9f9f7;");
    expect(dark).toMatch(/^:root\[data-theme="dark"\] \{/);
    expect(dark).toContain("--pulse-color-surface-page: #0d0d0d;");
    expect(dark).not.toContain("--pulse-space-4");
    expect(media).toContain(":root:not([data-theme])");
    expect(media).toContain("--pulse-color-surface-page: #0d0d0d;");
  });

  it("turns breakpoint tokens into custom media queries", async () => {
    const build = await buildTokens({ preset: "pulse", sections: SECTIONS });
    expect(build.media).toContain("@custom-media --pulse-breakpoint-sm (min-width: 40rem);");
    expect(build.media).toContain("@custom-media --pulse-breakpoint-xl (min-width: 64rem);");
    const instanceDir = instanceWith({
      "base/size.json": { breakpoint: { sm: { $value: { value: 36, unit: "rem" } } } },
    });
    const custom = await buildTokens({ preset: "pulse", instanceDir, sections: SECTIONS });
    expect(custom.media).toContain("@custom-media --pulse-breakpoint-sm (min-width: 36rem);");
    const out = mkdtempSync(join(tmpdir(), "pulse-tokens-out-"));
    writeTokenBuild(build, out);
    expect(readFileSync(join(out, MEDIA_FILE), "utf8")).toBe(build.media);
  });

  it("lists the Fontsource packages of the preset's fonts", async () => {
    expect((await buildTokens({ preset: "pulse", sections: SECTIONS })).fonts).toEqual([
      "@fontsource-variable/inter",
      "@fontsource-variable/jetbrains-mono",
      "@fontsource-variable/newsreader",
    ]);
    expect((await buildTokens({ preset: "paper", sections: SECTIONS })).fonts).toEqual([
      "@fontsource-variable/jetbrains-mono",
      "@fontsource-variable/newsreader",
      "@fontsource-variable/source-serif-4",
    ]);
  });

  it("builds every engine preset", async () => {
    for (const preset of ["pulse", "paper", "terminal"]) {
      const build = await buildTokens({ preset, sections: SECTIONS });
      expect(build.resolved.dark.preset).toBe(preset);
    }
  });

  it("names the available presets when the preset is unknown", async () => {
    await expect(buildTokens({ preset: "neon", sections: SECTIONS })).rejects.toThrow(
      'unknown theme preset "neon"; available: paper, pulse, terminal',
    );
  });

  it("lets instance token files override the engine and add presets", async () => {
    // A new preset is a full theme: start from an engine preset and change what differs.
    const brandTheme = (mode: string, page: string) => {
      const theme = JSON.parse(
        readFileSync(join(ENGINE_TOKENS_DIR, "themes/pulse", `${mode}.json`), "utf8"),
      );
      theme.color.surface.page.$value = page;
      return theme;
    };
    const instanceDir = instanceWith({
      "themes/pulse/light.json": { color: { surface: { page: { $value: "#fffef0" } } } },
      "themes/brand/light.json": brandTheme("light", "#ffffff"),
      "themes/brand/dark.json": brandTheme("dark", "#000000"),
    });
    const pulse = await buildTokens({ preset: "pulse", instanceDir, sections: SECTIONS });
    expect(token(pulse.resolved.light, "color.surface.page").value).toBe("#fffef0");
    expect(token(pulse.resolved.dark, "color.surface.page").value).toBe("#0d0d0d");
    const brand = await buildTokens({ preset: "brand", instanceDir, sections: SECTIONS });
    expect(token(brand.resolved.dark, "color.surface.page").value).toBe("#000000");
  });

  it("applies config overrides for accent, fonts, and section colors", async () => {
    const build = await buildTokens({
      preset: "pulse",
      sections: SECTIONS,
      overrides: {
        accent: "#123456",
        font_body: "Atkinson Hyperlegible",
        sections: { models: "#654321" },
      },
    });
    for (const mode of MODES) {
      expect(token(build.resolved[mode], "color.accent.default").value).toBe("#123456");
      expect(token(build.resolved[mode], "color.section.models").value).toBe("#654321");
    }
    expect(token(build.resolved.light, "font.family.body").value).toMatch(
      /^'Atkinson Hyperlegible', system-ui/,
    );
    expect(build.fonts).not.toContain("@fontsource-variable/inter");
  });

  it("rejects an override for a section that does not exist", async () => {
    await expect(
      buildTokens({
        preset: "pulse",
        sections: SECTIONS,
        overrides: { sections: { weather: "#000000" } },
      }),
    ).rejects.toThrow('theme.overrides.sections names unknown section "weather"');
  });

  it("rejects a section whose color token is not defined", async () => {
    await expect(
      buildTokens({
        preset: "pulse",
        sections: [...SECTIONS, { id: "extra", color_token: "color.section.extra" }],
      }),
    ).rejects.toThrow('section "extra" uses color token "color.section.extra"');
  });

  it("reports a broken alias", async () => {
    const instanceDir = instanceWith({
      "themes/pulse/light.json": { color: { surface: { page: { $value: "{palette.nope.1}" } } } },
    });
    await expect(buildTokens({ preset: "pulse", instanceDir, sections: SECTIONS })).rejects.toThrow(
      TokenError,
    );
  });

  it("reports an invalid extension with the token path", async () => {
    const instanceDir = instanceWith({
      "themes/pulse/light.json": {
        color: {
          text: {
            primary: { $extensions: { "org.pulseai": { contrast_against: "color.surface.page" } } },
          },
        },
      },
    });
    await expect(buildTokens({ preset: "pulse", instanceDir, sections: SECTIONS })).rejects.toThrow(
      'color.text.primary: invalid $extensions["org.pulseai"]',
    );
  });

  it("writes CSS and resolved maps that pass the schema", async () => {
    const out = mkdtempSync(join(tmpdir(), "pulse-tokens-out-"));
    const build = await buildTokens({ preset: "pulse", sections: SECTIONS });
    writeTokenBuild(build, out);
    expect(readFileSync(join(out, CSS_FILE), "utf8")).toBe(build.css);
    for (const mode of MODES) {
      const resolved = readResolved(out, mode);
      expect(validator("tokens-resolved").safeParse(resolved).success).toBe(true);
      expect(resolved).toEqual(build.resolved[mode]);
    }
  });
});
