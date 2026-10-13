import { join, resolve } from "node:path";

/** The instance directory the build reads (set by scripts/pulse-site.ts). */
export const INSTANCE_ENV = "PULSE_INSTANCE_DIR";

// Layout of an instance directory. WORK_DIR, CONTEXT_FILE and TOKENS_DIR must match the CLI
// (pulseai.site.context and pulseai.tokens.check), which writes and reads the same files.
export const WORK_DIR = ".pulse";
export const CONTEXT_FILE = "site-context.json";
export const TOKENS_DIR = "tokens";
export const CACHE_DIR = "astro-cache";
export const REPORTS_DIR = "reports";
export const OUT_DIR = "dist";

export class SiteSetupError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SiteSetupError";
  }
}

export interface SitePaths {
  instanceDir: string;
  workDir: string;
  contextFile: string;
  tokensDir: string;
  cacheDir: string;
  reportsDir: string;
  outDir: string;
}

export function sitePaths(instanceDir: string): SitePaths {
  const root = resolve(instanceDir);
  const workDir = join(root, WORK_DIR);
  return {
    instanceDir: root,
    workDir,
    contextFile: join(workDir, CONTEXT_FILE),
    tokensDir: join(workDir, TOKENS_DIR),
    cacheDir: join(workDir, CACHE_DIR),
    reportsDir: join(root, REPORTS_DIR),
    outDir: join(root, OUT_DIR),
  };
}

/** The instance directory from the environment, or undefined (unit tests render without one). */
export function instanceDirFromEnv(env: NodeJS.ProcessEnv = process.env): string | undefined {
  const value = env[INSTANCE_ENV];
  return value ? resolve(value) : undefined;
}

export function requireInstanceDir(env: NodeJS.ProcessEnv = process.env): string {
  const dir = instanceDirFromEnv(env);
  if (dir === undefined) {
    throw new SiteSetupError(
      `${INSTANCE_ENV} is not set; build with "node scripts/pulse-site.ts build --instance <dir>"`,
    );
  }
  return dir;
}

export interface SiteLocation {
  /** Origin for absolute URLs (feeds, sitemap); absent when config.site.url is null. */
  site?: string;
  /** Path prefix of every page, with leading and trailing slashes. */
  base: string;
}

/** Split config.site.url into Astro's `site` (origin) and `base` (path). */
export function siteLocation(url: string | null | undefined): SiteLocation {
  if (!url) return { base: "/" };
  const parsed = new URL(url);
  const base = parsed.pathname.endsWith("/") ? parsed.pathname : `${parsed.pathname}/`;
  return { site: parsed.origin, base };
}
