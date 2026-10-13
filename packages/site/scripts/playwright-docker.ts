#!/usr/bin/env node
/**
 * Run Playwright inside the pinned Playwright image (package.json config.playwrightImage), so the
 * browsers and fonts match CI and the screenshot baselines.
 *
 *   node scripts/playwright-docker.ts [playwright test arguments]
 *
 * The repository is mounted at its own path with its installed node_modules, which therefore must
 * be built for Linux x64: run this on a Linux host (or in CI). Elsewhere, update screenshots from
 * the CI artifact instead.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { userInfo } from "node:os";
import { fileURLToPath } from "node:url";

const SITE_DIR = fileURLToPath(new URL("..", import.meta.url));
const REPO_DIR = fileURLToPath(new URL("../../..", import.meta.url));
const PASSED_ENV = ["CI", "PULSE_E2E_INSTANCE", "PULSE_E2E_PORT"];

export function playwrightImage(): string {
  const manifest = JSON.parse(
    readFileSync(new URL("../package.json", import.meta.url), "utf8"),
  ) as {
    config?: { playwrightImage?: string };
  };
  const image = manifest.config?.playwrightImage;
  if (!image) throw new Error("package.json has no config.playwrightImage");
  return image;
}

export function dockerArgs(image: string, testArgs: readonly string[]): string[] {
  const { uid, gid } = userInfo();
  return [
    "run",
    "--rm",
    "--ipc=host",
    `--user=${uid}:${gid}`,
    "--env=HOME=/tmp",
    ...PASSED_ENV.filter((name) => process.env[name] !== undefined).map((name) => `--env=${name}`),
    `--volume=${REPO_DIR}:${REPO_DIR}`,
    `--workdir=${SITE_DIR}`,
    image,
    "npx",
    "playwright",
    "test",
    ...testArgs,
  ];
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const result = spawnSync("docker", dockerArgs(playwrightImage(), process.argv.slice(2)), {
    stdio: "inherit",
  });
  process.exitCode = result.status ?? 1;
}
