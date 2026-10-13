import { createRequire } from "node:module";
import { join, sep } from "node:path";
import { fileURLToPath } from "node:url";
import sitemap from "@astrojs/sitemap";
import postcssGlobalData from "@csstools/postcss-global-data";
import { MEDIA_FILE } from "@pulseai/tokens";
import { defineConfig, passthroughImageService } from "astro/config";
import pagefind from "astro-pagefind";
import postcssCustomMedia from "postcss-custom-media";
import { loadSiteContext } from "./src/lib/context.ts";
import { instanceDirFromEnv, siteLocation, sitePaths } from "./src/lib/setup.ts";

// Unit tests load this file without an instance; builds always have one (scripts/pulse-site.ts).
const instanceDir = instanceDirFromEnv();
const paths = instanceDir === undefined ? undefined : sitePaths(instanceDir);
const context = paths === undefined ? undefined : loadSiteContext(paths.contextFile);
const location = siteLocation(context?.config.site.url);
const siteDir = fileURLToPath(new URL(".", import.meta.url));

/** The directory that holds node_modules for the installed packages (instance or engine repo). */
function modulesRoot(): string {
  const astro = createRequire(import.meta.url).resolve("astro/package.json");
  const marker = `${sep}node_modules${sep}`;
  return astro.slice(0, astro.indexOf(marker));
}

export default defineConfig({
  output: "static",
  trailingSlash: "always",
  build: { format: "directory" },
  // Images are hotlinked, never optimized or copied (see Figure.astro).
  image: { service: passthroughImageService() },
  base: location.base,
  ...(location.site === undefined ? {} : { site: location.site }),
  ...(paths === undefined ? {} : { outDir: paths.outDir, cacheDir: paths.cacheDir }),
  integrations: [
    ...(context?.config.site.search ? [pagefind()] : []),
    ...(location.site === undefined ? [] : [sitemap()]),
  ],
  vite: {
    ...(paths === undefined
      ? {}
      : {
          resolve: { alias: { "@pulse-generated": paths.workDir } },
          server: { fs: { allow: [siteDir, paths.instanceDir, modulesRoot()] } },
          // Breakpoints come from tokens as @custom-media; every stylesheet can use them.
          css: {
            postcss: {
              plugins: [
                postcssGlobalData({ files: [join(paths.tokensDir, MEDIA_FILE)] }),
                postcssCustomMedia(),
              ],
            },
          },
        }),
  },
});
