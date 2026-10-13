import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";
import { dockerArgs, dockerFailure, playwrightImage } from "../scripts/playwright-docker.ts";

const IMAGE = /^mcr\.microsoft\.com\/playwright:v(?<version>[^-@]+)-[a-z]+@sha256:[0-9a-f]{64}$/;

describe("playwright in docker", () => {
  it("pins the image by tag and digest, at the installed @playwright/test version", () => {
    const installed = createRequire(import.meta.url)("@playwright/test/package.json") as {
      version: string;
    };
    const match = IMAGE.exec(playwrightImage());
    expect(match?.groups?.version).toBe(installed.version);
  });

  it("runs the installed Playwright, never one fetched from the registry", () => {
    const args = dockerArgs("image", ["--grep", "x"]);
    const command = args.slice(args.indexOf("image") + 1);
    expect(command).toEqual(["node_modules/.bin/playwright", "test", "--grep", "x"]);
    expect(args).not.toContain("npx");
  });

  it("explains a failure to start Docker, and stays quiet when only tests fail", () => {
    const missing = Object.assign(new Error("spawn docker ENOENT"), { code: "ENOENT" });
    expect(dockerFailure({ error: missing, status: null })).toMatch(/Docker is not installed/);
    expect(dockerFailure({ error: undefined, status: 125 })).toMatch(
      /Docker could not run the container/,
    );
    expect(dockerFailure({ error: undefined, status: 1 })).toBeUndefined();
    expect(dockerFailure({ error: undefined, status: 0 })).toBeUndefined();
  });
});
